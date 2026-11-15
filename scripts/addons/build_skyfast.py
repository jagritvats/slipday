"""Gather the whole-map skylines (data/addons/fullmap/chunks_2000m/chunk_*.npz) into one memory-mappable array.

Writes data/addons/skyfast/fullmap_el_i16.npy (points, 720) int16, row = grid index, and fullmap_points.npz
(lat, lon, height_m, grid_m, have). Values are copied unchanged. Run once off line:

    python scripts/addons/build_skyfast.py
"""
import glob
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "data", "addons", "fullmap", "chunks_2000m")
OUT = os.path.join(ROOT, "data", "addons", "skyfast")


def main():
    grid = json.load(open(os.path.join(SRC, "grid.json")))
    n = grid["n"] * grid["n"]
    os.makedirs(OUT, exist_ok=True)
    el = np.lib.format.open_memmap(os.path.join(OUT, "fullmap_el_i16.tmp.npy"), mode="w+", dtype=np.int16, shape=(n, 720))
    lat = np.full(n, np.nan); lon = np.full(n, np.nan)
    h = np.full(n, np.nan, dtype=np.float32); gm = np.full(n, np.nan, dtype=np.float32)
    have = np.zeros(n, dtype=bool)
    for p in sorted(glob.glob(os.path.join(SRC, "chunk_*.npz"))):
        z = np.load(p)
        i = z["idx"]
        el[i] = z["el"]; lat[i] = z["lat"]; lon[i] = z["lon"]; h[i] = z["height_m"]; gm[i] = z["grid_m"]
        have[i] = np.isfinite(z["height_m"])
    el.flush(); del el
    os.replace(os.path.join(OUT, "fullmap_el_i16.tmp.npy"), os.path.join(OUT, "fullmap_el_i16.npy"))
    np.savez(os.path.join(OUT, "fullmap_points.npz"), lat=lat, lon=lon, height_m=h, grid_m=gm, have=have)
    meta = {k: grid[k] for k in ("n", "step_m", "mast_m", "n_az", "el_scale_deg", "dem_fingerprint", "dem_label")}
    meta.update(points=int(n), with_terrain=int(have.sum()), source="data/addons/fullmap/chunks_2000m")
    json.dump(meta, open(os.path.join(OUT, "fullmap.json"), "w"), indent=1)
    print(meta)


if __name__ == "__main__":
    main()
