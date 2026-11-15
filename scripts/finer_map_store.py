"""20 m skylines for every point of the stored scatter skylines (rule R6, pass 4), computed once.

    python scripts/finer_map_store.py [--procs 6]

For each of the map points that have stored 80 m scatter skylines (data/field/scatter_el_i16.npy), the 13
touchdown points (the point and its 12 scatter points, the same positions as the 80 m store) get a skyline
on the stack whose finest grid is the 20 m mosaic (data/dem20; beyond the crop the 80 m stack), with the
app's own ray-march.  A skyline does not depend on the date, so every map date can then be re-checked on
20 m without new ray-marching (scripts/finer_map_dates.py).

Writes data/dem20/scatter20_el_i16.npy (points, 13, 720; int16 in units of the field's EL_SCALE) and
data/dem20/scatter20_done.npy (which points are finished), every few minutes, so a stopped run keeps its
part.  The 20 m crop is git-ignored, and so are these files.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "data", "dem20", "scatter20_el_i16.npy")
DONE = os.path.join(ROOT, "data", "dem20", "scatter20_done.npy")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=6)
    ap.add_argument("--dem", default=os.path.join(ROOT, "data", "dem20"))
    a = ap.parse_args()
    from slipday import field, scatterfield
    fld, store = field.load(), scatterfield.load()
    n = len(store["idx"])
    if os.path.exists(OUT) and os.path.exists(DONE):
        el, done = np.load(OUT), np.load(DONE)
    else:
        el, done = np.zeros((n, 13, 720), dtype=np.int16), np.zeros(n, dtype=bool)
    jobs = []
    for k, i in enumerate(store["idx"]):
        if done[k]:
            continue
        pts = [(float(fld["lat"][i]), float(fld["lon"][i]))] + [(float(store["lat"][k][j]), float(store["lon"][k][j]))
                                                                for j in range(store["lat"].shape[1])]
        jobs.append((k, pts))
    t0, last = time.time(), time.time()

    def save():
        np.save(OUT + ".tmp.npy", el)
        os.replace(OUT + ".tmp.npy", OUT)
        np.save(DONE, done)

    with Pool(a.procs, initializer=_init, initargs=(a.dem,)) as pool:
        for j, (k, out) in enumerate(pool.imap_unordered(_work, jobs, chunksize=2)):
            el[k], done[k] = out, True
            if time.time() - last > 120:
                save()
                last = time.time()
                print(f"{int(done.sum())}/{n} points, {time.time() - t0:.0f} s", flush=True)
    save()
    print(f"done: {int(done.sum())}/{n} points, {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
