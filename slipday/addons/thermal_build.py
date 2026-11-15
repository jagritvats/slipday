"""Build the compact Diviner grids used by slipday.addons.thermal.

Inputs (downloaded with plain curl, see ADDON_thermal.md):
  data/addons/thermal/raw/dgdr_tbol_avg_pols_2010*/2016*n_240_img.img  (25 night maps)
  data/addons/thermal/raw/dlre_prp_south.zip  (polar resource product; the .tab is read from the zip)

Outputs (small, kept in the repo):
  data/addons/thermal/night_min_240m.npy   int16, x0.02 K, coldest of the
       2016 night maps, cropped to CROP px around the pole
  data/addons/thermal/night_count_240m.npy uint8, number of maps with data
  data/addons/thermal/prp_south_84.npz          PRP points poleward of 84 S:
       lat, lon, temp_avg, temp_max (multi-year Diviner values)

Run:  .venv/Scripts/python -I slipday/addons/thermal_build.py  (from entry root)
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np

N = 3812          # lines and samples of the 240 m south polar GDR maps
CENTER = 1905.5   # LINE/SAMPLE_PROJECTION_OFFSET (1-based)
CROP = 900        # half width in pixels kept (900 * 240 m = 216 km, about 83 S)
MISSING = -32768

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "data", "addons", "thermal")
RAW = os.path.join(DATA, "raw")


def crop_bounds():
    c0 = int(round(CENTER - 1))  # 0-based index of the pixel holding the pole
    return c0 - CROP, c0 + CROP


def build_night() -> None:
    files = sorted(glob.glob(os.path.join(RAW, "dgdr_tbol_avg_pols_20[01][06]*n_240_img.img")))
    if not files:
        print("no night maps found", file=sys.stderr)
        return
    a, b = crop_bounds()
    mn = None
    cnt = None
    for f in files:
        img = np.fromfile(f, dtype="<i2")
        if img.size != N * N:
            print("skip (size)", f, img.size, file=sys.stderr)
            continue
        img = img.reshape(N, N)[a:b, a:b]
        valid = (img != MISSING) & (img > 0)
        v = np.where(valid, img, np.int16(32767))
        if mn is None:
            mn = v.copy()
            cnt = valid.astype(np.uint8)
        else:
            mn = np.minimum(mn, v)
            cnt += valid.astype(np.uint8)
        print("night map", os.path.basename(f), int(valid.sum()))
    mn = np.where(cnt > 0, mn, np.int16(MISSING)).astype(np.int16)
    np.save(os.path.join(DATA, "night_min_240m.npy"), mn)
    np.save(os.path.join(DATA, "night_count_240m.npy"), cnt)
    print("night grids saved", mn.shape, "files", len(files))


def build_prp() -> None:
    import io
    import zipfile
    zpath = os.path.join(RAW, "dlre_prp_south.zip")
    if not os.path.exists(zpath):
        print("no PRP zip", file=sys.stderr)
        return
    lats, lons, tavg, tmax = [], [], [], []
    with zipfile.ZipFile(zpath) as z, io.TextIOWrapper(z.open("dlre_prp_south.tab"), "ascii") as fh:
        fh.readline()  # header record
        for line in fh:
            p = line.split(",")
            if len(p) < 15:
                continue
            lat = float(p[10])
            if lat > -84.0:
                continue
            lats.append(lat)
            lons.append(float(p[9]))
            tavg.append(float(p[12]))
            tmax.append(float(p[13]))
    np.savez_compressed(
        os.path.join(DATA, "prp_south_84.npz"),
        lat=np.array(lats, np.float32), lon=np.array(lons, np.float32),
        temp_avg=np.array(tavg, np.float32), temp_max=np.array(tmax, np.float32),
    )
    print("PRP points saved", len(lats))


if __name__ == "__main__":
    what = sys.argv[1:] or ["night", "prp"]
    if "night" in what:
        build_night()
    if "prp" in what:
        build_prp()
