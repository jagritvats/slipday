"""Lunar against terrestrial conditions, in one small view.

The challenge text asks to "make the extreme differences between lunar and terrestrial conditions
apparent".  This module puts the Sun's height above the horizon at the chosen lunar site beside the
Sun's height at two places on Earth over the same days:

  moon     the chosen site, from this app's own model: JPL DE421 directions and the LOLA terrain skyline
           (derived; model output, not an observation)
  earth    a place on Earth at the same latitude, and a town at 45 degrees north, from a textbook
           solar-position formula (the NOAA solar-calculator approximation, level horizon, no
           refraction).  Computed for comparison only; it is not NASA data and nothing else in the app
           uses it.

Every figure in the answer carries a ``kind``: "derived" (this app's model on NASA data), "formula"
(the textbook Earth curve) or "constant" (a published constant).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from . import load
from .ephem import parse_utc
from .metrics import SYNODIC_DAYS, Criteria, longest_run, series
from .sites import custom_site, get_site

router = APIRouter()

EARTH_NOTE = ("Earth curves: textbook solar-position formula (NOAA solar-calculator approximation), level horizon, "
              "no refraction, longitude 0. Computed for comparison only; not NASA data.")
MOON_NOTE = ("Lunar curve: this app's model (JPL DE421 directions, terrain skyline ray-cast from LOLA elevation "
             "data where it covers the site). Model output, not an observation.")
CIVIL_TWILIGHT_DEG = -6.0


def earth_sun_elevation(unix, lat_deg: float, lon_deg: float = 0.0) -> np.ndarray:
    """Geometric elevation (deg) of the Sun's centre above a level horizon at a place on Earth.

    The NOAA solar-calculator formulas (after Meeus, Astronomical Algorithms): good to a few hundredths
    of a degree, which is far finer than this comparison needs.  No refraction, no terrain."""
    unix = np.asarray(unix, dtype=float)
    t = (unix / 86400.0 + 2440587.5 - 2451545.0) / 36525.0          # Julian centuries from J2000
    rad = np.deg2rad
    l0 = np.mod(280.46646 + t * (36000.76983 + 0.0003032 * t), 360.0)
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    c = (np.sin(rad(m)) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + np.sin(rad(2 * m)) * (0.019993 - 0.000101 * t) + np.sin(rad(3 * m)) * 0.000289)
    omega = 125.04 - 1934.136 * t
    lam = l0 + c - 0.00569 - 0.00478 * np.sin(rad(omega))
    eps = (23.0 + (26.0 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0) / 60.0
           + 0.00256 * np.cos(rad(omega)))
    decl = np.arcsin(np.sin(rad(eps)) * np.sin(rad(lam)))
    y = np.tan(rad(eps / 2.0)) ** 2
    eq_min = 4.0 * np.rad2deg(y * np.sin(2 * rad(l0)) - 2 * e * np.sin(rad(m))
                              + 4 * e * y * np.sin(rad(m)) * np.cos(2 * rad(l0))
                              - 0.5 * y * y * np.sin(4 * rad(l0)) - 1.25 * e * e * np.sin(2 * rad(m)))
    solar_min = np.mod(np.mod(unix, 86400.0) / 60.0 + eq_min + 4.0 * lon_deg, 1440.0)
    hour_angle = rad(solar_min / 4.0 - 180.0)
    phi = rad(lat_deg)
    return np.rad2deg(np.arcsin(np.clip(np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.cos(hour_angle),
                                        -1.0, 1.0)))


def _rises(up: np.ndarray) -> int:
    up = np.asarray(up, dtype=bool)
    return int(np.count_nonzero(~up[:-1] & up[1:]))


def _circular_span_deg(az: np.ndarray) -> float:
    """Width of the smallest arc that holds every azimuth."""
    a = np.sort(np.mod(np.asarray(az, dtype=float), 360.0))
    gaps = np.diff(np.concatenate([a, [a[0] + 360.0]]))
    return float(360.0 - gaps.max())


def _earth_place(label: str, lat: float, unix: np.ndarray, days: float) -> dict:
    """One place on Earth.  The curve is hourly like the lunar one; the counts use 10-minute steps, because
    an Earth day is short enough for hourly samples to blur twilight."""
    fine = unix[0] + 600.0 * np.arange((len(unix) - 1) * 6 + 1)
    el = earth_sun_elevation(fine, lat, 0.0)
    up = el > 0.0
    twilight = (el <= 0.0) & (el > CIVIL_TWILIGHT_DEG)
    return {"label": label, "lat": round(float(lat), 4), "lon": 0.0, "kind": "formula",
            "sun_el": [round(float(v), 2) for v in el[::6]],
            "max_sun_el": round(float(el.max()), 1), "min_sun_el": round(float(el.min()), 1),
            "sunrises": _rises(up), "sun_up_share_pct": round(float(up.mean()) * 100.0, 1),
            "longest_light_h": round(float(longest_run(up)) / 6.0, 1),
            "longest_dark_h": round(float(longest_run(~up)) / 6.0, 1),
            "civil_twilight_h_per_day": round(float(twilight.sum()) / 6.0 / days, 1)}


def contrast(site, start, days: float = 60.0, crit: Criteria = Criteria()) -> dict:
    """The Sun's height at ``site`` and at two places on Earth, hourly from ``start`` for ``days`` days."""
    hours = int(round(days * 24))
    s = series(site, start, hours, 60, crit, lookahead_days=1)
    n = s["count"]
    unix = s["start_unix"] + 3600.0 * np.arange(n)
    span_days = (n - 1) / 24.0
    sun_el = np.array(s["sun_el"])
    lit = np.array(s["lit"], dtype=bool)
    earth_el = np.array(s["earth_el"])
    terrain = s["horizon"].get("kind") == "profile"
    moon = {"label": s["site"]["name"], "lat": s["site"]["lat"], "lon": s["site"]["lon"], "kind": "derived",
            "horizon": s["horizon"], "terrain": terrain,
            "sun_el": [round(float(v), 2) for v in sun_el],
            "skyline_under_sun": [round(float(v), 2) for v in s["sun_horizon"]],
            "sun_up": [int(v) for v in lit], "sun_rule": s["criteria"]["sun_rule"],
            "max_sun_el": round(float(sun_el.max()), 2), "min_sun_el": round(float(sun_el.min()), 2),
            "sunrises": _rises(lit), "sun_up_share_pct": round(float(lit.mean()) * 100.0, 1),
            "longest_light_h": int(longest_run(lit)), "longest_dark_h": int(longest_run(~lit)),
            "civil_twilight_h_per_day": 0.0,
            "earth_in_sky": {"el_min": round(float(earth_el.min()), 2), "el_max": round(float(earth_el.max()), 2),
                             "az_span_deg": round(_circular_span_deg(np.array(s["earth_az"])), 2)}}
    same_lat = _earth_place(f"Earth, same latitude ({abs(site.lat):.1f} {'S' if site.lat < 0 else 'N'})", site.lat,
                            unix, span_days)
    town = _earth_place("Earth, a town at 45 N", 45.0, unix, span_days)
    e = moon["earth_in_sky"]
    facts = [
        {"k": "One day and night", "moon": f"{SYNODIC_DAYS:.1f} Earth days", "earth": "24 hours", "kind": "constant",
         "note": "the Moon's synodic month, 29.53 days"},
        {"k": f"Sun's height in these {span_days:.0f} days",
         "moon": f"{moon['min_sun_el']:+.1f} to {moon['max_sun_el']:+.1f} deg",
         "earth": f"{town['min_sun_el']:+.0f} to {town['max_sun_el']:+.0f} deg at 45 N, "
                  f"{same_lat['min_sun_el']:+.0f} to {same_lat['max_sun_el']:+.0f} deg at the same latitude",
         "kind": "derived / formula",
         "note": "above the level horizon. Where the lunar range is only a few degrees wide, the Sun grazes the "
                 "horizon all the time and a ridge a degree high decides whether there is light"},
        {"k": f"Sunrises in these {span_days:.0f} days", "moon": str(moon["sunrises"]),
         "earth": f"{town['sunrises']} at 45 N, {same_lat['sunrises']} at the same latitude", "kind": "derived / formula",
         "note": ("lunar count: the Sun clearing the terrain skyline" if terrain else
                  "lunar count: the Sun clearing a smooth sphere; no terrain data covers this site")
                 + f" ({moon['sun_rule']}); "
                 + ("the Sun stays up for the whole span" if moon["longest_light_h"] >= n else
                    "the Sun stays down for the whole span" if moon["longest_dark_h"] >= n else
                    f"longest unbroken light {moon['longest_light_h']} h, longest dark {moon['longest_dark_h']} h")},
        {"k": "Twilight", "moon": "none", "earth": f"{town['civil_twilight_h_per_day']:.1f} h a day at 45 N",
         "kind": "constant / formula",
         "note": "no atmosphere scatters light on the Moon: sunlight ends when terrain covers the disc. Earth "
                 "figure: Sun between 0 and 6 degrees below the horizon (civil twilight)"},
        {"k": "The Earth in the lunar sky", "moon": f"stays inside {e['az_span_deg']:.1f} deg of azimuth, "
                                                  f"{e['el_min']:+.1f} to {e['el_max']:+.1f} deg high",
         "earth": "the Moon crosses the whole sky every day", "kind": "derived",
         "note": "the Moon keeps one face to the Earth, so from the surface the Earth only wobbles (libration): "
                 "a ridge either hides it for days or never does"},
    ]
    return {"start_utc": s["start_utc"], "start_unix": s["start_unix"], "step_minutes": 60, "count": n,
            "days": round(span_days, 2), "truncated_at_ephemeris_end": s["truncated_at_ephemeris_end"],
            "moon": moon, "earth": [same_lat, town], "facts": facts,
            "notes": {"moon": MOON_NOTE, "earth": EARTH_NOTE,
                      "kinds": {"derived": "this app's model on NASA data (JPL DE421, LOLA)",
                                "formula": "textbook solar-position formula for a place on Earth; not NASA data",
                                "constant": "published constant"}}}


@router.get("/api/contrast")
def api_contrast(start: str, site: Optional[str] = None, lat: Optional[float] = Query(None, ge=-90, le=90),
                 lon: Optional[float] = Query(None, ge=-360, le=360), name: Optional[str] = None,
                 days: float = Query(60.0, ge=7, le=120), mast_m: float = Query(2.0, ge=0, le=500),
                 terrain: bool = True):
    """The Sun's height at a lunar site beside two places on Earth over the same days."""
    try:
        parse_utc(start)
    except (ValueError, TypeError):
        raise HTTPException(422, "start is not a date or time I can read (use e.g. 2026-11-14 or 2026-11-14T06:00:00Z)")

    def work():
        if site:
            try:
                s = get_site(site, 0.0, mast_m, terrain)
            except KeyError:
                raise HTTPException(404, f"unknown site id {site!r}")
        elif lat is None or lon is None:
            raise HTTPException(422, "a site needs either an id or both lat and lon")
        else:
            s = custom_site(name or "", lat, lon, 0.0, mast_m, terrain)
        try:
            return contrast(s, start, days)
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    # stored skylines answer in the light lane; a site nobody has asked for queues in the cold lane
    runner = getattr(load, "run", None)
    return runner(work) if runner else work()
