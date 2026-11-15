"""Add-on: the nearest precomputed skyline, served at once while the exact one is worked out.

A click on the map asks ``/api/why`` for the skyline at that exact point: 720 directions ray-cast over LOLA
terrain, 5 to 10 s. Skylines are already stored for the map's grid points (same ray-march, same terrain stack,
same 2 m mast):

    data/field/pole_el_i16.npy        close-up, 120 x 120 points 500 m apart (60 km square round the pole)
    data/field/scatter_el_i16.npy     12 touchdown points 50 m and 100 m round 2407 of those
    data/addons/skyfast/fullmap_el_i16.npy   whole map to 80 deg S, 304 x 304 points 2 km apart
                                      (gathered from data/addons/fullmap/chunks_2000m by scripts/addons/build_skyfast.py)

``GET /api/addons/skyfast?lat=..&lon=..`` returns the skyline of the nearest of all of them, in the shape
``/api/why`` uses for ``skyline`` (az_deg, el_deg, dist_km, site_height_m, mast_m), so the page can draw it with the
same code and replace it when the exact answer arrives. Arrays are memory-mapped; one request reads one row.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from .. import field

router = APIRouter()

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FULL_DIR = os.path.join(ROOT, "data", "addons", "skyfast")
MOON_RADIUS_M = 1737400.0
LABEL = "approximate: nearest precomputed point"
MAX_DIST_M = 3000.0         # farther than this from every stored point: outside the stored maps

_lock = threading.Lock()
_state: dict = {"sets": None}


def _xy(lat, lon):
    """South polar stereographic x, y (m); only used to find the nearest point."""
    la, lo = np.deg2rad(np.asarray(lat, dtype=np.float64)), np.deg2rad(np.asarray(lon, dtype=np.float64))
    r = 2.0 * MOON_RADIUS_M * np.tan((np.pi / 2.0 + la) / 2.0)
    return r * np.sin(lo), r * np.cos(lo)


def _sets() -> list:
    with _lock:
        if _state["sets"] is not None:
            return _state["sets"]
        sets = []
        fd = field.FIELD_DIR
        try:
            meta = json.load(open(os.path.join(fd, "pole_field.json")))
            pts = np.load(os.path.join(fd, "pole_points.npz"))
            el = np.load(os.path.join(fd, "pole_el_i16.npy"), mmap_mode="r")
            sets.append({"name": "close-up", "step_m": float(meta["step_m"]), "lat": np.asarray(pts["lat"]),
                         "lon": np.asarray(pts["lon"]), "h": np.asarray(pts["height_m"]), "el": el, "row": None,
                         "mast_m": float(meta["mast_m"]), "scale": float(meta["el_scale_deg"]),
                         "text": "close-up map, 500 m grid"})
        except (OSError, ValueError, KeyError):
            pass
        try:
            meta = json.load(open(os.path.join(fd, "scatter_field.json")))
            pts = np.load(os.path.join(fd, "scatter_points.npz"))
            el = np.load(os.path.join(fd, "scatter_el_i16.npy"), mmap_mode="r")
            m = el.shape[1]
            sets.append({"name": "close-up scatter", "step_m": float(meta["scatter_m"]),
                         "lat": np.asarray(pts["lat"]).ravel(), "lon": np.asarray(pts["lon"]).ravel(), "h": None,
                         "el": el, "row": lambda i, m=m: (i // m, i % m), "mast_m": float(meta["mast_m"]),
                         "scale": float(meta["el_scale_deg"]),
                         "text": "landing-scatter point 50 m or 100 m round a close-up grid point"})
        except (OSError, ValueError, KeyError):
            pass
        try:
            meta = json.load(open(os.path.join(FULL_DIR, "fullmap.json")))
            pts = np.load(os.path.join(FULL_DIR, "fullmap_points.npz"))
            el = np.load(os.path.join(FULL_DIR, "fullmap_el_i16.npy"), mmap_mode="r")
            have = np.asarray(pts["have"])
            lat = np.where(have, pts["lat"], np.nan)
            sets.append({"name": "whole map", "step_m": float(meta["step_m"]), "lat": lat, "lon": np.asarray(pts["lon"]),
                         "h": np.asarray(pts["height_m"]), "el": el, "row": None, "mast_m": float(meta["mast_m"]),
                         "scale": float(meta["el_scale_deg"]), "text": "whole-map 2 km grid (South pole to 80 deg S)"})
        except (OSError, ValueError, KeyError):
            pass
        for s in sets:
            x, y = _xy(s["lat"], s["lon"])
            bad = ~np.isfinite(x)
            s["x"], s["y"] = np.where(bad, 1e12, x), np.where(bad, 1e12, y)
        _state["sets"] = sets
        return sets


def reload() -> None:
    with _lock:
        _state["sets"] = None


def _gc_m(la1, lo1, la2, lo2) -> float:
    la1, lo1, la2, lo2 = map(np.deg2rad, (la1, lo1, la2, lo2))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return float(2.0 * MOON_RADIUS_M * np.arcsin(min(1.0, np.sqrt(a))))


def nearest(lat: float, lon: float) -> Optional[dict]:
    """The nearest stored skyline to (lat, lon), as ``/api/why`` shapes ``skyline``, or None if none is stored."""
    sets = _sets()
    if not sets:
        return None
    x, y = _xy(lat, lon)
    best = None
    for s in sets:
        d2 = (s["x"] - x) ** 2 + (s["y"] - y) ** 2
        i = int(np.argmin(d2))
        if best is None or d2[i] < best[0]:
            best = (float(d2[i]), s, i)
    _, s, i = best
    plat, plon = float(s["lat"][i]), float(s["lon"][i])
    row = s["el"][s["row"](i)] if s["row"] else s["el"][i]
    el = np.asarray(row, dtype=np.float64) * s["scale"]
    n = len(el)
    az = np.arange(n) * (360.0 / n)
    h = None if s["h"] is None else float(s["h"][i])
    return {
        "approximate": True, "label": LABEL,
        "clicked": {"lat": float(lat), "lon": float(lon)},
        "point": {"lat": round(plat, 6), "lon": round(((plon + 180.0) % 360.0) - 180.0, 6)},
        "distance_m": round(_gc_m(lat, lon, plat, plon), 1),
        "grid": {"name": s["name"], "step_m": s["step_m"], "text": s["text"]},
        "skyline": {"az_deg": [round(float(v), 1) for v in az], "el_deg": [round(float(v), 3) for v in el],
                    "dist_km": [None] * n,
                    "site_height_m": None if h is None or not np.isfinite(h) else round(h, 1),
                    "mast_m": s["mast_m"]},
        "note": "dist_km is not stored for precomputed skylines (null in every direction); the exact /api/why skyline has it",
    }


@router.get("/api/addons/skyfast")
def api_skyfast(lat: float = Query(..., ge=-90.0, le=90.0), lon: float = Query(..., ge=-360.0, le=360.0)):
    """Nearest precomputed skyline, for drawing at once while ``/api/why`` works out the exact one."""
    out = nearest(lat, lon)
    if out is None:
        raise HTTPException(503, "no precomputed skylines are installed")
    if out["distance_m"] > MAX_DIST_M:
        raise HTTPException(404, f"no precomputed skyline within {MAX_DIST_M:.0f} m (nearest {out['distance_m']:.0f} m); "
                                 "the stored maps cover the South pole to 80 deg S")
    return out
