"""Compare slipday.stations.moon_elevation_deg with saved JPL Horizons tables.

Offline: reads fixtures/stations/horizons_moon_<complex>_<date>.txt (raw
Horizons API responses, observer tables of the Moon's airless apparent azimuth
and elevation from DSS-14, DSS-63 and DSS-43; fixtures/stations/SOURCES.md has
the URLs and sha256) and prints, per complex, the number of rows and the
largest and mean absolute elevation difference in degrees.

    .venv\\Scripts\\python.exe scripts\\check_stations_horizons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from slipday import stations  # noqa: E402
from slipday.horizons import parse_table  # noqa: E402

FIXTURES = ROOT / "fixtures" / "stations"
TAGS = ("2026nov", "2034jun")


def load(complex_id: str, tag: str) -> np.ndarray:
    """Rows (unix seconds UTC, azimuth deg, elevation deg) of one saved response."""
    text = (FIXTURES / f"horizons_moon_{complex_id}_{tag}.txt").read_text(encoding="utf-8")
    rows = parse_table(text)
    if not rows:
        raise RuntimeError(f"no data rows in the {complex_id} {tag} fixture")
    return np.array(rows, dtype=float)


def compare() -> list[dict]:
    """One dict per complex: rows, largest and mean absolute difference (degrees)."""
    out = []
    for i, c in enumerate(stations.COMPLEXES):
        diffs, per_tag = [], {}
        for tag in TAGS:
            rows = load(c["id"], tag)
            d = stations.moon_elevation_deg(rows[:, 0])[i] - rows[:, 2]
            diffs.append(d)
            per_tag[tag] = {"rows": int(d.size), "max_abs_deg": float(np.abs(d).max()),
                            "mean_abs_deg": float(np.abs(d).mean())}
        d = np.concatenate(diffs)
        out.append({"id": c["id"], "antenna": c["antenna"], "rows": int(d.size),
                    "max_abs_deg": float(np.abs(d).max()), "mean_abs_deg": float(np.abs(d).mean()),
                    "per_date": per_tag})
    return out


def main() -> int:
    print("Moon elevation, slipday.stations minus JPL Horizons (airless apparent), degrees")
    print(f"{'complex':10s} {'antenna':14s} {'rows':>5s} {'largest':>10s} {'mean':>10s}")
    worst = 0.0
    for r in compare():
        print(f"{r['id']:10s} {r['antenna']:14s} {r['rows']:5d} {r['max_abs_deg']:10.5f} {r['mean_abs_deg']:10.5f}")
        for tag, p in r["per_date"].items():
            print(f"{'':10s} {tag:14s} {p['rows']:5d} {p['max_abs_deg']:10.5f} {p['mean_abs_deg']:10.5f}")
        worst = max(worst, r["max_abs_deg"])
    print(f"largest difference over all complexes: {worst:.5f} deg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
