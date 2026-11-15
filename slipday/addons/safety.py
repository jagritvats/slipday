"""Add-on: "Flat enough to land?"  Ground slope at lander scale at the 13 touchdown points of a site.

Slipday checks light and Earth contact.  This module adds the other question a landing site must answer:
is the ground flat enough where the lander may come down?

The limit (read first-hand, 15 Nov 2026):
  NASA, Human Landing System (HLS) Requirements Document, HLS-RQMT-001, initial release, 27 Sep 2019,
  requirement HLS-R-0071 "Landing Site Vertical Orientation": "The HLS shall provide vertical orientation of
  0 to 8 deg (threshold) and 0 to 5 deg (goal) from local vertical for surface operations."
  Strictly this is a limit on how far the lander may lean, not on the ground.  Wueller et al. 2026 (JGR Planets,
  e2025JE009434, section 2.2) and Kring et al. 2023 apply it to the ground: landing areas with slopes under 8 deg.
  We do the same and say so on the page.  HLS-R-0021 in the same document gives the landing accuracy, 100 m
  (3-sigma), which is why the 13 touchdown points reach 100 m from the target.

The slope:
  At each touchdown point, a flat plane is fitted (least squares) to the terrain heights of the grid cells
  around it, and the slope is the tilt of that plane.  The finest grid on disk that covers the point is used:
    5 m  LOLA site models (Site01 connecting ridge, Site07 peak near Shackleton): 3 x 3 cells, a 10 m square.
         10 m is about the width of a crewed lander standing on its legs, and the baseline NASA's own
         white paper (HLS solicitation attachment A20) uses for slopes seen in LOLA 5 m data.
    20 m LOLA south-pole mosaic (crop to about 88.4 S): the 2 x 2 cells around the point, a 20 m square.
    80 m LOLA south-pole mosaic (to 80 S): the 2 x 2 cells around the point, an 80 m square.
  On 20 m and 80 m grids the square is wider than a lander, so the slope is averaged over more ground and
  usually reads lower than the slope under the lander's feet.  No grid here shows boulders or craters smaller
  than a few grid cells.

All grids are read in place, read-only, memory-mapped.
"""
from __future__ import annotations

import json
import math
import os
import threading
from functools import lru_cache
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..dem import PolarStereoDEM

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LIMIT_DEG = 8.0          # HLS-R-0071 threshold
GOAL_DEG = 5.0           # HLS-R-0071 goal
LANDER_BASELINE_M = 10.0  # the square the slope is measured over, where the grid allows it
DEFAULT_SCATTER_M = 100.0  # HLS-R-0021: 100 m landing accuracy; the card's default scatter radius
DEFAULT_MIN_SLIP_DAYS = 1  # "slip-tolerant" on the map layer: keeps a margin of at least this many days

SOURCE = {
    "limit": ("NASA, Human Landing System (HLS) Requirements Document, HLS-RQMT-001, initial release, 27 September "
              "2019, requirement HLS-R-0071 Landing Site Vertical Orientation: \"The HLS shall provide vertical "
              "orientation of 0 to 8° (threshold) and 0 to 5° (goal) from local vertical for surface operations.\""),
    "limit_url": "https://sam.gov/opp/f3f8689858d6fc2c7f91e6533235f6e7/view",
    "limit_file": "Attachment_F_-_Requirements.zip, file 'HLS-RQMT-001 SRD Rev R 20190927.pdf', page 37 of 315 (HLS-R-0021 is on page 32)",
    "limit_note": ("NASA's number limits how far the lander may lean. Published site studies (Wueller et al. 2026; "
                   "Kring et al. 2023) use it as a limit on the slope of the ground, and so do we."),
    "accuracy": "Same document, HLS-R-0021: the lander must come down within 100 m (3-sigma) of the target.",
    "study": ("Wueller, L. et al. (2026), JGR Planets 131(3), e2025JE009434, section 2.2: landing areas with slopes "
              "under 8° on the LOLA 20 m grid, and at least 100 m from steeper ground."),
    "baseline": ("NASA HLS solicitation attachment A20, Lunar Landing Site Characterization White Paper (2019): LOLA "
                 "5 m data show slopes of about 6° over a 10 m baseline."),
}

# (name, dems.json folder relative to ROOT, short label, place)
_GRIDS = [
    ("ldem_site01_5m", os.path.join("data", "dem5", "site01"), "LOLA 5 m site model Site01 (connecting ridge)"),
    ("ldem_site07_5m", os.path.join("data", "dem5", "site07"), "LOLA 5 m site model Site07 (peak near Shackleton)"),
    ("ldem_pole_20m", os.path.join("data", "dem20"), "LOLA 20 m south-pole mosaic"),
    ("ldem_80s_80m", os.path.join("data", "dem"), "LOLA 80 m south-pole mosaic"),
]

PLAIN_LIMITS = [
    "No grid here can see boulders or small craters: 5 m terrain shows nothing smaller than about 10 m, 20 m terrain "
    "nothing smaller than about 40 m, and 80 m terrain is far too coarse to see boulders at all.",
    "Outside the two 5 m site models the slope is measured over 20 m or 80 m, wider than a lander, so it usually reads "
    "lower than the ground under the lander's feet.",
    "NASA's 8° is a limit on how far the lander may lean. A lander that can level itself may cope with steeper "
    "ground; one that lands on a rock may lean more than the ground slope.",
    "The 13 touchdown points are a sample of the landing area, not every square metre of it.",
]


@lru_cache(maxsize=1)
def grids() -> tuple:
    """The grids on disk, finest first, as (name, label, PolarStereoDEM).  Missing ones are left out."""
    out = []
    for name, folder, label in _GRIDS:
        base = os.path.join(ROOT, folder)
        try:
            with open(os.path.join(base, "dems.json"), encoding="utf-8") as fh:
                cfg = json.load(fh)
            e = next(x for x in cfg["dems"] if x["name"] == name)
            path = e["path"] if os.path.isabs(e["path"]) else os.path.join(base, e["path"])
            if not os.path.exists(path) or e.get("kind") != "polar_stereo":
                continue
            z = np.load(path, mmap_mode="r")
            g = PolarStereoDEM(name=name, source="LOLA", pixel_m=float(e["pixel_m"]), x0_m=float(e["x0_m"]),
                               y0_m=float(e["y0_m"]), scale=float(e.get("scale", 1.0)), offset=float(e.get("offset", 0.0)),
                               nodata=e.get("nodata"), pole=int(e.get("pole", -1)), z=z,
                               provenance=e.get("provenance", ""))
            g.product = e.get("product", name)
            out.append((name, label, g))
        except (OSError, ValueError, KeyError, StopIteration):
            continue
    out.sort(key=lambda t: t[2].pixel_m)
    return tuple(out)


def _block(px: float) -> int:
    """Cells per side of the square the plane is fitted to: the smallest square at least LANDER_BASELINE_M wide."""
    return max(2, int(math.ceil(LANDER_BASELINE_M / px - 1e-9)) + 1)


def slope_on(g: PolarStereoDEM, lat, lon):
    """(slope in degrees, baseline in metres) on one grid; NaN where the grid does not cover the point."""
    lat = np.atleast_1d(np.asarray(lat, dtype=float))
    lon = np.atleast_1d(np.asarray(lon, dtype=float))
    px = g.pixel_m
    k = _block(px)
    x, y = g.project(lat, lon)
    col = (x - g.x0_m) / px
    row = (g.y0_m - y) / px
    if k % 2:                                   # odd: centred on the nearest cell
        r0 = np.rint(row).astype(np.int64) - k // 2
        c0 = np.rint(col).astype(np.int64) - k // 2
    else:                                       # even: the cells around the point
        r0 = np.floor(row).astype(np.int64) - (k // 2 - 1)
        c0 = np.floor(col).astype(np.int64) - (k // 2 - 1)
    ny, nx = g.z.shape
    ok = (r0 >= 0) & (c0 >= 0) & (r0 + k - 1 <= ny - 1) & (c0 + k - 1 <= nx - 1) & ((lat * g.pole) > 0)
    out = np.full(lat.shape, np.nan)
    if ok.any():
        idx = np.nonzero(ok)[0]
        off = np.arange(k)
        rr = r0[idx][:, None, None] + off[None, :, None]
        cc = c0[idx][:, None, None] + off[None, None, :]
        z = np.asarray(g.z[rr, cc], dtype=float) * g.scale + g.offset
        if g.nodata is not None:
            z[np.asarray(g.z[rr, cc]) == g.nodata] = np.nan
        d = off - (k - 1) / 2.0                 # cell offsets from the square's centre
        s2 = k * float((d ** 2).sum())
        # map distance -> ground distance: polar stereographic, true scale at the pole
        kf = 2.0 / (1.0 + np.sin(np.abs(np.deg2rad(lat[idx]))))
        gx = (z * d[None, None, :]).sum(axis=(1, 2)) / s2 / px * kf      # metres up per metre east-ish
        gy = (z * d[None, :, None]).sum(axis=(1, 2)) / s2 / px * kf
        out[idx] = np.degrees(np.arctan(np.hypot(gx, gy)))
    return out, (k - 1) * px


def slope_finest(lat, lon) -> dict:
    """Slope at each point from the finest grid that covers it, and from every grid that covers it."""
    lat = np.atleast_1d(np.asarray(lat, dtype=float))
    lon = np.atleast_1d(np.asarray(lon, dtype=float))
    best = np.full(lat.shape, np.nan)
    which = np.full(lat.shape, -1, dtype=np.int64)
    base = np.full(lat.shape, np.nan)
    every = []
    for gi, (_name, _label, g) in enumerate(grids()):
        s, b = slope_on(g, lat, lon)
        every.append((gi, s, b))
        take = np.isnan(best) & np.isfinite(s)
        best[take] = s[take]
        which[take] = gi
        base[take] = b
    return {"slope": best, "grid": which, "baseline": base, "every": every}


def _grid_info(gi: int) -> dict:
    name, label, g = grids()[gi]
    return {"name": name, "label": label, "grid_m": g.pixel_m, "baseline_m": (_block(g.pixel_m) - 1) * g.pixel_m,
            "product": getattr(g, "product", name)}


def touchdown_points(lat: float, lon: float, scatter_m: float) -> list:
    """The card's 13 touchdown points: the target, 8 on a circle of scatter_m, 4 at half that (robust.SCATTER_LAYOUT)."""
    from ..robust import SCATTER_LAYOUT, scatter_points
    pts = [("the target", float(lat), float(lon))]
    for (frac, bearing), (la, lo) in zip(SCATTER_LAYOUT, scatter_points(lat, lon, scatter_m)):
        pts.append((f"{frac * scatter_m:g} m to the {_compass(bearing)}", la, lo))
    return pts


def _compass(b: float) -> str:
    names = ["north", "north-north-east", "north-east", "east-north-east", "east", "east-south-east", "south-east",
             "south-south-east", "south", "south-south-west", "south-west", "west-south-west", "west",
             "west-north-west", "north-west", "north-north-west"]
    return names[int(round((b % 360) / 22.5)) % 16]


def _r(x: float, nd: int = 2) -> Optional[float]:
    return None if x is None or not math.isfinite(x) else round(float(x), nd)


def _fmt(x: float) -> str:
    """Degrees for a sentence: one decimal, two when one would hide which side of 5 or 8 it is on."""
    nd = 2 if min(abs(x - LIMIT_DEG), abs(x - GOAL_DEG)) < 0.05 else 1
    return f"{x:.{nd}f}°"


def site_slopes(lat: float, lon: float, scatter_m: float = DEFAULT_SCATTER_M, name: str = "") -> dict:
    """Slope and pass/fail at each of the 13 touchdown points of one site."""
    if not grids():
        return {"available": False, "reason": "no LOLA polar grid is installed on this machine"}
    pts = touchdown_points(lat, lon, scatter_m)
    la = np.array([p[1] for p in pts])
    lo = np.array([p[2] for p in pts])
    r = slope_finest(la, lo)
    rows = []
    for i, (label, a, b) in enumerate(pts):
        s = float(r["slope"][i])
        gi = int(r["grid"][i])
        row = {"point": label, "lat": round(a, 5), "lon": round(b, 5), "slope_deg": _r(s),
               "passes": bool(math.isfinite(s) and s <= LIMIT_DEG) if math.isfinite(s) else None,
               "meets_goal": bool(s <= GOAL_DEG) if math.isfinite(s) else None,
               "grid_m": None if gi < 0 else grids()[gi][2].pixel_m,
               "baseline_m": None if gi < 0 else float(r["baseline"][i]),
               "grid": None if gi < 0 else grids()[gi][1],
               "by_grid": [{"grid_m": grids()[g][2].pixel_m, "baseline_m": float(bb), "slope_deg": _r(float(sv[i]))}
                           for g, sv, bb in r["every"] if math.isfinite(sv[i])]}
        rows.append(row)
    known = [x for x in rows if x["slope_deg"] is not None]
    passing = sum(1 for x in known if x["passes"])
    goal = sum(1 for x in known if x["meets_goal"])
    steep = max(known, key=lambda x: x["slope_deg"]) if known else None
    used = sorted({int(g) for g in r["grid"] if g >= 0})
    if not known:
        verdict, word = "unknown", "Not known"
        headline = "No terrain grid on this machine covers this site, so its slope is not known."
    elif len(known) < len(rows):
        verdict, word = "unknown", "Not known"
        headline = f"Only {len(known)} of {len(rows)} touchdown points are covered by a terrain grid."
    elif passing == len(rows):
        verdict, word = "flat", "Yes"
        headline = (f"Flat enough at all {len(rows)} touchdown points: the steepest is {_fmt(steep['slope_deg'])}, "
                    f"under NASA's {LIMIT_DEG:g}° limit.")
    else:
        verdict, word = "steep", "No"
        headline = (f"Too steep at {len(rows) - passing} of {len(rows)} touchdown points: the steepest is "
                    f"{_fmt(steep['slope_deg'])} ({steep['point']}), over NASA's {LIMIT_DEG:g}° limit.")
    grid_words = ", ".join(f"{_grid_info(g)['grid_m']:g} m terrain (slope over {_grid_info(g)['baseline_m']:g} m)" for g in used)
    return {
        "available": True,
        "site": {"name": name or f"{lat:.3f}, {lon:.3f}", "lat": float(lat), "lon": float(lon)},
        "scatter_m": float(scatter_m), "limit_deg": LIMIT_DEG, "goal_deg": GOAL_DEG,
        "verdict": verdict, "word": word, "headline": headline,
        "points_total": len(rows), "points_known": len(known), "points_passing": passing, "points_meeting_goal": goal,
        "steepest": steep, "grids_used": [_grid_info(g) for g in used], "grid_words": grid_words,
        "points": rows,
        "how": ("At each touchdown point a flat plane is fitted to the terrain heights around it; the slope is how much "
                "that plane tilts. The finest grid that covers the point is used: 5 m (over a 10 m square, about a "
                "lander's width), else 20 m (over 20 m), else 80 m (over 80 m)."),
        "source": SOURCE, "limits": PLAIN_LIMITS,
    }


# ---------------- the map layer ----------------

_map_lock = threading.Lock()
_map_cache: dict = {}


def map_point_slopes() -> Optional[dict]:
    """For every map point whose 12 extra touchdown points are stored: the steepest slope of its 13 points.

    It does not depend on the date, so it is worked out once."""
    from .. import field, scatterfield
    fld, store = field.load(), scatterfield.load()
    if fld is None or store is None or not grids():
        return None
    key = (fld["meta"].get("dem_fingerprint"), len(store["idx"]))
    with _map_lock:
        if _map_cache.get("key") == key:
            return _map_cache["val"]
    idx = np.asarray(store["idx"], dtype=np.int64)
    la = np.concatenate([np.asarray(fld["lat"])[idx][:, None], np.asarray(store["lat"])], axis=1)
    lo = np.concatenate([np.asarray(fld["lon"])[idx][:, None], np.asarray(store["lon"])], axis=1)
    r = slope_finest(la.ravel(), lo.ravel())
    s = r["slope"].reshape(la.shape)
    g = r["grid"].reshape(la.shape)
    n_all = len(fld["lat"])
    steepest = np.full(n_all, np.nan)
    steepest[idx] = np.where(np.isnan(s).any(axis=1), np.nan, s.max(axis=1))
    finest = np.full(n_all, -1, dtype=np.int64)
    finest[idx] = np.where((g < 0).any(axis=1), -1, g.min(axis=1))
    coarsest = np.full(n_all, -1, dtype=np.int64)
    coarsest[idx] = g.max(axis=1)
    val = {"steepest": steepest, "finest_grid": finest, "coarsest_grid": coarsest, "stored": idx,
           "scatter_m": float(store["meta"].get("scatter_m", DEFAULT_SCATTER_M))}
    with _map_lock:
        _map_cache.update(key=key, val=val)
    return val


class SafetyMapRequest(BaseModel):
    """The same body the page sends to /api/robust-map, plus how many days of slip count as slip-tolerant."""
    start: str
    n_dates: int = Field(default=60, ge=2, le=90)
    need_sun_h: float = Field(default=240.0, ge=0, le=24 * 120)
    need_earth_h: float = Field(default=100.0, ge=0, le=24 * 120)
    window_days: float = Field(default=14.0, gt=0, le=120)
    sun_at_touchdown: bool = True
    earth_at_touchdown: bool = True
    mask_deg: float = Field(default=0.0, ge=0, le=30)
    min_sun_el: float = Field(default=-90.0, ge=-90, le=90)
    min_earth_el: float = Field(default=-90.0, ge=-90, le=90)
    terrain: bool = True
    mast_m: float = Field(default=2.0, ge=0, le=500)
    min_sun_fraction: float = Field(default=0.5, ge=0, le=1)
    earth_margin_deg: float = Field(default=0.0, ge=0, le=20)
    earth_stations: bool = False
    min_slip_days: int = Field(default=DEFAULT_MIN_SLIP_DAYS, ge=0, le=60)


CODES = {
    "2": "slip-tolerant and flat enough",
    "1": "slip-tolerant but too steep",
    "0": "not slip-tolerant",
    "-1": "not slip-tolerant: the planned date already fails here",
    "-2": "not checked: the 12 extra touchdown points are not stored for this map point",
}


def map_layer(req: SafetyMapRequest) -> dict:
    from .. import field, scatterfield
    from ..ephem import parse_utc
    from ..metrics import Criteria
    try:
        parse_utc(req.start)
    except (ValueError, TypeError):
        raise HTTPException(422, "start is not a date and time the server can read")
    fld = field.load()
    if fld is None:
        return {"available": False, "reason": "the slip-margin map has not been built on this installation"}
    meta = (scatterfield.load() or {}).get("meta") or fld["meta"]
    if meta.get("mast_m") is not None and abs(req.mast_m - float(meta["mast_m"])) > 1e-6:
        return {"available": False, "reason": f"the map is stored for an observer {float(meta['mast_m']):g} m above the "
                                              f"ground only (choose {float(meta['mast_m']):g} m to see it)"}
    crit = Criteria(req.min_sun_fraction, req.min_sun_el, req.min_earth_el, req.earth_margin_deg, req.earth_stations)
    r = scatterfield.robust_margin(req.start, req.n_dates, req.window_days, crit, req.mask_deg, req.need_sun_h,
                                   req.need_earth_h, req.sun_at_touchdown, req.earth_at_touchdown)
    if not r or not r.get("available"):
        return {"available": False, "reason": (r or {}).get("reason", "the scatter-checked map is not available")}
    sl = map_point_slopes()
    if sl is None:
        return {"available": False, "reason": "no terrain grid for the slope is installed"}
    robust = np.asarray(r["robust"], dtype=np.int64)
    steep = sl["steepest"]
    tolerant = robust >= req.min_slip_days
    flat = np.isfinite(steep) & (steep <= LIMIT_DEG)
    code = np.full(len(robust), 0, dtype=np.int64)
    code[robust == scatterfield.NOT_COLOURED] = -1
    code[robust == scatterfield.NOT_CHECKED] = -2
    code[tolerant & flat] = 2
    code[tolerant & ~flat] = 1
    # a tolerant point with no slope (never expected: every stored point is inside the 20 m grid) counts as not checked
    code[tolerant & ~np.isfinite(steep)] = -2
    counts = {CODES[str(c)]: int((code == c).sum()) for c in (2, 1, 0, -1, -2)}
    tol = int(tolerant.sum())
    used = sorted({int(x) for x in np.unique(sl["finest_grid"][tolerant]) if x >= 0} |
                  {int(x) for x in np.unique(sl["coarsest_grid"][tolerant]) if x >= 0})
    m = fld["meta"]
    summary = (f"{counts[CODES['2']]} of the {tol} map points that keep at least {req.min_slip_days} day"
               f"{'' if req.min_slip_days == 1 else 's'} of slip at all 13 touchdown points are also flat enough "
               f"(under {LIMIT_DEG:g}°) at all 13; {counts[CODES['1']]} are too steep at one or more of them.")
    return {
        "available": True, "n": m["n"], "half_km": m["half_km"], "step_m": m["step_m"],
        "start_utc": r["start_utc"], "dates": r["dates"], "min_slip_days": req.min_slip_days,
        "limit_deg": LIMIT_DEG, "scatter_m": sl["scatter_m"],
        "codes": CODES, "counts": counts, "slip_tolerant": tol, "summary": summary,
        "grids_used": [_grid_info(g) for g in used],
        "layer": [int(x) for x in code],
        "steepest_deg": [None if not math.isfinite(x) else round(float(x), 2) for x in steep],
        "source": SOURCE, "limits": PLAIN_LIMITS,
    }


# ---------------- the router ----------------

router = APIRouter(tags=["add-on: flat enough to land"])


@router.get("/api/addons/safety/site")
def api_site(id: Optional[str] = Query(default=None, description="a site id from /api/sites"),
             lat: Optional[float] = Query(default=None, ge=-90, le=90),
             lon: Optional[float] = Query(default=None, ge=-360, le=360),
             name: str = Query(default="", max_length=200),
             scatter_m: float = Query(default=DEFAULT_SCATTER_M, ge=0, le=500)):
    """Slope at each of the 13 touchdown points of a site, the grid used, and pass or fail against NASA's 8 deg."""
    if id:
        from ..sites import SITES
        hit = next((s for s in SITES if s["id"] == id), None)
        if hit is None:
            raise HTTPException(404, f"no site with id {id!r}")
        lat, lon, name = hit["lat"], hit["lon"], name or hit["name"]
    if lat is None or lon is None:
        raise HTTPException(422, "give a site id, or lat and lon")
    lon = ((float(lon) + 180.0) % 360.0) - 180.0
    return site_slopes(float(lat), lon, scatter_m, name)


@router.post("/api/addons/safety/map-layer")
def api_map_layer(req: SafetyMapRequest):
    """Each slip-margin map point: slip-tolerant and flat enough, slip-tolerant but too steep, or not slip-tolerant."""
    from .. import load as lanes

    def work():
        try:
            return map_layer(req)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    return lanes.run(work)


@router.get("/api/addons/safety/about")
def api_about():
    """The limit, its source, the grids on this machine and what the check cannot tell."""
    return {"limit_deg": LIMIT_DEG, "goal_deg": GOAL_DEG, "lander_baseline_m": LANDER_BASELINE_M,
            "grids": [_grid_info(i) for i in range(len(grids()))], "source": SOURCE, "limits": PLAIN_LIMITS}
