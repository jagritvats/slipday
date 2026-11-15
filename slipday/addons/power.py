"""Add-on: battery through the night.  Does the lander's battery last through the darkness it meets?

The card counts sunlit hours.  This add-on turns those hours into energy, hour by hour, for one site and each
day of slip:
  solar power   = array power at full Sun x share of the Sun's disc above the terrain skyline x the cosine of
                  the angle between the Sun and the panel x (1 AU / Sun distance)^2
  load          = the operating load while the Sun is up, the survival (keep-alive and heater) load while it is down
  battery       = starts full at touchdown, charges with the surplus (times a charge efficiency), never above
                  its capacity; the run ends at the battery's empty point
The run covers the card's 14-day window from touchdown and, if a night is under way when the window ends,
carries on (on the survival load) until that night ends, up to 45 days.  The answer per slip day is either
"survives the longest night with X % charge left" or "battery empties N hours after touchdown".

The lander figures come from LANDER below.  Each figure carries its source (a file stored in data/addons/power
with its sha256) or the word "illustrative" where no first-hand figure was found.  Every figure can be changed
in the request, so the model is also a calculator: enter battery kWh and night load.

    GET /api/addons/power            the model, the lander figures and their sources
    GET /api/addons/power/site       one site and landing: per slip day, the lowest charge or the hour it empties
"""
from __future__ import annotations

import math
import os
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from ..ephem import MOON_RADIUS_KM, available_steps, cached_table, grid_start, iso, parse_utc
from ..geometry import Site, _enu, track
from ..metrics import STEP_S

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT, "data", "addons", "power")
AU_KM = 149_597_870.7
WINDOW_DAYS, SLIP_DAYS, TAIL_DAYS = 14.0, 30, 45

PANELS = {
    "vertical_tracking": "vertical panel turned to face the Sun's direction (best case for a vertical panel)",
    "vertical_fixed": "vertical panels fixed on the lander's sides, facing evenly spaced directions",
    "horizontal": "flat panel on the top deck, facing straight up",
}

# Filled from the stored sources (see SOURCES).  "source" names a key of SOURCES; None means illustrative.
NO_FLOWN = ("No published battery capacity, array power or night load was found for a flown lunar lander "
            "(searched 15 Nov 2026: Astrobotic Peregrine/Griffin user guide, NASA VIPER papers, NASA NTRS; Nova-C, "
            "Blue Ghost and HAKUTO-R pages gave no figures). This is therefore a calculator: enter your own battery and "
            "loads. The defaults below are labelled one by one.")
LANDER: dict = {
    "name": ("calculator, defaults from a NASA Glenn design study of a small lander built to survive the lunar night "
             "(not a flown lander), with array power, day load, face count and charge efficiency illustrative"),
    "array_w": {"value": 400.0, "unit": "W", "what": "array power at full Sun, normal incidence (no figure found)",
                "source": None},
    "battery_wh": {"value": 20000.0, "unit": "Wh", "what": "battery capacity", "source": "compass2022",
                   "quote": "1568 cells in 8s-196p configuration, ~20 kWh capacity"},
    "usable_frac": {"value": 0.9, "unit": "", "what": "share of the capacity that may be used (depth of discharge)",
                    "source": "compass2022", "quote": "Use 90% DoD to reduce battery mass"},
    "day_load_w": {"value": 46.0, "unit": "W", "what": ("load while the Sun is up (no figure found; set equal to the "
                                                       "study's night load)"), "source": None},
    "night_load_w": {"value": 46.0, "unit": "W", "what": "load in darkness: ~40 W operations plus ~6 W power-system losses",
                     "source": "compass2022", "quote": "Operational nighttime power is ~40 W, EPS losses total ~6W"},
    "charge_eff": {"value": 0.9, "unit": "", "what": "share of surplus power stored in the battery", "source": None},
    "panel": {"value": "vertical_fixed", "unit": "", "what": "panel geometry: side-mounted (vertical) panels",
              "source": "astrobotic_pug", "quote": "whereas polar missions utilize side-mounted panels"},
    "faces": {"value": 4, "unit": "", "what": "number of fixed vertical faces carrying cells", "source": None},
}
SOURCES: dict = {
    "compass2022": {
        "short": "NASA Glenn design study (Oleson, Colozza, Uguccini 2022), not a flown lander",
        "title": "Overnight Power & Thermal Solutions for Lunar Landers (Compass Team, Survive The Night Technology "
                 "Workshop, 6 Dec 2022)",
        "authors": "Steven Oleson, Anthony Colozza, Nicholas Uguccini (NASA Glenn Research Center, HX5 LLC)",
        "record_url": "https://ntrs.nasa.gov/citations/20220018215",
        "file_url": ("https://ntrs.nasa.gov/api/citations/20220018215/downloads/"
                     "Overnight%20Power%20and%20Thermal%20Solutions%20for%20Small%20Landers%20final2.pdf"),
        "file_sha256": "da6c1c46bca7c7779f03660ad5453ea2e78c628a9f0fd503843f0065f8446ef3",
        "note": ("the PDF (11.9 MB) is not stored; the text below was extracted from it with pdftotext -layout, line ends LF. "
                 "The study is for a mid-latitude night of 354 hours, not a polar site."),
        "text_file": "ntrs_20220018215.txt",
        "sha256": {"ntrs_20220018215.txt": "e9d3684f25baa5483d8feb3e9a7a01119fd9bfd15435ac8a064c014d49986845"},
    },
    "astrobotic_pug": {
        "short": "Astrobotic Peregrine/Griffin Payload User's Guide (2022)",
        "title": "Astrobotic Lunar Landers Payload User's Guide (PUGLanders_011222)",
        "file_url": "https://www.astrobotic.com/wp-content/uploads/2022/01/PUGLanders_011222.pdf",
        "file_sha256": "bbb21c232b2dcfbf262996c745f2c28b30f8bc73fc7ccb18eac34f9f33234a24",
        "note": ("the PDF (10.4 MB) is not stored; text extracted with pdftotext -layout, line ends LF. It gives no battery capacity, "
                 "array power or survival load."),
        "text_file": "astrobotic_PUGLanders_011222.txt",
        "sha256": {"astrobotic_PUGLanders_011222.txt":
                   "636243df7445def7ea4b087e3f881c2fb56518fc9d152fb46ece50d9c30a247e"},
    },
}


def figure_labels() -> dict:
    out = {}
    for k, v in LANDER.items():
        if isinstance(v, dict):
            src = v.get("source")
            out[k] = {"value": v["value"], "unit": v["unit"], "what": v["what"],
                      "label": (SOURCES[src]["short"] if src in SOURCES else "illustrative"),
                      "source": src, "quote": v.get("quote")}
    return out


# ---------------- the hour-by-hour series ----------------

def sun_series(site: Site, landing, n_hours: int):
    """Hourly Sun at the site from touchdown: share of disc above the skyline, elevation, azimuth (deg) and
    distance (AU).  Uses the entry's DE421 table and the site's terrain skyline."""
    s = grid_start(parse_utc(landing), STEP_S)
    n = min(n_hours, available_steps(s, STEP_S))
    table = cached_table(s, n, STEP_S)
    tr = track(site, table)
    east, north, up = _enu(site.lat, site.lon)
    dist = np.linalg.norm(table.sun - (MOON_RADIUS_KM + site.alt_km) * up, axis=1) / AU_KM
    return s, table.unix, np.clip(tr.sun_frac, 0.0, 1.0), tr.sun_el, tr.sun_az, dist


def incidence(sun_el, sun_az, panel: str, faces: int = 4) -> np.ndarray:
    """Cosine factor between the Sun and the panel, per hour (0 when the Sun is behind the panel).
    For fixed vertical faces, the array power is shared evenly among the faces."""
    el = np.deg2rad(np.asarray(sun_el, dtype=float))
    up = el > -0.02
    if panel == "vertical_tracking":
        f = np.cos(el)
    elif panel == "horizontal":
        f = np.maximum(np.sin(el), 0.0)
    elif panel == "vertical_fixed":
        faces = max(1, int(faces))
        az = np.deg2rad(np.asarray(sun_az, dtype=float))
        f = np.zeros_like(el)
        for k in range(faces):
            f += np.maximum(np.cos(az - 2 * math.pi * k / faces), 0.0)
        f = f * np.cos(el) / faces
    else:
        raise ValueError(f"panel must be one of {sorted(PANELS)}")
    return np.where(up, f, 0.0)


def solar_power(frac, sun_el, sun_az, dist_au, array_w: float, panel: str, faces: int) -> np.ndarray:
    return array_w * np.asarray(frac) * incidence(sun_el, sun_az, panel, faces) / np.asarray(dist_au) ** 2


def simulate(power_w: np.ndarray, sunlit: np.ndarray, start: int, window_h: int, battery_wh: float,
             day_load_w: float, night_load_w: float, charge_eff: float) -> dict:
    """Battery from touchdown at hour ``start``: full at touchdown, one-hour steps.  Runs through the window and,
    if a night is under way at the window's end, on until it ends (or the series ends).  Returns the charge
    curve, the lowest charge, and the hour (after touchdown) at which the battery empties, if it does."""
    n = len(power_w)
    end = min(start + window_h, n)
    extended = False
    if end < n and not sunlit[end - 1]:          # a night under way at the window's end: run on until it ends
        while end < n and not sunlit[end]:
            end += 1
            extended = True
    e = float(battery_wh)
    curve = [e]
    empty_at: Optional[int] = None
    for t in range(start, end):
        load = day_load_w if sunlit[t] else night_load_w
        net = power_w[t] - load
        e = min(battery_wh, e + net * charge_eff) if net > 0 else e + net
        if e <= 0:
            empty_at = t - start + 1
            curve.append(0.0)
            break
        curve.append(e)
    open_end = empty_at is None and extended and end >= n
    c = np.asarray(curve)
    return {"curve_wh": c, "min_wh": float(c.min()), "empty_after_h": empty_at, "hours": len(c) - 1,
            "open_end": bool(open_end)}


def dark_runs_from(sunlit: np.ndarray, start: int, hours: int) -> int:
    """Longest run of hours without the Sun up, in [start, start + hours)."""
    seg = ~np.asarray(sunlit[start:start + hours], dtype=bool)
    best = run = 0
    for v in seg:
        run = run + 1 if v else 0
        best = max(best, run)
    return int(best)


def params_from(**over) -> dict:
    p = {k: (v["value"] if isinstance(v, dict) else v) for k, v in LANDER.items() if isinstance(v, dict)}
    changed = []
    for k, v in over.items():
        if v is not None and k in p and v != p[k]:
            p[k] = v
            changed.append(k)
    if p["panel"] not in PANELS:
        raise ValueError(f"panel must be one of {sorted(PANELS)}")
    return p | {"changed": changed}


def analyse(site: Site, landing, slip_days: int = SLIP_DAYS, window_days: float = WINDOW_DAYS, **over) -> dict:
    p = params_from(**over)
    w = int(round(window_days * 24))
    n_need = (slip_days - 1) * 24 + w + TAIL_DAYS * 24 + 1
    s, unix, frac, el, az, dist = sun_series(site, landing, n_need)
    n = len(unix)
    sunlit = frac > 0.5                         # the card's default Sun rule: half the disc above the skyline
    pw = solar_power(frac, el, az, dist, p["array_w"], p["panel"], p["faces"])
    cap = p["battery_wh"] * p["usable_frac"]          # the energy the run may use
    days = []
    for d in range(slip_days):
        st = d * 24
        if st + w > n:
            break
        r = simulate(pw, sunlit, st, w, cap, p["day_load_w"], p["night_load_w"], p["charge_eff"])
        night = dark_runs_from(sunlit, st, r["hours"])
        pct = 100.0 * r["min_wh"] / cap
        if r["empty_after_h"] is not None:
            text = f"battery empties {r['empty_after_h']} hours after touchdown"
        else:
            text = ((f"survives the longest night ({night} h) with {pct:.0f} % of the usable charge left" if night
                     else f"no night in the run; the lowest charge is {pct:.0f} % of the usable charge")
                    + (" (that night was still going when the ephemeris table ended)" if r["open_end"] else ""))
        days.append({"day": d, "landing_utc": iso(s + st * STEP_S), "survives": r["empty_after_h"] is None,
                     "min_charge_pct": round(pct, 1), "empty_after_h": r["empty_after_h"],
                     "longest_night_h": night, "hours_run": r["hours"], "text": text})
    if not days:
        raise ValueError("that landing window runs past the end of the ephemeris (2050)")
    r0 = simulate(pw, sunlit, 0, w, cap, p["day_load_w"], p["night_load_w"], p["charge_eff"])
    hours0 = r0["hours"]
    ok = [x["survives"] for x in days]
    first_fail = next((x["day"] for x in days if not x["survives"]), None)
    return {
        "available": True,
        "site": {"name": site.name, "lat": site.lat, "lon": site.lon},
        "horizon": site.horizon.describe(),
        "landing_utc": iso(s), "window_hours": w, "slip_days_checked": len(days),
        "lander": LANDER["name"], "no_flown_figures": NO_FLOWN, "figures": figure_labels(),
        "used": {k: v for k, v in p.items() if k != "changed"}, "changed_by_user": p["changed"],
        "days": days,
        "headline": days[0]["text"],
        "first_failing_slip_day": first_fail,
        "days_surviving": int(sum(ok)),
        "day0_curve_pct": [round(100.0 * v / cap, 1) for v in r0["curve_wh"]],
        "day0_solar_w": [round(float(v), 1) for v in pw[:hours0]],
        "day0_sunlit": [bool(v) for v in sunlit[:hours0]],
        "rule": rule_text(),
    }


def rule_text() -> str:
    return ("Hour by hour from touchdown: solar power = array power x share of the Sun's disc above the terrain "
            "skyline x cosine of the Sun-to-panel angle x (1 AU / Sun distance)^2. Operating load while at least half "
            "the Sun's disc is above the skyline, survival load otherwise. The battery starts full, charges with the "
            "surplus times the charge efficiency, and only the usable share of its capacity (depth of discharge) is drawn; the run ends when that is used up. The run covers the 14-day window "
            "and, if a night is under way at its end, on until that night ends. Not modelled: cell temperature and "
            "ageing, dust, shadowing by the lander itself, battery ageing and temperature, light reflected from the "
            "ground, and any change of load the operators would make.")


def describe() -> dict:
    return {"available": True, "lander": LANDER["name"], "no_flown_figures": NO_FLOWN, "figures": figure_labels(),
            "sources": SOURCES,
            "panels": PANELS, "rule": rule_text(), "window_days": WINDOW_DAYS, "tail_days": TAIL_DAYS}


router = APIRouter(prefix="/api/addons/power", tags=["power"])


@router.get("")
def power_info():
    return describe()


def site_from(site: Optional[str], lat: Optional[float], lon: Optional[float], name: Optional[str]) -> Site:
    from ..sites import custom_site, get_site
    try:
        if site:
            return get_site(site)
        if lat is None or lon is None:
            raise HTTPException(422, "give a site id, or both lat and lon")
        return custom_site(name or "", lat, lon)
    except KeyError:
        raise HTTPException(404, f"unknown site id {site!r}")


@router.get("/site")
def power_site(landing: str = "2026-11-18T00:00:00Z", site: Optional[str] = None,
               lat: Optional[float] = Query(None, ge=-90, le=90), lon: Optional[float] = Query(None, ge=-360, le=360),
               name: Optional[str] = None, slip_days: int = Query(SLIP_DAYS, ge=1, le=60),
               battery_kwh: Optional[float] = Query(None, gt=0, le=1000),
               night_load_w: Optional[float] = Query(None, ge=0, le=100000),
               day_load_w: Optional[float] = Query(None, ge=0, le=100000),
               array_w: Optional[float] = Query(None, ge=0, le=1000000),
               charge_eff: Optional[float] = Query(None, gt=0, le=1),
               usable_frac: Optional[float] = Query(None, gt=0, le=1),
               panel: Optional[str] = Query(None, pattern="^(vertical_tracking|vertical_fixed|horizontal)$"),
               faces: Optional[int] = Query(None, ge=1, le=12)):
    try:
        parse_utc(landing)
    except (ValueError, TypeError):
        raise HTTPException(422, "landing is not a date I can read (use e.g. 2026-11-18T00:00:00Z)")
    if site is None and lat is None and lon is None:
        site = "robust_pick"
    from ..load import run

    def work():
        s = site_from(site, lat, lon, name)
        try:
            return analyse(s, landing, slip_days,
                           battery_wh=(battery_kwh * 1000.0 if battery_kwh is not None else None),
                           night_load_w=night_load_w, day_load_w=day_load_w, array_w=array_w,
                           charge_eff=charge_eff, usable_frac=usable_frac, panel=panel, faces=faces)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    return run(work)
