"""Georeferencing controls for the Earth-visibility comparison.  python -I earth_controls.py <entry root>

1. Orientation: the Earth is seen from the near side, so the Earth-facing half of each map (top rows,
   longitude 0) must be better lit by the Earth than the far half.
2. The comparison repeated with the map flipped up-down, left-right and transposed: a correct
   georeferencing must lose its correlation under each.
3. The label keywords the reader uses.
"""
import json
import os
import sys

import numpy as np

root = sys.argv[1]
sys.path.insert(0, root)
from slipday import refmaps  # noqa: E402

more = json.load(open(os.path.join(root, "data", "validation", "more_validation.json")))
ref_dir = os.path.join(root, "data", "reference")
for m in more["e"]["maps"]:
    path = refmaps.find(ref_dir, m["region"], earth=True)
    rm = refmaps.load(path)
    z = np.asarray(rm.z)
    half = z.shape[0] // 2
    kv = refmaps.parse_label(open(os.path.splitext(path)[0] + ".LBL", errors="replace").read())
    print(os.path.basename(path), "shape", z.shape, "pixel_m", rm.pixel_m, "x0,y0 of pixel (0,0) centre", rm.x0_m, rm.y0_m, "scale", rm.scale,
          "| label: MAP_SCALE", kv["MAP_SCALE"], "LINE_PROJECTION_OFFSET", kv["LINE_PROJECTION_OFFSET"], "SAMPLE_PROJECTION_OFFSET",
          kv["SAMPLE_PROJECTION_OFFSET"], "CENTER_LONGITUDE", kv.get("CENTER_LONGITUDE"), "DN max", int(z.max()), "label max", kv.get("DERIVED_MAXIMUM"))
    print("   mean Earth visibility: near-side half (top rows) %.4f, far-side half (bottom rows) %.4f, left half %.4f, right half %.4f"
          % (z[:half].mean() * rm.scale, z[half:].mean() * rm.scale, z[:, :half].mean() * rm.scale, z[:, half:].mean() * rm.scale))
    pts = np.array(m["points"])
    calc = pts[:, 3]                                    # any part of the Earth's disc
    for name, arr in (("as read", z), ("flipped up-down", z[::-1]), ("flipped left-right", z[:, ::-1]), ("transposed", z.T),
                      ("rotated 180 deg", z[::-1, ::-1])):
        ctrl = refmaps.RefMap(path=path, z=arr, pixel_m=rm.pixel_m, x0_m=rm.x0_m, y0_m=rm.y0_m, scale=rm.scale)
        ref = ctrl.nearest(pts[:, 0], pts[:, 1])
        ok = np.isfinite(ref)
        r = float(np.corrcoef(calc[ok], ref[ok])[0, 1])
        print(f"   {name:20s} n {int(ok.sum())}  mean |difference| {float(np.abs(calc[ok] - ref[ok]).mean()) * 100:6.2f} pts  correlation {r:+.4f}")
    # one pixel off in each direction: how sharp is the registration?
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ctrl = refmaps.RefMap(path=path, z=z, pixel_m=rm.pixel_m, x0_m=rm.x0_m + dc * rm.pixel_m, y0_m=rm.y0_m + dr * rm.pixel_m, scale=rm.scale)
        ref = ctrl.nearest(pts[:, 0], pts[:, 1])
        ok = np.isfinite(ref)
        print(f"   shifted by one pixel ({dr:+d},{dc:+d})   mean |difference| {float(np.abs(calc[ok] - ref[ok]).mean()) * 100:6.2f} pts  correlation {float(np.corrcoef(calc[ok], ref[ok])[0, 1]):+.4f}")
