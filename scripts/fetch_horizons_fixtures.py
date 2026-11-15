"""Re-download the Horizons reference tables into fixtures/raw/: one added first line with the request
address, then the response as served.

Needs direct internet access to ssd.jpl.nasa.gov (not available in the build
sandbox, where the tables under fixtures/ were relayed through WebFetch).

Usage: python scripts/fetch_horizons_fixtures.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from slipday import horizons  # noqa: E402

CASES = [
    ("chandrayaan3", -69.37, 32.32, "2023-08-20", "2023-09-08"),
    ("im1", -80.13, 1.44, "2024-02-16", "2024-03-04"),
    ("blueghost1", 18.56, 61.81, "2025-03-01", "2025-03-18"),
]


def main():
    out = os.path.join(os.path.dirname(__file__), "..", "fixtures", "raw")
    os.makedirs(out, exist_ok=True)
    for name, lat, lon, start, stop in CASES:
        for target in ("sun", "earth"):
            url, text = horizons.fetch(target, lat, lon, start, stop, "12h")
            path = os.path.join(out, f"horizons_{target}_{name}.txt")
            # newline="" keeps the response's own line ends: text mode on Windows would turn LF into CRLF
            with open(path, "w", newline="", encoding="utf-8") as fh:
                fh.write(f"# URL: {url}\n{text}")
            print(path, len(horizons.parse_table(text)), "rows")


if __name__ == "__main__":
    main()
