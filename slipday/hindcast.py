"""Hindcast: compare predicted local sunrise/sunset with what real missions reported.

Reported facts were checked against the listed sources on 2026-11-14.  Items
that could not be confirmed are marked ``verified: False``.

Each prediction is made twice where a DEM covers the site: over the smooth
sphere and over the terrain horizon.  No pass/fail tolerance is applied: the
reports are operational events (sleep commands, power loss, last contact),
not measured sunsets, so the table gives the signed difference and a plain
size class that is the same for every row.
"""
from __future__ import annotations

from functools import lru_cache

from .ephem import cached_table, grid_start, iso, parse_utc
from .geometry import track, track_at
from .metrics import STEP_S, find_events
from .metrics import Criteria
from .sites import get_site, smooth_twin

MISSIONS = [
    {
        "id": "chandrayaan3", "mission": "Chandrayaan-3 (Vikram)",
        "landing_utc": "2023-08-23T12:33:00Z",
        "landing_source": "https://en.wikipedia.org/wiki/Chandrayaan-3",
        "reported": [
            {"label": "Lander put into sleep mode (about 08:00 IST, 4 Sep 2023)", "utc": "2023-09-04T02:30:00Z",
             "compare_to": "sunset_after", "verified": True,
             "source": "https://spacepolicyonline.com/news/india-says-good-night-to-chandrayaan-3/",
             "note": "Operators shut down ahead of sunset, so the report should come before the predicted sunset."},
            {"label": "ISRO wake-up target, 'sunlight returns on September 22' (date only)", "utc": "2023-09-22T00:00:00Z",
             "compare_to": "next_sunrise", "verified": True,
             "source": "https://spacepolicyonline.com/news/india-says-good-night-to-chandrayaan-3/",
             "note": "A wake-up needs the Sun well above the horizon for power, so it should follow geometric sunrise by a day or two."},
        ],
    },
    {
        "id": "im1", "mission": "IM-1 Odysseus",
        "landing_utc": "2024-02-22T23:23:53Z",
        "landing_source": "https://en.wikipedia.org/wiki/IM-1",
        "reported": [
            {"label": "Lander lost power (29 Feb 2024, date only)", "utc": "2024-02-29T00:00:00Z",
             "compare_to": "sunset_after", "verified": True,
             "source": "https://en.wikipedia.org/wiki/IM-1",
             "note": "Not a clean test: the lander was tipped about 30 degrees and sits among polar terrain, so it lost "
                     "power days before a smooth-sphere sunset. The date has no time of day and is compared at 00:00 UTC."},
        ],
    },
    {
        "id": "blueghost1", "mission": "Blue Ghost Mission 1",
        "landing_utc": "2025-03-02T08:34:00Z",
        "landing_source": "https://spaceflightnow.com/2025/03/18/firefly-aerospaces-blue-ghost-mission-1-concludes-successful-14-day-mission-on-the-moon/",
        "reported": [
            {"label": "Last communication (about 6:15 pm CDT, 16 Mar 2025)", "utc": "2025-03-16T23:15:00Z",
             "compare_to": "sunset_after", "verified": True,
             "source": "https://spaceflightnow.com/2025/03/18/firefly-aerospaces-blue-ghost-mission-1-concludes-successful-14-day-mission-on-the-moon/",
             "note": "The lander ran on battery for a few hours after sunset, so the report should come shortly after the predicted sunset."},
            {"label": "Landing + reported 346-hour mission", "utc": "2025-03-16T18:34:00Z",
             "compare_to": "sunset_after", "verified": True,
             "source": "https://spaceflightnow.com/2025/03/18/firefly-aerospaces-blue-ghost-mission-1-concludes-successful-14-day-mission-on-the-moon/",
             "note": "The article equates the 14-day operation with 346 hours; whether that figure counts the hours after sunset was not confirmed."},
        ],
    },
]


def size_class(diff_h):
    """One rule for every row, fixed before looking at any result."""
    if diff_h is None:
        return "no prediction"
    a = abs(diff_h)
    if a <= 6:
        return "within 6 h"
    if a <= 24:
        return "within 1 day"
    return f"off by {a / 24.0:.1f} days"


def _predict(site, t_land, start, crit):
    tr = track(site, cached_table(start, 80 * 24 + 1, STEP_S), crit.min_sun_fraction)
    out = {}
    for limb in ("center", "upper"):
        if limb == "upper" and site.horizon.is_terrain:
            # with terrain the "first/last light" figure is any part of the disc showing
            c0 = Criteria(min_sun_fraction=0.0)
            ev = find_events(site, track(site, cached_table(start, 80 * 24 + 1, STEP_S), 0.0), "sun", crit=c0)
        else:
            ev = find_events(site, tr, "sun", limb, crit=crit)
        before = [e for e in ev if e["type"] == "sunrise" and e["unix"] <= t_land]
        sets = [e for e in ev if e["type"] == "sunset" and e["unix"] > t_land]
        rises = [e for e in ev if e["type"] == "sunrise" and e["unix"] > t_land]
        out[limb] = {
            "sunrise_before": before[-1]["unix"] if before else None,
            "sunset_after": sets[0]["unix"] if sets else None,
            "next_sunrise": rises[0]["unix"] if rises else None,
        }
    return out


@lru_cache(maxsize=4)
def hindcast(mast_m: float = 2.0) -> dict:
    crit = Criteria()
    out = []
    any_terrain = False
    for m in MISSIONS:
        site = get_site(m["id"], mast_m=mast_m)
        models = [("smooth sphere", smooth_twin(site))]
        if site.horizon.is_terrain:
            models.append(("terrain", site))
            any_terrain = True
        t_land = parse_utc(m["landing_utc"]).timestamp()
        start = grid_start(parse_utc(m["landing_utc"])) - 32 * 86400
        pred = {name: _predict(s, t_land, start, crit) for name, s in models}
        at = track_at(site, [t_land])
        c = pred["smooth sphere"]["center"]
        checks = []
        for r in m["reported"]:
            rep = parse_utc(r["utc"]).timestamp()
            by_model = {}
            for name, _ in models:
                p = pred[name]["center"][r["compare_to"]]
                diff_h = (p - rep) / 3600.0 if p is not None else None
                by_model[name] = {
                    "predicted_utc": iso(p) if p is not None else None,
                    "predicted_minus_reported_h": round(diff_h, 1) if diff_h is not None else None,
                    "size": size_class(diff_h),
                }
            smooth = by_model["smooth sphere"]
            checks.append({
                "label": r["label"], "reported_utc": r["utc"], "compare_to": r["compare_to"],
                "predicted_utc": smooth["predicted_utc"],
                "predicted_minus_reported_h": smooth["predicted_minus_reported_h"],
                "size": smooth["size"], "models": by_model,
                "verified": r["verified"], "source": r["source"], "note": r["note"],
            })
        out.append({
            "id": m["id"], "mission": m["mission"],
            "site": {"name": site.name, "lat": site.lat, "lon": site.lon},
            "landing_utc": m["landing_utc"], "landing_source": m["landing_source"],
            "sun_el_at_landing": round(float(at.sun_el[0]), 2),
            "earth_el_at_landing": round(float(at.earth_el[0]), 2),
            "sun_horizon_at_landing": round(float(at.sun_el[0] - at.sun_clear[0]), 2),
            "terrain": site.horizon.describe() if site.horizon.is_terrain else None,
            "predicted": {
                limb: {k: (iso(v) if v is not None else None) for k, v in pred["smooth sphere"][limb].items()}
                for limb in pred["smooth sphere"]
            },
            "predicted_by_model": {
                name: {limb: {k: (iso(v) if v is not None else None) for k, v in pred[name][limb].items()}
                       for limb in pred[name]} for name in pred
            },
            "hours_from_sunrise_to_landing": (round((t_land - c["sunrise_before"]) / 3600.0, 1)
                                              if c["sunrise_before"] else None),
            "daylight_hours_predicted": (round((c["sunset_after"] - c["sunrise_before"]) / 3600.0, 1)
                                         if c["sunrise_before"] and c["sunset_after"] else None),
            "checks": checks,
        })
    return {
        "horizon": "Each event is predicted over the smooth sphere (0 deg, no terrain)"
                   + (" and over the terrain horizon where a DEM covers the site" if any_terrain else "")
                   + ". Events are for half the solar disc above the horizon (the disc centre on a level horizon).",
        "size_rule": "Size classes are the same for every row: within 6 h, within 1 day, otherwise off by N days. "
                     "They describe the difference; they are not a pass mark.",
        "terrain_used": any_terrain,
        "missions": out,
    }
