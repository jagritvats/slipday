"""Compare Slipday az/el with the JPL Horizons tables saved under fixtures/.

Usage: python scripts/compare_horizons.py
"""
import glob
import os
import re
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from slipday.ephem import compute_table  # noqa: E402
from slipday.geometry import Site, track  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def load_fixture(path):
    meta, rows = {}, []
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                m = re.search(r"Target: (\w+).*E-lon ([-\d.]+) deg, lat ([-\d.]+) deg", line)
                if m:
                    meta = {"target": m.group(1).lower(), "lon": float(m.group(2)), "lat": float(m.group(3))}
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                continue
            t = datetime.strptime(parts[0], "%Y-%b-%d %H:%M").replace(tzinfo=timezone.utc)
            rows.append((t.timestamp(), float(parts[1]), float(parts[2])))
    return meta, np.array(rows)


def compare(path, orientation="de421"):
    meta, rows = load_fixture(path)
    tr = track(Site("fixture", meta["lat"], meta["lon"]), compute_table(rows[:, 0], orientation=orientation))
    az = tr.sun_az if meta["target"] == "sun" else tr.earth_az
    el = tr.sun_el if meta["target"] == "sun" else tr.earth_el
    d_az = (az - rows[:, 1] + 180.0) % 360.0 - 180.0
    d_el = el - rows[:, 2]
    # azimuth error expressed on the sky (scaled by cos elevation)
    return {"file": os.path.basename(path), "rows": len(rows), "target": meta["target"],
            "max_abs_el": float(np.abs(d_el).max()), "max_abs_az": float(np.abs(d_az).max()),
            "max_abs_az_sky": float(np.abs(d_az * np.cos(np.deg2rad(rows[:, 2]))).max()),
            "rms_el": float(np.sqrt((d_el ** 2).mean()))}


def main():
    paths = sorted(glob.glob(os.path.join(FIX, "horizons_*.csv")))
    for orientation in ("de421", "iau2009"):
        results = [compare(p, orientation) for p in paths]
        print(f"orientation model: {orientation}")
        print(f"  {'fixture':34s} rows  max|dEl| deg  max|dAz| deg  rms dEl deg")
        for r in results:
            print(f"  {r['file']:34s} {r['rows']:4d}  {r['max_abs_el']:12.2e}  {r['max_abs_az']:12.2e}  {r['rms_el']:11.2e}")
        print(f"  overall: {sum(r['rows'] for r in results)} rows, max|dEl| = {max(r['max_abs_el'] for r in results):.2e} deg, "
              f"max|dAz| = {max(r['max_abs_az'] for r in results):.2e} deg")


if __name__ == "__main__":
    main()
