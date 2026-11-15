"""Write data/dem_live/dems.json: the live terrain stack, finest grid first.

    python scripts/build_live_stack.py [--convert]

Order: the LOLA 5 m site models (data/dem5/site07, site01), then 20 m, then the installed 80 m, 240 m and coarser
grids (data/dem).  For 20 m it uses the full south-pole mosaic when it has been converted
(data/dem20/ldem_80s_20m_f32.npy, pole to 80 S), else the 96 km crop around the pole (data/dem20/ldem_pole_20m_f32.npy).

--convert decodes data/reference/LDEM_80S_20MPP_ADJ.TIF (2,696,082,051 bytes; a BigTIFF of 30,400 x 30,400 float32
heights in deflate-compressed 512 x 512 tiles) into a memory-mapped float32 .npy, values unchanged.  The demstore
memory-maps every grid, so memory stays bounded by the pages a calculation touches.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIF = os.path.join(ROOT, "data", "reference", "LDEM_80S_20MPP_ADJ.TIF")
FULL = os.path.join(ROOT, "data", "dem20", "ldem_80s_20m_f32.npy")
FULL_BYTES = 2_696_082_051


def convert() -> dict:
    import tifffile
    if not os.path.exists(TIF) or os.path.getsize(TIF) != FULL_BYTES:
        raise SystemExit("the full 20 m mosaic is not downloaded (or not complete)")
    with tifffile.TiffFile(TIF) as tf:
        pg = tf.pages[0]
        tie = pg.tags["ModelTiepointTag"].value
        scale = pg.tags["ModelPixelScaleTag"].value
        out = np.lib.format.open_memmap(FULL, mode="w+", dtype=np.float32, shape=pg.shape)
        pg.asarray(out=out)
        out.flush()
    px = float(scale[0])
    x_edge, y_edge = float(tie[3]), float(tie[4])
    return {"pixel_m": px, "x0_m": x_edge + px / 2, "y0_m": y_edge - px / 2, "shape": list(pg.shape)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--convert", action="store_true")
    a = ap.parse_args()
    geo_path = FULL + ".json"
    if a.convert:
        geo = convert()
        json.dump(geo, open(geo_path, "w"), indent=1)
    base = json.load(open(os.path.join(ROOT, "data", "dem", "dems.json"), encoding="utf-8"))["dems"]
    s1 = json.load(open(os.path.join(ROOT, "data", "dem5", "site01", "dems.json"), encoding="utf-8"))["dems"][0]
    s7 = json.load(open(os.path.join(ROOT, "data", "dem5", "site07", "dems.json"), encoding="utf-8"))["dems"][0]
    s1 = dict(s1, path="../dem5/site01/" + s1["path"])
    s7 = dict(s7, path="../dem5/site07/" + s7["path"])
    if os.path.exists(FULL) and os.path.exists(geo_path):
        geo = json.load(open(geo_path))
        g20 = {"name": "ldem_80s_20m", "kind": "polar_stereo", "path": "../dem20/ldem_80s_20m_f32.npy", "format": "npy",
               "pole": -1, "pixel_m": geo["pixel_m"], "x0_m": geo["x0_m"], "y0_m": geo["y0_m"], "scale": 1.0, "offset": 0.0,
               "nodata": None, "source": "LOLA", "product": "LDEM_80S_20MPP_ADJ",
               "provenance": "LDEM_80S_20MPP_ADJ.TIF, LOLA south-pole 20 m mosaic, NASA GSFC PGDA product 90 (Barker et al. 2023), "
                             "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF; decoded, values unchanged"}
    else:
        c20 = json.load(open(os.path.join(ROOT, "data", "dem20", "dems.json"), encoding="utf-8"))["dems"][0]
        g20 = dict(c20, path="../dem20/" + c20["path"])
    rest = [dict(e, path="../dem/" + e["path"]) for e in base]
    base_doc = json.load(open(os.path.join(ROOT, "data", "dem", "dems.json"), encoding="utf-8"))
    layers = {k: dict(v, path="../dem/" + v["path"]) for k, v in base_doc.get("layers", {}).items()}   # map layers stay
    doc = {"note": "The live stack: the finest LOLA grid that covers each point is used (5 m site models, then 20 m, then "
                   "80 m, then 240 m and coarser). Written by scripts/build_live_stack.py.",
           "dems": [s7, s1, g20] + rest, "layers": layers, "source_notes": base_doc.get("source_notes")}
    os.makedirs(os.path.join(ROOT, "data", "dem_live"), exist_ok=True)
    json.dump(doc, open(os.path.join(ROOT, "data", "dem_live", "dems.json"), "w", encoding="utf-8"), indent=1)
    print("wrote data/dem_live/dems.json:", [d["name"] for d in doc["dems"]])


if __name__ == "__main__":
    main()
