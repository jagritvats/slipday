"""Fetch the part of NASA's 20 m LOLA south-pole mosaic that lies around the pole, by HTTP range requests.

    python scripts/fetch_ldem20_crop.py            # tiles 26..32 x 26..32: a 71.7 km square around the pole

The mosaic LDEM_80S_20MPP_ADJ.TIF (NASA GSFC PGDA product 90, Barker et al. 2023; the same folder as the
80 m file this entry uses) is 2,696,082,051 bytes: a BigTIFF of 30,400 x 30,400 float32 heights in 512 x 512
tiles, deflate-compressed with the floating-point predictor.  Its tile table sits at the start of the
file, so the 49 tiles around the pole can be read on their own (about 28 MB) instead of the whole file.

What this writes:
  data/reference/LDEM_80S_20MPP_ADJ_tiles_r26-32_c26-32.bin    the tile bytes exactly as received, in row order
  data/reference/LDEM_80S_20MPP_ADJ_tiles_r26-32_c26-32.json   which bytes of the official file each tile is
  data/dem20/ldem_pole_20m_f32.npy    3,584 x 3,584 float32 heights in metres decoded from those bytes, values unchanged
  data/dem20/dems.json                a terrain stack with that crop as the finest grid, then the installed ones
  one line in data/reference/DOWNLOADS.tsv with the URL, the file of received bytes and its sha256

The crop is NOT part of the default terrain stack: every number on the page and in the tests stays on the
80 m grid.  To compute with it, point SLIPDAY_DEM_DIR at data/dem20 (scripts/ridge_20m.py does).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.request

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF"
AGENT = "slipday-data-fetch/1.0"
HEAD_BYTES = 1 << 20


def fetch(first: int, last: int, tries: int = 4) -> bytes:
    for k in range(tries):
        try:
            req = urllib.request.Request(URL, headers={"Range": f"bytes={first}-{last}", "User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) == last - first + 1:
                return data
        except OSError:
            pass
        time.sleep(3 * (k + 1))
    raise SystemExit(f"could not fetch bytes {first}-{last} of {URL}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", type=int, default=26, help="first tile row and column (0-based)")
    ap.add_argument("--last", type=int, default=32, help="last tile row and column")
    a = ap.parse_args()
    import tifffile

    out_dir = os.path.join(ROOT, "data", "dem20")
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    head = fetch(0, HEAD_BYTES - 1)
    with tempfile.TemporaryDirectory(prefix="ldem20_") as tmp:
        hp = os.path.join(tmp, "head.tif")
        with open(hp, "wb") as fh:
            fh.write(head)
        with tifffile.TiffFile(hp) as tif:
            pg = tif.pages[0]
            ny, nx = pg.shape
            tw, th = pg.tilewidth, pg.tilelength
            across = -(-nx // tw)
            scale = pg.tags["ModelPixelScaleTag"].value
            tie = pg.tags["ModelTiepointTag"].value
            assert pg.dtype == np.float32 and tw == th and scale[0] == scale[1] == 20.0, (pg.dtype, tw, th, scale)
            n = a.last - a.first + 1
            crop = np.full((n * th, n * tw), np.nan, dtype=np.float32)
            sha = hashlib.sha256()
            got = 0
            ref_dir = os.path.join(ROOT, "data", "reference")
            os.makedirs(ref_dir, exist_ok=True)
            stem = f"LDEM_80S_20MPP_ADJ_tiles_r{a.first}-{a.last}_c{a.first}-{a.last}"
            raw_out = open(os.path.join(ref_dir, stem + ".bin"), "wb")
            index = []
            for row in range(a.first, a.last + 1):
                for col in range(a.first, a.last + 1):
                    i = row * across + col
                    off, cnt = int(pg.dataoffsets[i]), int(pg.databytecounts[i])
                    raw = fetch(off, off + cnt - 1)
                    sha.update(raw)
                    raw_out.write(raw)
                    index.append({"tile_row": row, "tile_col": col, "first_byte": off, "bytes": cnt, "offset_in_bin": got})
                    got += cnt
                    seg = pg.decode(raw, i)[0]
                    crop[(row - a.first) * th:(row - a.first + 1) * th, (col - a.first) * tw:(col - a.first + 1) * tw] = \
                        np.asarray(seg, dtype=np.float32).reshape(th, tw)
                print(f"tile row {row} done, {got / 1e6:.1f} MB so far, {time.time() - t0:.0f} s", flush=True)
    raw_out.close()
    with open(os.path.join(ref_dir, stem + ".json"), "w") as fh:
        json.dump({"source": URL, "file_bytes": 2696082051, "tile_px": int(tw), "tiles_across": int(across),
                   "compression": "deflate, floating-point predictor", "sha256_of_bin": sha.hexdigest(), "tiles": index}, fh, indent=1)
    px = float(scale[0])
    x_edge, y_edge = float(tie[3]) + a.first * tw * px, float(tie[4]) - a.first * th * px       # outer edge of the crop
    npy = os.path.join(out_dir, "ldem_pole_20m_f32.npy")
    np.save(npy, crop)
    with open(npy, "rb") as fh:
        npy_sha = hashlib.sha256(fh.read()).hexdigest()
    entry = {"name": "ldem_pole_20m", "kind": "polar_stereo", "path": "ldem_pole_20m_f32.npy", "format": "npy", "pole": -1,
             "pixel_m": px, "x0_m": x_edge + px / 2, "y0_m": y_edge - px / 2, "scale": 1.0, "offset": 0.0, "nodata": None,
             "source": "LOLA", "product": "LDEM_80S_20MPP_ADJ (crop)",
             "provenance": (f"tiles {a.first}..{a.last} x {a.first}..{a.last} of LDEM_80S_20MPP_ADJ.TIF, LOLA south-pole 20 m "
                            "mosaic, NASA GSFC PGDA product 90 (Barker et al. 2023), read by HTTP range request; deflate and "
                            f"floating-point predictor decoded, values unchanged; sha256 of the received tile bytes {sha.hexdigest()[:16]}")}
    with open(os.path.join(ROOT, "data", "dem", "dems.json")) as fh:
        base = json.load(fh)
    others = []
    for e in base["dems"]:
        e = dict(e)
        if not os.path.isabs(e["path"]):
            e["path"] = "../dem/" + e["path"]
        others.append(e)
    cfg = {"note": "written by scripts/fetch_ldem20_crop.py: the 20 m crop around the pole on top of the installed grids; "
                   "not the default stack (use SLIPDAY_DEM_DIR=data/dem20)", "dems": [entry] + others}
    with open(os.path.join(out_dir, "dems.json"), "w") as fh:
        json.dump(cfg, fh, indent=1)
    line = "\t".join([stem + ".bin", str(got), sha.hexdigest(),
                      f"{URL} (HTTP range requests for tiles {a.first}..{a.last} x {a.first}..{a.last}; byte ranges in {stem}.json; the first "
                      f"{HEAD_BYTES} bytes were also read, for the tile table; the full file is 2,696,082,051 bytes and was not downloaded; "
                      f"decoded to data/dem20/ldem_pole_20m_f32.npy, {os.path.getsize(npy)} bytes, sha256 {npy_sha})"])
    tsv = os.path.join(ROOT, "data", "reference", "DOWNLOADS.tsv")
    if os.path.exists(tsv):
        with open(tsv, encoding="utf-8") as fh:
            have = fh.read()
        if sha.hexdigest() + "\thttps" not in have:
            with open(tsv, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(("" if have.endswith("\n") else "\n") + line + "\n")
    print(json.dumps({"shape": crop.shape, "pixel_m": px, "x0_m": entry["x0_m"], "y0_m": entry["y0_m"],
                      "min_m": float(np.nanmin(crop)), "max_m": float(np.nanmax(crop)), "nan_cells": int(np.isnan(crop).sum()),
                      "tile_bytes": got, "tile_bytes_sha256": sha.hexdigest(), "npy_sha256": npy_sha,
                      "seconds": round(time.time() - t0, 1)}, indent=1))
    print("DOWNLOADS.tsv line:\n" + line)


if __name__ == "__main__":
    main()
