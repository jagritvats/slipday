"""Ephemeris and lunar orientation.

Positions come from the JPL DE421 planetary and lunar ephemeris, read from the
``de421`` PyPI package with ``jplephem`` (no network access needed at run time).

Two orientation models for the Moon are implemented:

* ``de421`` (default): the numerically integrated lunar libration angles that
  ship inside DE421, rotated from the principal-axis frame to the Mean
  Earth/polar axis frame, which is the frame LOLA/LRO products use.
* ``iau2009``: the IAU/WGCCRE 2009 series (Archinal et al. 2011, Celest. Mech.
  Dyn. Astr. 109, 101-135): pole right ascension/declination and prime
  meridian W with the periodic terms E1..E13.  SPICE calls this IAU_MOON.  It
  is a truncated series kept as an independent cross-check.

See TEST_REPORT.md for the measured difference of each against JPL Horizons.

Everything here depends on time only, not on the site, so one EphemTable can
be shared by any number of sites.
"""
from __future__ import annotations

import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import numpy as np

C_KM_S = 299792.458
MOON_RADIUS_KM = 1737.4
SUN_RADIUS_KM = 695700.0
EARTH_RADIUS_KM = 6378.137
J2000_JD = 2451545.0
UNIX_EPOCH_JD = 2440587.5
# The de421 package documents DE421 as valid for 1900 through 2050; stay inside that.
SUPPORTED_JD = (2415020.5, 2469807.5)

# (UTC date from which the value applies, TAI-UTC seconds). 1972 onward.
_LEAP_TABLE = [
    ("1972-01-01", 10), ("1972-07-01", 11), ("1973-01-01", 12), ("1974-01-01", 13),
    ("1975-01-01", 14), ("1976-01-01", 15), ("1977-01-01", 16), ("1978-01-01", 17),
    ("1979-01-01", 18), ("1980-01-01", 19), ("1981-07-01", 20), ("1982-07-01", 21),
    ("1983-07-01", 22), ("1985-07-01", 23), ("1988-01-01", 24), ("1990-01-01", 25),
    ("1991-01-01", 26), ("1992-07-01", 27), ("1993-07-01", 28), ("1994-07-01", 29),
    ("1996-01-01", 30), ("1997-07-01", 31), ("1999-01-01", 32), ("2006-01-01", 33),
    ("2009-01-01", 34), ("2012-07-01", 35), ("2015-07-01", 36), ("2017-01-01", 37),
]
_LEAP_UNIX = np.array(
    [datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp() for d, _ in _LEAP_TABLE]
)
_LEAP_VAL = np.array([v for _, v in _LEAP_TABLE], dtype=float)


def parse_utc(text: str | datetime) -> datetime:
    """Parse an ISO-8601 instant; naive values are taken as UTC."""
    if isinstance(text, datetime):
        dt = text
    else:
        s = text.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso(unix_seconds: float) -> str:
    dt = datetime.fromtimestamp(round(float(unix_seconds)), tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def unix_to_jd_tdb(unix_seconds) -> np.ndarray:
    """UTC (as Unix seconds) -> Julian date in TDB.

    TT = UTC + (TAI-UTC) + 32.184 s.  TDB-TT (under 2 ms) is ignored: the Moon
    turns 0.0000003 degrees in that time.
    """
    u = np.atleast_1d(np.asarray(unix_seconds, dtype=float))
    idx = np.clip(np.searchsorted(_LEAP_UNIX, u, side="right") - 1, 0, len(_LEAP_VAL) - 1)
    tt_minus_utc = _LEAP_VAL[idx] + 32.184
    return UNIX_EPOCH_JD + (u + tt_minus_utc) / 86400.0


@lru_cache(maxsize=1)
def _ephemeris():
    """DE421 as shipped in the ``de421`` PyPI package (numpy Chebyshev tables)."""
    import de421
    from jplephem import Ephemeris

    return Ephemeris(de421)


def ephemeris_span_jd() -> tuple[float, float]:
    e = _ephemeris()
    return float(e.jalpha), float(e.jomega)


def _earth_and_moon(jd, with_velocity: bool = False):
    """Barycentric Earth and Moon (km) from the Earth-Moon barycentre and the
    geocentric Moon, split with the DE421 Earth/Moon mass ratio."""
    e = _ephemeris()
    f = 1.0 / (1.0 + e.EMRAT)
    if with_velocity:
        emb, v_emb = e.position_and_velocity("earthmoon", jd)
        gm, v_gm = e.position_and_velocity("moon", jd)
        earth = emb - gm * f
        v_moon = (v_emb - v_gm * f + v_gm) / 86400.0  # km/day -> km/s
        return earth, earth + gm, v_moon
    emb = e.position("earthmoon", jd)
    gm = e.position("moon", jd)
    earth = emb - gm * f
    return earth, earth + gm, None


def _moon_state(jd):
    _, moon, v = _earth_and_moon(jd, with_velocity=True)
    return moon, v


def _sun_pos(jd):
    return _ephemeris().position("sun", jd)


def _earth_pos(jd):
    return _earth_and_moon(jd)[0]


def moon_orientation(jd_tdb) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """IAU/WGCCRE 2009 pole (alpha0, delta0) and prime meridian W, in radians."""
    d = np.asarray(jd_tdb, dtype=float) - J2000_JD
    T = d / 36525.0
    r = np.deg2rad
    E1 = r(125.045 - 0.0529921 * d)
    E2 = r(250.089 - 0.1059842 * d)
    E3 = r(260.008 + 13.0120009 * d)
    E4 = r(176.625 + 13.3407154 * d)
    E5 = r(357.529 + 0.9856003 * d)
    E6 = r(311.589 + 26.4057084 * d)
    E7 = r(134.963 + 13.0649930 * d)
    E8 = r(276.617 + 0.3287146 * d)
    E9 = r(34.226 + 1.7484877 * d)
    E10 = r(15.134 - 0.1589763 * d)
    E11 = r(119.743 + 0.0036096 * d)
    E12 = r(239.961 + 0.1643573 * d)
    E13 = r(25.053 + 12.9590088 * d)
    s, c = np.sin, np.cos
    alpha = (269.9949 + 0.0031 * T - 3.8787 * s(E1) - 0.1204 * s(E2) + 0.0700 * s(E3)
             - 0.0172 * s(E4) + 0.0072 * s(E6) - 0.0052 * s(E10) + 0.0043 * s(E13))
    delta = (66.5392 + 0.0130 * T + 1.5419 * c(E1) + 0.0239 * c(E2) - 0.0278 * c(E3)
             + 0.0068 * c(E4) - 0.0029 * c(E6) + 0.0009 * c(E7) + 0.0008 * c(E10)
             - 0.0009 * c(E13))
    W = (38.3213 + 13.17635815 * d - 1.4e-12 * d * d + 3.5610 * s(E1) + 0.1208 * s(E2)
         - 0.0642 * s(E3) + 0.0158 * s(E4) + 0.0252 * s(E5) - 0.0066 * s(E6)
         - 0.0047 * s(E7) - 0.0046 * s(E8) + 0.0028 * s(E9) + 0.0052 * s(E10)
         + 0.0040 * s(E11) + 0.0019 * s(E12) - 0.0044 * s(E13))
    return r(alpha), r(delta), r(np.mod(W, 360.0))


def icrf_to_moon_fixed(jd_tdb) -> np.ndarray:
    """Rotation matrices (N,3,3) taking ICRF vectors to the Moon body-fixed frame."""
    a, dl, w = moon_orientation(np.atleast_1d(jd_tdb))
    # R = Rz(W) . Rx(90deg - delta0) . Rz(90deg + alpha0), passive rotations.
    sa, ca = np.sin(a), np.cos(a)
    sd, cd = np.sin(dl), np.cos(dl)
    # pole (body z axis) in ICRF
    z = np.stack([cd * ca, cd * sa, sd], axis=-1)
    # node direction Q = (cos(alpha+90), sin(alpha+90), 0); W is measured from Q along the equator
    q = np.stack([-sa, ca, np.zeros_like(a)], axis=-1)
    m = np.cross(z, q)
    cw, sw = np.cos(w)[:, None], np.sin(w)[:, None]
    x = cw * q + sw * m
    y = -sw * q + cw * m
    return np.stack([x, y, z], axis=1)


_ARCSEC = np.deg2rad(1.0 / 3600.0)


def _r1(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[1, 0, 0], [0, c, s], [0, -s, c]])


def _r2(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])


def _r3(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])


# DE421 principal-axis frame -> Mean Earth/polar axis frame (Williams, Boggs &
# Folkner 2008, "DE421 Lunar Orbit, Physical Librations, and Surface
# Coordinates"; the same constants as the MOON_ME_DE421 frame in NAIF's
# moon_080317.tf): ME = R1(-0.30") R2(-78.56") R3(-67.92") PA.
_PA_TO_ME = _r1(-0.30 * _ARCSEC) @ _r2(-78.56 * _ARCSEC) @ _r3(-67.92 * _ARCSEC)


def icrf_to_moon_me_de421(jd_tdb) -> np.ndarray:
    """Rotation matrices (N,3,3) from ICRF to the lunar Mean Earth frame using
    the numerically integrated DE421 libration angles (phi, theta, psi)."""
    jd = np.atleast_1d(np.asarray(jd_tdb, dtype=float))
    phi, theta, psi = _ephemeris().position("librations", jd)

    def r3(t):
        c, s, z, o = np.cos(t), np.sin(t), np.zeros_like(t), np.ones_like(t)
        return np.stack([np.stack([c, s, z], -1), np.stack([-s, c, z], -1), np.stack([z, z, o], -1)], 1)

    def r1(t):
        c, s, z, o = np.cos(t), np.sin(t), np.zeros_like(t), np.ones_like(t)
        return np.stack([np.stack([o, z, z], -1), np.stack([z, c, s], -1), np.stack([z, -s, c], -1)], 1)

    pa = r3(psi) @ r1(theta) @ r3(phi)
    return _PA_TO_ME @ pa


ORIENTATIONS = ("de421", "iau2009")


def rotation(jd_tdb, orientation: str = "de421") -> np.ndarray:
    if orientation == "de421":
        return icrf_to_moon_me_de421(jd_tdb)
    if orientation == "iau2009":
        return icrf_to_moon_fixed(jd_tdb)
    raise ValueError(f"unknown orientation model {orientation!r}; use one of {ORIENTATIONS}")


@dataclass(frozen=True)
class EphemTable:
    """Apparent Sun and Earth positions relative to the Moon's centre, in the
    Moon body-fixed frame (km), on a grid of UTC instants."""

    unix: np.ndarray      # (N,) seconds since 1970-01-01 UTC
    sun: np.ndarray       # (N,3) km
    earth: np.ndarray     # (N,3) km


def _apparent(target_pos_fn, jd, moon_pos, moon_vel, light_time: bool, aberration: bool):
    vec = target_pos_fn(jd) - moon_pos
    if light_time:
        for _ in range(2):
            lt_days = np.linalg.norm(vec, axis=0) / C_KM_S / 86400.0
            vec = target_pos_fn(jd - lt_days) - moon_pos
    if aberration:
        # first-order stellar aberration: shift the target by |r| * v_observer / c
        vec = vec + np.linalg.norm(vec, axis=0) * moon_vel / C_KM_S
    return vec


def compute_table(unix_seconds, light_time: bool = True, aberration: bool = True,
                  orientation: str = "de421") -> EphemTable:
    u = np.atleast_1d(np.asarray(unix_seconds, dtype=float))
    jd = unix_to_jd_tdb(u)
    lo, hi = ephemeris_span_jd()
    lo, hi = max(lo + 1, SUPPORTED_JD[0]), min(hi - 1, SUPPORTED_JD[1])
    if not np.all(np.isfinite(jd)) or jd.min() < lo or jd.max() > hi:
        raise ValueError("time outside the supported ephemeris span (1900-01-01 to 2050-01-01)")
    mp, mv = _moon_state(jd)
    sun = _apparent(_sun_pos, jd, mp, mv, light_time, aberration)
    earth = _apparent(_earth_pos, jd, mp, mv, light_time, aberration)
    rot = rotation(jd, orientation)
    sun_bf = np.einsum("nij,jn->ni", rot, sun)
    earth_bf = np.einsum("nij,jn->ni", rot, earth)
    return EphemTable(unix=u, sun=sun_bf, earth=earth_bf)


def supported_unix_span() -> tuple[float, float]:
    """First and last UTC instants (Unix seconds) a table may contain."""
    lo, hi = ephemeris_span_jd()
    lo, hi = max(lo + 1, SUPPORTED_JD[0]), min(hi - 1, SUPPORTED_JD[1])
    # TT-UTC is at most 69.184 s in the leap-second table; keep a small margin.
    to_unix = lambda jd: (jd - UNIX_EPOCH_JD) * 86400.0  # noqa: E731
    return to_unix(lo) + 120.0, to_unix(hi) - 120.0


def available_steps(start_unix: float, step_seconds: int) -> int:
    """How many grid samples starting at ``start_unix`` fit inside the supported span."""
    lo, hi = supported_unix_span()
    if start_unix < lo or start_unix > hi:
        raise ValueError("time outside the supported ephemeris span (1900-01-01 to 2050-01-01)")
    return int((hi - start_unix) // step_seconds) + 1


# One table costs 56 bytes per sample.  Requests are capped and the cache is
# bounded by total samples so a small host cannot be pushed out of memory.
MAX_TABLE_SAMPLES = 180_000
_CACHE_BUDGET_SAMPLES = 700_000
_table_cache: "OrderedDict[tuple, EphemTable]" = OrderedDict()
_table_lock = threading.Lock()


def cached_table(start_unix: int, n_steps: int, step_seconds: int) -> EphemTable:
    """Ephemeris table on a regular grid, cached because every site reuses it."""
    if n_steps > MAX_TABLE_SAMPLES:
        raise ValueError(f"request too large: {n_steps} time samples (limit {MAX_TABLE_SAMPLES}); "
                         "use a shorter span or a coarser step")
    key = (int(start_unix), int(n_steps), int(step_seconds))
    with _table_lock:
        hit = _table_cache.get(key)
        if hit is not None:
            _table_cache.move_to_end(key)
            return hit
    u = start_unix + step_seconds * np.arange(n_steps, dtype=float)
    table = compute_table(u)
    with _table_lock:
        _table_cache[key] = table
        total = sum(k[1] for k in _table_cache)
        while total > _CACHE_BUDGET_SAMPLES and len(_table_cache) > 1:
            old, _ = _table_cache.popitem(last=False)
            total -= old[1]
    return table


def cache_samples() -> int:
    with _table_lock:
        return sum(k[1] for k in _table_cache)


def grid_start(dt: datetime, step_seconds: int = 3600) -> int:
    """Snap an instant down to the step grid so cache keys repeat."""
    t = int(parse_utc(dt).timestamp())
    return t - (t % step_seconds)


def add_days(dt: datetime, days: float) -> datetime:
    return dt + timedelta(days=days)
