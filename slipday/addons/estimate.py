"""Add-on: a learned instant estimate of the slip margin at any point of the map.

The full check for a clicked point traces the terrain skyline (10 to 40 s). This add-on gives a first answer in a few
milliseconds from cheap terrain numbers read straight from the 80 m LOLA mosaic (height, local relief, slope,
distance to the pole, and coarse skyline heights in 16 directions), fed to a small model trained off line on the
92,416 points of the whole-map layer (``scripts/addons/train_estimate.py``).

It is valid for the page's opening plan only (landing 18 Nov 2026, 60 landing dates, 240 sunlit hours and 100 hours
of Earth contact in the first 14 days), because that is the plan its training answers were worked out for.

The server only reads ``data/addons/estimate/``; it never writes. The 80 m mosaic is memory-mapped, never copied.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Optional

import numpy as np
from fastapi import APIRouter, Query

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.environ.get("SLIPDAY_ESTIMATE_DIR", os.path.join(ROOT, "data", "addons", "estimate"))
DEM_PATH = os.path.join(ROOT, "data", "dem", "ldem_80s_80m_f32.npy")
MOON_R = 1737400.0
PIX = 80.0
X0, Y0 = -303960.0, 303960.0        # top-left corner of the 80 m mosaic (polar stereographic, metres)
LABEL = "a learned estimate; the full check follows"

N_DIR = 16
DIST_M = np.array([400, 800, 1600, 3200, 6400, 12800, 25600, 51200, 100000], dtype=np.float64)
OFFS_M = np.array([1000.0, 5000.0])  # radii for local relief and slope context
MAST_M = 2.0

_dem_lock = threading.Lock()
_dem: dict = {}


def dem() -> np.ndarray:
    """The 80 m mosaic, memory-mapped (read-only)."""
    with _dem_lock:
        if "a" not in _dem:
            _dem["a"] = np.load(DEM_PATH, mmap_mode="r")
        return _dem["a"]


def project(lat, lon):
    """South polar stereographic (true scale at the pole), x toward 90 E, y toward longitude 0."""
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    r = 2.0 * MOON_R * np.tan(np.deg2rad(90.0 + lat) / 2.0)
    return r * np.sin(np.deg2rad(lon)), r * np.cos(np.deg2rad(lon))


def _sample(a: np.ndarray, x, y) -> np.ndarray:
    """Nearest-pixel height at map coordinates; points off the mosaic are clamped to its edge."""
    n = a.shape[0]
    col = np.clip(np.floor((np.asarray(x) - X0) / PIX).astype(np.int64), 0, a.shape[1] - 1)
    row = np.clip(np.floor((Y0 - np.asarray(y)) / PIX).astype(np.int64), 0, n - 1)
    flat = row * a.shape[1] + col
    order = np.argsort(flat, axis=None)                 # sorted reads are kinder to the memory map
    out = np.empty(flat.size, dtype=np.float32)
    out[order] = a.reshape(-1)[flat.ravel()[order]]
    return out.reshape(np.shape(flat))


FEATURE_NAMES = (["x_km", "y_km", "pole_km", "height_m", "slope_deg"]
                 + [f"relief_{int(r / 1000)}km" for r in OFFS_M] + [f"above_mean_{int(r / 1000)}km" for r in OFFS_M]
                 + [f"sky_{int(round(d * 360 / N_DIR))}deg" for d in range(N_DIR)]
                 + ["sky_mean", "sky_max", "sky_min", "sky_toward_earth"])


def features(x, y, a: Optional[np.ndarray] = None) -> np.ndarray:
    """Cheap terrain features for points at map coordinates x, y (metres). Returns (n, len(FEATURE_NAMES))."""
    a = dem() if a is None else a
    x = np.atleast_1d(np.asarray(x, dtype=np.float64))
    y = np.atleast_1d(np.asarray(y, dtype=np.float64))
    h0 = _sample(a, x, y).astype(np.float64)
    # slope from the four neighbours one pixel away
    hx1, hx0 = _sample(a, x + PIX, y), _sample(a, x - PIX, y)
    hy1, hy0 = _sample(a, x, y + PIX), _sample(a, x, y - PIX)
    slope = np.rad2deg(np.arctan(np.hypot((hx1 - hx0) / (2 * PIX), (hy1 - hy0) / (2 * PIX))))
    cols = [x / 1000.0, y / 1000.0, np.hypot(x, y) / 1000.0, h0, slope]
    # local relief and position against the surroundings: a 9 x 9 sample ring per radius
    relief, above = [], []
    g = np.linspace(-1.0, 1.0, 9)
    gx, gy = np.meshgrid(g, g)
    for r in OFFS_M:
        hs = _sample(a, x[:, None] + r * gx.ravel()[None, :], y[:, None] + r * gy.ravel()[None, :])
        relief.append(hs.max(axis=1) - hs.min(axis=1))
        above.append(h0 - hs.mean(axis=1))
    cols += relief + above
    # coarse skyline: highest elevation angle (deg) along 16 map directions, 9 distances out to 100 km
    az = np.arange(N_DIR) * 2 * np.pi / N_DIR
    dx = np.sin(az)[None, :, None] * DIST_M[None, None, :]
    dy = np.cos(az)[None, :, None] * DIST_M[None, None, :]
    hs = _sample(a, x[:, None, None] + dx, y[:, None, None] + dy).astype(np.float64)
    drop = DIST_M ** 2 / (2 * MOON_R)
    ang = np.rad2deg(np.arctan2(hs - (h0 + MAST_M)[:, None, None] - drop[None, None, :], DIST_M[None, None, :]))
    sky = ang.max(axis=2)                                # (n, 16)
    cols += [sky[:, k] for k in range(N_DIR)]
    # Earth sits roughly over longitude 0, i.e. toward +y on this map
    cols += [sky.mean(axis=1), sky.max(axis=1), sky.min(axis=1), sky[:, 0]]
    return np.column_stack(cols).astype(np.float32)


GRID_R_M = 2900.0
GRID_FEATURE_NAMES = ["grid_nearest_margin", "grid_nearest_km", "grid_mean_margin", "grid_max_margin",
                      "grid_min_margin", "grid_share_yes"]


def grid_features(gx, gy, gmargin, qx, qy, exclude_self: bool, tree=None) -> np.ndarray:
    """Answers of the 2 km grid points within 2.9 km of each query point (a point never sees itself if asked)."""
    from scipy.spatial import cKDTree
    tree = tree or cKDTree(np.column_stack([gx, gy]))
    q = np.column_stack([np.atleast_1d(qx), np.atleast_1d(qy)])
    k = 13
    d, j = tree.query(q, k=k, distance_upper_bound=GRID_R_M)
    ok = np.isfinite(d)
    if exclude_self:
        ok &= d > 1.0
    jj = np.where(ok, j, 0)
    m = np.where(ok, np.asarray(gmargin)[jj], np.nan).astype(float)
    first = np.argmax(ok, axis=1)
    rows = np.arange(q.shape[0])
    with np.errstate(all="ignore"):
        out = np.column_stack([m[rows, first], d[rows, first] / 1000.0, np.nanmean(m, axis=1), np.nanmax(m, axis=1),
                               np.nanmin(m, axis=1), np.nanmean(m >= 0, axis=1) * (ok.sum(1) > 0)])
    return out.astype(np.float32)


_glock = threading.Lock()
_grid: dict = {}


def grid():
    """The whole-map layer's positions and margins (page's opening plan, station rule), read once."""
    with _glock:
        if "x" not in _grid:
            from scipy.spatial import cKDTree
            z = np.load(os.path.join(ROOT, "data", "addons", "fullmap", "fullmap_2000m.npz"))
            x, y = project(z["lat"], z["lon"])
            _grid.update({"x": x, "y": y, "margin": np.asarray(z["stations__margin"]).astype(int),
                          "tree": cKDTree(np.column_stack([x, y]))})
        return _grid


# ------------------------------------------------------------------------------------------------ the served model
_mlock = threading.Lock()
_model: dict = {}


def load_model() -> Optional[dict]:
    """The trained model and its report, or None if not built."""
    mp, rp = os.path.join(DATA_DIR, "model.joblib"), os.path.join(DATA_DIR, "report.json")
    if not (os.path.exists(mp) and os.path.exists(rp)):
        return None
    stamp = (os.path.getmtime(mp), os.path.getmtime(rp))
    with _mlock:
        if _model.get("stamp") != stamp:
            try:
                import joblib
                import sklearn  # noqa: F401  (the stored model needs scikit-learn)
            except ImportError:
                return None
            with open(rp, encoding="utf-8") as fh:
                rep = json.load(fh)
            _model.update({"stamp": stamp, "m": joblib.load(mp), "report": rep})
        return {"m": _model["m"], "report": _model["report"]}


def estimate(lat: float, lon: float) -> dict:
    loaded = load_model()
    if loaded is None:
        return {"available": False, "label": LABEL,
                "reason": "the estimate model has not been built here (run scripts/addons/train_estimate.py), "
                          "or scikit-learn is not installed"}
    m, rep = loaded["m"], loaded["report"]
    x, y = project(lat, lon)
    x, y = float(x), float(y)
    half = 303960.0
    if abs(x) > half or abs(y) > half:
        return {"available": False, "label": LABEL, "lat": lat, "lon": lon,
                "reason": "outside the 80 m terrain map (the 608 km square round the south pole)"}
    f = features([x], [y])
    if m.get("uses_grid"):
        g = grid()
        f = np.hstack([f, grid_features(g["x"], g["y"], g["margin"], [x], [y], False, tree=g["tree"])])
    p_yes = float(m["classifier"].predict_proba(f)[0, 1])
    margin = float(m["regressor"].predict(f)[0])
    yes = p_yes >= float(m.get("threshold", 0.5))
    days = int(max(0, round(margin))) if yes else None
    return {
        "available": True, "label": LABEL, "lat": lat, "lon": lon,
        "plan": "landing 18 Nov 2026, 60 landing dates, 240 sunlit hours and 100 hours of Earth contact in the first "
                "14 days (the page's opening plan)",
        "verdict": "yes" if yes else "no",
        "verdict_words": ("the planned landing date probably meets the need here" if yes else
                          "the planned landing date probably does not meet the need here"),
        "chance_yes": round(p_yes, 3),
        "margin_days_estimate": days,
        "margin_days_raw": round(margin, 2),
        "ships_on_page": bool(rep.get("ships_on_page", False)),
        "measured_accuracy": rep.get("served_summary", {}),
        "how": "a small boosted-tree model reading height, slope, local relief, distance to the pole and coarse "
               "skyline heights in 16 directions from the 80 m LOLA map"
               + (", plus the answers of the whole-map grid points within 2.9 km" if m.get("uses_grid") else "")
               + "; trained on the 92,416 points of the whole-map layer, tested on points it never saw",
    }


router = APIRouter()


@router.get("/api/addons/estimate")
def api_estimate(lat: float = Query(..., ge=-90.0, le=-60.0), lon: float = Query(..., ge=-360.0, le=360.0)):
    """A learned instant estimate of the verdict and slip margin at one point, with its measured accuracy."""
    return estimate(lat, lon)
