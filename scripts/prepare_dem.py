"""Turn the official LOLA files into the grids Slipday reads at run time.

    python3 scripts/prepare_dem.py /path/to/folder/with/the/NASA/files

Reads (data only; nothing in that folder is executed):
    LDEM_80S_80MPP_ADJ.TIF           LOLA south-pole 80 m mosaic (NASA GSFC PGDA)
    LDEM_75S_240M.JP2                PDS LOLA GDR south-polar DEM, 240 m, to 75S
    ldem_64_uint.tif                 NASA SVS CGI Moon Kit whole-Moon grid (LOLA), optional; cropped here to 60S-90S
    ldem_64_uint_south_60S_90S.npy   that crop, if the 531 MB source file is not kept (optional)
    LDEM_16.IMG                      PDS LOLA GDR LDEM_16 (global, 16 px/deg)
    AVGVISIB_75S_120M_201608.TIF     LOLA team average solar visibility (reference map), optional
    AVGVISIB_85S_060M_201608.TIF     same at 60 m, optional

Writes into data/dem/:
    ldem_80s_80m_f32.npy      the 80 m mosaic, values unchanged (float32 metres), memory-mappable; 231 MB, not for git
    ldem_75s_240m_i16.npy     PDS LDEM_75S_240M decoded from JPEG2000, values unchanged (int16 half-metres); 29 MB
    ldem_64_south.npy         hard link or copy of the 64 px/deg crop
    LDEM_16.IMG               hard link or copy
    avgvis_80s_480m_u8.npy    DERIVED for the map layer only: 4x4 block mean of AVGVISIB_75S_120M, 0..250 = 0..100 %
    dems.json                 the layout of each grid for slipday/demstore.py

Needs tifffile and imagecodecs (the mosaic uses deflate with a floating-point predictor; the PDS grid is JPEG2000).
"""
import hashlib
import json
import os
import shutil
import sys

import numpy as np


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def link_or_copy(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def main(src, out):
    import tifffile
    os.makedirs(out, exist_ok=True)
    dems = []
    notes = {}

    p80 = os.path.join(src, "LDEM_80S_80MPP_ADJ.TIF")
    if os.path.exists(p80):
        with tifffile.TiffFile(p80) as t:
            pg = t.pages[0]
            scale = pg.tags["ModelPixelScaleTag"].value
            tie = pg.tags["ModelTiepointTag"].value
            a = pg.asarray()
        assert a.shape == (7600, 7600) and a.dtype == np.float32, (a.shape, a.dtype)
        assert abs(scale[0] - 80.0) < 1e-9 and abs(tie[3] + 304000.0) < 1e-6 and abs(tie[4] - 304000.0) < 1e-6, (scale, tie)
        assert not np.isnan(a).any()
        np.save(os.path.join(out, "ldem_80s_80m_f32.npy"), a)
        digest = sha256(p80)
        dems.append({
            "name": "ldem_80s_80m", "kind": "polar_stereo", "path": "ldem_80s_80m_f32.npy", "format": "npy",
            "pole": -1, "pixel_m": 80.0, "x0_m": -304000.0 + 40.0, "y0_m": 304000.0 - 40.0,
            "scale": 1.0, "offset": 0.0, "nodata": None, "source": "LOLA", "product": "LDEM_80S_80MPP_ADJ",
            "provenance": "LDEM_80S_80MPP_ADJ.TIF, LOLA south-pole 80 m mosaic, NASA GSFC PGDA product 90 (Barker et al. 2023); "
                          f"values unchanged, re-saved as .npy; source sha256 {digest[:16]}"})
        notes["ldem_80s_80m"] = {"min_m": float(a.min()), "max_m": float(a.max()), "sha256_source": digest}
        del a

    p240 = os.path.join(src, "LDEM_75S_240M.JP2")
    if os.path.exists(p240):
        import imagecodecs
        a = imagecodecs.imread(p240)
        assert a.shape == (3812, 3812) and a.dtype == np.int16, (a.shape, a.dtype)
        np.save(os.path.join(out, "ldem_75s_240m_i16.npy"), a)
        dems.append({
            "name": "ldem_75s_240m", "kind": "polar_stereo", "path": "ldem_75s_240m_i16.npy", "format": "npy",
            "pole": -1, "pixel_m": 240.0, "x0_m": -457440.0 + 120.0, "y0_m": 457440.0 - 120.0,
            "scale": 0.5, "offset": 0.0, "nodata": None, "source": "LOLA", "product": "LDEM_75S_240M (PDS GDR)",
            "provenance": "LDEM_75S_240M.JP2, PDS LRO-L-LOLA-4-GDR-V1.0 south-polar DEM to 75S; JPEG2000 decoded, "
                          f"values unchanged (int16 half-metres), re-saved as .npy; source sha256 {sha256(p240)[:16]}"})
        del a

    p64 = os.path.join(src, "ldem_64_uint_south_60S_90S.npy")
    p64_full = os.path.join(src, "ldem_64_uint.tif")
    full_digest = None
    if os.path.exists(p64_full):
        # the whole-Moon NASA SVS file is here: make the 60S-90S crop from it (rows 9600 to 11519, no resampling)
        full = tifffile.imread(p64_full, key=0)
        assert full.shape == (11520, 23040) and full.dtype == np.uint16, (full.shape, full.dtype)
        crop = np.ascontiguousarray(full[9600:11520, :])
        if not (os.path.exists(p64) and np.array_equal(np.load(p64, mmap_mode="r"), crop)):
            np.save(p64, crop)
        full_digest = sha256(p64_full)
        del full, crop
    if os.path.exists(p64):
        link_or_copy(p64, os.path.join(out, "ldem_64_south.npy"))
        dems.append({
            "name": "ldem_64_south", "kind": "equirect", "path": "ldem_64_south.npy", "format": "npy",
            "ppd": 64.0, "lat0": -60.0 - 0.5 / 64.0, "lon0": -180.0 + 0.5 / 64.0,
            "scale": 0.5, "offset": -10000.0, "nodata": None, "source": "LOLA", "product": "SVS CGI Moon Kit ldem_64_uint",
            "provenance": "60S-90S crop (rows 9600 to 11519, no resampling) of NASA SVS CGI Moon Kit ldem_64_uint.tif "
                          f"(LOLA, svs.gsfc.nasa.gov/4720); sha256 of the crop {sha256(p64)[:16]}"
                          + (f", of the source file {full_digest[:16]}" if full_digest else "")})
        if full_digest:
            notes["ldem_64_south"] = {"sha256_source": full_digest, "sha256_crop": sha256(p64)}

    p16 = os.path.join(src, "LDEM_16.IMG")
    if os.path.exists(p16):
        assert os.path.getsize(p16) == 2880 * 5760 * 2
        link_or_copy(p16, os.path.join(out, "LDEM_16.IMG"))
        dems.append({
            "name": "ldem_16", "kind": "equirect", "path": "LDEM_16.IMG", "format": "raw", "dtype": "<i2",
            "shape": [2880, 5760], "header_bytes": 0, "ppd": 16.0, "lat0": 90.0 - 0.5 / 16.0, "lon0": 0.5 / 16.0,
            "scale": 0.5, "offset": 0.0, "nodata": None, "source": "LOLA", "product": "LDEM_16 (PDS GDR V3.1)",
            "provenance": f"LDEM_16.IMG, PDS LRO-L-LOLA-4-GDR-V1.0 product LDEM_16; sha256 {sha256(p16)[:16]}"})

    layers = {}
    pv = os.path.join(src, "AVGVISIB_75S_120M_201608.TIF")
    if os.path.exists(pv):
        v = tifffile.imread(pv, key=0)
        assert v.shape == (7624, 7624) and v.dtype == np.int16
        # crop to the 80S square (+/-304 km) and average 4x4 blocks -> 480 m
        half = 304000.0
        c0 = int(round((-half + 457440.0) / 120.0))
        c1 = int(round((half + 457440.0) / 120.0))
        crop = v[c0:c1, c0:c1].astype(np.float32) * 4e-5
        n = crop.shape[0] // 4
        m = crop[:n * 4, :n * 4].reshape(n, 4, n, 4).mean(axis=(1, 3))
        np.save(os.path.join(out, "avgvis_80s_480m_u8.npy"), np.clip(np.round(m * 250.0), 0, 250).astype(np.uint8))
        layers["avgvis"] = {
            "path": "avgvis_80s_480m_u8.npy", "pixel_m": 480.0, "x0_m": -half + 240.0, "y0_m": half - 240.0,
            "scale": 1.0 / 250.0, "label": "average solar visibility, LOLA team map AVGVISIB_75S_120M_201608 "
                                            "(Mazarico et al.), shown at 480 m",
            "provenance": "DERIVED for display from AVGVISIB_75S_120M_201608.TIF: cropped to 80S, 4x4 block mean"}

    with open(os.path.join(out, "dems.json"), "w") as fh:
        json.dump({"note": "written by scripts/prepare_dem.py; paths are relative to this folder",
                   "dems": dems, "layers": layers, "source_notes": notes}, fh, indent=1)
    for d in dems:
        p = os.path.join(out, d["path"])
        print(f"{d['name']:16s} {os.path.getsize(p):>11d} bytes  {d['provenance'][:90]}")
    for k, d in layers.items():
        print(f"layer {k:10s} {os.path.getsize(os.path.join(out, d['path'])):>11d} bytes")


if __name__ == "__main__":
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "data", "dem"))
