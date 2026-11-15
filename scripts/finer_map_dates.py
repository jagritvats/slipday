"""The 20 m mark of the slip-margin map for 14 map dates (rule R6, pass 4).

    python scripts/finer_map_dates.py

Start dates 18 Nov 2026 and every 7th day up to 17 Feb 2027.  For each, the page's default need and rules
(240 sunlit hours and 100 hours of Earth contact in 14 days, Sun and Earth at touchdown, station rule on, 2 m
observer, 100 m scatter, 60 landing dates): every point that the 80 m scatter check colours (keeps or loses a
margin) is re-checked with its 13 skylines on the 20 m stack, read from data/dem20/scatter20_el_i16.npy
(scripts/finer_map_store.py).  A point "agrees" when both grids give the same answer to "do all 13 touchdown
points pass on the planned date".  Printed per date whatever it is.  Writes data/validation/finer_map_dates.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from slipday import demstore, field, scatterfield  # noqa: E402
from slipday.ephem import available_steps, cached_table, grid_start, parse_utc  # noqa: E402
from slipday.metrics import STEP_S, Criteria  # noqa: E402

NEED = dict(need_sun_h=240.0, need_earth_h=100.0, window_days=14.0, sun_at_touchdown=True, earth_at_touchdown=True)
EL20 = os.path.join(ROOT, "data", "dem20", "scatter20_el_i16.npy")
DONE20 = os.path.join(ROOT, "data", "dem20", "scatter20_done.npy")
OUT = os.path.join(ROOT, "data", "validation", "finer_map_dates.json")


def margin_of(ok_all: np.ndarray) -> int:
    if not ok_all[0]:
        return -1
    bad = np.nonzero(~ok_all)[0]
    return int(bad[0]) - 1 if len(bad) else len(ok_all) - 1


def main() -> None:
    fld, store = field.load(), scatterfield.load()
    el20, done = np.load(EL20, mmap_mode="r"), np.load(DONE20)
    crit = Criteria(stations=True)
    starts = [(datetime(2026, 11, 18, tzinfo=timezone.utc) + timedelta(days=7 * k)).strftime("%Y-%m-%dT%H:%M:%SZ") for k in range(14)]
    pos = {int(i): k for k, i in enumerate(store["idx"])}
    rows_out = []
    t_all = time.time()
    for start in starts:
        t0 = time.time()
        r = scatterfield.robust_margin(start, 60, NEED["window_days"], crit, 0.0, NEED["need_sun_h"], NEED["need_earth_h"],
                                       NEED["sun_at_touchdown"], NEED["earth_at_touchdown"])
        robust = np.asarray(r["robust"])
        todo = [int(i) for i in np.nonzero((robust >= 0) | (robust == scatterfield.LOST))[0] if int(i) in pos and done[pos[int(i)]]]
        missing = int(sum(1 for i in np.nonzero((robust >= 0) | (robust == scatterfield.LOST))[0] if int(i) in pos and not done[pos[int(i)]]))
        s = grid_start(parse_utc(start), STEP_S)
        w = int(round(NEED["window_days"] * 24))
        n = min(59 * 24 + w + 1, available_steps(s, STEP_S))
        table = cached_table(s, n, STEP_S)
        st = np.arange(60) * 24
        sv = st[st + w <= n - 1]
        cells = {}
        for c0 in range(0, len(todo), 40):
            part = todo[c0:c0 + 40]
            lat, lon, el = [], [], []
            for i in part:
                k = pos[i]
                lat += [fld["lat"][i]] + list(store["lat"][k])
                lon += [fld["lon"][i]] + list(store["lon"][k])
                el.append(np.asarray(el20[k]))
            el = np.concatenate(el, axis=0)
            ok = scatterfield._passes(np.array(lat), np.array(lon), el, table, crit, 0.0, sv, w, NEED["need_sun_h"], NEED["need_earth_h"],
                                      NEED["sun_at_touchdown"], NEED["earth_at_touchdown"])
            for j, i in enumerate(part):
                m20 = margin_of(ok[13 * j:13 * j + 13].all(axis=0))
                m80 = int(robust[i]) if robust[i] >= 0 else -1
                cells[str(i)] = [m80, m20, bool((m20 >= 0) == (m80 >= 0))]
        vals = list(cells.values())
        agree = sum(1 for v in vals if v[2])
        row = {"start": start, "points": len(vals), "points_without_20m_skylines": missing, "agree": agree,
               "agree_share": round(agree / max(len(vals), 1), 4),
               "keeps_on_80m_loses_on_20m": sum(1 for v in vals if v[0] >= 0 and v[1] < 0),
               "loses_on_80m_keeps_on_20m": sum(1 for v in vals if v[0] < 0 and v[1] >= 0),
               "equal_margins": sum(1 for v in vals if v[0] == v[1]),
               "keep_on_80m": sum(1 for v in vals if v[0] >= 0), "keep_on_20m": sum(1 for v in vals if v[1] >= 0),
               "seconds": round(time.time() - t0, 1), "cells": cells}
        rows_out.append(row)
        print(f"{start[:10]}: {row['points']} points, agree {agree} ({100 * row['agree_share']:.1f} %), 80 m keeps/20 m loses "
              f"{row['keeps_on_80m_loses_on_20m']}, 80 m loses/20 m keeps {row['loses_on_80m_keeps_on_20m']}, equal margins "
              f"{row['equal_margins']}, keep on 80 m {row['keep_on_80m']} / on 20 m {row['keep_on_20m']}"
              + (f", {missing} points without 20 m skylines" if missing else "") + f" ({row['seconds']} s)", flush=True)
    doc = {"what": __doc__.strip().split("\n")[0], "rule": "R6 in LOCAL_PASS_2_RESULTS.md, pass 4",
           "scenario": {"n_dates": 60, **NEED, "mast_m": 2.0, "scatter_m": 100.0, "earth_rule": "Earth's centre above the skyline and a DSN station (10 deg)"},
           "used_grid": demstore.status().get("label"),
           "fine_grid": "LOLA 20 m mosaic (LDEM_80S_20MPP_ADJ, 81 tiles by HTTP range request); beyond the crop the 80 m stack",
           "made_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seconds": round(time.time() - t_all, 1), "dates": rows_out}
    with open(OUT + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(doc, fh, separators=(",", ":"))
    os.replace(OUT + ".tmp", OUT)
    print(f"wrote {OUT}: {len(rows_out)} dates, {os.path.getsize(OUT)} bytes")


if __name__ == "__main__":
    main()
