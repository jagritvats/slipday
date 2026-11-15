"""Crop rows 9600..11519 (60S to 90S) of NASA SVS ldem_64_uint.tif into a .npy, as the data scout did.

    python -I crop_ldem64.py <ldem_64_uint.tif> <out.npy>
"""
import hashlib
import sys

import numpy as np
import tifffile


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


src, out = sys.argv[1], sys.argv[2]
print("source sha256", sha256(src))
with tifffile.TiffFile(src) as t:
    pg = t.pages[0]
    print("shape", pg.shape, "dtype", pg.dtype, "compression", pg.compression,
          "DocumentName", pg.tags["DocumentName"].value if "DocumentName" in pg.tags else None,
          "Software", pg.tags["Software"].value if "Software" in pg.tags else None)
    a = pg.asarray()
assert a.shape == (11520, 23040) and a.dtype == np.uint16, (a.shape, a.dtype)
crop = np.ascontiguousarray(a[9600:11520, :])
assert crop.shape == (1920, 23040)
np.save(out, crop)
print("crop sha256", sha256(out), "bytes", __import__("os").path.getsize(out))
