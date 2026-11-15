"""Terrain stacks whose finest grid is one of the LOLA team's 5 m/px south-pole site models.

    python scripts/prepare_dem5.py Site07 Site01

Reads data/reference/<Site>_final_adj_5mpp_surf.tif (PGDA "South Pole Landing Site LOLA DEMs",
https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/, fetched by HTTP range requests; Barker et al. 2021, PSS 203,
105119), writes data/dem5/<site>/ldem_<site>_5m_f32.npy and a dems.json that puts the 5 m model on top of the
20 m crop and the 80 m and coarser grids (beyond the 16 km square the 20 m grid takes over, then 80 m).
Values unchanged.  The README of the product says X/Y are south polar stereographic metres and the GeoTIFF
gives the upper-left corner of the first pixel; the stack stores pixel centres.  Git-ignored.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import tifffile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = {"Site01": "Connecting ridge", "Site04": "Shackleton rim", "Site07": "Peak near Shackleton",
         "Site11": "de Gerlache rim", "Site20": "Leibnitz beta plateau", "Site23": "Malapert massif"}


def main() -> None:
    base = json.load(open(os.path.join(ROOT, "data", "dem20", "dems.json"), encoding="utf-8"))
    for site in sys.argv[1:] or ["Site07", "Site01"]:
        src = os.path.join(ROOT, "data", "reference", f"{site}_final_adj_5mpp_surf.tif")
        t = tifffile.TiffFile(src)
        p = t.pages[0]
        z = p.asarray().astype(np.float32)
        sx, sy = p.tags["ModelPixelScaleTag"].value[:2]
        tie = p.tags["ModelTiepointTag"].value
        with open(src, "rb") as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()
        out = os.path.join(ROOT, "data", "dem5", site.lower())
        os.makedirs(out, exist_ok=True)
        np.save(os.path.join(out, f"ldem_{site.lower()}_5m_f32.npy"), z)
        dems = [{"name": f"ldem_{site.lower()}_5m", "kind": "polar_stereo", "path": f"ldem_{site.lower()}_5m_f32.npy", "format": "npy",
                 "pole": -1, "pixel_m": float(sx), "x0_m": float(tie[3]) + sx / 2, "y0_m": float(tie[4]) - sy / 2, "scale": 1.0,
                 "offset": 0.0, "nodata": None, "source": "LOLA",
                 "product": f"LOLA 5 m/px south-pole site model {site} ({NAMES.get(site, '')})",
                 "provenance": f"{site}_final_adj_5mpp_surf.tif from https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/{site}/ (HTTP range requests), sha256 {sha[:16]}; Barker et al. 2021; values unchanged"}]
        for d in base["dems"]:
            e = dict(d)
            e["path"] = os.path.relpath(os.path.join(ROOT, "data", "dem20", d["path"]), out).replace("\\", "/")
            dems.append(e)
        json.dump({"note": f"5 m site model {site} on top of the 20 m crop and the installed grids; use SLIPDAY_DEM_DIR=data/dem5/{site.lower()}",
                   "dems": dems}, open(os.path.join(out, "dems.json"), "w", encoding="utf-8"), indent=1)
        print(site, z.shape, "x", dems[0]["x0_m"], "y", dems[0]["y0_m"], "finite", float(np.isfinite(z).mean()), "sha256", sha)


if __name__ == "__main__":
    main()
