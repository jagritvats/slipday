"""Download NASA's 80 m south-pole mosaic and build the array the app reads (231 MB, not kept in git).

    python scripts/fetch_grid80.py            # downloads into data/reference/, writes data/dem/ldem_80s_80m_f32.npy
    python scripts/fetch_grid80.py --reference DIR --out FILE.npy     # other locations (used to test the download)

Used by the Dockerfile (--build-arg GRID80=1) and by anyone who cloned the repository without the grid.
The download is checked against the sha256 recorded when the file was fetched from pgda.gsfc.nasa.gov on
14 Nov 2026; a different hash stops the build rather than serving unverified terrain.  The other grids
and data/dem/dems.json are already in the repository; scripts/prepare_dem.py rebuilds everything.
"""
import hashlib
import os
import sys
import time
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF"
SHA256 = "82030dcbdd7c4bb0c7d858e9b4b293b9f2cda5a543ba31ec0f42784bd6beee5a"
SIZE = 189_158_392


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, dest, attempts=6):
    """Download to ``dest``, resuming a partial file after a dropped connection (the server closed one
    189 MB transfer part-way on 14 Nov 2026)."""
    part = dest + ".part"
    for attempt in range(1, attempts + 1):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        if have >= SIZE:
            break
        headers = {"User-Agent": "slipday-fetch/1.0"}
        if have:
            headers["Range"] = f"bytes={have}-"
        print(f"downloading {url}" + (f" (resuming at {have:,} bytes, attempt {attempt})" if have else ""), flush=True)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as resp:
                resumed = have and resp.status == 206
                with open(part, "ab" if resumed else "wb") as fh:
                    while True:
                        chunk = resp.read(1 << 20)
                        if not chunk:
                            break
                        fh.write(chunk)
        except Exception as exc:                      # dropped connection, timeout: keep the part and try again
            print(f"  interrupted: {exc!r}"[:200], flush=True)
            time.sleep(3)
    if not os.path.exists(part) or os.path.getsize(part) != SIZE:
        sys.exit(f"could not download {url}: got {os.path.getsize(part) if os.path.exists(part) else 0:,} of {SIZE:,} bytes")
    os.replace(part, dest)


def _arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def main():
    import tifffile
    ref = _arg("--reference", os.path.join(HERE, "data", "reference"))        # where the NASA file is kept
    out = _arg("--out", os.path.join(HERE, "data", "dem", "ldem_80s_80m_f32.npy"))
    tif = os.path.join(ref, "LDEM_80S_80MPP_ADJ.TIF")
    os.makedirs(ref, exist_ok=True)
    if not (os.path.exists(tif) and os.path.getsize(tif) == SIZE):
        download(URL, tif)
    got = sha256(tif)
    if got != SHA256:
        sys.exit(f"sha256 of {tif} is {got}, expected {SHA256}: not the product this build was validated on")
    with tifffile.TiffFile(tif) as t:
        pg = t.pages[0]
        scale, tie = pg.tags["ModelPixelScaleTag"].value, pg.tags["ModelTiepointTag"].value
        a = pg.asarray()
    assert a.shape == (7600, 7600) and a.dtype == np.float32, (a.shape, a.dtype)
    assert abs(scale[0] - 80.0) < 1e-9 and abs(tie[3] + 304000.0) < 1e-6 and abs(tie[4] - 304000.0) < 1e-6, (scale, tie)
    assert not np.isnan(a).any()
    np.save(out, a)
    print("hash ok;", out, os.path.getsize(out), "bytes")      # the source file stays in data/reference/


if __name__ == "__main__":
    main()
