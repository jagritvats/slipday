"""Add a 'verified against a direct download' line to each relayed Horizons fixture header.

    python mark_fixtures.py <entry root>

Only adds the line when every row of the fixture equals the directly downloaded table in fixtures/raw/.
"""
import glob
import os
import sys

root = sys.argv[1]
sys.path.insert(0, root)
from slipday import horizons  # noqa: E402

MARK = "# Verified 2026-11-14 on a machine with direct access to ssd.jpl.nasa.gov:"
for path in sorted(glob.glob(os.path.join(root, "fixtures", "horizons_*.csv"))):
    raw = os.path.join(root, "fixtures", "raw", os.path.basename(path)[:-4] + ".txt")
    with open(path, newline="") as fh:
        text = fh.read()
    with open(raw) as fh:
        direct = horizons.parse_table(fh.read())
    relayed = horizons.parse_table(text)
    if MARK in text or direct != relayed:
        print("skipped", os.path.basename(path), "already marked" if MARK in text else "ROWS DIFFER")
        continue
    nl = "\r\n" if "\r\n" in text else "\n"
    anchor = "# columns:"
    i = text.index(anchor)
    line = (f"{MARK} all {len(direct)} rows equal the table downloaded directly with{nl}"
            f"# scripts/fetch_horizons_fixtures.py (raw response in fixtures/raw/{os.path.basename(raw)}).{nl}")
    with open(path, "w", newline="") as fh:
        fh.write(text[:i] + line + text[i:])
    print("marked", os.path.basename(path), len(direct), "rows")
