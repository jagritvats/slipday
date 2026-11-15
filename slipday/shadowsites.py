"""Where can you land beside permanent shadow and still survive a slip?

The scatter-checked slip-margin map (``scatterfield``) crossed with ground that never sees the Sun.
Permanent shadow here is the set of pixels of the LOLA team's 60 m average solar visibility map that read
zero (``scripts/prepare_psr.py`` cuts the mask; DERIVED from an official map).  It is where it is dark in
that 18.6-year model.  It is not a map of ice.

Rule (thresholds from the planning note of 14 Nov 2026; LOCAL_PASS_2_RESULTS.md, pass 3, R2):
  beside permanent shadow   at least AREA_HA hectares of zero pixels with their centre within REACH_M of the point
  survives a slip           all 13 touchdown points pass on the planned date and for at least one day of slip
  on shadow itself          the point's own pixel, or the pixel under any of its 13 touchdown points, is a zero
                            pixel: listed apart and not ranked, because a 500 m map cannot separate such a point
                            from the crest beside it
  ranking                   larger surviving margin, then larger shadowed area within reach, then lower map index;
                            the list shows the first LIST_N that are at least MIN_SEPARATION_M apart
"""
from __future__ import annotations

import json
import os
import threading
from typing import Optional

import numpy as np

from . import field, scatterfield
from .dem import MOON_RADIUS_M

REACH_M = 1000.0
AREA_HA = 10.0
LIST_N = 12
MIN_SEPARATION_M = 1000.0
SEARCH_M = 8000.0            # how far the nearest shadowed pixel is looked for
NOTE = ("Permanent shadow: pixels of the LOLA team's 60 m average solar visibility map that read zero (the Sun never "
        "reaches them in its 18.6-year model). It is where it is dark, not where ice is: no ice data is used here.")

_lock = threading.Lock()
_state: dict = {"loaded": False, "psr": None, "per_point": None}


def _xy(lat, lon):
    r = 2.0 * MOON_RADIUS_M * np.tan(np.pi / 4 - np.deg2rad(np.abs(lat)) / 2)
    return r * np.sin(np.deg2rad(lon)), r * np.cos(np.deg2rad(lon))


def load() -> Optional[dict]:
    """The permanent-shadow mask, or None when it has not been cut on this installation."""
    with _lock:
        if _state["loaded"]:
            return _state["psr"]
        _state["loaded"] = True
        try:
            f = np.load(os.path.join(field.FIELD_DIR, "psr_pole_60m.npz"), allow_pickle=False)
            _state["psr"] = {"mask": np.asarray(f["mask"], dtype=bool), "x0_m": float(f["x0_m"]), "y0_m": float(f["y0_m"]),
                             "pixel_m": float(f["pixel_m"]), "meta": json.loads(str(f["meta"]))}
        except (OSError, ValueError, KeyError):
            _state["psr"] = None
        return _state["psr"]


def reload() -> None:
    with _lock:
        _state.update({"loaded": False, "psr": None, "per_point": None})


def _is_shadow(psr: dict, x, y) -> np.ndarray:
    col = np.round((np.asarray(x) - psr["x0_m"]) / psr["pixel_m"]).astype(int)
    row = np.round((psr["y0_m"] - np.asarray(y)) / psr["pixel_m"]).astype(int)
    ok = (row >= 0) & (row < psr["mask"].shape[0]) & (col >= 0) & (col < psr["mask"].shape[1])
    out = np.zeros(np.shape(x), dtype=bool)
    out[ok] = psr["mask"][row[ok], col[ok]]
    return out


def per_point() -> Optional[dict]:
    """For every point of the slip-margin map: shadowed area within reach (ha), distance and bearing to the nearest
    shadowed pixel, and whether the point or one of its stored touchdown points sits on a shadowed pixel.
    Depends on the terrain only, so it is worked out once."""
    psr, fld = load(), field.load()
    if psr is None or fld is None:
        return None
    with _lock:
        if _state["per_point"] is not None:
            return _state["per_point"]
    stored = os.path.join(field.FIELD_DIR, "psr_points.npz")          # written by scripts/prepare_psr.py
    try:
        f = np.load(stored, allow_pickle=False)
        if len(f["area_ha"]) == len(fld["lat"]) and float(f["reach_m"]) == REACH_M and float(f["search_m"]) == SEARCH_M:
            out = {k: np.asarray(f[k]) for k in ("area_ha", "dist_m", "bearing_deg", "near_lat", "near_lon",
                                                 "own_pixel_shadowed", "on_shadow_itself")}
            with _lock:
                _state["per_point"] = out
            return out
    except (OSError, ValueError, KeyError):
        pass
    px, mask = psr["pixel_m"], psr["mask"]
    x, y = _xy(fld["lat"], fld["lon"])
    n = len(x)
    area = np.zeros(n)
    dist = np.full(n, np.nan)
    brg = np.full(n, np.nan)
    near_lat = np.full(n, np.nan)
    near_lon = np.full(n, np.nan)
    k = int(np.ceil(SEARCH_M / px))
    yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
    for i in range(n):
        c = (x[i] - psr["x0_m"]) / px
        r = (psr["y0_m"] - y[i]) / px
        ci, ri = int(round(c)), int(round(r))
        r0, r1, c0, c1 = ri - k, ri + k + 1, ci - k, ci + k + 1
        if r0 < 0 or c0 < 0 or r1 > mask.shape[0] or c1 > mask.shape[1]:
            a0, a1, b0, b1 = max(r0, 0), min(r1, mask.shape[0]), max(c0, 0), min(c1, mask.shape[1])
            win = np.zeros((2 * k + 1, 2 * k + 1), dtype=bool)
            win[a0 - r0:a1 - r0, b0 - c0:b1 - c0] = mask[a0:a1, b0:b1]
        else:
            win = mask[r0:r1, c0:c1]
        if not win.any():
            continue
        dx = (xx + ci - c) * px                      # east of the point, metres on the polar grid
        dy = -(yy + ri - r) * px                     # towards +y of the grid
        d = np.hypot(dx, dy)
        area[i] = float((win & (d <= REACH_M)).sum()) * px * px / 1e4
        dm = np.where(win, d, np.inf)
        j = int(np.argmin(dm))
        if np.isfinite(dm.flat[j]):
            dist[i] = float(dm.flat[j])
            # bearing clockwise from local north; on the south polar grid north points away from the pole
            rr = max(float(np.hypot(x[i], y[i])), 1e-9)
            nx, ny = x[i] / rr, y[i] / rr
            ex, ey = ny, -nx
            brg[i] = float(np.rad2deg(np.arctan2(dx.flat[j] * ex + dy.flat[j] * ey, dx.flat[j] * nx + dy.flat[j] * ny)) % 360.0)
            px_, py_ = x[i] + dx.flat[j], y[i] + dy.flat[j]
            near_lat[i] = -(90.0 - float(np.rad2deg(2.0 * np.arctan(np.hypot(px_, py_) / (2.0 * MOON_RADIUS_M)))))
            near_lon[i] = float(np.rad2deg(np.arctan2(px_, py_)))
    own = _is_shadow(psr, x, y)
    touch = own.copy()                              # the point or any stored touchdown point on a shadowed pixel
    store = scatterfield.load()
    if store is not None:
        sx, sy = _xy(store["lat"], store["lon"])   # (points, 12)
        touch[store["idx"]] |= _is_shadow(psr, sx, sy).any(axis=1)
    out = {"area_ha": area, "dist_m": dist, "bearing_deg": brg, "near_lat": near_lat, "near_lon": near_lon,
           "own_pixel_shadowed": own, "on_shadow_itself": touch}
    with _lock:
        _state["per_point"] = out
    return out


def shadow_sites(robust: np.ndarray, single: np.ndarray) -> Optional[dict]:
    """Rule R2 applied to one scatter-checked map (``robust`` and ``single`` as ``scatterfield.robust_margin`` gives them)."""
    pp, fld = per_point(), field.load()
    if pp is None or fld is None:
        return None
    psr = load()
    beside = pp["area_ha"] >= AREA_HA
    flagged = pp["on_shadow_itself"]
    counts = {}
    for name, cond in (("pass_at_the_point", single >= 0), ("keep_a_margin_0_or_more", robust >= 0),
                       ("survive_a_slip_1_or_more", robust >= 1), ("margin_5_or_more", robust >= 5)):
        counts[name] = {"all": int(cond.sum()), "beside_shadow": int((cond & beside).sum()),
                        "beside_shadow_not_on_it": int((cond & beside & ~flagged).sum()),
                        "beside_shadow_but_on_it": int((cond & beside & flagged).sum())}
    ok = (robust >= 1) & beside & ~flagged
    order = sorted(np.nonzero(ok)[0].tolist(), key=lambda i: (-int(robust[i]), -float(pp["area_ha"][i]), int(i)))
    x, y = _xy(fld["lat"], fld["lon"])

    def row(i: int) -> dict:
        la, lo = round(float(fld["lat"][i]), 5), round(float(fld["lon"][i]), 5)
        return {"map_index": int(i), "lat": la, "lon": lo, "name": f"{abs(la):.3f} S, {abs(lo):.3f} {'W' if lo < 0 else 'E'}",
                "surviving_margin_days": int(robust[i]), "single_point_margin_days": int(single[i]),
                "shadow_area_ha_within_reach": round(float(pp["area_ha"][i]), 1),
                "nearest_shadow_m": None if not np.isfinite(pp["dist_m"][i]) else int(round(float(pp["dist_m"][i]))),
                "nearest_shadow_bearing_deg": None if not np.isfinite(pp["bearing_deg"][i]) else round(float(pp["bearing_deg"][i])),
                "nearest_shadow_lat": None if not np.isfinite(pp["near_lat"][i]) else round(float(pp["near_lat"][i]), 4),
                "nearest_shadow_lon": None if not np.isfinite(pp["near_lon"][i]) else round(float(pp["near_lon"][i]), 4),
                "own_pixel_shadowed": bool(pp["own_pixel_shadowed"][i])}

    rows, taken = [], []
    for i in order:
        if all(np.hypot(x[i] - x[j], y[i] - y[j]) >= MIN_SEPARATION_M for j in taken):
            taken.append(i)
            rows.append(row(i))
            if len(rows) >= LIST_N:
                break
    fl = np.nonzero((robust >= 1) & beside & flagged)[0]
    fl_rows = [row(int(i)) for i in sorted(fl.tolist(), key=lambda i: (-int(robust[i]), -float(pp["area_ha"][i]), int(i)))[:LIST_N]]
    code = np.zeros(len(robust), dtype=np.int8)        # 1 = qualifies, 2 = qualifies but sits on shadow itself
    code[ok] = 1
    code[(robust >= 1) & beside & flagged] = 2
    return {"available": True, "rule": {"reach_m": REACH_M, "area_ha": AREA_HA, "min_margin_days": 1, "list": LIST_N,
                                         "min_separation_m": MIN_SEPARATION_M, "pixel_m": psr["pixel_m"]},
            "counts": counts, "qualifying": int(ok.sum()), "rows": rows, "on_shadow_itself": fl_rows,
            "best": rows[0] if rows else None, "layer": [int(v) for v in code],
            "area_ha": [round(float(v), 1) for v in pp["area_ha"]],
            "dist_m": [None if not np.isfinite(v) else int(round(float(v))) for v in pp["dist_m"]],
            "source": psr["meta"], "note": NOTE}
