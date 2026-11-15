"""Pre-compute the landing-scatter skylines for the points of the slip-margin map that can ever be coloured.

The slip-margin map (data/field/, scripts/build_field.py) has one skyline per map point, so its margins
are single-point figures.  The mission card asks the same question at 13 touchdown points: the target
and 12 points around it (8 on a 100 m circle, 4 at 50 m; ``slipday.robust.SCATTER_LAYOUT``).  This script
stores those 12 extra skylines for a selection of map points, so that the map itself can be coloured by
the slip margin that survives the scatter (``slipday.scatterfield``).

Which map points: those where the single-point check passes on at least one landing date of the spans
given by ``--starts`` (60 daily dates each by default), for the default need of the page (240 sunlit hours
and 100 hours of Earth contact in 14 days, landing in sunlight with the Earth in view, half the solar disc
above the skyline).  A point outside that selection can only be coloured for another need or another
season; the page then shows it as "not re-checked".  The points that pass on the first date of the first
span are done first, so an interrupted run already covers the documented example.

Each skyline is made with ``slipday.terrain.horizon_profile``, the same ray-march as a single site and as
the map's own skylines, at the coordinates ``slipday.robust.scatter_points`` gives for the map point
rounded to five decimals (what the slip-robust site list uses), and stored like the map's (int16, 0.002 deg).

    python scripts/build_scatter_field.py --procs 6
    python scripts/build_scatter_field.py --procs 6 --limit 733        # only the first 733 points

The run can be stopped and started again: it keeps what is already stored for the same selection.
About 0.3 to 0.5 s per skyline per process on the laptop it was written on (12 skylines per map point).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slipday import demstore, field, terrain  # noqa: E402
from slipday.field import EL_SCALE, FIELD_DIR  # noqa: E402
from slipday.metrics import Criteria  # noqa: E402
from slipday.robust import SCATTER_LAYOUT, scatter_points  # noqa: E402

MAST = 2.0
SCATTER_M = 100.0
NEED = {"need_sun_h": 240.0, "need_earth_h": 100.0, "window_days": 14.0, "sun_at_touchdown": True,
        "earth_at_touchdown": True, "min_sun_fraction": 0.5}


def _work(args):
    lat, lon = args
    dem = demstore.get_dem()
    out = np.zeros((len(SCATTER_LAYOUT), 720), dtype=np.int16)
    pts = scatter_points(round(float(lat), 5), round(float(lon), 5), SCATTER_M)
    for k, (la, lo) in enumerate(pts):
        p = terrain.horizon_profile(dem, la, lo, MAST)
        out[k] = np.clip(np.round(p.el_deg / EL_SCALE), -32000, 32000).astype(np.int16)
    return out, np.array(pts, dtype=np.float64)


def _save(out_dir, idx, el, pts, meta):
    tmp = os.path.join(out_dir, "scatter_el_i16.tmp.npy")
    np.save(tmp, el)
    os.replace(tmp, os.path.join(out_dir, "scatter_el_i16.npy"))
    tmp = os.path.join(out_dir, "scatter_points.tmp.npz")
    np.savez(tmp, idx=idx.astype(np.int32), lat=pts[:, :, 0], lon=pts[:, :, 1])
    os.replace(tmp, os.path.join(out_dir, "scatter_points.npz"))
    tmp = os.path.join(out_dir, "scatter_field.tmp.json")
    with open(tmp, "w") as fh:
        json.dump(meta, fh, indent=1)
    os.replace(tmp, os.path.join(out_dir, "scatter_field.json"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--starts", default="2026-11-18T00:00:00Z,2026-11-14T00:00:00Z",
                    help="comma-separated first landing dates of the spans that select the map points")
    ap.add_argument("--n-dates", type=int, default=60)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="stop after this many map points (0: all selected)")
    ap.add_argument("--out", default=FIELD_DIR)
    a = ap.parse_args()
    dem = demstore.get_dem()
    fld = field.load()
    if dem is None or fld is None:
        sys.exit("needs the terrain data and the skyline field (scripts/build_field.py)")
    if fld["meta"].get("dem_fingerprint") != dem.fingerprint:
        sys.exit("the skyline field was built from a different terrain stack than the one installed")
    crit = Criteria(NEED["min_sun_fraction"], -90.0, -90.0, 0.0)
    starts = [s for s in a.starts.split(",") if s]
    order: list[int] = []
    seen = set()
    counts = []
    for k, start in enumerate(starts):
        pd = field.per_date(start, a.n_dates, 24, NEED["window_days"], crit, 0.0)
        st = field.statistics(pd, NEED["need_sun_h"], NEED["need_earth_h"], NEED["sun_at_touchdown"], NEED["earth_at_touchdown"])
        groups = [np.nonzero(st["margin"] >= 0)[0], np.nonzero(st["good"] > 0)[0]] if k == 0 else [np.nonzero(st["good"] > 0)[0]]
        for g in groups:
            new = [int(i) for i in g if int(i) not in seen]
            seen.update(new)
            order.extend(new)
            counts.append(len(new))
    selection = {"starts": starts, "n_dates": a.n_dates, "need": NEED,
                 "rule": "map points where the single-point check passes on at least one landing date of these spans",
                 "group_sizes_in_order": counts}
    idx_all = np.array(order, dtype=np.int32)
    if a.limit:
        idx_all = idx_all[:a.limit]
    print(f"selected {len(order)} map points (groups {counts}); doing {len(idx_all)}", flush=True)

    n = len(idx_all)
    el = np.zeros((n, len(SCATTER_LAYOUT), 720), dtype=np.int16)
    pts = np.zeros((n, len(SCATTER_LAYOUT), 2), dtype=np.float64)
    done = np.zeros(n, dtype=bool)
    try:                                          # keep what an earlier run of the same selection stored
        old = np.load(os.path.join(a.out, "scatter_points.npz"))
        old_el = np.load(os.path.join(a.out, "scatter_el_i16.npy"), mmap_mode="r")
        with open(os.path.join(a.out, "scatter_field.json")) as fh:
            old_meta = json.load(fh)
        if old_meta.get("dem_fingerprint") == dem.fingerprint and old_meta.get("scatter_m") == SCATTER_M:
            pos = {int(v): k for k, v in enumerate(old["idx"])}
            for k, v in enumerate(idx_all):
                j = pos.get(int(v))
                if j is not None:
                    el[k], pts[k, :, 0], pts[k, :, 1], done[k] = old_el[j], old["lat"][j], old["lon"][j], True
            print(f"kept {int(done.sum())} points from an earlier run", flush=True)
    except (OSError, ValueError, KeyError):
        pass

    here = dem.describe_for(float(fld["lat"][0]), float(fld["lon"][0]))
    t0 = time.time()

    def meta_now():
        return {"points": int(done.sum()), "selected": len(order), "members_per_point": len(SCATTER_LAYOUT),
                "scatter_m": SCATTER_M, "layout_fraction_bearing": SCATTER_LAYOUT, "mast_m": MAST, "n_az": 720,
                "el_scale_deg": EL_SCALE, "max_km": 300.0, "dem_label": here["label"], "dem_name": dem.name,
                "dem_fingerprint": dem.fingerprint, "selection": selection, "complete": bool(done.all() and not a.limit),
                "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seconds_this_run": round(time.time() - t0, 1)}

    todo = np.nonzero(~done)[0]
    jobs = [(fld["lat"][idx_all[k]], fld["lon"][idx_all[k]]) for k in todo]
    last = time.time()
    with Pool(a.procs) as pool:
        for j, res in enumerate(pool.imap(_work, jobs, chunksize=2)):
            k = todo[j]
            el[k], pts[k], done[k] = res[0], res[1], True
            if time.time() - last > 90 or j == len(jobs) - 1:
                keep = np.nonzero(done)[0]
                _save(a.out, idx_all[keep], el[keep], pts[keep], meta_now())
                last = time.time()
                print(f"{j + 1}/{len(jobs)} new points, {int(done.sum())}/{n} stored, {time.time() - t0:.0f} s", flush=True)
    keep = np.nonzero(done)[0]
    _save(a.out, idx_all[keep], el[keep], pts[keep], meta_now())
    print(json.dumps(meta_now(), indent=1))


if __name__ == "__main__":
    main()
