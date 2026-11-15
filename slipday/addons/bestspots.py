"""Best spots this month: the three south-pole landing spots that suit the opening plan best this month.

``GET /api/addons/bestspots?month=YYYY-MM`` (default: the current UTC month).

How it is chosen, from data the page already has:

- The landing time: the opening plan lands 18 Nov 2026 00:00 UTC.  For another month the landing moves by whole
  synodic months (29.530589 days, the same time of the lunar day), as the card's "next windows" line does; the
  landing that falls in the asked month is used.  (Our inference, as on the card, not a published rule.)
- The need: the opening plan's (240 sunlit hours and 100 hours of Earth contact in 14 days, the Sun and the Earth in
  view at touchdown, 13 touchdown points within 100 m).  The 100 hours are illustrative.
- The candidates: the curated south-pole sites of the site list (not the always-dark crater floors), and the best
  points of the slip-margin map, re-checked at 13 touchdown points, on the coarser grid and with the near-field
  sampling (the same list as "Which of the best map points stay a clear yes?" on the page).  NASA's 78 published
  region sites are judged over 2027 to 2030 by the regions panel, not here: a mission card for each one would take
  minutes per month.
- Each candidate gets the full mission card.  Only a clear Yes counts.  Ranked by slip margin, then by the number of
  good landing dates in 60; a spot whose slope is known (5 m or 20 m terrain) and too steep (over NASA's 8 degree limit) is left out;
  a map point within 1 km of a listed site is dropped in favour of the listed site.
- Each spot has a friendly name from the IAU gazetteer (``gazetteer.naming_fields``), its coordinates, its slope where
  the slope add-on's grids cover it, and ``map`` data to show it on the page's map.

The first call for a month works out every card (about a minute on a laptop); after that the answer is kept.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import gazetteer
from ..sites import SITES

router = APIRouter()

OPENING = datetime(2026, 11, 18, 0, 0, tzinfo=timezone.utc)
SYNODIC_DAYS = 29.530589
NEED = {"need_sun_h": 240.0, "need_earth_h": 100.0, "window_days": 14.0, "scatter_m": 100.0}
SKIP = ("always dark",)
_lock = threading.Lock()
_cache: dict = {}


def landing_for_month(month: str) -> datetime:
    """The opening plan's landing moved by whole synodic months into ``month`` (YYYY-MM)."""
    y, m = (int(x) for x in month.split("-"))
    first = datetime(y, m, 1, tzinfo=timezone.utc)
    k = round(((first - OPENING).total_seconds() / 86400.0 + 14.0) / SYNODIC_DAYS)
    for kk in (k - 1, k, k + 1):
        t = OPENING + timedelta(days=kk * SYNODIC_DAYS)
        if (t.year, t.month) == (y, m):
            break
    else:
        t = OPENING + timedelta(days=k * SYNODIC_DAYS)
    return (t + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)     # nearest hour, as the card


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:00:00Z")


def _candidates(api, landing: str) -> list:
    out = [{"id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"], "from": "site list"}
           for s in SITES if s.get("group") == "South pole" and not any(w in s["name"] for w in SKIP)]
    try:
        r = api.api_robust_sites(api.RobustSitesRequest(start=landing))
        for row in (r.get("rows") or []) if r.get("available") else []:
            out.append({"id": None, "name": "Map point (" + row["name"] + ")", "lat": row["lat"], "lon": row["lon"],
                        "from": "slip-margin map"})
    except HTTPException:
        pass
    return out


def _slope(lat: float, lon: float) -> Optional[dict]:
    try:
        from . import safety
        s = safety.site_slopes(lat, lon, NEED["scatter_m"])
    except Exception:      # the slope add-on is an extra
        return None
    if not s.get("available") or s.get("verdict") == "unknown":
        return None
    st = s.get("steepest") or {}
    g = st.get("grid_m")
    return {"verdict": s["verdict"], "word": s.get("word"), "steepest_deg": st.get("slope_deg"), "grid_m": g,
            "known": bool(g is not None and g <= 20.0),     # 80 m is too coarse to call a slope known
            "headline": s.get("headline")}


def best_spots(month: str) -> dict:
    from .. import api            # imported here: api.py loads this module at its end
    landing = _iso(landing_for_month(month))
    t0 = time.time()
    rows = []
    cands = _candidates(api, landing)
    for c in cands:
        ref = api.SiteRef(id=c["id"]) if c["id"] else api.SiteRef(name=c["name"], lat=c["lat"], lon=c["lon"])
        try:
            m = api.api_mission(api.MissionRequest(site=ref, landing=landing, need_sun_h=NEED["need_sun_h"],
                                                   need_earth_h=NEED["need_earth_h"], window_days=NEED["window_days"],
                                                   scatter_m=NEED["scatter_m"], earth_stations=True))
        except HTTPException:
            continue
        if m.get("verdict") != "yes":
            continue
        slope = _slope(c["lat"], c["lon"])
        if slope and slope["known"] and slope["verdict"] == "steep":
            continue
        if any(gazetteer._dist_km(c["lat"], c["lon"], r["lat"], r["lon"]) < 1.0 for r in rows):
            continue          # a map point on top of a listed site: keep the listed one
        site = dict(c, **gazetteer.naming_fields(c))
        rows.append({
            "friendly_name": site["friendly_name"], "subtitle": site["subtitle"], "name_full": site["name_full"],
            "lat": c["lat"], "lon": c["lon"], "site_id": c["id"], "from": c["from"],
            "landing_utc": m["landing_utc"], "verdict": "yes", "slip_margin_days": m["slip_margin_days"],
            "good_dates": m.get("good_dates"), "points_passing": m["sure"]["points_passing"],
            "points": m["sure"]["points"], "sunlit_h": m["days"][0]["sunlit_h"], "earth_h": m["days"][0]["earth_h"],
            "terrain_grid": m.get("terrain_grid"), "slope": slope,
            "map": {"lat": c["lat"], "lon": c["lon"], "site": ({"id": c["id"]} if c["id"] else
                                                               {"name": site["friendly_name"], "lat": c["lat"], "lon": c["lon"]}),
                    "landing": m["landing_utc"]}})
    rows.sort(key=lambda r: (-r["slip_margin_days"], -(r["good_dates"] or 0), not (r["slope"] or {}).get("known")))
    return {"available": True, "month": month, "landing_utc": landing,
            "need": {"sunlit_h": NEED["need_sun_h"], "earth_h": NEED["need_earth_h"], "days": NEED["window_days"],
                     "landing_within_m": NEED["scatter_m"], "illustrative": "the 100 hours of Earth contact"},
            "rule": "the opening plan's need; a clear Yes at all 13 touchdown points; ranked by slip margin, then good "
                    "dates in 60; left out when the slope is known (5 m or 20 m terrain) and over NASA's 8 degree limit",
            "landing_rule": "the opening landing (18 Nov 2026 00:00 UTC) moved by whole synodic months into this month "
                            "(our inference, as on the card)",
            "candidates_from": ["the site list (south pole)", "the slip-margin map's best points, re-checked"],
            "candidates_checked": len(cands), "spots": rows[:3], "yes_found": len(rows),
            "seconds": round(time.time() - t0, 1)}


@router.get("/api/addons/bestspots")
def api_bestspots(month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$",
                                                description="YYYY-MM; default the current UTC month")):
    month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    y, m = (int(x) for x in month.split("-"))
    if not 1 <= m <= 12 or not 2000 <= y <= 2100:
        raise HTTPException(422, "month must be YYYY-MM")
    with _lock:
        if month in _cache:
            return _cache[month]
    out = best_spots(month)
    with _lock:
        _cache[month] = out
    return out
