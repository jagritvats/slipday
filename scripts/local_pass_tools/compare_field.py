"""Compare a rebuilt skyline field with an earlier one.  python -I compare_field.py <old dir> <new dir>"""
import hashlib
import json
import os
import sys

import numpy as np

old, new = sys.argv[1], sys.argv[2]
a = np.load(os.path.join(old, "pole_el_i16.npy"), mmap_mode="r")
b = np.load(os.path.join(new, "pole_el_i16.npy"), mmap_mode="r")
print("shapes", a.shape, b.shape, "dtype", a.dtype, b.dtype)
d = np.asarray(a, dtype=np.int32) - np.asarray(b, dtype=np.int32)
print("values", d.size, "identical", int((d == 0).sum()), "differing", int((d != 0).sum()),
      "max |difference| in stored units", int(np.abs(d).max()), "(one unit = 0.002 deg)")
pa, pb = np.load(os.path.join(old, "pole_points.npz")), np.load(os.path.join(new, "pole_points.npz"))
for k in ("lat", "lon", "height_m"):
    print(k, "identical", bool(np.array_equal(pa[k], pb[k], equal_nan=True)))
for d_ in (old, new):
    h = hashlib.sha256(open(os.path.join(d_, "pole_el_i16.npy"), "rb").read()).hexdigest()
    m = json.load(open(os.path.join(d_, "pole_field.json")))
    print(d_, "sha256", h, "built", m["built_utc"], "fingerprint", m["dem_fingerprint"], "seconds", m["seconds"])
