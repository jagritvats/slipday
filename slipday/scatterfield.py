"""The slip-margin map with the landing scatter: the margin that survives at all 13 touchdown points.

The slip-margin map (``field``) asks, at one point per map cell, how many days of slip the planned
landing survives.  The mission card asks the same question at 13 touchdown points (the target, 8 points
on a 100 m circle and 4 at 50 m) and only says "yes" when all agree.  ``scripts/build_scatter_field.py``
stores the 12 extra skylines for the map points that can be coloured at all; this module evaluates them
for the landing dates asked for and returns, per map point, the margin that all 13 points share.

Codes in the ``robust`` layer (one value per map point):
    >= 0   days of slip that every one of the 13 touchdown points survives
    -1     the planned date does not meet the need at the map point itself (not coloured on either map)
    -2     the map point passes, but its scatter skylines are not stored: not re-checked
    -3     the map point passes on the planned date, but not all 13 touchdown points do: the margin is lost

It is the 13-point part of the card's check only.  The card also asks a coarser grid and a finer sampling
of the nearest ground; the map does not (the slip-robust site list does, for 12 points).
"""
from __future__ import annotations

import json
import os
import threading
from collections import OrderedDict
from typing import Optional

import numpy as np

from . import field
from . import load as lanes
from .ephem import available_steps, cached_table, grid_start, parse_utc
from .metrics import STEP_S, Criteria

_lock = threading.Lock()
_state: dict = {"loaded": False, "store": None}
_results: "OrderedDict[tuple, dict]" = OrderedDict()
_compute_lock = threading.Lock()

NOT_COLOURED, NOT_CHECKED, LOST = -1, -2, -3


def load() -> Optional[dict]:
    """The stored scatter skylines, or None when they have not been built on this installation."""
    with _lock:
        if _state["loaded"]:
            return _state["store"]
        _state["loaded"] = True
        try:
            with open(os.path.join(field.FIELD_DIR, "scatter_field.json")) as fh:
                meta = json.load(fh)
            pts = np.load(os.path.join(field.FIELD_DIR, "scatter_points.npz"))
            el = np.load(os.path.join(field.FIELD_DIR, "scatter_el_i16.npy"), mmap_mode="r")
            idx = np.asarray(pts["idx"], dtype=np.int64)
            fld = field.load()
            if fld is None or el.shape[0] != len(idx) or fld["meta"].get("dem_fingerprint") != meta.get("dem_fingerprint"):
                raise ValueError("scatter skylines do not belong to the installed skyline field")
            if fld["meta"].get("thinned_by"):
                raise ValueError("the skyline field is thinned on this installation")
            pos = np.full(len(fld["lat"]), -1, dtype=np.int64)
            pos[idx] = np.arange(len(idx))
            _state["store"] = {"meta": meta, "idx": idx, "pos": pos, "lat": np.asarray(pts["lat"]),
                               "lon": np.asarray(pts["lon"]), "el": el}
        except (OSError, ValueError, KeyError):
            _state["store"] = None
        return _state["store"]


def reload() -> None:
    with _lock:
        _state["loaded"] = False
        _results.clear()


def _passes(lat, lon, el_i16, table, crit: Criteria, mask_deg: float, sv: np.ndarray, w: int, need_sun_h: float,
            need_earth_h: float, sun_td: bool, earth_td: bool) -> np.ndarray:
    """(rows, dates) True where the need is met; the same counting as ``field.per_date`` and ``field.statistics``."""
    out = np.zeros((len(lat), len(sv)), dtype=bool)
    for i0 in range(0, len(lat), field.CHUNK):
        sl = slice(i0, min(i0 + field.CHUNK, len(lat)))
        el = np.asarray(el_i16[sl], dtype=np.float32) * np.float32(field.EL_SCALE)
        lit, earth = field.evaluate_points(lat[sl], lon[sl], el, table, crit, mask_deg)
        hours = []
        for flags in (lit, earth):
            cs = np.concatenate([np.zeros((flags.shape[0], 1), dtype=np.int32), np.cumsum(flags, axis=1, dtype=np.int32)], axis=1)
            hours.append(cs[:, sv + w] - cs[:, sv])
        ok = (hours[0] >= need_sun_h) & (hours[1] >= need_earth_h)
        if sun_td:
            ok &= lit[:, sv]
        if earth_td:
            ok &= earth[:, sv]
        out[sl] = ok
    return out


def robust_margin(start, n_dates: int = 60, window_days: float = 14.0, crit: Criteria = Criteria(), mask_deg: float = 0.0,
                  need_sun_h: float = 240.0, need_earth_h: float = 100.0, sun_at_touchdown: bool = True,
                  earth_at_touchdown: bool = True) -> Optional[dict]:
    """Per map point: the single-point margin, the margin shared by all 13 touchdown points, and the counts.

    Returns None when the skyline field is not installed, and ``{"available": False, ...}`` when the field
    is there but the scatter skylines are not."""
    fld = field.load()
    if fld is None:
        return None
    store = load()
    if store is None:
        return {"available": False, "reason": "the landing-scatter skylines have not been built on this installation "
                                              "(run scripts/build_scatter_field.py)"}
    s = grid_start(parse_utc(start), STEP_S)
    w = int(round(window_days * 24))
    key = field._key(s, n_dates, 24, w, crit, mask_deg) + (float(need_sun_h), float(need_earth_h),
                                                           bool(sun_at_touchdown), bool(earth_at_touchdown))
    hit = _results.get(key)
    if hit is not None:
        return hit
    lanes.require_cold()
    with _compute_lock:
        hit = _results.get(key)
        if hit is not None:
            return hit
        pd = field.per_date(start, n_dates, 24, window_days, crit, mask_deg)
        st = field.statistics(pd, need_sun_h, need_earth_h, sun_at_touchdown, earth_at_touchdown)
        single = st["margin"].astype(np.int64)
        valid = pd["valid"]
        nd = int(valid.sum())
        robust = np.full(len(single), NOT_COLOURED, dtype=np.int64)
        passing = np.zeros(len(single), dtype=np.int64)          # touchdown points passing on the planned date
        cand = np.nonzero(single >= 0)[0]
        have = cand[store["pos"][cand] >= 0]
        robust[cand] = NOT_CHECKED
        members = store["el"].shape[1]
        if len(have):
            k = store["pos"][have]
            n = min((n_dates - 1) * 24 + w + 1, available_steps(s, STEP_S))
            table = cached_table(s, n, STEP_S)
            sv = (np.arange(n_dates) * 24)[valid]
            ok_s = _passes(store["lat"][k].ravel(), store["lon"][k].ravel(), store["el"][k].reshape(-1, store["el"].shape[2]),
                           table, crit, mask_deg, sv, w, need_sun_h, need_earth_h, sun_at_touchdown, earth_at_touchdown)
            ok_s = ok_s.reshape(len(have), members, nd)
            ok_t = (pd["sunlit"][have][:, valid] >= need_sun_h) & (pd["earth"][have][:, valid] >= need_earth_h)
            if sun_at_touchdown:
                ok_t &= pd["sun0"][have][:, valid]
            if earth_at_touchdown:
                ok_t &= pd["earth0"][have][:, valid]
            all_ok = ok_t & ok_s.all(axis=1)
            bad = ~all_ok
            first_bad = np.where(bad.any(axis=1), np.argmax(bad, axis=1), nd)
            m = first_bad - 1
            robust[have] = np.where(m < 0, LOST, m)
            passing[have] = ok_t[:, 0].astype(np.int64) + ok_s[:, :, 0].sum(axis=1)
        checked = robust[have]
        keep = checked >= 0
        sm = single[have]
        hist = {}
        for v in np.unique(checked[keep]):
            hist[int(v)] = int((checked == v).sum())
        out = {
            "available": True, "single": single, "robust": robust, "points_passing": passing,
            "members": members + 1, "scatter_m": float(store["meta"].get("scatter_m", 100.0)), "dates": nd,
            "start_utc": pd["start_utc"], "window_hours": pd["window_hours"],
            "counts": {
                "map_points": int(len(single)), "single_point_coloured": int(len(cand)), "re_checked": int(len(have)),
                "not_re_checked": int(len(cand) - len(have)), "keep_a_margin": int(keep.sum()),
                "lose_their_margin": int((checked == LOST).sum()),
                "keep_the_same_margin": int((keep & (checked == sm)).sum()),
                "keep_a_shorter_margin": int((keep & (checked < sm)).sum()),
                "largest_single_point_margin": int(single.max()) if len(single) else -1,
                "largest_surviving_margin": int(checked[keep].max()) if keep.any() else -1,
                "surviving_margin_histogram": hist,
                "single_margin_5_or_more": int((sm >= 5).sum()), "surviving_margin_5_or_more": int((checked >= 5).sum()),
            },
            "stored": {"points": int(len(store["idx"])), "selected": store["meta"].get("selected"),
                       "complete": bool(store["meta"].get("complete")), "selection": store["meta"].get("selection"),
                       "dem_label": store["meta"].get("dem_label")},
            "what": ("Each coloured map point is re-checked at 13 touchdown points (the point itself, 8 points on a "
                     f"{store['meta'].get('scatter_m', 100.0):g} m circle and 4 at half that distance) and coloured by the "
                     "days of slip that all 13 survive. It is the 13-point part of the mission card's check; the coarser "
                     "grid and the finer near-field sampling are not part of the map."),
        }
        _results[key] = out
        field.evict(_results, 3)
        return out
