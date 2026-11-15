"""Add-on: relay satellites, contact when the Earth is hidden.

A relay is a satellite circling the Moon that passes messages between a lander and Earth.  When the Earth is
behind the terrain skyline, a relay above the skyline could still carry the link.  This module counts, hour by
hour over the landing window, contact by Earth alone, by relay alone and by either, and what the slip margin of
the stated point would be if contact by either counted.  The card's Earth verdict is never changed.

Orbit source (read first-hand, 15 Nov 2026):
  NASA, "NASA Lunar Communications Relay and Navigation Systems (LCRNS) Reference Constellation 3.1",
  G. Ryden and M. Volle, NASA GSFC, March 2025.  NTRS 20250002698.  "This reference design is not final".
  Five satellites in elliptical lunar frozen orbits with apolune above the south pole, period "approximately
  30 hours on average", states at 2027-03-01 00:00:00 UTC.  Copies and sha256: data/addons/relay/.

Model: two-body (a point-mass Moon), started from the source's Table 2 states (Moon-centred ICRF), rotated into
the Moon-fixed frame with the app's DE421 lunar orientation.  The source states that its orbits need a full force
model (GRGM-900c 25x25, Sun/Earth/planets, solar pressure) to stay as designed; two-body is not what the source
supports, so the satellite's position at a given hour is not a prediction.  Every count is therefore also run
for 144 other starting positions (12 along the orbit x 12 turns of the plane about the Moon's pole) and the page
shows the spread.  See ADDON_relay.md.

    GET /api/addons/relay              source, model and the satellites used
    GET /api/addons/relay/window       one site and landing: the hour strip, the counts, the slip margins
"""
from __future__ import annotations

import math
import os
from functools import lru_cache
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from ..ephem import (MOON_RADIUS_KM, _ephemeris, available_steps, cached_table, grid_start, iso, parse_utc,
                     rotation, unix_to_jd_tdb)
from ..geometry import Site, _azel, _enu, track
from ..metrics import STEP_S, Criteria, earth_up, station_ok, sun_up

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT, "data", "addons", "relay")

LABEL = ("a representative relay orbit from NASA's LCRNS Reference Constellation 3.1 (March 2025), "
         "not a live service")
SOURCE = {
    "title": "NASA Lunar Communications Relay and Navigation Systems (LCRNS) Reference Constellation 3.1",
    "authors": "Grant Ryden and Michael Volle, NASA Goddard Space Flight Center",
    "date": "March 2025",
    "record_url": "https://ntrs.nasa.gov/citations/20250002698",
    "file_url": ("https://ntrs.nasa.gov/api/citations/20250002698/downloads/"
                 "LCRNS_Reference_Constellation_White_Paper_03_2025.docx"),
    "sha256": {
        "LCRNS_Reference_Constellation_White_Paper_03_2025.docx":
            "a0812ed8405567125c3266c6cd0e7cbd7f115fff220f688bb978c4f7eccac0aa",
        "LCRNS_Reference_Constellation_White_Paper_03_2025.docx.txt":
            "a52bf9345f58ead9781e6f2dbdc267439f7858bc9b6b1a61a82be67d98160f3b",
        "ntrs_record_20250002698.json":
            "a821501a7547abb0c186910aebb1597d808befb2d01d7189949e061acbb2c0b6",
    },
    "quote_not_final": "This reference design is not final; the final design choice belongs to Intuitive Machines (IM)",
    "quote_period": "The period of these orbits is approximately 30 hours on average.",
    "quote_orbit": ("a class of orbits known as Elliptical Lunar Frozen Orbits (ELFO) was selected to provide longer "
                    "dwell times with apolune above the south pole"),
}

EPOCH_UTC = "2027-03-01T00:00:00Z"
# Table 2 of the source: Moon-centred ICRF position (km) and velocity (km/s) at EPOCH_UTC.
STATES = {
    "SV-1": (-198.931445, 386.023132, 3458.355412, -1.539867, 0.022243, -0.091059),
    "SV-2": (1089.980598, -2260.918271, -18984.562823, 0.280301, -0.004049, 0.016575),
}
# Table 1 of the source (Moon principal-axis frame): SMA km, ECC, INC deg, RAAN deg, AOP deg, TA deg.
TABLE1 = {
    "SV-1": (11315.936501, 0.691982, 59.373229, 321.019197, 92.494031, 0.0),
    "SV-2": (11317.948675, 0.691982, 58.951732, 320.997768, 92.505016, 180.0),
}
CONFIGS = {"two": ("SV-1", "SV-2"), "one": ("SV-1",)}
CONFIG_TEXT = {
    "two": "two relays (SV-1 and SV-2): the source's only pair sharing one orbit plane, half an orbit apart",
    "one": "one relay (SV-1)",
}
N_PHASE, N_NODE = 12, 12          # the spread: 12 positions along the orbit x 12 turns of the plane (30 deg apart)

NEED_SUN_H, NEED_CONTACT_H, WINDOW_DAYS, SLIP_DAYS = 240.0, 100.0, 14.0, 60


@lru_cache(maxsize=1)
def gm_moon() -> float:
    """The Moon's gravity constant (km^3/s^2) from the DE421 header: GM(Earth+Moon) / (1 + Earth/Moon mass ratio)."""
    e = _ephemeris()
    au = float(e.AU)
    return float(e.GMB) / (1.0 + float(e.EMRAT)) * au ** 3 / 86400.0 ** 2


def elements(state, mu: Optional[float] = None) -> dict:
    """Ellipse of a two-body orbit from one position (km) and velocity (km/s)."""
    mu = gm_moon() if mu is None else mu
    r = np.array(state[:3], float)
    v = np.array(state[3:], float)
    rn = np.linalg.norm(r)
    h = np.cross(r, v)
    ev = np.cross(v, h) / mu - r / rn
    e = float(np.linalg.norm(ev))
    a = 1.0 / (2.0 / rn - v @ v / mu)
    p_hat = ev / e
    w_hat = h / np.linalg.norm(h)
    q_hat = np.cross(w_hat, p_hat)
    nu = math.atan2(float(r @ q_hat), float(r @ p_hat))
    E = 2.0 * math.atan2(math.sqrt(1 - e) * math.sin(nu / 2), math.sqrt(1 + e) * math.cos(nu / 2))
    M0 = E - e * math.sin(E)
    return {"a_km": float(a), "e": e, "P": p_hat, "Q": q_hat, "W": w_hat, "M0": M0,
            "n_rad_s": math.sqrt(mu / a ** 3), "period_h": 2 * math.pi * math.sqrt(a ** 3 / mu) / 3600.0}


def _kepler(M: np.ndarray, e: float) -> np.ndarray:
    E = M + e * np.sin(M)
    for _ in range(30):
        E = E - (E - e * np.sin(E) - M) / (1.0 - e * np.cos(E))
    return E


def _rot_about(axis: np.ndarray, ang: float) -> np.ndarray:
    k = axis / np.linalg.norm(axis)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * (K @ K)


@lru_cache(maxsize=1)
def moon_pole_icrf() -> np.ndarray:
    """The Moon's north pole (unit vector, ICRF) at the source epoch, from the app's DE421 orientation."""
    t0 = parse_utc(EPOCH_UTC).timestamp()
    return rotation(unix_to_jd_tdb([t0]))[0][2].copy()


def positions_icrf(name: str, unix: np.ndarray, phase_rad: float = 0.0, node_rad: float = 0.0) -> np.ndarray:
    """(N,3) Moon-centred ICRF positions (km) of one satellite, two-body from the source state.

    ``phase_rad`` moves the satellite along its orbit (added to the mean anomaly); ``node_rad`` turns the orbit
    plane about the Moon's pole.  Both zero = as published."""
    el = elements(STATES[name])
    t0 = parse_utc(EPOCH_UTC).timestamp()
    M = el["M0"] + phase_rad + el["n_rad_s"] * (np.asarray(unix, float) - t0)
    E = _kepler(np.mod(M, 2 * math.pi), el["e"])
    x = el["a_km"] * (np.cos(E) - el["e"])
    y = el["a_km"] * math.sqrt(1 - el["e"] ** 2) * np.sin(E)
    P, Q = el["P"], el["Q"]
    if node_rad:
        R = _rot_about(moon_pole_icrf(), node_rad)
        P, Q = R @ P, R @ Q
    return x[:, None] * P[None, :] + y[:, None] * Q[None, :]


def _to_fixed(unix: np.ndarray, vec_icrf: np.ndarray, rot: Optional[np.ndarray] = None) -> np.ndarray:
    rot = rotation(unix_to_jd_tdb(unix)) if rot is None else rot
    return np.einsum("nij,nj->ni", rot, vec_icrf)


def _earth_clear_of_moon(relay_bf: np.ndarray, earth_bf: np.ndarray) -> np.ndarray:
    """True where the straight line from the relay to the Earth's centre misses the Moon (a ball of 1737.4 km)."""
    d = earth_bf - relay_bf
    d = d / np.linalg.norm(d, axis=1)[:, None]
    t = -np.einsum("ni,ni->n", relay_bf, d)
    closest = relay_bf + np.maximum(t, 0.0)[:, None] * d
    return np.linalg.norm(closest, axis=1) > MOON_RADIUS_KM


def relay_visible(site: Site, unix: np.ndarray, earth_bf: np.ndarray, sats, rot: np.ndarray,
                  phase_rad: float = 0.0, node_rad: float = 0.0) -> np.ndarray:
    """True where one or more of ``sats`` is above the site's skyline and sees the Earth."""
    east, north, up = _enu(site.lat, site.lon)
    pos = (MOON_RADIUS_KM + site.alt_km) * up
    out = np.zeros(len(unix), bool)
    for s in sats:
        p = _to_fixed(unix, positions_icrf(s, unix, phase_rad, node_rad), rot)
        az, el, _d = _azel(p, pos, east, north, up)
        above = el - site.horizon.elevation_at(az) > 0.0
        out |= above & _earth_clear_of_moon(p, earth_bf)
    return out


def _margin(ok_by_day: np.ndarray) -> int:
    m = -1
    for i, v in enumerate(ok_by_day):
        if not v:
            break
        m = i
    return m


def _ends_because(sun: np.ndarray, contact: np.ndarray, w: int, day: int, what: str) -> list[str]:
    """Plain reasons the given day of slip fails the need."""
    sv = day * 24
    if sv + w > len(sun):
        return []
    out = []
    sun_h, c_h = int(sun[sv:sv + w].sum()), int(contact[sv:sv + w].sum())
    if not sun[sv]:
        out.append("the Sun is behind the skyline at touchdown")
    if not contact[sv]:
        out.append(f"no {what} at touchdown")
    if sun_h < NEED_SUN_H:
        out.append(f"only {sun_h} sunlit hours of the {NEED_SUN_H:g} needed")
    if c_h < NEED_CONTACT_H:
        out.append(f"only {c_h} hours of {what} of the {NEED_CONTACT_H:g} needed")
    return out


def _by_day(sun: np.ndarray, contact: np.ndarray, w: int, n_days: int) -> tuple[np.ndarray, np.ndarray]:
    """Per day of slip: contact hours in the window, and whether the day passes the card's default need."""
    cs_sun = np.concatenate([[0], np.cumsum(sun)])
    cs_c = np.concatenate([[0], np.cumsum(contact)])
    sv = np.arange(n_days) * 24
    sun_h = cs_sun[sv + w] - cs_sun[sv]
    c_h = cs_c[sv + w] - cs_c[sv]
    ok = (sun_h >= NEED_SUN_H) & (c_h >= NEED_CONTACT_H) & sun[sv] & contact[sv]
    return c_h, ok


def analyse(site: Site, landing, config: str = "two", spread: bool = True, slip_days: int = SLIP_DAYS,
            stations: bool = True) -> dict:
    """Hour strip, counts and slip margins for one site and landing, with relays of the source's design.

    ``stations`` (the page's default): an hour of contact, by Earth or by relay, also needs a Deep Space Network
    complex with the Moon at least 10 degrees up, the card's own station rule.  Both paths end at a ground station."""
    if config not in CONFIGS:
        raise ValueError(f"config must be one of {sorted(CONFIGS)}")
    sats = CONFIGS[config]
    crit = Criteria(stations=stations)
    w = int(round(WINDOW_DAYS * 24))
    s = grid_start(parse_utc(landing), STEP_S)
    n = (slip_days - 1) * 24 + w + 1
    if n > available_steps(s, STEP_S):
        raise ValueError("that landing window runs past the end of the ephemeris (2050)")
    table = cached_table(s, n, STEP_S)
    unix = table.unix
    rot = rotation(unix_to_jd_tdb(unix))
    tr = track(site, table, crit.min_sun_fraction)
    sun = sun_up(tr)
    earth = earth_up(tr, crit)
    ground = station_ok(unix, crit)
    relay = relay_visible(site, unix, table.earth, sats, rot) & ground
    either = earth | relay

    win = slice(0, w)
    e_w, r_w = earth[win], relay[win]
    code = (e_w.astype(int) + 2 * r_w.astype(int))          # 0 none, 1 Earth only, 2 relay only, 3 both
    earth_h_day, ok_earth = _by_day(sun, earth, w, slip_days)
    either_h_day, ok_either = _by_day(sun, either, w, slip_days)
    m_e, m_x = _margin(ok_earth), _margin(ok_either)
    cs_sun = np.concatenate([[0], np.cumsum(sun)])
    sv_all = np.arange(slip_days) * 24
    out = {
        "available": True,
        "site": {"name": site.name, "lat": site.lat, "lon": site.lon},
        "horizon": site.horizon.describe(),
        "landing_utc": iso(s), "window_hours": w, "config": config, "config_text": CONFIG_TEXT[config],
        "satellites": list(sats), "label": LABEL, "stations": bool(stations),
        "hours": {"earth": int(e_w.sum()), "relay": int(r_w.sum()), "either": int((e_w | r_w).sum()),
                  "earth_only": int((code == 1).sum()), "relay_only": int((code == 2).sum()),
                  "both": int((code == 3).sum()), "none": int((code == 0).sum())},
        "code": [int(c) for c in code],
        "codes": {"0": "no contact", "1": "Earth only", "2": "relay only", "3": "Earth and relay"},
        "slip": {"rule": (f"at least {NEED_SUN_H:g} sunlit hours and {NEED_CONTACT_H:g} contact "
                          f"hours in {WINDOW_DAYS:g} days, Sun up and contact at touchdown"),
                 "days_checked": slip_days,
                 "margin_earth_days": m_e, "margin_either_days": m_x,
                 "earth_ends_because": _ends_because(sun, earth, w, m_e + 1, "Earth contact")
                 if m_e + 1 < slip_days else [],
                 "either_ends_because": _ends_because(sun, either, w, m_x + 1, "contact by Earth or relay")
                 if m_x + 1 < slip_days else [],
                 "earth_h_by_day": [int(v) for v in earth_h_day], "either_h_by_day": [int(v) for v in either_h_day],
                 "sunlit_h_by_day": [int(v) for v in (cs_sun[sv_all + w] - cs_sun[sv_all])]},
    }
    if spread:
        rel, either_w, marg = [], [], []
        for i in range(N_PHASE):
            for j in range(N_NODE):
                rv = relay_visible(site, unix, table.earth, sats, rot, 2 * math.pi * i / N_PHASE,
                                   2 * math.pi * j / N_NODE) & ground
                rel.append(int(rv[win].sum()))
                either_w.append(int((earth[win] | rv[win]).sum()))
                marg.append(_margin(_by_day(sun, earth | rv, w, slip_days)[1]))
        q = lambda a: {"lowest": int(np.min(a)), "middle": float(np.median(a)), "highest": int(np.max(a))}  # noqa: E731
        out["spread"] = {"runs": N_PHASE * N_NODE, "relay_h": q(rel), "either_h": q(either_w),
                         "margin_either_days": q(marg),
                         "what": ("the same counts for 144 other starting positions of the relays: 12 places along "
                                  "the orbit times 12 turns of the orbit plane about the Moon's pole")}
    return out


def describe() -> dict:
    els = {k: elements(v) for k, v in STATES.items()}
    return {
        "available": True, "label": LABEL, "source": SOURCE, "epoch_utc": EPOCH_UTC,
        "satellites": {k: {"table2_state_icrf": STATES[k], "table1_elements": dict(zip(
            ("sma_km", "ecc", "inc_deg", "raan_deg", "aop_deg", "ta_deg"), TABLE1[k])),
            "two_body_period_h": round(els[k]["period_h"], 3),
            "apolune_altitude_km": round(els[k]["a_km"] * (1 + els[k]["e"]) - MOON_RADIUS_KM, 1),
            "perilune_altitude_km": round(els[k]["a_km"] * (1 - els[k]["e"]) - MOON_RADIUS_KM, 1)}
            for k in STATES},
        "configs": CONFIG_TEXT, "gm_moon_km3_s2": round(gm_moon(), 6),
        "model": ("Two-body: each relay follows a fixed ellipse around a point-mass Moon, started from the source's "
                  "Table 2. This ignores the Moon's uneven gravity, the Earth, the Sun and sunlight pressure. The "
                  "source says its orbits need those to stay as designed, so it does not support two-body as a "
                  "prediction; the hour-by-hour position is illustrative and the spread over 144 starting "
                  "positions is shown."),
        "contact_rule": ("relay contact: a relay above the site's terrain skyline, with the Moon not between the relay "
                         "and the Earth. Earth contact: the Earth's centre above the skyline. With the station rule "
                         "on (the page's default), both also need a Deep Space Network complex with the Moon at "
                         "least 10 degrees up."),
    }


router = APIRouter(prefix="/api/addons/relay", tags=["relay"])


@router.get("")
def relay_info():
    return describe()


def _site(site: Optional[str], lat: Optional[float], lon: Optional[float], name: Optional[str]) -> Site:
    from ..sites import custom_site, get_site
    try:
        if site:
            return get_site(site)
        if lat is None or lon is None:
            raise HTTPException(422, "give a site id, or both lat and lon")
        return custom_site(name or "", lat, lon)
    except KeyError:
        raise HTTPException(404, f"unknown site id {site!r}")


@router.get("/window")
def relay_window(landing: str = "2026-11-18T00:00:00Z", site: Optional[str] = None,
                 lat: Optional[float] = Query(None, ge=-90, le=90), lon: Optional[float] = Query(None, ge=-360, le=360),
                 name: Optional[str] = None, config: str = Query("two", pattern="^(one|two)$"),
                 spread: bool = True, stations: bool = True):
    try:
        parse_utc(landing)
    except (ValueError, TypeError):
        raise HTTPException(422, "landing is not a date I can read (use e.g. 2026-11-18T00:00:00Z)")
    if site is None and lat is None and lon is None:
        site = "robust_pick"
    from ..load import run

    def work():
        s = _site(site, lat, lon, name)
        try:
            out = analyse(s, landing, config, spread, stations=stations)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        if config == "two":                 # the one-relay line, shown beside the headline
            one = analyse(s, landing, "one", spread, stations=stations)
            out["one_relay"] = {"config_text": one["config_text"], "hours": one["hours"], "code": one["code"],
                                "slip": {k: one["slip"][k] for k in ("margin_earth_days", "margin_either_days",
                                                                     "either_ends_because")}}
            if "spread" in one:
                out["one_relay"]["spread"] = one["spread"]
        return out
    return run(work)
