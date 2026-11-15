"""Add-on: surface temperature measured by NASA's Diviner Lunar Radiometer (LRO).

Two Diviner products from the PDS Geosciences node (no login; URLs and sha256 in ADDON_thermal.md):

  1. Polar Resource Product, south (LRO-L-DLRE-5-PRP-V2.0, DLRE_PRP_SOUTH.TAB, UCLA Diviner team, 2018).
     A triangle mesh of the south polar region (~0.5 km spacing) with the multi-year average and maximum
     bolometric temperature per triangle.  We keep the points poleward of 84 S (prp_south_84.npz).
  2. Gridded Data Record level 3, night-time average bolometric temperature, south polar stereographic,
     240 m/pixel (LRO-L-DLRE-5-GDR-V1.0, dgdr_tbol_avg_pols_YYYYMMDDn_240_img), one night-time map per lunar month.
     We take the lowest value per pixel over the 2010 and 2016 night maps (25 maps) ("coldest night") and keep a crop of
     +-216 km around the pole (night_min_240m.npy).

Cold trap: ground whose measured maximum temperature stays below 110 K (water ice is stable there over
geological time).  "In" = the nearest PRP triangle; "near" = any PRP triangle within NEAR_KM.

    GET /api/addons/thermal?lat=..&lon=..
"""
from __future__ import annotations

import math
import os
from functools import lru_cache

import numpy as np
from fastapi import APIRouter, HTTPException, Query

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT, "data", "addons", "thermal")
R_KM = 1737.4
COLD_TRAP_K = 110.0
NEAR_KM = 2.0
SITE_KM = 0.36           # radius used for the "at the site" PRP numbers (nearest triangles)
GDR_SCALE_KM = 0.240
GDR_OFFSET = 1905.5      # LINE/SAMPLE_PROJECTION_OFFSET of the full 3812 x 3812 map
GDR_CROP0 = 1904 - 900   # first full-map index kept in the crop (thermal_build.py CROP = 900)
GDR_DN = 0.02
MISSING = -32768

PRP_URL = ("https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/"
           "extras/prp/dlre_prp_south.zip")
GDR_URL = ("https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/"
           "data_derived_gdr_l3/{2010,2016}/polar/img/")

SOURCE = {
    "instrument": "Diviner Lunar Radiometer Experiment, Lunar Reconnaissance Orbiter (NASA)",
    "measured_by": "Diviner",
    "products": [
        {"id": "LRO-L-DLRE-5-PRP-V2.0 DLRE_PRP_SOUTH", "use": "maximum and average temperature",
         "url": PRP_URL},
        {"id": "LRO-L-DLRE-5-GDR-V1.0 dgdr_tbol_avg_pols_{2010,2016}*n_240_img", "use": "coldest night (2010 and 2016 night maps)",
         "url": GDR_URL},
    ],
    "archive": "NASA Planetary Data System, Geosciences Node",
}

router = APIRouter()


def _ps_xy(lat_deg: np.ndarray | float, lon_deg: np.ndarray | float):
    """South polar stereographic x, y in km (PDS convention, centre longitude 0)."""
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    r = 2.0 * R_KM * np.tan(np.pi / 4.0 + lat / 2.0)
    return r * np.sin(lon), r * np.cos(lon)


@lru_cache(maxsize=1)
def _prp():
    path = os.path.join(DATA_DIR, "prp_south_84.npz")
    if not os.path.exists(path):
        return None
    from scipy.spatial import cKDTree
    z = np.load(path)
    x, y = _ps_xy(z["lat"].astype(np.float64), z["lon"].astype(np.float64))
    return cKDTree(np.column_stack([x, y])), z["temp_max"], z["temp_avg"]


@lru_cache(maxsize=1)
def _night():
    path = os.path.join(DATA_DIR, "night_min_240m.npy")
    if not os.path.exists(path):
        return None
    cpath = os.path.join(DATA_DIR, "night_count_240m.npy")
    cnt = np.load(cpath) if os.path.exists(cpath) else None
    return np.load(path), cnt


def gdr_index(lat: float, lon: float):
    """Row, column in the cropped night grid (0-based)."""
    x, y = _ps_xy(lat, lon)
    col = GDR_OFFSET + float(x) / GDR_SCALE_KM
    row = GDR_OFFSET - float(y) / GDR_SCALE_KM
    return int(math.floor(row)) - GDR_CROP0 + 0, int(math.floor(col)) - GDR_CROP0 + 0


def thermal_at(lat: float, lon: float) -> dict:
    prp = _prp()
    night = _night()
    if prp is None and night is None:
        raise FileNotFoundError("Diviner data not installed under data/addons/thermal")
    out: dict = {"lat": lat, "lon": lon, "measured_by": "Diviner", "units": "K",
                 "cold_trap_threshold_k": COLD_TRAP_K}
    x, y = _ps_xy(lat, lon)
    if prp is not None:
        tree, tmax, tavg = prp
        d, i = tree.query([float(x), float(y)])
        if d > 1.0:
            out["max_k"] = out["avg_k"] = None
            out["note"] = "outside the Diviner polar product kept here (poleward of 84 S)"
        else:
            idx = tree.query_ball_point([float(x), float(y)], SITE_KM) or [int(i)]
            out["max_k"] = round(float(np.max(tmax[idx])), 1)
            out["avg_k"] = round(float(np.mean(tavg[idx])), 1)
            near = tree.query_ball_point([float(x), float(y)], NEAR_KM)
            cold = [j for j in near if tmax[j] < COLD_TRAP_K]
            in_trap = bool(tmax[i] < COLD_TRAP_K)
            out["cold_trap"] = {
                "in": in_trap,
                "near": bool(cold),
                "nearest_km": (round(float(min(math.hypot(tree.data[j][0] - x, tree.data[j][1] - y)
                                             for j in cold)), 2) if cold else None),
                "within_km": NEAR_KM,
                "share_within": round(len(cold) / max(1, len(near)), 3),
                "label": ("in a cold trap" if in_trap else
                          f"near a cold trap (within {NEAR_KM:g} km)" if cold else "no cold trap nearby"),
            }
    if night is not None:
        grid, cnt = night
        r, c = gdr_index(lat, lon)
        if 0 <= r < grid.shape[0] and 0 <= c < grid.shape[1]:
            r0, r1, c0, c1 = max(0, r - 1), min(grid.shape[0], r + 2), max(0, c - 1), min(grid.shape[1], c + 2)
            win = grid[r0:r1, c0:c1]
            ok = win[win != MISSING]
            out["min_k"] = round(float(ok.min()) * GDR_DN, 1) if ok.size else None
            out["coldest_night_k"] = round(float(grid[r, c]) * GDR_DN, 1) if grid[r, c] != MISSING else out["min_k"]
            out["night_maps"] = int(cnt[r, c]) if cnt is not None else None
        else:
            out["min_k"] = out["coldest_night_k"] = None
            out.setdefault("note", "outside the night-map crop kept here (about 83 S to the pole)")
    out["source"] = SOURCE
    return out


@router.get("/api/addons/thermal")
def api_thermal(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-360, le=360)):
    if lat > -80:
        raise HTTPException(422, "Diviner polar products here cover the south pole only (lat <= -80)")
    lon = ((lon + 180.0) % 360.0) - 180.0
    try:
        return thermal_at(lat, lon)
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc))
