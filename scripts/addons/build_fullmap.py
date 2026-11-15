"""Terrain skylines for the whole "South pole to 80 deg S" map, on a coarse grid, in resumable chunks.

The skyline at each point is made by ``scripts/build_field.py``'s own worker (``_work``: the same ray-march,
2 m observer, 720 azimuths, 300 km, int16 at 0.002 deg), on the same terrain stack as the 500 m close-up
(``data/dem``: LOLA 80 m, then 240 m, then coarser). Only the grid is different: one point every ``--step-m``
over the 80 m mosaic's square (608 km across), placed so that every point inside the close-up's 60 km square
falls exactly on one of the close-up's 500 m points (for the agreement check).

Order: first every 2nd point each way (a complete map at twice the spacing), then the rest, so a run cut
short still covers the whole map, more coarsely. Each chunk is written to its own file as soon as it is done
(``data/addons/fullmap/chunks/``); a re-run skips chunks already on disk.

    python scripts/addons/build_fullmap.py --step-m 2000 --procs 6              # the full run
    python scripts/addons/build_fullmap.py --step-m 2000 --procs 6 --limit 300  # a timing test (first 300 points)

Workers run at below-normal priority. Then run ``scripts/addons/finish_fullmap.py``.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from multiprocessing import Pool

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):   # one thread per worker: less memory
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
DEM_DIR = os.path.join(ROOT, "data", "dem")              # the 80 m stack the close-up was built from
os.environ.setdefault("SLIPDAY_DEM_DIR", DEM_DIR)

OUT = os.path.join(ROOT, "data", "addons", "fullmap")
HALF_M = 304000.0                                         # the 80 m mosaic: x, y from -303,960 to +303,960 m
CLOSE_STEP = 500.0                                        # the close-up's spacing; its points sit at +-250 m + k * 500 m


def grid_axis(step_m: float) -> np.ndarray:
    """Coordinates (m) along one axis: 250 + k * step, inside +-HALF_M (so close-up points are hit exactly)."""
    k0 = int(np.ceil((-HALF_M - 250.0) / step_m))
    k1 = int(np.floor((HALF_M - 250.0) / step_m))
    return 250.0 + step_m * np.arange(k0, k1 + 1)


def grid(step_m: float):
    """Points of the map grid, row 0 at the top (largest y, longitude 0 up) like the close-up."""
    c = grid_axis(step_m)
    X, Y = np.meshgrid(c, c[::-1])
    return c, X, Y


def unproject(x, y):
    from slipday.dem import MOON_RADIUS_M
    r = np.hypot(x, y)
    lat = -(90.0 - np.rad2deg(2.0 * np.arctan(r / (2.0 * MOON_RADIUS_M))))
    lon = np.rad2deg(np.arctan2(x, y))
    return lat, lon


def order(n: int) -> np.ndarray:
    """Flat indices: the every-2nd-point lattice first (row-major), then the rest (row-major)."""
    r, c = np.divmod(np.arange(n * n), n)
    coarse = (r % 2 == 0) & (c % 2 == 0)
    return np.concatenate([np.nonzero(coarse)[0], np.nonzero(~coarse)[0]])


def _load_build_field():
    spec = importlib.util.spec_from_file_location("build_field", os.path.join(ROOT, "scripts", "build_field.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_BF = None


def _init():
    global _BF
    os.environ["SLIPDAY_DEM_DIR"] = DEM_DIR
    try:
        import psutil
        p = psutil.Process()
        p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 10)
    except Exception:
        pass
    _BF = _load_build_field()


def _chunk(job):
    cid, idx, lat, lon, mast, out_dir = job
    from slipday import demstore
    dem = demstore.get_dem()
    t0 = time.time()
    el = np.zeros((len(idx), 720), dtype=np.int16)
    h = np.full(len(idx), np.nan, dtype=np.float32)
    grid_m = np.zeros(len(idx), dtype=np.float32)
    for i in range(len(idx)):
        res = _BF._work((lat[i], lon[i], mast))
        if res is not None:
            el[i], h[i] = res
            m = dem.member_at(float(lat[i]), float(lon[i]))
            grid_m[i] = float(m.resolution_m) if m is not None else np.nan
    path = os.path.join(out_dir, "chunk_%05d.npz" % cid)
    tmp = path + ".tmp.npz"
    np.savez(tmp, idx=idx, lat=lat, lon=lon, el=el, height_m=h, grid_m=grid_m, seconds=time.time() - t0,
             pid=os.getpid())
    os.replace(tmp, path)
    return cid, len(idx), time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step-m", type=float, default=2000.0)
    ap.add_argument("--procs", type=int, default=6)
    ap.add_argument("--chunk", type=int, default=64)
    ap.add_argument("--limit", type=int, default=0, help="only the first N points in run order (timing test)")
    ap.add_argument("--mast-m", type=float, default=2.0)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    if a.procs > 6:
        sys.exit("at most 6 worker processes on this machine")
    _init()                                                      # the parent at below-normal priority too
    from slipday import demstore
    dem = demstore.get_dem()
    if dem is None:
        sys.exit("no terrain data installed")
    c, X, Y = grid(a.step_m)
    n = len(c)
    lat, lon = unproject(X.ravel(), Y.ravel())
    run = order(n)
    if a.limit:
        run = run[:a.limit]
    sub = os.path.join(a.out, "chunks_%dm" % int(a.step_m))
    os.makedirs(sub, exist_ok=True)
    here = dem.describe_for(float(lat[0]), float(lon[0]))
    meta = {"n": n, "step_m": a.step_m, "axis_first_m": float(c[0]), "axis_last_m": float(c[-1]),
            "half_m_mosaic": HALF_M, "mast_m": a.mast_m, "n_az": 720, "el_scale_deg": 0.002, "max_km": 300.0,
            "chunk": a.chunk, "order": "every 2nd point each way first (row-major), then the rest (row-major)",
            "dem_dir": os.path.relpath(DEM_DIR, ROOT), "dem_name": dem.name, "dem_fingerprint": dem.fingerprint,
            "dem_label": here["label"],
            "projection": "south polar stereographic, true scale at the pole, R = 1737.4 km; row 0 is +y (longitude 0)"}
    mp = os.path.join(sub, "grid.json")
    if os.path.exists(mp):
        with open(mp) as fh:
            old = json.load(fh)
        for k in ("n", "step_m", "axis_first_m", "chunk", "dem_fingerprint", "mast_m"):
            if old.get(k) != meta[k]:
                sys.exit(f"existing chunks were made with {k}={old.get(k)!r}, not {meta[k]!r}; use another --out")
    with open(mp, "w") as fh:
        json.dump(meta, fh, indent=1)
    full = order(n)
    jobs = []
    for cid, i0 in enumerate(range(0, len(full), a.chunk)):
        idx = full[i0:i0 + a.chunk]
        if a.limit and i0 >= a.limit:
            break
        if os.path.exists(os.path.join(sub, "chunk_%05d.npz" % cid)):
            continue
        jobs.append((cid, idx, lat[idx], lon[idx], a.mast_m, sub))
    total = sum(len(j[1]) for j in jobs)
    print(f"grid {n} x {n} = {n * n} points at {a.step_m:g} m; {len(jobs)} chunks ({total} points) to do; "
          f"terrain {dem.name} ({dem.fingerprint})", flush=True)
    t0 = time.time()
    done = 0
    with Pool(a.procs, initializer=_init) as pool:
        for k, (cid, cnt, sec) in enumerate(pool.imap_unordered(_chunk, jobs)):
            done += cnt
            el = time.time() - t0
            if k % 5 == 0 or done == total:
                rate = el / max(done, 1)
                print(f"{done}/{total} points  {el:.0f} s  {rate:.3f} s/point (wall, {a.procs} procs)  "
                      f"eta {rate * (total - done) / 60:.1f} min  [chunk {cid}: {sec / cnt:.2f} s/point/proc]", flush=True)
    print(f"done: {done} points in {time.time() - t0:.1f} s", flush=True)


if __name__ == "__main__":
    main()
