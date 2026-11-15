"""Re-check the coloured points of the scatter-checked slip-margin map on NASA's 20 m grid (rule R4, pass 3).

    python scripts/finer_map_check.py [--procs 2]

For the page's default scenario (landing 18 Nov 2026, 60 landing dates, 240 sunlit hours and 100 hours of
Earth contact in 14 days, Sun and Earth at touchdown, 2 m observer, 100 m scatter) every map point that was
re-checked at 13 touchdown points on the 80 m stack is re-checked again on the stack whose finest grid is the
20 m mosaic (data/dem20, cut by scripts/fetch_ldem20_crop.py and scripts/fetch_ldem20_tiles.py; beyond the
crop the 80 m grid and the coarser ones take over, as in the app): 13 skylines, the point and its 12 scatter
points, with the app's own ray-march and counting.

A point "agrees" when the 20 m stack gives the same answer as the 80 m stack to "do all 13 touchdown points pass
on the planned date"; the share that agrees is printed whatever it is, with how many surviving margins are
equal.  The result is written to data/validation/finer_map_check.json as the run goes, so a run that is stopped
leaves the part done, with the share done.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

L = "2026-11-18T00:00:00Z"
NEED = dict(need_sun_h=240.0, need_earth_h=100.0, window_days=14.0, sun_at_touchdown=True, earth_at_touchdown=True)
OUT = os.path.join(ROOT, "data", "validation", "finer_map_check.json")


def _init(dem_dir):
    os.environ["SLIPDAY_DEM_DIR"] = dem_dir
    from slipday import demstore
    demstore.reload()


def _work(args):
    from slipday import demstore, terrain
    from slipday.field import EL_SCALE
    k, pts = args
    dem = demstore.get_dem()
    out = np.zeros((len(pts), 720), dtype=np.int16)
    for j, (la, lo) in enumerate(pts):
        p = terrain.horizon_profile(dem, float(la), float(lo), 2.0)
        out[j] = np.clip(np.round(p.el_deg / EL_SCALE), -32000, 32000).astype(np.int16)
    return k, out


def margin_of(ok_all: np.ndarray) -> int:
    if not ok_all[0]:
        return -1
    bad = np.nonzero(~ok_all)[0]
    return int(bad[0]) - 1 if len(bad) else len(ok_all) - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dem", default=os.path.join(ROOT, "data", "dem20"),
                    help="terrain stack for the re-check (the default stack gives a self-check: every point must agree)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    from slipday import demstore, field, scatterfield
    from slipday.ephem import available_steps, cached_table, grid_start, parse_utc
    from slipday.metrics import STEP_S, Criteria
    fld, store = field.load(), scatterfield.load()
    if fld is None or store is None:
        sys.exit("needs the skyline field and the scatter skylines")
    crit = Criteria()
    r = scatterfield.robust_margin(L, 60, NEED["window_days"], crit, 0.0, NEED["need_sun_h"], NEED["need_earth_h"],
                                   NEED["sun_at_touchdown"], NEED["earth_at_touchdown"])
    robust = np.asarray(r["robust"])
    pos = {int(i): k for k, i in enumerate(store["idx"])}
    todo = [int(i) for i in np.nonzero((robust >= 0) | (robust == scatterfield.LOST))[0] if int(i) in pos]
    if a.limit:
        todo = todo[:a.limit]
    s = grid_start(parse_utc(L), STEP_S)
    w = int(round(NEED["window_days"] * 24))
    n = min(59 * 24 + w + 1, available_steps(s, STEP_S))
    table = cached_table(s, n, STEP_S)
    starts = np.arange(60) * 24
    sv = starts[starts + w <= n - 1]
    used80 = demstore.status().get("label")
    jobs = []
    for i in todo:
        k = pos[i]
        pts = [(float(fld["lat"][i]), float(fld["lon"][i]))] + [(float(store["lat"][k][j]), float(store["lon"][k][j]))
                                                                for j in range(store["lat"].shape[1])]
        jobs.append((i, pts))
    rows, t0, last = [], time.time(), 0.0
    dem20 = a.dem

    def save(final=False):
        agree = sum(1 for x in rows if x[3])
        equal = sum(1 for x in rows if x[1] == x[2])
        doc = {"what": __doc__.strip().split("\n")[0], "rule": "R4 in LOCAL_PASS_2_RESULTS.md, pass 3",
               "scenario": {"start": L, "n_dates": 60, **NEED, "mast_m": 2.0, "scatter_m": 100.0, "earth_rule": "Earth's centre above the skyline"},
               "used_grid": used80, "fine_grid": "LOLA 20 m mosaic (LDEM_80S_20MPP_ADJ, tiles fetched by HTTP range request); beyond the crop the 80 m stack",
               "points_total": len(jobs), "points_done": len(rows), "share_done": round(len(rows) / max(len(jobs), 1), 4),
               "agree": agree, "disagree": len(rows) - agree, "agree_share": round(agree / max(len(rows), 1), 4),
               "equal_margins": equal, "complete": final and len(rows) == len(jobs),
               "made_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seconds": round(time.time() - t0, 1),
               "columns": ["map_index", "margin_80m", "margin_20m", "agrees"], "rows": rows}
        tmp = a.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, separators=(",", ":"))
        os.replace(tmp, a.out)
        return doc

    with Pool(a.procs, initializer=_init, initargs=(dem20,)) as pool:
        for j, (i, el) in enumerate(pool.imap_unordered(_work, jobs, chunksize=1)):
            k = pos[i]
            lat = np.array([fld["lat"][i]] + list(store["lat"][k]))
            lon = np.array([fld["lon"][i]] + list(store["lon"][k]))
            ok = scatterfield._passes(lat, lon, el, table, crit, 0.0, sv, w, NEED["need_sun_h"], NEED["need_earth_h"],
                                      NEED["sun_at_touchdown"], NEED["earth_at_touchdown"])
            m20 = margin_of(ok.all(axis=0))
            m80 = int(robust[i]) if robust[i] >= 0 else -1
            rows.append([i, m80, m20, bool((m20 >= 0) == (m80 >= 0))])
            if time.time() - last > 60:
                d = save()
                last = time.time()
                print(f"{d['points_done']}/{d['points_total']} done, agree {d['agree']} ({100 * d['agree_share']:.1f}%), "
                      f"equal margins {d['equal_margins']}, {d['seconds']:.0f} s", flush=True)
    d = save(final=True)
    print(json.dumps({k: v for k, v in d.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
