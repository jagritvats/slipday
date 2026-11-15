"""The 20 m mark of the slip-margin map for any start date, worked out on request from stored 20 m skylines.

The 20 m skylines of the 2,407 stored map points (13 each, data/dem20/scatter20_el_i16.npy, made by
scripts/finer_map_store.py) do not depend on the date, so re-checking a new map date on 20 m only needs the
counting, not new ray-marching.  The rule is R4/R6 (LOCAL_PASS_2_RESULTS.md): a re-checked point "agrees" when
both grids give the same answer to "do all 13 touchdown points pass on the planned date".  The files are
git-ignored (they come with the 20 m crop); without them nothing is marked.
"""
from __future__ import annotations

import os
import threading
from collections import OrderedDict
from typing import Optional

import numpy as np

from . import field, scatterfield
from . import load as lanes
from .ephem import available_steps, cached_table, grid_start, parse_utc
from .metrics import STEP_S, Criteria

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EL20 = os.path.join(ROOT, "data", "dem20", "scatter20_el_i16.npy")
DONE20 = os.path.join(ROOT, "data", "dem20", "scatter20_done.npy")
_lock = threading.Lock()
_cache: "OrderedDict[tuple, dict]" = OrderedDict()


def available() -> bool:
    return os.path.exists(EL20) and os.path.exists(DONE20)


def _margin(ok_all: np.ndarray) -> int:
    if not ok_all[0]:
        return -1
    bad = np.nonzero(~ok_all)[0]
    return int(bad[0]) - 1 if len(bad) else len(ok_all) - 1


def cells(start: str, n_dates: int, window_days: float, crit: Criteria, mask_deg: float, need_sun_h: float,
          need_earth_h: float, sun_td: bool, earth_td: bool) -> Optional[dict]:
    """{map index: [margin on 80 m, margin on 20 m, agrees]} for every point the 80 m scatter check colours."""
    if not available():
        return None
    key = (start[:13], n_dates, window_days, field._key(0, 0, 0, 0, crit, mask_deg), need_sun_h, need_earth_h, sun_td, earth_td)
    with _lock:
        if key in _cache:
            return _cache[key]
    lanes.require_cold()
    fld, store = field.load(), scatterfield.load()
    r = scatterfield.robust_margin(start, n_dates, window_days, crit, mask_deg, need_sun_h, need_earth_h, sun_td, earth_td)
    if not r or not r.get("available"):
        return None
    el20, done = np.load(EL20, mmap_mode="r"), np.load(DONE20)
    robust = np.asarray(r["robust"])
    pos = {int(i): k for k, i in enumerate(store["idx"])}
    todo = [int(i) for i in np.nonzero((robust >= 0) | (robust == scatterfield.LOST))[0] if int(i) in pos and done[pos[int(i)]]]
    s = grid_start(parse_utc(start), STEP_S)
    w = int(round(window_days * 24))
    n = min((n_dates - 1) * 24 + w + 1, available_steps(s, STEP_S))
    table = cached_table(s, n, STEP_S)
    st = np.arange(n_dates) * 24
    sv = st[st + w <= n - 1]
    out = {}
    for c0 in range(0, len(todo), 40):
        part = todo[c0:c0 + 40]
        lat, lon, el = [], [], []
        for i in part:
            k = pos[i]
            lat += [fld["lat"][i]] + list(store["lat"][k])
            lon += [fld["lon"][i]] + list(store["lon"][k])
            el.append(np.asarray(el20[k]))
        ok = scatterfield._passes(np.array(lat), np.array(lon), np.concatenate(el, axis=0), table, crit, mask_deg, sv, w,
                                  need_sun_h, need_earth_h, sun_td, earth_td)
        for j, i in enumerate(part):
            m20 = _margin(ok[13 * j:13 * j + 13].all(axis=0))
            m80 = int(robust[i]) if robust[i] >= 0 else -1
            out[str(i)] = [m80, m20, bool((m20 >= 0) == (m80 >= 0))]
    v = list(out.values())
    agree = sum(1 for x in v if x[2])
    res = {"points_done": len(v), "points_total": len(v), "share_done": 1.0, "agree": agree, "disagree": len(v) - agree,
           "agree_share": round(agree / max(len(v), 1), 4), "equal_margins": sum(1 for x in v if x[0] == x[1]),
           "complete": True, "on_request": True,
           "fine_grid": "LOLA 20 m mosaic (LDEM_80S_20MPP_ADJ, 81 tiles by HTTP range request); beyond the crop the 80 m stack",
           "cells": {k: [x[1], x[2]] for k, x in out.items()}}
    with _lock:
        _cache[key] = res
        while len(_cache) > 8:
            _cache.popitem(last=False)
    return res
