"""A polar-stereographic picture of the terrain for the site picker.

The picture is made from the installed DEM itself: heights are sampled on a
south-polar stereographic grid and rendered as shaded relief (hill shading
with an elevation tint).  It is therefore real data whenever the DEM is, and
it is labelled SYNTHETIC when the DEM is the test fixture.

The page projects latitude/longitude onto it with the same formula:
x = r sin(lon), y = r cos(lon), r = 2 R tan(pi/4 - |lat|/2), image centre at
the pole, +y (longitude 0, towards the Earth-facing side) up.
"""
from __future__ import annotations

import io
import threading
from typing import Optional

import numpy as np

from . import demstore
from .dem import MOON_RADIUS_M, PolarStereoDEM

_lock = threading.Lock()
_cache: dict = {}


def _default_edge_lat(dem) -> float:
    """Outer latitude of the map: the edge of the finest south-polar grid that reaches 80 S (the 80 m mosaic when it
    is installed), else of the finest south-polar grid, else 80 S.  Finer grids that cover only a small area near
    the pole (the 20 m crop, the 5 m site models) change the skylines, not the extent of the map."""
    polar = [m for m in getattr(dem, "members", [dem]) if isinstance(m, PolarStereoDEM) and m.pole < 0]   # finest first
    wide = [m for m in polar if m.edge_latitude() >= -80.5]
    for m in (wide or polar):
        return float(np.clip(m.edge_latitude(), -89.0, -60.0))
    return -80.0


def _half_m(edge_lat: float, half_km: Optional[float]) -> float:
    if half_km:
        return float(half_km) * 1000.0
    return 2.0 * MOON_RADIUS_M * np.tan(np.pi / 4 - np.deg2rad(abs(edge_lat)) / 2)


def _edge_lat(half_m: float) -> float:
    return -(90.0 - float(np.rad2deg(2.0 * np.arctan(half_m / (2.0 * MOON_RADIUS_M)))))


def _render(edge_lat: float, size: int, half_km: Optional[float] = None):
    dem = demstore.get_dem()
    if dem is None:
        return None
    half = _half_m(edge_lat, half_km)
    edge_lat = _edge_lat(half)
    px = 2.0 * half / size
    xs = -half + px * (np.arange(size) + 0.5)
    ys = half - px * (np.arange(size) + 0.5)
    X, Y = np.meshgrid(xs, ys)
    r = np.hypot(X, Y)
    colat = 2.0 * np.arctan(r / (2.0 * MOON_RADIUS_M))
    lat = -(90.0 - np.rad2deg(colat))
    lon = np.rad2deg(np.arctan2(X, Y))
    z = dem.height_m(lat, lon)
    inside = np.ones_like(r, dtype=bool)      # the grid is square: keep the corners
    valid = np.isfinite(z) & inside
    if not valid.any():
        return None
    zf = np.where(np.isfinite(z), z, np.nanmedian(z[valid]))
    gy, gx = np.gradient(zf, px)
    # light from the upper left, 35 degrees up; relief exaggerated for legibility
    exag = 4.0 if px > 400 else 2.0
    az, alt = np.deg2rad(315.0), np.deg2rad(35.0)
    lx, ly, lz = np.sin(az) * np.cos(alt), np.cos(az) * np.cos(alt), np.sin(alt)
    nx, ny, nz = -gx * exag, gy * exag, np.ones_like(zf)   # image rows run towards -y
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    shade = np.clip((nx * lx + ny * ly + nz * lz) / norm, 0.0, 1.0)
    lo, hi = np.nanpercentile(z[valid], [1, 99])
    tint = np.clip((zf - lo) / max(hi - lo, 1.0), 0.0, 1.0)
    grey = 0.18 + 0.82 * (0.7 * shade + 0.3 * tint)
    rgb = np.stack([grey * 232, grey * 228, grey * 218], axis=-1)
    rgb = np.where(valid[..., None], rgb, 20.0).astype(np.uint8)
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buf, format="JPEG", quality=86)
    meta = {
        "available": True, "projection": "south polar stereographic, true scale at the pole, R = 1737.4 km",
        "pole": -1, "edge_lat": edge_lat, "half_width_km": round(half / 1000.0, 2), "size_px": size,
        "km_per_px": round(px / 1000.0, 3), "image": "/api/map/image",
        "kind": "shaded relief computed from the elevation model",
        "dem_label": dem.label(), "synthetic": bool(dem.synthetic),
        "height_range_m": [round(float(lo)), round(float(hi))],
        "coverage_share": round(float(valid.sum() / max(inside.sum(), 1)), 3),
    }
    return buf.getvalue(), meta


def get(edge_lat: Optional[float] = None, size: int = 760, half_km: Optional[float] = None):
    """(JPEG bytes, metadata) for the south-polar map, or None without a DEM.

    ``half_km`` asks for a close-up: a square of that half-width centred on the pole."""
    dem = demstore.get_dem()
    if dem is None:
        return None
    if edge_lat is None:
        edge_lat = _default_edge_lat(dem)
    key = (dem.name, getattr(dem, "fingerprint", ""), round(edge_lat, 3), size, half_km)
    with _lock:
        if key not in _cache:
            if len(_cache) > 3:
                _cache.clear()
            _cache[key] = _render(edge_lat, size, half_km)
        return _cache[key]


def _render_layer(name: str, edge_lat: float, size: int, half_km: Optional[float] = None):
    """A published reference raster (e.g. the LOLA team's average solar visibility)
    resampled onto the same polar grid as the relief picture."""
    got = demstore.layer(name)
    if got is None:
        return None
    arr, entry = got
    half = _half_m(edge_lat, half_km)
    px = 2.0 * half / size
    xs = -half + px * (np.arange(size) + 0.5)
    ys = half - px * (np.arange(size) + 0.5)
    col = np.round((xs - entry["x0_m"]) / entry["pixel_m"]).astype(int)
    row = np.round((entry["y0_m"] - ys) / entry["pixel_m"]).astype(int)
    ok_c = (col >= 0) & (col < arr.shape[1])
    ok_r = (row >= 0) & (row < arr.shape[0])
    v = np.zeros((size, size), dtype=float)
    valid = np.outer(ok_r, ok_c)
    sub = np.asarray(arr[np.clip(row, 0, arr.shape[0] - 1)][:, np.clip(col, 0, arr.shape[1] - 1)], dtype=float)
    v[valid] = sub[valid] * entry.get("scale", 1.0)
    # one hue, dark to light: more light = brighter
    t = np.clip(v, 0.0, 1.0) ** 0.8
    lo, hi = np.array([14, 20, 34.0]), np.array([255, 236, 170.0])
    rgb = lo[None, None, :] + (hi - lo)[None, None, :] * t[..., None]
    rgb = np.where(valid[..., None], rgb, 20.0).astype(np.uint8)
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buf, format="JPEG", quality=86)
    return buf.getvalue(), {"label": entry.get("label", name), "provenance": entry.get("provenance", "")}


def get_layer(name: str, edge_lat: Optional[float] = None, size: int = 760, half_km: Optional[float] = None):
    dem = demstore.get_dem()
    if dem is None:
        return None
    if edge_lat is None:
        edge_lat = _default_edge_lat(dem)
    key = ("layer", name, round(edge_lat, 3), size, half_km)
    with _lock:
        if key not in _layer_cache:
            if len(_layer_cache) > 3:
                _layer_cache.clear()
            _layer_cache[key] = _render_layer(name, edge_lat, size, half_km)
        return _layer_cache[key]


_layer_cache: dict = {}


# --------------------------------------------------------------------------- permanent shadow

PSR_NOTE = ("DERIVED: cells of the average-illumination layer that read zero. The layer is a 4x4 block mean (480 m) of the "
            "LOLA team's 120 m map AVGVISIB_75S_120M_201608 (18.6 years, hourly), whose label gives 0 as permanent shadow; "
            "a 480 m cell is drawn only when all of it is zero, so shadowed patches smaller than that are not shown.")


def _psr_mask():
    got = demstore.layer("avgvis")
    if got is None:
        return None
    arr, entry = got
    return np.asarray(arr) == 0, entry


def permanent_shadow_overlay(edge_lat: Optional[float] = None, size: int = 760, half_km: Optional[float] = None):
    """(PNG bytes with transparency, metadata) marking permanently shadowed cells on the same grid as the map."""
    dem = demstore.get_dem()
    got = _psr_mask()
    if dem is None or got is None:
        return None
    mask, entry = got
    if edge_lat is None:
        edge_lat = _default_edge_lat(dem)
    key = ("psr", round(edge_lat, 3), size, half_km)
    with _lock:
        if key in _layer_cache:
            return _layer_cache[key]
    half = _half_m(edge_lat, half_km)
    px = 2.0 * half / size
    xs = -half + px * (np.arange(size) + 0.5)
    ys = half - px * (np.arange(size) + 0.5)
    col = np.round((xs - entry["x0_m"]) / entry["pixel_m"]).astype(int)
    row = np.round((entry["y0_m"] - ys) / entry["pixel_m"]).astype(int)
    ok = np.outer((row >= 0) & (row < mask.shape[0]), (col >= 0) & (col < mask.shape[1]))
    sub = mask[np.clip(row, 0, mask.shape[0] - 1)][:, np.clip(col, 0, mask.shape[1] - 1)] & ok
    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    rgba[sub] = (122, 60, 190, 150)
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG", optimize=True)
    area = float(sub.sum()) * (px / 1000.0) ** 2
    out = (buf.getvalue(), {"label": "permanent shadow (average sunlight zero on the LOLA team's map)", "note": PSR_NOTE,
                            "cell_m": entry["pixel_m"], "shown_km2": round(area, 1)})
    with _lock:
        if len(_layer_cache) > 6:
            _layer_cache.clear()
        _layer_cache[key] = out
    return out


def nearest_permanent_shadow(lat: float, lon: float, search_km: float = 60.0) -> Optional[dict]:
    """Distance and direction from a point to the nearest permanently shadowed 480 m cell, or None when the
    layer is not installed or the point is outside it.  Distances are measured on the polar stereographic
    grid (within about 1 % of true inside 80 S)."""
    got = _psr_mask()
    if got is None or lat > -80.0:
        return None
    mask, entry = got
    r = 2.0 * MOON_RADIUS_M * np.tan(np.pi / 4 - np.deg2rad(abs(lat)) / 2)
    x, y = r * np.sin(np.deg2rad(lon)), r * np.cos(np.deg2rad(lon))
    pm = entry["pixel_m"]
    c0, r0 = (x - entry["x0_m"]) / pm, (entry["y0_m"] - y) / pm
    k = int(np.ceil(search_km * 1000.0 / pm))
    ra, rb = max(0, int(r0) - k), min(mask.shape[0], int(r0) + k + 1)
    ca, cb = max(0, int(c0) - k), min(mask.shape[1], int(c0) + k + 1)
    if ra >= rb or ca >= cb:
        return None
    rr, cc = np.nonzero(mask[ra:rb, ca:cb])
    if rr.size == 0:
        return {"found": False, "searched_km": search_km, "note": PSR_NOTE}
    dx = (cc + ca - c0) * pm
    dy = -(rr + ra - r0) * pm
    d = np.hypot(dx, dy)
    i = int(np.argmin(d))
    inside = bool(mask[int(np.clip(round(r0), 0, mask.shape[0] - 1)), int(np.clip(round(c0), 0, mask.shape[1] - 1))])
    # bearing clockwise from local north; on the south polar grid local north points away from the pole along +r
    north = np.array([x, y]) / max(float(np.hypot(x, y)), 1e-9)          # away from the pole = towards north
    east = np.array([north[1], -north[0]])
    brg = float(np.rad2deg(np.arctan2(dx[i] * east[0] + dy[i] * east[1], dx[i] * north[0] + dy[i] * north[1])) % 360.0)
    rx, ry = x + dx[i], y + dy[i]
    rlat = -(90.0 - float(np.rad2deg(2.0 * np.arctan(np.hypot(rx, ry) / (2.0 * MOON_RADIUS_M)))))
    rlon = float(np.rad2deg(np.arctan2(rx, ry)))
    within = d <= 5000.0
    return {"found": True, "site_cell_is_shadowed": inside, "dist_km": round(float(d[i]) / 1000.0, 2), "bearing_deg": round(brg, 0),
            "lat": round(rlat, 3), "lon": round(rlon, 3), "cell_m": pm,
            "shadowed_km2_within_5km": round(float(within.sum()) * (pm / 1000.0) ** 2, 1), "note": PSR_NOTE}
