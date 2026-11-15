"""Add single tiles of NASA's 20 m LOLA south-pole mosaic to the crop in data/dem20, by HTTP range request.

    python scripts/fetch_ldem20_tiles.py --rows 30 32 --cols 33 33

Used when a site needs 20 m ground that the 71.7 km square of scripts/fetch_ldem20_crop.py does not hold.
The crop array grows to the bounding box of the old crop and the new tiles; cells of that box for which no
tile was fetched stay empty (NaN), and the terrain stack falls back to the 80 m grid there.

Writes, like the first script: the tile bytes exactly as received and their byte ranges in data/reference/,
the enlarged array in data/dem20/, its georeference in data/dem20/dems.json, and a line in
data/reference/DOWNLOADS.tsv.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("fetch_ldem20_crop", os.path.join(ROOT, "scripts", "fetch_ldem20_crop.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, nargs=2, required=True, help="first and last tile row (0-based)")
    ap.add_argument("--cols", type=int, nargs=2, required=True, help="first and last tile column")
    a = ap.parse_args()
    import tifffile

    d20 = os.path.join(ROOT, "data", "dem20")
    ref = os.path.join(ROOT, "data", "reference")
    with open(os.path.join(d20, "dems.json")) as fh:
        cfg = json.load(fh)
    entry = cfg["dems"][0]
    old = np.load(os.path.join(d20, entry["path"]))
    px = float(entry["pixel_m"])
    tile_m = 512 * px
    # tile rows and columns the old array covers (its corner pixel centre is half a pixel inside its edge)
    oc0 = int(round((entry["x0_m"] - px / 2 + 304000.0) / tile_m))
    or0 = int(round((304000.0 - (entry["y0_m"] + px / 2)) / tile_m))
    oc1, or1 = oc0 + old.shape[1] // 512 - 1, or0 + old.shape[0] // 512 - 1
    r0, r1 = min(or0, a.rows[0]), max(or1, a.rows[1])
    c0, c1 = min(oc0, a.cols[0]), max(oc1, a.cols[1])
    new = np.full(((r1 - r0 + 1) * 512, (c1 - c0 + 1) * 512), np.nan, dtype=np.float32)
    new[(or0 - r0) * 512:(or0 - r0) * 512 + old.shape[0], (oc0 - c0) * 512:(oc0 - c0) * 512 + old.shape[1]] = old

    t0 = time.time()
    head = base.fetch(0, base.HEAD_BYTES - 1)
    stem = f"LDEM_80S_20MPP_ADJ_tiles_r{a.rows[0]}-{a.rows[1]}_c{a.cols[0]}-{a.cols[1]}"
    sha, got, index = hashlib.sha256(), 0, []
    with tempfile.TemporaryDirectory(prefix="ldem20_") as tmp:
        hp = os.path.join(tmp, "head.tif")
        with open(hp, "wb") as fh:
            fh.write(head)
        with tifffile.TiffFile(hp) as tif, open(os.path.join(ref, stem + ".bin"), "wb") as raw_out:
            pg = tif.pages[0]
            across = -(-pg.shape[1] // pg.tilewidth)
            for row in range(a.rows[0], a.rows[1] + 1):
                for col in range(a.cols[0], a.cols[1] + 1):
                    i = row * across + col
                    off, cnt = int(pg.dataoffsets[i]), int(pg.databytecounts[i])
                    raw = base.fetch(off, off + cnt - 1)
                    sha.update(raw)
                    raw_out.write(raw)
                    index.append({"tile_row": row, "tile_col": col, "first_byte": off, "bytes": cnt, "offset_in_bin": got})
                    got += cnt
                    seg = np.asarray(pg.decode(raw, i)[0], dtype=np.float32).reshape(512, 512)
                    new[(row - r0) * 512:(row - r0 + 1) * 512, (col - c0) * 512:(col - c0 + 1) * 512] = seg
    with open(os.path.join(ref, stem + ".json"), "w") as fh:
        json.dump({"source": base.URL, "file_bytes": 2696082051, "tile_px": 512, "tiles_across": int(across),
                   "compression": "deflate, floating-point predictor", "sha256_of_bin": sha.hexdigest(), "tiles": index}, fh, indent=1)
    npy = os.path.join(d20, entry["path"])
    np.save(npy, new)
    with open(npy, "rb") as fh:
        npy_sha = hashlib.sha256(fh.read()).hexdigest()
    entry["x0_m"] = -304000.0 + c0 * tile_m + px / 2
    entry["y0_m"] = 304000.0 - r0 * tile_m - px / 2
    entry["provenance"] += (f"; plus tiles rows {a.rows[0]}..{a.rows[1]}, columns {a.cols[0]}..{a.cols[1]} (sha256 of their bytes "
                            f"{sha.hexdigest()[:16]}); cells with no tile are empty")
    with open(os.path.join(d20, "dems.json"), "w") as fh:
        json.dump(cfg, fh, indent=1)
    rows = [
        "\t".join([stem + ".bin", str(got), sha.hexdigest(),
                   f"{base.URL} (HTTP range requests for tile rows {a.rows[0]}..{a.rows[1]}, columns {a.cols[0]}..{a.cols[1]}; byte ranges in "
                   f"{stem}.json; merged into data/dem20/ldem_pole_20m_f32.npy, which is now {os.path.getsize(npy)} bytes, sha256 {npy_sha}, "
                   f"{new.shape[0]} x {new.shape[1]} cells of which {int(np.isnan(new).sum())} are empty)"]),
    ]
    jp = os.path.join(ref, stem + ".json")
    with open(jp, "rb") as fh:
        rows.append("\t".join([stem + ".json", str(os.path.getsize(jp)), hashlib.sha256(fh.read()).hexdigest(),
                               "(derived here: which bytes of the official file each tile in the .bin is, scripts/fetch_ldem20_tiles.py)"]))
    tsv = os.path.join(ref, "DOWNLOADS.tsv")
    with open(tsv, encoding="utf-8") as fh:
        have = fh.read()
    with open(tsv, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(have.rstrip("\n") + "\n" + "\n".join(rows) + "\n")
    print(json.dumps({"tiles": len(index), "tile_bytes": got, "tile_bytes_sha256": sha.hexdigest(), "array_shape": list(new.shape),
                      "empty_cells": int(np.isnan(new).sum()), "x0_m": entry["x0_m"], "y0_m": entry["y0_m"], "npy_bytes": os.path.getsize(npy),
                      "npy_sha256": npy_sha, "seconds": round(time.time() - t0, 1)}, indent=1))


if __name__ == "__main__":
    main()
