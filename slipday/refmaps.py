"""Readers for the LOLA team's polar reference maps (average Sun or Earth visibility).

Three containers are handled, because the same product is served in all three:
  GeoTIFF          (PGDA product 69): georeferencing from the TIFF tags
  PDS .IMG + .LBL  (imbrium.mit.edu, PDS Geosciences): raw samples, layout from the label
  PDS .JP2 + .LBL  JPEG2000 with the same label keywords

All are south polar stereographic on the 1737.4 km sphere, true scale at the pole, longitude 0
up.  ``RefMap.nearest`` reads the map at the nearest pixel and refuses points outside it.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .dem import MOON_RADIUS_M


@dataclass
class RefMap:
    path: str
    z: np.ndarray
    pixel_m: float
    x0_m: float            # projected x of the centre of pixel (0, 0)
    y0_m: float            # projected y of the centre of pixel (0, 0)
    scale: float
    offset: float = 0.0
    description: str = ""
    product_id: str = ""

    def nearest(self, lat, lon) -> np.ndarray:
        lat = np.asarray(lat, dtype=float)
        lon = np.deg2rad(np.asarray(lon, dtype=float))
        r = 2.0 * MOON_RADIUS_M * np.tan(np.pi / 4 - np.deg2rad(np.abs(lat)) / 2)
        x, y = r * np.sin(lon), r * np.cos(lon)
        col = np.round((x - self.x0_m) / self.pixel_m).astype(int)
        row = np.round((self.y0_m - y) / self.pixel_m).astype(int)
        ok = (row >= 0) & (row < self.z.shape[0]) & (col >= 0) & (col < self.z.shape[1])
        out = np.full(lat.shape, np.nan)
        out[ok] = self.z[row[ok], col[ok]].astype(float) * self.scale + self.offset
        return out


def _clean(text: str) -> str:
    import html
    return html.unescape(html.unescape(text)).strip().strip('"').strip()


def parse_label(text: str) -> dict:
    """KEY = VALUE pairs of a PDS3 label (first occurrence wins; units and quotes stripped)."""
    out: dict = {}
    for m in re.finditer(r"^\s*\^?([A-Z_]+)\s*=\s*(.+?)\s*$", text, flags=re.M):
        key, val = m.group(1), m.group(2)
        if key in out:
            continue
        val = re.sub(r"<[^>]*>", "", val).strip().strip('"').strip("'")
        out[key] = val
    d = re.search(r"^DESCRIPTION\s*=\s*\"(.*?)\"", text, flags=re.M | re.S)
    if d:
        out["DESCRIPTION"] = " ".join(d.group(1).split())
    return out


def _label_for(path: str) -> Optional[str]:
    stem = os.path.splitext(path)[0]
    folder = os.path.dirname(path) or "."
    want = {os.path.basename(stem).lower() + e for e in (".lbl", "_jp2.lbl", "_img.lbl")}
    for name in os.listdir(folder):
        if name.lower() in want:
            return os.path.join(folder, name)
    return None


def _from_label(path: str, read_samples) -> RefMap:
    lbl = _label_for(path)
    if lbl is None:
        raise ValueError(f"{os.path.basename(path)} needs its PDS label (.LBL) beside it")
    with open(lbl, errors="replace") as fh:
        kv = parse_label(fh.read())
    lines, samples = int(kv["LINES"]), int(kv["LINE_SAMPLES"])
    z = read_samples(kv, lines, samples)
    if z.shape != (lines, samples):
        raise ValueError(f"{os.path.basename(path)}: {z.shape} samples, label says {(lines, samples)}")
    px = float(kv["MAP_SCALE"]) * (1000.0 if float(kv["MAP_SCALE"]) < 1.0 else 1.0)     # km/pix in some labels
    return RefMap(path=path, z=z, pixel_m=px, x0_m=-float(kv["SAMPLE_PROJECTION_OFFSET"]) * px,
                  y0_m=float(kv["LINE_PROJECTION_OFFSET"]) * px, scale=float(kv.get("SCALING_FACTOR", 1.0)),
                  offset=float(kv.get("OFFSET", 0.0)), description=kv.get("DESCRIPTION", ""),
                  product_id=kv.get("PRODUCT_ID", ""))


def _img_samples(path):
    def read(kv, lines, samples):
        bits = int(kv.get("SAMPLE_BITS", 16))
        st = kv.get("SAMPLE_TYPE", "LSB_INTEGER").upper()
        if "REAL" in st:
            dt = np.dtype(("<" if "PC" in st or "LSB" in st else ">") + f"f{bits // 8}")
        else:
            dt = np.dtype(("<" if "LSB" in st or "PC" in st else ">") + ("u" if "UNSIGNED" in st else "i") + str(bits // 8))
        size = os.path.getsize(path)
        header = size - lines * samples * dt.itemsize          # attached label records, if any
        if header < 0:
            raise ValueError(f"{os.path.basename(path)} is too short for {lines} x {samples} samples")
        return np.memmap(path, dtype=dt, mode="r", offset=header, shape=(lines, samples))
    return read


def load(path: str) -> RefMap:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".tif", ".tiff"):
        import tifffile
        with tifffile.TiffFile(path) as tf:
            page = tf.pages[0]
            z = page.asarray()
            scale = page.tags["ModelPixelScaleTag"].value
            tie = page.tags["ModelTiepointTag"].value
            meta = page.tags["GDAL_METADATA"].value if "GDAL_METADATA" in page.tags else ""
        px = float(scale[0])
        m = re.search(r'name="SCALING_FACTOR"[^>]*>([^<]+)<', meta) or re.search(r'role="scale"[^>]*>([^<]+)<', meta)
        d = re.search(r'name="DESCRIPTION"[^>]*>([^<]+)<', meta)
        pid = re.search(r'name="PRODUCT_ID"[^>]*>([^<]+)<', meta)
        # tie point: raster (i, j) -> model (x, y) of the pixel's outer corner
        x_corner, y_corner = float(tie[3]) - float(tie[0]) * px, float(tie[4]) + float(tie[1]) * px
        return RefMap(path=path, z=z, pixel_m=px, x0_m=x_corner + px / 2, y0_m=y_corner - px / 2,
                      scale=float(m.group(1)) if m else 4e-5, description=" ".join(_clean(d.group(1)).split()) if d else "",
                      product_id=_clean(pid.group(1)) if pid else "")
    if ext == ".img":
        return _from_label(path, _img_samples(path))
    if ext == ".jp2":
        def read(kv, lines, samples):
            import imagecodecs
            with open(path, "rb") as fh:
                return imagecodecs.jpeg2k_decode(fh.read())
        return _from_label(path, read)
    raise ValueError(f"unsupported reference map format: {path}")


def find(folder: str, region: str, earth: bool) -> Optional[str]:
    """Path of the map for ``region`` (e.g. '85S_060M') in ``folder``; the Earth version when asked.

    Matching ignores case; GeoTIFF is preferred, then IMG, then JP2."""
    hits = []
    for p in glob.glob(os.path.join(folder, "*")):
        name = os.path.basename(p).upper()
        ext = os.path.splitext(name)[1]
        if "AVGVISIB" in name and region.upper() in name and ("EARTH" in name) == earth \
                and ext in (".TIF", ".TIFF", ".IMG", ".JP2"):
            hits.append((["." + e for e in ("TIF", "TIFF", "IMG", "JP2")].index(ext), p))
    return sorted(hits)[0][1] if hits else None
