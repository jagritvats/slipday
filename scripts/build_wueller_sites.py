"""Write data/regions/wueller2026_sites.json from the published shapefile of Wueller et al. 2026.

    python -I scripts/build_wueller_sites.py [path/to/Landing_Sites.zip]

Input: Landing_Sites.zip from Zenodo record 17084058 (CC BY 4.0; default path data/reference/wueller2026/).  The
zip holds a second zip; only LandingSites.dbf is read from it, in memory (nothing is unpacked).  Columns kept, with
their meaning from the paper (section 2.3, Table A2) and the dataset's READ_ME:
  Landing_Re  region code;  Name;  Latitude, Longitude (degrees);
  SunDaysYY   longest run of consecutive days with the Sun visible in the midsummer period of 20YY;
  SunEarthYY  the same for the Sun and the Earth both visible ("Sun_Earth2" is SunEarth25, the name cut short).
Columns whose meaning is not established are not copied (StereoX, StereoY, coldest_te, oldest_PSR, PSR_AREA).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import struct
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "reference", "wueller2026", "Landing_Sites.zip")
OUT = os.path.join(ROOT, "data", "regions", "wueller2026_sites.json")


def read_dbf(b: bytes) -> list:
    n, header_len, rec_len = struct.unpack("<IHH", b[4:12])
    fields, o = [], 32
    while b[o] != 0x0D:
        fields.append((b[o:o + 11].split(b"\0")[0].decode("ascii"), chr(b[o + 11]), b[o + 16]))
        o += 32
    rows, p = [], header_len
    for _ in range(n):
        r, q, d = b[p:p + rec_len], 1, {}
        p += rec_len
        if r[:1] == b"*":                     # deleted record
            continue
        for name, _t, ln in fields:
            d[name] = r[q:q + ln].decode("latin-1").replace(chr(0), "").strip()
            q += ln
        rows.append(d)
    return rows


def num(v: str):
    return int(v) if v else None              # empty (null) cells stay empty


def main(src: str = SRC):
    raw = open(src, "rb").read()
    inner = zipfile.ZipFile(io.BytesIO(zipfile.ZipFile(io.BytesIO(raw)).read("Landing_Sites.zip")))
    rows = read_dbf(inner.read("LandingSites.dbf"))
    key = {y: [k for k in rows[0] if k.lower() == f"sundays{y % 100:02d}"][0] for y in range(2025, 2033)}
    ekey = {y: ("Sun_Earth2" if y == 2025 else f"SunEarth{y % 100:02d}") for y in range(2025, 2033)}
    sites = []
    for r in rows:
        sites.append({"name": r["Name"], "region": r["Landing_Re"], "lat": round(float(r["Latitude"]), 6),
                      "lon": round(float(r["Longitude"]), 6),
                      "sun_days": {str(y): num(r[key[y]]) for y in key},
                      "sun_earth_days": {str(y): num(r[ekey[y]]) for y in ekey}})
    doc = {"source": "Wueller et al. 2026, JGR Planets 131(3) e2025JE009434; data: Zenodo record 17084058, Landing_Sites.zip "
                     "(LandingSites.dbf); CC BY 4.0",
           "zip_sha256": hashlib.sha256(raw).hexdigest(),
           "columns": {"sun_days": "longest run of consecutive days with the Sun visible in that year's midsummer period "
                                   "(QuickMap TerrainShadows, 60 m/pixel, 12-hour steps, 2 m above the surface)",
                       "sun_earth_days": "the same with the Sun and the Earth both visible"},
           "sites": sites}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(doc, open(OUT, "w", encoding="utf-8"), indent=1)
    print("wrote", OUT, len(sites), "sites")


if __name__ == "__main__":
    main(*sys.argv[1:])
