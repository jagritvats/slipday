"""Add-on: slope guide for the whole close-up of the pole.

For every point of the slip-margin map (120 x 120 points, one every 500 m, 60 km across round the pole: the same
points as ``data/field/pole_points.npz``), the slope at the card's 13 touchdown points (the target, 8 points at
100 m, 4 at 50 m: ``robust.SCATTER_LAYOUT``), each on the finest LOLA grid that covers it (5 m site models, then
the 20 m crop, then the 80 m mosaic), measured exactly as the "Flat enough to land?" card does
(``safety.slope_finest``: a plane fitted over 10 m on 5 m terrain, 20 m on 20 m terrain, 80 m on 80 m terrain).

Unlike ``POST /api/addons/safety/map-layer`` it covers every map point (not only the 2,407 whose slip skylines
are stored) and does not depend on the date or the need.  It is worked out once:
``python -m slipday.addons.slopemap`` writes ``data/addons/safety/slopemap.npz`` and ``slopemap.json``.  If the
stored file is missing or was made from other inputs, the server works it out on first request (a few seconds)
and keeps it in memory; it never writes at run time.

Classes, the same rule as the card (pass is "8 degrees or less", goal is "5 degrees or less"):
  2  flat: all 13 touchdown points at 5 deg or less (NASA's goal)
  1  flat enough: all 13 at 8 deg or less, at least one over 5 deg
  0  too steep: at least one of the 13 over 8 deg
 -1  not known: a touchdown point is outside every grid
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from typing import Optional

import numpy as np
from fastapi import APIRouter

from . import safety

ROOT = safety.ROOT
OUT_DIR = os.path.join(ROOT, "data", "addons", "safety")
NPZ = os.path.join(OUT_DIR, "slopemap.npz")
META = os.path.join(OUT_DIR, "slopemap.json")
FIELD_DIR = os.environ.get("SLIPDAY_FIELD_DIR", os.path.join(ROOT, "data", "field"))
SCATTER_M = safety.DEFAULT_SCATTER_M          # HLS-R-0021: 100 m; the card's default
VERSION = 1

CLASSES = {
    "2": "flat: all 13 touchdown points at 5° or less (NASA's goal)",
    "1": "flat enough: all 13 at 8° or less, at least one over 5°",
    "0": "too steep: at least one of the 13 over 8°",
    "-1": "not known: a touchdown point is outside every terrain grid",
}

_lock = threading.Lock()
_mem: dict = {}


# ---------------- the points ----------------

def map_points() -> Optional[dict]:
    """The slip-margin map's points (lat, lon, n, half_km, step_m), read from the stored field, or None."""
    try:
        with open(os.path.join(FIELD_DIR, "pole_field.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
        pts = np.load(os.path.join(FIELD_DIR, "pole_points.npz"))
        lat, lon = np.asarray(pts["lat"], dtype=float), np.asarray(pts["lon"], dtype=float)
    except (OSError, ValueError, KeyError):
        return None
    n = int(meta["n"])
    if len(lat) != n * n:
        return None
    return {"lat": lat, "lon": lon, "n": n, "half_km": float(meta["half_km"]), "step_m": float(meta["step_m"])}


def _inputs_key(pts: dict) -> str:
    """What the stored answer depends on: the map points, the grids on disk, the scatter, the method version."""
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(pts["lat"]).tobytes())
    h.update(np.ascontiguousarray(pts["lon"]).tobytes())
    for name, _label, g in safety.grids():
        h.update(f"{name}|{g.pixel_m}|{g.x0_m}|{g.y0_m}|{g.z.shape}|{g.z.dtype}|{g.scale}|{g.offset};".encode())
    h.update(f"scatter={SCATTER_M};limit={safety.LIMIT_DEG};goal={safety.GOAL_DEG};"
             f"baseline={safety.LANDER_BASELINE_M};v={VERSION}".encode())
    return h.hexdigest()[:24]


# ---------------- the computation ----------------

def compute(pts: dict) -> dict:
    """Slope at the 13 touchdown points of every map point, finest grid first."""
    from ..robust import scatter_points
    lat, lon = pts["lat"], pts["lon"]
    npt = len(lat)
    la = np.empty((npt, 13))
    lo = np.empty((npt, 13))
    la[:, 0], lo[:, 0] = lat, lon
    for i in range(npt):
        sp = scatter_points(float(lat[i]), float(lon[i]), SCATTER_M)
        la[i, 1:] = [p[0] for p in sp]
        lo[i, 1:] = [p[1] for p in sp]
    r = safety.slope_finest(la.ravel(), lo.ravel())
    s = r["slope"].reshape(la.shape)
    gi = r["grid"].reshape(la.shape)
    px = np.array([g.pixel_m for _n, _l, g in safety.grids()] + [np.nan])     # index -1 -> NaN
    gm = px[gi]
    known = np.isfinite(s).all(axis=1)
    steepest = np.where(known, np.nanmax(np.where(np.isfinite(s), s, -np.inf), axis=1), np.nan)
    passing = (s <= safety.LIMIT_DEG).sum(axis=1)
    goal = (s <= safety.GOAL_DEG).sum(axis=1)
    cls = np.full(npt, -1, dtype=np.int8)
    cls[known] = 0
    cls[known & (passing == 13)] = 1
    cls[known & (goal == 13)] = 2
    coarsest = np.where(known, np.nanmax(np.where(np.isfinite(gm), gm, -np.inf), axis=1), np.nan)
    return {"steepest_deg": steepest, "target_deg": s[:, 0], "points_passing": passing.astype(np.int8),
            "points_meeting_goal": goal.astype(np.int8), "grid_m": gm[:, 0], "coarsest_grid_m": coarsest,
            "cls": cls}


def build() -> dict:
    """Work it out and store it under data/addons/safety/.  Returns the stored meta."""
    pts = map_points()
    if pts is None:
        raise SystemExit("the slip-margin map's points (data/field) are not built on this installation")
    if not safety.grids():
        raise SystemExit("no LOLA polar grid is installed")
    t0 = time.time()
    val = compute(pts)
    os.makedirs(OUT_DIR, exist_ok=True)
    np.savez_compressed(NPZ, **val)
    meta = {"version": VERSION, "inputs_key": _inputs_key(pts), "n": pts["n"], "half_km": pts["half_km"],
            "step_m": pts["step_m"], "scatter_m": SCATTER_M, "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "seconds": round(time.time() - t0, 1),
            "grids": [safety._grid_info(i) for i in range(len(safety.grids()))]}
    with open(META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    with open(NPZ, "rb") as fh:
        meta["npz_sha256"] = hashlib.sha256(fh.read()).hexdigest()
    with open(META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    with _lock:
        _mem.clear()
    return meta


def load() -> Optional[dict]:
    """The slope guide: from the stored file when it matches the inputs, else worked out now and kept in memory."""
    pts = map_points()
    if pts is None or not safety.grids():
        return None
    key = _inputs_key(pts)
    with _lock:
        if _mem.get("key") == key:
            return _mem["val"]
    val, stored = None, False
    try:
        with open(META, encoding="utf-8") as fh:
            meta = json.load(fh)
        if meta.get("inputs_key") == key:
            with np.load(NPZ) as z:
                val = {k: z[k] for k in z.files}
            stored = True
    except (OSError, ValueError, KeyError):
        val = None
    if val is None:
        val = compute(pts)
    out = {"val": val, "pts": pts, "stored": stored}
    with _lock:
        _mem.update(key=key, val=out)
    return out


# ---------------- the answer ----------------

def _num(a, nd=2):
    return [None if not math.isfinite(float(x)) else round(float(x), nd) for x in a]


def answer() -> dict:
    d = load()
    if d is None:
        return {"available": False, "reason": "the slip-margin map's points or the LOLA polar grids are not installed"}
    v, p = d["val"], d["pts"]
    cls = np.asarray(v["cls"])
    gm = np.asarray(v["grid_m"], dtype=float)
    cg = np.asarray(v["coarsest_grid_m"], dtype=float)
    used = sorted({float(x) for x in np.unique(np.concatenate([gm, cg])) if math.isfinite(x)})
    by_grid = {f"{g:g}": int((cg == g).sum()) for g in used}
    counts = {CLASSES[str(c)]: int((cls == c).sum()) for c in (2, 1, 0, -1)}
    total = len(cls)
    known = int((cls >= 0).sum())
    return {
        "available": True, "stored": d["stored"],
        "n": p["n"], "half_km": p["half_km"], "step_m": p["step_m"], "points": total, "points_known": known,
        "order": ("row by row, row 0 at the top of the close-up (+y, towards longitude 0), column 0 at the left "
                  "(-x, towards 90° W); the same points and order as /api/slipmap's layers"),
        "scatter_m": SCATTER_M, "limit_deg": safety.LIMIT_DEG, "goal_deg": safety.GOAL_DEG,
        "classes": CLASSES, "counts": counts,
        "points_by_coarsest_grid_m": by_grid,
        "grids": [g for g in (safety._grid_info(i) for i in range(len(safety.grids()))) if g["grid_m"] in used],
        "class": [int(x) for x in cls],
        "steepest_deg": _num(v["steepest_deg"]),
        "target_deg": _num(v["target_deg"]),
        "points_passing": [int(x) for x in v["points_passing"]],
        "points_meeting_goal": [int(x) for x in v["points_meeting_goal"]],
        "grid_m": _num(gm, 0),
        "coarsest_grid_m": _num(cg, 0),
        "summary": (f"Of the {total:,} map points, {counts[CLASSES['2']]:,} are flat (all 13 touchdown points at "
                    f"{safety.GOAL_DEG:g}° or less), {counts[CLASSES['1']]:,} flat enough (all 13 at "
                    f"{safety.LIMIT_DEG:g}° or less) and {counts[CLASSES['0']]:,} too steep at one or more."),
        "how": ("At each map point the slope is measured at the 13 touchdown points the site card uses (the "
                "target, 8 points 100 m away and 4 points 50 m away), each on the finest terrain that covers it: "
                "5 m (slope over 10 m, about a lander's width), else 20 m (over 20 m), else 80 m (over 80 m). "
                "grid_m is the grid under the map point itself; coarsest_grid_m the coarsest used among the 13."),
        "source": safety.SOURCE, "limits": safety.PLAIN_LIMITS + [
            "One map point every 500 m: a flat patch smaller than that, or between two points, can be missed."],
    }


router = APIRouter(tags=["add-on: slope guide for the close-up"])


@router.get("/api/addons/slopemap")
def api_slopemap():
    """Slope at the 13 touchdown points of every close-up map point (finest grid each), and its class."""
    from .. import load as lanes
    return lanes.run(answer)


if __name__ == "__main__":
    m = build()
    a = answer()
    print(json.dumps({k: m[k] for k in ("inputs_key", "seconds", "npz_sha256")}, indent=1))
    print(a["summary"], a["points_by_coarsest_grid_m"], "known", a["points_known"], "of", a["points"])
