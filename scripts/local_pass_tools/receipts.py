"""Write a download receipt for data/reference: name, bytes, sha256, source URL.  python -I receipts.py <reference dir> <out.tsv>"""
import hashlib
import os
import sys

ref, out = sys.argv[1], sys.argv[2]
IMB = "https://imbrium.mit.edu/EXTRAS/ILLUMINATION/"
PDS = "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/"
PGDA = "https://pgda.gsfc.nasa.gov/data/"
URL = {
    "AVGVISIB_85S_060M_201608_EARTH.IMG": IMB + "IMG/", "AVGVISIB_85S_060M_201608_EARTH.LBL": IMB + "IMG/",
    "AVGVISIB_75S_120M_201608_EARTH.IMG": IMB + "IMG/", "AVGVISIB_75S_120M_201608_EARTH.LBL": IMB + "IMG/",
    "AVGVISIB_65S_240M_201608_EARTH.IMG": IMB + "IMG/", "AVGVISIB_65S_240M_201608_EARTH.LBL": IMB + "IMG/",
    "AVGVISIB_85S_060M_201608.LBL": IMB + "IMG/", "AVGVISIB_75S_120M_201608.LBL": IMB + "IMG/", "AVGVISIB_65S_240M_201608.LBL": IMB + "IMG/",
    "AVGVISIB_65S_240M_201608.JP2": IMB + "JP2/", "AVGVISIB_65S_240M_201608_JP2.LBL": IMB + "JP2/",
    "README_ILLUMINATION_2016.TXT": IMB,
    "AVGVISIB_85S_060M_201608.TIF": PGDA + "MoonIllumination/", "AVGVISIB_75S_120M_201608.TIF": PGDA + "MoonIllumination/",
    "LDEM_80S_80MPP_ADJ.TIF": PGDA + "LOLA_20mpp/",
    "LDEM_75S_240M.JP2": PDS + "polar/jp2/ldem_75s_240m.jp2", "LDEM_75S_240M_JP2.LBL": PDS + "polar/jp2/ldem_75s_240m_jp2.lbl",
    "LDEM_16.IMG": PDS + "cylindrical/img/ldem_16.img", "LDEM_16.LBL": PDS + "cylindrical/img/ldem_16.lbl",
    "ldem_64_uint.tif": "https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/",
    "ldem_64_uint_south_60S_90S.npy": "(derived here: rows 9600 to 11519 of ldem_64_uint.tif, scripts/prepare_dem.py)",
}
rows = []
for name in sorted(os.listdir(ref)):
    p = os.path.join(ref, name)
    if not os.path.isfile(p) or name in ("DOWNLOADS.tsv",):
        continue
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    u = URL.get(name, "?")
    if u.endswith("/"):
        u += name
    rows.append((name, os.path.getsize(p), h.hexdigest(), u))
with open(out, "w", newline="\n") as fh:
    fh.write("# Official files downloaded on 2026-11-14 by scripts/fetch_on_your_machine.sh and the commands in LOCAL_PASS_RESULTS.md\n")
    fh.write("file\tbytes\tsha256\tsource\n")
    for r in rows:
        fh.write("\t".join(str(x) for x in r) + "\n")
for r in rows:
    print(f"| `{r[0]}` | {r[1]:,} | `{r[2]}` | {r[3]} |")
print("total bytes", sum(r[1] for r in rows), "files", len(rows))
