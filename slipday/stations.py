"""When can each NASA Deep Space Network complex see the Moon.

Three ground complexes carry a lunar lander's link to Earth: Goldstone
(California), Madrid (Robledo de Chavela, Spain) and Canberra (Tidbinbilla,
Australia).  This module answers one question on a grid of UTC instants: how
high is the Moon's centre above the horizon at each complex, and is that at or
above the elevation mask.

What is computed
----------------
* Moon: geocentric position from JPL DE421 (the kernel ``slipday.ephem``
  already holds), read at the instant minus the Earth-Moon light time, which
  to first order is the light-time plus aberration correction of an "apparent"
  place.
* Earth orientation: IAU 1976 precession, a four-term nutation series
  (Meeus, Astronomical Algorithms, ch. 22, good to about 0.5 arcsecond),
  Greenwich apparent sidereal time from the IAU 1982 GMST expression plus the
  equation of the equinoxes.  UT1 is taken as UTC (they differ by under 0.9 s,
  0.004 degrees of Earth rotation) and polar motion is left out (under
  0.0002 degrees).
* Station: geodetic latitude, east longitude and height on the WGS 84
  ellipsoid, one antenna per complex (the 70-m dish), from the DSN
  Telecommunications Link Design Handbook 810-005, module 301 Rev. P, Table 5.
* Elevation: topocentric (the station's geocentric position is subtracted from
  the Moon's), measured from the plane perpendicular to the ellipsoid normal.
  NO atmospheric refraction, NO terrain and NO per-antenna horizon mask: the
  mask is one flat angle for all azimuths.

Measured against JPL Horizons (airless apparent elevation, 294 hourly rows on
two dates, see scripts/check_stations_horizons.py and fixtures/stations/): the
figures are printed by that script and held by tests/test_stations.py.
"""
from __future__ import annotations

import threading
from collections import OrderedDict

import numpy as np

from . import ephem

# --------------------------------------------------------------------------
# Inputs read first-hand (fixtures/stations/SOURCES.md has the quotes, the
# byte counts and the sha256 of each file read).
# --------------------------------------------------------------------------
_HANDBOOK = ("DSN Telecommunications Link Design Handbook, DSN No. 810-005, module 301 "
             "\"Coverage and Geometry\", Rev. P (issue date May 22, 2026), Jet Propulsion Laboratory")
_HANDBOOK_URL = "https://deepspace.jpl.nasa.gov/dsndocs/810-005/301/301P.pdf"
_TABLE5 = _HANDBOOK + ", Table 5 \"Geodetic Coordinates for DSN Stations With Respect to the WGS 84 Ellipsoid\""


def _dms(sign: float, d: float, m: float, s: float) -> float:
    return sign * (d + m / 60.0 + s / 3600.0)


def _east180(lon_0_360: float) -> float:
    """East longitude folded into (-180, 180]."""
    return lon_0_360 - 360.0 if lon_0_360 > 180.0 else lon_0_360


# Table 5 prints degrees, minutes, seconds and east longitude in 0..360.  The
# values below are those figures converted to decimal degrees; lon_deg is east
# positive in (-180, 180], so Goldstone's 243.1104618 E is -116.8895382.
COMPLEXES: list[dict] = [
    {
        "id": "goldstone",
        "name": "Goldstone Deep Space Communications Complex, California, USA",
        "antenna": "DSS 14 (70-m)",
        "lat_deg": round(_dms(+1, 35, 25, 33.24312), 7),
        "lon_deg": round(_east180(_dms(+1, 243, 6, 37.66244)), 7),
        "height_m": 1001.390,
        "source": _TABLE5 + ", row \"DSS 14 70-m 35 25 33.24312 243 6 37.66244 1001.390\"",
        "source_url": _HANDBOOK_URL,
    },
    {
        "id": "madrid",
        "name": "Madrid Deep Space Communications Complex, Robledo de Chavela, Spain",
        "antenna": "DSS 63 (70-m)",
        "lat_deg": round(_dms(+1, 40, 25, 52.35510), 7),
        "lon_deg": round(_east180(_dms(+1, 355, 45, 7.16924)), 7),
        "height_m": 864.816,
        "source": _TABLE5 + ", row \"DSS 63 70-m 40 25 52.35510 355 45 7.16924 864.816\"",
        "source_url": _HANDBOOK_URL,
    },
    {
        "id": "canberra",
        "name": "Canberra Deep Space Communication Complex, Tidbinbilla, Australia",
        "antenna": "DSS 43 (70-m)",
        "lat_deg": round(_dms(-1, 35, 24, 8.72724), 7),
        "lon_deg": round(_east180(_dms(+1, 148, 58, 52.56231)), 7),
        "height_m": 688.867,
        "source": _TABLE5 + ", row \"DSS 43 70-m -35 24 8.72724 148 58 52.56231 688.867\"",
        "source_url": _HANDBOOK_URL,
    },
]

# Elevation mask.  Cited: the handbook's generic limits.  A lander needs
# commands up as well as telemetry down, so the transmit figure is the default.
MASK_DEG: float = 10.0
MASK_CITED: bool = True
MASK_QUOTE: str = ("The spacecraft coverage spreadsheet uses generic elevation limits for the receive "
                   "and transmit elevations. These are 6.0 degrees for receive, 10.0 degrees for "
                   "low-power transmit, and 13.5 degrees for high-power transmit.")
MASK_SOURCE: str = (_HANDBOOK + ", section 2.2.3: \"" + MASK_QUOTE + "\"  The 10.0-degree low-power "
                    "transmit limit is used as one flat angle at every azimuth; the handbook's "
                    "per-antenna horizon masks (terrain, neighbouring antennas) are not applied.")
MASK_URL: str = _HANDBOOK_URL
RECEIVE_MASK_DEG: float = 6.0   # same sentence; pass mask_deg=RECEIVE_MASK_DEG for downlink only

# WGS 84 ellipsoid (the handbook's Table 5 is "With Respect to the WGS 84 Ellipsoid").
_WGS84_A_KM = 6378.137
_WGS84_F = 1.0 / 298.257223563

_ARCSEC = np.deg2rad(1.0 / 3600.0)
_J2000_UNIX = 946728000.0  # 2000-01-01T12:00:00 UTC


def station_ecef_km() -> np.ndarray:
    """Earth-fixed Cartesian position of each complex, shape (3 complexes, 3), km."""
    lat = np.deg2rad([c["lat_deg"] for c in COMPLEXES])
    lon = np.deg2rad([c["lon_deg"] for c in COMPLEXES])
    h = np.array([c["height_m"] for c in COMPLEXES]) / 1000.0
    e2 = _WGS84_F * (2.0 - _WGS84_F)
    n = _WGS84_A_KM / np.sqrt(1.0 - e2 * np.sin(lat) ** 2)
    return np.stack([(n + h) * np.cos(lat) * np.cos(lon),
                     (n + h) * np.cos(lat) * np.sin(lon),
                     (n * (1.0 - e2) + h) * np.sin(lat)], axis=1)


def _zenith_unit() -> np.ndarray:
    """Outward normal of the ellipsoid at each complex, shape (3 complexes, 3)."""
    lat = np.deg2rad([c["lat_deg"] for c in COMPLEXES])
    lon = np.deg2rad([c["lon_deg"] for c in COMPLEXES])
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=1)


_STATION = station_ecef_km()
_ZENITH = _zenith_unit()


# Passive rotations of a vector held as three component arrays.
def _rot1(v, t):
    x, y, z = v
    c, s = np.cos(t), np.sin(t)
    return x, c * y + s * z, -s * y + c * z


def _rot2(v, t):
    x, y, z = v
    c, s = np.cos(t), np.sin(t)
    return c * x - s * z, y, s * x + c * z


def _rot3(v, t):
    x, y, z = v
    c, s = np.cos(t), np.sin(t)
    return c * x + s * y, -s * x + c * y, z


def _moon_earth_fixed_km(u: np.ndarray, nutation: bool = True, light_time: bool = True) -> np.ndarray:
    """Geocentric Moon in the Earth-fixed frame, shape (3, n), km."""
    jd = ephem.unix_to_jd_tdb(u)
    eph = ephem._ephemeris()                 # the DE421 kernel ephem.py already loaded
    gm = eph.position("moon", jd)            # geocentric Moon, ICRF, km
    if light_time:
        lt_days = np.sqrt((gm * gm).sum(axis=0)) / ephem.C_KM_S / 86400.0
        gm = eph.position("moon", jd - lt_days)

    t = (jd - ephem.J2000_JD) / 36525.0      # Julian centuries, TT
    # IAU 1976 precession, J2000 mean equator and equinox -> mean of date
    zeta = (2306.2181 * t + 0.30188 * t * t + 0.017998 * t ** 3) * _ARCSEC
    zed = (2306.2181 * t + 1.09468 * t * t + 0.018203 * t ** 3) * _ARCSEC
    theta = (2004.3109 * t - 0.42665 * t * t - 0.041833 * t ** 3) * _ARCSEC
    v = _rot3(_rot2(_rot3((gm[0], gm[1], gm[2]), -zeta), theta), -zed)

    # Greenwich mean sidereal time (IAU 1982), UT1 taken as UTC
    d_ut = (u - _J2000_UNIX) / 86400.0
    t_ut = d_ut / 36525.0
    gst = np.deg2rad(np.mod(280.46061837 + 360.98564736629 * d_ut
                            + 0.000387933 * t_ut * t_ut - t_ut ** 3 / 38710000.0, 360.0))
    if nutation:
        eps = (84381.448 - 46.8150 * t - 0.00059 * t * t + 0.001813 * t ** 3) * _ARCSEC
        om = np.deg2rad(125.04452 - 1934.136261 * t)       # Moon's ascending node
        ls = np.deg2rad(280.4665 + 36000.7698 * t)         # Sun's mean longitude
        lm = np.deg2rad(218.3165 + 481267.8813 * t)        # Moon's mean longitude
        dpsi = (-17.20 * np.sin(om) - 1.32 * np.sin(2 * ls) - 0.23 * np.sin(2 * lm)
                + 0.21 * np.sin(2 * om)) * _ARCSEC
        deps = (9.20 * np.cos(om) + 0.57 * np.cos(2 * ls) + 0.10 * np.cos(2 * lm)
                - 0.09 * np.cos(2 * om)) * _ARCSEC
        v = _rot1(_rot3(_rot1(v, eps), -dpsi), -(eps + deps))   # mean -> true of date
        gst = gst + dpsi * np.cos(eps)                          # equation of the equinoxes
    return np.stack(_rot3(v, gst), axis=0)


def _elevation_uncached(u: np.ndarray, nutation: bool = True, light_time: bool = True) -> np.ndarray:
    m = _moon_earth_fixed_km(u, nutation=nutation, light_time=light_time)   # (3, n)
    up = _ZENITH @ m - (_ZENITH * _STATION).sum(axis=1)[:, None]            # (3 complexes, n)
    dist2 = ((m * m).sum(axis=0)[None, :] - 2.0 * (_STATION @ m)
             + (_STATION * _STATION).sum(axis=1)[:, None])
    return np.rad2deg(np.arcsin(np.clip(up / np.sqrt(dist2), -1.0, 1.0)))


_CACHE_BUDGET_SAMPLES = 700_000          # 24 bytes per sample
_cache: "OrderedDict[tuple, np.ndarray]" = OrderedDict()
_cache_lock = threading.Lock()


def _grid_key(u: np.ndarray):
    """(first unix, count, step) for an evenly spaced grid, else None."""
    n = u.size
    if n == 1:
        return (float(u[0]), 1, 0.0)
    step = float(u[1] - u[0])
    if n > 2 and not np.all(np.diff(u) == step):
        return None
    return (float(u[0]), int(n), step)


def _as_times(unix) -> np.ndarray:
    u = np.atleast_1d(np.asarray(unix, dtype=float)).ravel()
    if u.size == 0:
        return u
    lo, hi = ephem.supported_unix_span()
    if not np.all(np.isfinite(u)) or u.min() < lo or u.max() > hi:
        raise ValueError("time outside the supported ephemeris span (1900-01-01 to 2050-01-01)")
    return u


def _elevation(unix) -> np.ndarray:
    """Cached elevations; the array returned is shared, do not write to it."""
    u = _as_times(unix)
    if u.size == 0:
        return np.empty((len(COMPLEXES), 0))
    key = _grid_key(u)
    if key is not None:
        with _cache_lock:
            hit = _cache.get(key)
            if hit is not None:
                _cache.move_to_end(key)
                return hit
    el = _elevation_uncached(u)
    if key is not None:
        el.setflags(write=False)
        with _cache_lock:
            _cache[key] = el
            total = sum(k[1] for k in _cache)
            while total > _CACHE_BUDGET_SAMPLES and len(_cache) > 1:
                old, _ = _cache.popitem(last=False)
                total -= old[1]
    return el


def moon_elevation_deg(unix) -> np.ndarray:
    """Elevation (degrees) of the Moon's centre at each complex, shape (3, n).

    ``unix`` is UTC as Unix seconds (scalar or array).  Row order is that of
    ``COMPLEXES``: Goldstone, Madrid, Canberra.  The elevation is topocentric
    (the station's own geocentric position is subtracted) and is measured
    above the geometric horizon of the WGS 84 ellipsoid at the antenna: no
    atmospheric refraction, no terrain.  The Moon is taken at the instant
    minus the light time (apparent place).  Earth orientation uses IAU 1976
    precession, a four-term nutation series and sidereal time with UT1 taken
    as UTC; polar motion is left out.
    """
    return np.array(_elevation(unix), dtype=float)   # a copy the caller may change


def _mask(mask_deg) -> float:
    return MASK_DEG if mask_deg is None else float(mask_deg)


def in_view(unix, mask_deg=None) -> np.ndarray:
    """Bool array (3, n): the Moon's centre is at or above the mask at each complex."""
    return _elevation(unix) >= _mask(mask_deg)


def any_in_view(unix, mask_deg=None) -> np.ndarray:
    """Bool array (n,): the Moon is at or above the mask at one or more complexes."""
    return in_view(unix, mask_deg).any(axis=0)


def carrier(unix, mask_deg=None) -> np.ndarray:
    """int8 array (n,): index into ``COMPLEXES`` (0 Goldstone, 1 Madrid, 2 Canberra)
    of the complex at which the Moon stands highest among those with it at or
    above the mask; -1 when none has."""
    el = _elevation(unix)
    best = el.argmax(axis=0).astype(np.int8)
    best[el.max(axis=0) < _mask(mask_deg)] = -1
    return best


def describe() -> dict:
    """The complexes, the mask, its source and the rule in one sentence."""
    return {
        "complexes": [dict(c) for c in COMPLEXES],
        "mask_deg": MASK_DEG,
        "mask_source": MASK_SOURCE,
        "mask_url": MASK_URL,
        "mask_cited": MASK_CITED,
        "mask_quote": MASK_QUOTE,
        "receive_mask_deg": RECEIVE_MASK_DEG,
        "rule": (f"An hour counts when the Moon's centre is at or above {MASK_DEG:g} degrees at one "
                 "or more of the three Deep Space Network complexes (Goldstone, Madrid, Canberra), "
                 "and it is credited to the complex at which the Moon stands highest."),
        "model": ("Moon from JPL DE421 at the instant minus the light time; IAU 1976 precession, "
                  "four-term nutation, sidereal time with UT1 taken as UTC, no polar motion; "
                  "topocentric elevation above the WGS 84 ellipsoid horizon at one 70-m antenna per "
                  "complex; no refraction, no terrain, one flat mask at every azimuth."),
    }
