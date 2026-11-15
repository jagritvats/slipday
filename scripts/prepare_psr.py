"""Cut the permanent-shadow mask the slip-margin map is crossed with, from the LOLA team's 60 m Sun map.

    python scripts/prepare_psr.py data/reference

Reads AVGVISIB_85S_060M_201608.TIF (LOLA average solar visibility, 60 m, 85 S to the pole; its label gives
0 as permanent shadow), keeps the square of +/-32 km around the pole (the slip-margin map is +/-30 km and
the question asked of it reaches 1 km further), and stores which pixels read zero:

    data/field/psr_pole_60m.npz     mask (uint8, 1 = the map reads zero), x0_m, y0_m, pixel_m, meta (JSON)

DERIVED data: a yes/no cut of an official map, nothing else.  Permanent shadow is where the Sun never
reaches in the LOLA team's 18.6-year model; it says nothing about ice.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from slipday import refmaps  # noqa: E402

HALF_M = 32000.0
NAME = "AVGVISIB_85S_060M_201608.TIF"


def main() -> None:
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "reference")
    path = os.path.join(folder, NAME)
    if not os.path.exists(path):
        sys.exit(f"{path} is not there: fetch the official downloads first (scripts/fetch_on_your_machine.sh)")
    m = refmaps.load(path)
    px = m.pixel_m
    c0 = int(np.floor((-HALF_M - m.x0_m) / px + 0.5))
    c1 = int(np.floor((HALF_M - m.x0_m) / px + 0.5))
    r0 = int(np.floor((m.y0_m - HALF_M) / px + 0.5))
    r1 = int(np.floor((m.y0_m + HALF_M) / px + 0.5))
    crop = np.asarray(m.z[r0:r1 + 1, c0:c1 + 1])
    mask = (crop == 0).astype(np.uint8)
    with open(path, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    meta = {"source_file": NAME, "source_sha256": sha, "product_id": m.product_id, "description": m.description,
            "pixel_m": px, "half_width_m": HALF_M, "shape": list(mask.shape), "zero_pixels": int(mask.sum()),
            "zero_area_km2": round(float(mask.sum()) * px * px / 1e6, 2),
            "made_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "what": "1 where the LOLA team's 60 m average solar visibility map reads zero (permanent shadow in its 18.6-year "
                    "model); DERIVED by scripts/prepare_psr.py, values otherwise unchanged"}
    out = os.path.join(ROOT, "data", "field", "psr_pole_60m.npz")
    np.savez_compressed(out, mask=mask, x0_m=m.x0_m + c0 * px, y0_m=m.y0_m - r0 * px, pixel_m=px, meta=json.dumps(meta))
    meta["file_bytes"] = os.path.getsize(out)
    print(json.dumps(meta, indent=1))
    # the per-point figures the app needs (area within reach, nearest shadowed pixel), so that it does not
    # have to work them out at its first request
    from slipday import shadowsites
    pts = os.path.join(ROOT, "data", "field", "psr_points.npz")
    if os.path.exists(pts):
        os.remove(pts)
    shadowsites.reload()
    t0 = time.time()
    pp = shadowsites.per_point()
    if pp is None:
        sys.exit("the skyline field is not installed (scripts/build_field.py), so the per-point figures were not made")
    np.savez_compressed(pts, reach_m=shadowsites.REACH_M, search_m=shadowsites.SEARCH_M, **pp)
    print(json.dumps({"points": int(len(pp["area_ha"])), "with_shadow_within_reach": int((pp["area_ha"] > 0).sum()),
                      "with_10_ha_or_more": int((pp["area_ha"] >= shadowsites.AREA_HA).sum()),
                      "own_pixel_shadowed": int(pp["own_pixel_shadowed"].sum()),
                      "point_or_touchdown_point_on_shadow": int(pp["on_shadow_itself"].sum()),
                      "seconds": round(time.time() - t0, 1), "file_bytes": os.path.getsize(pts)}, indent=1))


if __name__ == "__main__":
    main()
