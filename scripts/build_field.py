"""Pre-compute the terrain skyline at every point of a square grid around the south pole.

The result (data/field/) is what the slip-robustness map is computed from at run time:
one 720-azimuth skyline per grid point, made with exactly the same ray-march as a single
site (slipday.terrain.horizon_profile), so clicking a map pixel and adding that point as
a site gives the same answer.

    python3 scripts/build_field.py                 # +/-30 km at 500 m, 2 m observer, 2 processes
    python3 scripts/build_field.py --half-km 30 --step-m 500 --procs 2

Takes about 0.16 s per point per core (14,400 points: about 20 minutes on two cores).
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

from slipday import demstore, terrain  # noqa: E402
from slipday.dem import MOON_RADIUS_M  # noqa: E402
from slipday.field import EL_SCALE, FIELD_DIR  # noqa: E402

MAST = 2.0


def _unproject(x, y):
    r = np.hypot(x, y)
    lat = -(90.0 - np.rad2deg(2.0 * np.arctan(r / (2.0 * MOON_RADIUS_M))))
    lon = np.rad2deg(np.arctan2(x, y))
    return lat, lon


def _work(args):
    lat, lon, mast = args
    dem = demstore.get_dem()
    try:
        p = terrain.horizon_profile(dem, float(lat), float(lon), mast)
    except ValueError:
        return None
    el = np.clip(np.round(p.el_deg / EL_SCALE), -32000, 32000).astype(np.int16)
    return el, p.site_height_m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--half-km", type=float, default=30.0)
    ap.add_argument("--step-m", type=float, default=500.0)
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--mast-m", type=float, default=MAST)
    ap.add_argument("--out", default=FIELD_DIR)
    a = ap.parse_args()
    dem = demstore.get_dem()
    if dem is None:
        sys.exit("no terrain data installed")
    n = int(round(2 * a.half_km * 1000.0 / a.step_m))
    c = -a.half_km * 1000.0 + a.step_m * (np.arange(n) + 0.5)
    X, Y = np.meshgrid(c, c[::-1])            # row 0 = largest y (longitude 0 up), like the DEM
    lat, lon = _unproject(X.ravel(), Y.ravel())
    jobs = [(la, lo, a.mast_m) for la, lo in zip(lat, lon)]
    t0 = time.time()
    el = np.zeros((len(jobs), 720), dtype=np.int16)
    h = np.full(len(jobs), np.nan, dtype=np.float32)
    with Pool(a.procs) as pool:
        for i, res in enumerate(pool.imap(_work, jobs, chunksize=16)):
            if res is not None:
                el[i], h[i] = res
            if i % 500 == 0:
                print(f"{i}/{len(jobs)}  {time.time() - t0:.0f} s", flush=True)
    os.makedirs(a.out, exist_ok=True)
    np.save(os.path.join(a.out, "pole_el_i16.npy"), el)
    np.savez(os.path.join(a.out, "pole_points.npz"), lat=lat.astype(np.float64), lon=lon.astype(np.float64), height_m=h)
    here = dem.describe_for(float(lat[0]), float(lon[0]))
    meta = {"n": n, "half_km": a.half_km, "step_m": a.step_m, "mast_m": a.mast_m, "n_az": 720, "el_scale_deg": EL_SCALE,
            "max_km": 300.0, "dem_label": here["label"], "dem_name": dem.name, "dem_fingerprint": dem.fingerprint,
            "resolution_m": here["resolution_m"], "provenance": here.get("provenance", ""),
            "projection": "south polar stereographic, true scale at the pole, R = 1737.4 km; row 0 is +y (longitude 0)",
            "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seconds": round(time.time() - t0, 1),
            "points": len(jobs), "points_without_terrain": int(np.isnan(h).sum())}
    with open(os.path.join(a.out, "pole_field.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
