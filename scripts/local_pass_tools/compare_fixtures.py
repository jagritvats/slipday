"""Are the relayed Horizons fixtures the rows JPL serves?  python compare_fixtures.py <entry root>

Compares fixtures/horizons_*.csv (relayed through a web-fetch tool in the build sandbox) with
fixtures/raw/horizons_*.txt (downloaded directly by scripts/fetch_horizons_fixtures.py), row by row,
and reports the model's largest difference from the directly downloaded tables.
"""
import glob
import hashlib
import os
import sys

root = sys.argv[1]
sys.path.insert(0, root)
from slipday import horizons  # noqa: E402
from slipday.geometry import Site  # noqa: E402

COORDS = {"chandrayaan3": (-69.37, 32.32), "im1": (-80.13, 1.44), "blueghost1": (18.56, 61.81)}
worst_el = worst_az = 0.0
total = same = 0
for raw in sorted(glob.glob(os.path.join(root, "fixtures", "raw", "horizons_*.txt"))):
    name = os.path.basename(raw)[:-4]
    target, site = name.split("_")[1], name.split("_")[2]
    with open(raw) as fh:
        text = fh.read()
    r_raw = horizons.parse_table(text)
    with open(os.path.join(root, "fixtures", name + ".csv")) as fh:
        r_rel = horizons.parse_table(fh.read())
    n_same = sum(1 for a, b in zip(r_raw, r_rel) if a == b)
    lat, lon = COORDS[site]
    res = horizons.compare_rows(Site(site, lat, lon), target, r_raw)
    worst_el, worst_az = max(worst_el, res["max_abs_el_deg"]), max(worst_az, res["max_abs_az_deg"])
    total += len(r_raw)
    same += n_same
    sha = hashlib.sha256(open(raw, "rb").read()).hexdigest()
    print(f"{name}: direct rows {len(r_raw)}, relayed rows {len(r_rel)}, identical {n_same}; model vs direct: "
          f"max |dEl| {res['max_abs_el_deg']:.2e} deg, max |dAz| {res['max_abs_az_deg']:.2e} deg; raw bytes {os.path.getsize(raw)}, sha256 {sha[:16]}")
print(f"TOTAL direct rows {total}, identical to the relayed fixture rows {same}; model vs direct max |dEl| {worst_el:.3e} deg, max |dAz| {worst_az:.3e} deg")
