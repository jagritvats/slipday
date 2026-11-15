"""Add-on: darkness check (a simple thermal check).  How long is the longest stretch of total darkness, against a cold limit?

Without sunlight a lander cools; how fast depends on its insulation, heaters and battery, which this entry does
not model.  This check gives only the longest run of hours in which no part of the Sun's disc is above the
terrain skyline (total darkness, stricter than the card's "night", which starts when half the disc is down),
for a landing on each day of slip, measured from touchdown or its start inside the 14-day window to its end,
even past the window (up to 45 days).  It is set against an hour limit: one the user enters, or LIMIT below
when a first-hand figure is stored for it (NASA VIPER's 96 hours, a rover's figure).  No temperature is computed.

    GET /api/addons/darkness          the rule, the limit and its source
    GET /api/addons/darkness/site     one site and landing: per slip day, the longest total darkness vs the limit
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from ..ephem import iso, parse_utc
from ..metrics import STEP_S
from ..survival import full_runs
from .power import SLIP_DAYS, TAIL_DAYS, WINDOW_DAYS, site_from, sun_series

# An hour limit with a first-hand source, or None: then only the user's limit is used.
LIMIT: dict = {"hours": 96.0,
               "what": ("NASA's VIPER rover design figure for surviving darkness (a polar rover, not a lander; no "
                        "figure was found for a lander)"),
               "source": "viper2020", "quote": "Dark Survivability: 96hrs"}
CONTEXT = {"electronics_limit_c": -40.0, "source": "compass2022", "quote": "kept > -40C",
           "what": ("a NASA Glenn design study keeps the electronics above -40 C through the night; shown for context "
                    "only, no temperature is computed here")}
SOURCES: dict = {
    "viper2020": {
        "short": "NASA VIPER mission overview (Vaughan 2020)",
        "title": "VIPER - Volatiles Investigating Polar Exploration Rover: Mission Overview (ISSC, 11 May 2020)",
        "record_url": "https://ntrs.nasa.gov/citations/20205001794",
        "file_url": ("https://ntrs.nasa.gov/api/citations/20205001794/downloads/"
                     "VIPER_Mission_Overview_ISSC_Vaughan_05-11-2020.pptx.pdf"),
        "file_sha256": "4ce17f1dca23d438900f55745be0b9d3a4fc099505d617e321beea1cef24f765",
        "note": "the PDF (26.5 MB) is not stored; text extracted with pdftotext -layout, line ends LF.",
        "text_file": "ntrs_20205001794.txt",
        "sha256": {"ntrs_20205001794.txt": "9832b898c65281f4b7a8ff290c4e7848d1e131af7755aaece6f70917f7862d0f"},
    },
}


def rule_text() -> str:
    return ("Total darkness: no part of the Sun's disc above the terrain skyline (from the entry's DE421 Sun and the "
            "site's LOLA skyline, 2 m above ground). For each slip day, the longest such run under way at touchdown or "
            "starting inside the 14-day window, measured to its end even past the window (up to 45 days). Only hours "
            "are compared with the limit; no temperature is computed, and insulation, heaters, the battery and heat "
            "from the ground are not modelled.")


def analyse(site, landing, slip_days: int = SLIP_DAYS, limit_h: Optional[float] = None) -> dict:
    w = int(round(WINDOW_DAYS * 24))
    s, unix, frac, el, az, dist = sun_series(site, landing, (slip_days - 1) * 24 + w + TAIL_DAYS * 24 + 1)
    n = len(unix)
    dark = frac <= 0.0
    starts = np.arange(slip_days) * 24
    starts = starts[starts + w <= n]
    if not len(starts):
        raise ValueError("that landing window runs past the end of the ephemeris (2050)")
    best, open_ = full_runs(dark, starts, w)
    lim = limit_h if limit_h is not None else LIMIT["hours"]
    lim_label = ("set by the user" if limit_h is not None
                 else (LIMIT["what"] if LIMIT["hours"] is not None else None))
    days = []
    for k, st in enumerate(starts):
        h = int(best[0, k])
        within = None if lim is None else bool(h <= lim)
        if lim is None:
            text = f"longest total darkness {h} h" if h else "no total darkness"
        elif within:
            text = (f"longest total darkness {h} h, within the {lim:g} h limit" if h
                    else f"no total darkness, within the {lim:g} h limit")
        else:
            text = f"longest total darkness {h} h, {h - lim:g} h past the {lim:g} h limit"
        if open_[0, k]:
            text += " (still dark when the ephemeris table ended, so at least this long)"
        days.append({"day": int(k), "landing_utc": iso(s + int(st) * STEP_S), "darkness_h": h,
                     "open_end": bool(open_[0, k]), "within_limit": within, "text": text})
    first_over = next((x["day"] for x in days if x["within_limit"] is False), None)
    return {"available": True, "site": {"name": site.name, "lat": site.lat, "lon": site.lon},
            "horizon": site.horizon.describe(), "landing_utc": iso(s), "window_hours": w,
            "limit_h": lim, "limit_label": lim_label, "limit_source": LIMIT if limit_h is None else None,
            "days": days, "headline": days[0]["text"], "first_slip_day_over_limit": first_over,
            "longest_over_days_h": int(max(x["darkness_h"] for x in days)), "context": CONTEXT,
            "rule": rule_text()}


router = APIRouter(prefix="/api/addons/darkness", tags=["darkness"])


@router.get("")
def darkness_info():
    return {"available": True, "rule": rule_text(), "limit": LIMIT, "context": CONTEXT, "sources": SOURCES}


@router.get("/site")
def darkness_site(landing: str = "2026-11-18T00:00:00Z", site: Optional[str] = None,
                 lat: Optional[float] = Query(None, ge=-90, le=90), lon: Optional[float] = Query(None, ge=-360, le=360),
                 name: Optional[str] = None, slip_days: int = Query(SLIP_DAYS, ge=1, le=60),
                 limit_h: Optional[float] = Query(None, ge=0, le=10000)):
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
            return analyse(s, landing, slip_days, limit_h)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    return run(work)
