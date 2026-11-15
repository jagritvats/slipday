"""Add-on: launch windows from orbital mechanics (a simplified patched-conic sketch).

The card's own rule says a missed window moves about one synodic month (29.53 days); that rule is labelled as
our inference.  This add-on works the windows out from geometry instead:

  1. Landing lighting.  With the app's DE421 Sun and its terrain skyline (``track``), the landing must fall
     while the Sun counts as up over the skyline, its disc centre is between 0 and SUN_BAND_MAX_DEG above the
     skyline, and its true elevation is rising.  Each run of such hours lasting at least MIN_RUN_H is one
     lighting window; touchdown is allowed in its first LANDING_BAND_H hours.  The band numbers are
     illustrative, not taken from any mission rule.
  2. Arrival.  Touchdown is taken as the arrival instant (no time spent in lunar orbit).  The Moon's
     geocentric position at arrival comes from DE421.
  3. Launch.  Launch = arrival - transfer time (default TRANSFER_DAYS, a direct transfer).  The parking
     orbit plane must contain the Earth's centre, the launch site at the launch instant and the Moon's
     direction at arrival.  Earth rotation (GMST) carries the site round; the plane's launch azimuth is
     computed minute by minute and the launch counts as possible when that azimuth is inside the range
     limits AZ_MIN_DEG..AZ_MAX_DEG.  That gives up to two launch periods a day (one heading north-east, one
     south-east).

Limits, stated plainly: two-body legs only (no lunar gravity on the way in, no Sun, no Earth oblateness), a
fixed transfer time, the Moon's direction taken as the transfer's target (a real trajectory aims ahead of the
Moon and needs a lunar-orbit insertion), no rocket performance, no range or weather rules, the J2000 equator used
as the equator of date (about 0.4 degree of precession by 2026 is ignored), UT1 taken equal to UTC.  This is a
geometry check, not a mission design.

    GET /api/addons/trajwindows           method, assumptions, sources
    GET /api/addons/trajwindows/windows   one site: lighting windows, Moon declination, daily launch periods
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from ..ephem import _ephemeris, cached_table, grid_start, iso, parse_utc, unix_to_jd_tdb
from ..geometry import Site, track

SYNODIC_DAYS = 29.530589
STEP_S = 3600
MINUTE = 60

# ---- assumptions (every one is labelled in the JSON) ----
TRANSFER_DAYS = 4.0          # direct Earth-Moon transfer (assumption, not quoted first-hand)
SUN_BAND_MAX_DEG = 10.0      # illustrative upper edge of the landing-Sun band above the skyline
MIN_RUN_H = 12               # illustrative: a lighting window must last at least this long
LANDING_BAND_H = 48          # illustrative: touchdown allowed in the first 48 h of a lighting window
AZ_MIN_DEG, AZ_MAX_DEG = 35.0, 120.0   # illustrative launch-azimuth range for Kennedy (not quoted first-hand)
KENNEDY = (28.573, -80.649)

ASSUMPTIONS = [
    {"key": "model", "label": "assumption",
     "text": "Simplified patched conic: two-body legs, fixed transfer time, no lunar gravity on approach, "
             "no Sun or Earth-oblateness effects, no rocket performance or range rules. A geometry check, "
             "not a mission design."},
    {"key": "transfer_days", "value": TRANSFER_DAYS, "label": "assumption",
     "text": "Direct transfer of 4 days (an assumption, not quoted first-hand; change it with transfer_days). Low-energy "
             "transfers take months and are not modelled."},
    {"key": "arrival_is_landing", "label": "assumption",
     "text": "Touchdown is taken as the arrival instant: no time is spent in lunar orbit."},
    {"key": "sun_band_deg", "value": [0.0, SUN_BAND_MAX_DEG], "label": "illustrative",
     "text": "Landing Sun: disc centre 0 to 10 degrees above the terrain skyline and rising. Illustrative "
             "band, not a quoted mission rule."},
    {"key": "min_run_h", "value": MIN_RUN_H, "label": "illustrative",
     "text": "A lighting window is a run of such hours lasting at least 12 h."},
    {"key": "landing_band_h", "value": LANDING_BAND_H, "label": "illustrative",
     "text": "Touchdown allowed in the first 48 h of each lighting window."},
    {"key": "azimuth_deg", "value": [AZ_MIN_DEG, AZ_MAX_DEG], "label": "illustrative",
     "text": "Launch azimuth range 35 to 120 degrees for a Kennedy-latitude site. Illustrative, not quoted "
             "first-hand from range documents."},
    {"key": "frames", "label": "assumption",
     "text": "Moon from JPL DE421 (geocentric, ICRF). The J2000 equator is used as the equator of date "
             "(about 0.4 degree of precession ignored); Earth rotation from the IAU 1982 GMST formula with "
             "UT1 = UTC. The error this adds to the launch times has not been measured."},
    {"key": "target", "label": "assumption",
     "text": "The transfer plane holds the Earth's centre, the launch site at launch and the Moon's direction at "
             "arrival. A real trajectory aims ahead of the Moon; how much that moves the times is not worked out here."},
]
SOURCES = [
    {"what": "Moon and Sun positions, lunar orientation", "source": "JPL DE421 via the app's own ephem.py"},
    {"what": "Terrain skyline", "source": "the app's horizon (LOLA DEM when installed, else smooth sphere)"},
    {"what": "Earth rotation", "source": "GMST, IAU 1982 expression (Aoki et al. 1982), UT1 taken as UTC"},
]


def describe() -> dict:
    return {"name": "trajwindows",
            "title": "Launch windows from orbital mechanics",
            "method": ("Lighting windows at the site from DE421 and the terrain skyline; arrival = touchdown; "
                       "launch = arrival - transfer time; daily launch periods when Earth rotation puts the "
                       "launch site in a plane holding the Earth's centre and the Moon at arrival with a launch "
                       "azimuth inside the range limits."),
            "compares_with": {"rule": "one synodic month per missed window", "days": SYNODIC_DAYS,
                              "label": "the card's inference"},
            "assumptions": ASSUMPTIONS, "sources": SOURCES,
            "limits": "Two-body legs, fixed transfer time, no performance or range rules: a geometry check only."}


# ---------------- geometry ----------------

def gmst_rad(unix) -> np.ndarray:
    """Greenwich mean sidereal time (radians), IAU 1982 expression, UT1 taken as UTC."""
    jd = np.asarray(unix, float) / 86400.0 + 2440587.5
    d = jd - 2451545.0
    T = d / 36525.0
    deg = 280.46061837 + 360.98564736629 * d + 0.000387933 * T * T - T ** 3 / 38710000.0
    return np.deg2rad(np.mod(deg, 360.0))


def moon_geocentric(unix) -> np.ndarray:
    """(N,3) geocentric Moon (km, ICRF) from DE421."""
    jd = unix_to_jd_tdb(unix)
    return np.asarray(_ephemeris().position("moon", jd)).T


def declination_deg(vec: np.ndarray) -> np.ndarray:
    v = np.atleast_2d(vec)
    return np.rad2deg(np.arcsin(v[:, 2] / np.linalg.norm(v, axis=1)))


def launch_geometry(launch_unix, moon_dir: np.ndarray, lat_deg: float, lon_deg: float):
    """Launch azimuth and orbit inclination (degrees) of the prograde plane that holds the Earth's centre, the
    launch site at ``launch_unix`` and the direction ``moon_dir`` (N,3)."""
    t = np.atleast_1d(np.asarray(launch_unix, float))
    phi = math.radians(lat_deg)
    th = gmst_rad(t) + math.radians(lon_deg)
    s = np.stack([math.cos(phi) * np.cos(th), math.cos(phi) * np.sin(th), np.full_like(th, math.sin(phi))], -1)
    m = moon_dir / np.linalg.norm(moon_dir, axis=1)[:, None]
    h = np.cross(s, m)
    h = h / np.maximum(np.linalg.norm(h, axis=1), 1e-12)[:, None]
    h = np.where(h[:, 2:3] < 0, -h, h)                 # prograde: angular momentum towards north
    v = np.cross(h, s)
    east = np.stack([-np.sin(th), np.cos(th), np.zeros_like(th)], -1)
    north = np.stack([-math.sin(phi) * np.cos(th), -math.sin(phi) * np.sin(th), np.full_like(th, math.cos(phi))], -1)
    az = np.mod(np.rad2deg(np.arctan2((v * east).sum(1), (v * north).sum(1))), 360.0)
    inc = np.rad2deg(np.arccos(np.clip(h[:, 2], -1, 1)))
    return az, inc


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """[start, end) index pairs of True runs."""
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def lighting_runs(site: Site, start_unix: int, n_hours: int, band_max: float = SUN_BAND_MAX_DEG,
                  min_run_h: int = MIN_RUN_H):
    table = cached_table(start_unix, n_hours, STEP_S)
    tr = track(site, table)
    rising = np.gradient(tr.sun_el) > 0
    ok = (tr.sun_lit > 0) & (tr.sun_clear >= 0) & (tr.sun_clear <= band_max) & rising
    runs = [(a, b) for a, b in _runs(ok) if b - a >= min_run_h and a > 0 and b < n_hours]
    return tr, runs


def analyse(site: Site, landing, launch_lat: float = KENNEDY[0], launch_lon: float = KENNEDY[1],
            transfer_days: float = TRANSFER_DAYS, months: int = 3, band_max: float = SUN_BAND_MAX_DEG,
            landing_band_h: int = LANDING_BAND_H) -> dict:
    land = parse_utc(landing).timestamp()
    start = grid_start(parse_utc(iso(land - 16 * 86400)), STEP_S)
    n_hours = int((16 + (months + 1) * SYNODIC_DAYS + 4) * 24)
    tr, runs = lighting_runs(site, start, n_hours, band_max)
    u = tr.unix
    # k = 0: the window containing the planned landing, else the first that opens after it
    first = next((i for i, (a, b) in enumerate(runs) if u[b - 1] >= land), None)
    windows = []
    if first is not None:
        for k, (a, b) in enumerate(runs[first:first + months + 1]):
            windows.append(_window(k, tr, a, b, landing_band_h, launch_lat, launch_lon, transfer_days))
    for i in range(1, len(windows)):
        windows[i]["step_from_previous_days"] = round((windows[i]["_open"] - windows[i - 1]["_open"]) / 86400, 2)
        windows[i]["synodic_rule_open"] = iso(windows[0]["_open"] + i * SYNODIC_DAYS * 86400)
        windows[i]["differs_from_synodic_rule_days"] = round(
            (windows[i]["_open"] - windows[0]["_open"]) / 86400 - i * SYNODIC_DAYS, 2)
    steps = [w["step_from_previous_days"] for w in windows[1:]]
    for w in windows:
        w.pop("_open")
    hz = site.horizon.describe()
    return {
        "site": {"name": site.name, "lat": site.lat, "lon": site.lon, "horizon": hz["label"],
                 "terrain": hz["kind"] == "profile"},
        "planned_landing": iso(land),
        "launch_site": {"lat": launch_lat, "lon": launch_lon,
                        "label": "Kennedy (default)" if (launch_lat, launch_lon) == KENNEDY else "user-set"},
        "transfer_days": transfer_days, "transfer_label": "assumption: direct transfer, fixed duration",
        "sun_band_deg": [0.0, band_max], "sun_band_label": "illustrative, not a quoted mission rule",
        "landing_band_h": landing_band_h, "azimuth_limits_deg": [AZ_MIN_DEG, AZ_MAX_DEG],
        "azimuth_label": "illustrative, not quoted first-hand",
        "windows": windows,
        "steps_days": steps,
        "synodic_rule_days": SYNODIC_DAYS,
        "synodic_rule_label": "the card's inference: a missed window moves one synodic month",
        "note": ("Simplified patched conic: a geometry check, not a mission design. "
                 + ("Smooth sphere: no terrain skyline." if not hz["kind"] == "profile" else "")).strip(),
    }


def _window(k, tr, a, b, band_h, lat, lon, transfer_days) -> dict:
    u = tr.unix
    open_u = float(u[a])
    end_band = float(u[min(b - 1, a + band_h - 1)]) + STEP_S
    arr = np.arange(open_u, end_band, MINUTE)
    hour_ok = np.zeros(len(arr), bool)
    idx = np.clip(((arr - u[0]) // STEP_S).astype(int), 0, len(u) - 1)
    hour_ok = (idx >= a) & (idx < b)
    arr = arr[hour_ok]
    moon = moon_geocentric(arr)
    launch = arr - transfer_days * 86400.0
    az, inc = launch_geometry(launch, moon, lat, lon)
    ok = (az >= AZ_MIN_DEG) & (az <= AZ_MAX_DEG)
    periods = []
    for s0, s1 in _runs(ok):
        j = s0 + int(np.argmin(np.abs(az[s0:s1] - 90.0)))
        periods.append({"launch_from": iso(launch[s0]), "launch_to": iso(launch[s1 - 1]),
                        "best_launch": iso(launch[j]), "best_azimuth_deg": round(float(az[j]), 1),
                        "inclination_deg": round(float(inc[j]), 1), "landing_at_best": iso(arr[j]),
                        "heading": "north-east" if az[j] < 90 else "south-east",
                        "minutes": int(s1 - s0)})
    dec = declination_deg(moon)
    sun_el = float(tr.sun_el[a])
    return {
        "k": k, "_open": open_u,
        "window_open": iso(open_u), "window_close": iso(float(u[b - 1]) + STEP_S),
        "window_hours": int(b - a),
        "landing_band": [iso(open_u), iso(end_band)],
        "sun_elevation_at_open_deg": round(sun_el, 2),
        "sun_clearance_at_open_deg": round(float(tr.sun_clear[a]), 2),
        "moon_declination_deg": [round(float(dec.min()), 2), round(float(dec.max()), 2)],
        "declination_check": {"limit_deg": round(_i_max(lat), 1),
                              "ok": bool(np.abs(dec).max() <= _i_max(lat)),
                              "label": "|dec| must not exceed the highest inclination the azimuth range allows"},
        "launch_periods": periods,
        "launch_days": sorted({p["best_launch"][:10] for p in periods}),
    }


def _i_max(lat: float) -> float:
    """Highest inclination reachable inside the azimuth range: cos i = cos(lat) sin(az)."""
    c = math.cos(math.radians(lat))
    return max(math.degrees(math.acos(min(1.0, c * math.sin(math.radians(a))))) for a in (AZ_MIN_DEG, AZ_MAX_DEG))


# ---------------- router ----------------

router = APIRouter(prefix="/api/addons/trajwindows", tags=["trajwindows"])


@router.get("")
def trajwindows_info():
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


@router.get("/windows")
def trajwindows_windows(landing: str = "2026-11-18T00:00:00Z", site: Optional[str] = None,
                        lat: Optional[float] = Query(None, ge=-90, le=90),
                        lon: Optional[float] = Query(None, ge=-360, le=360), name: Optional[str] = None,
                        launch_lat: float = Query(KENNEDY[0], ge=-90, le=90),
                        launch_lon: float = Query(KENNEDY[1], ge=-180, le=360),
                        transfer_days: float = Query(TRANSFER_DAYS, ge=2.5, le=6.0),
                        months: int = Query(3, ge=1, le=6)):
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
            return analyse(s, landing, launch_lat, launch_lon, transfer_days, months)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    return run(work)
