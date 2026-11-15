"""Accuracy against JPL Horizons tables saved under fixtures/, plus the client's parser."""
import glob
import os
import re

import pytest

from slipday import horizons
from slipday.geometry import Site

FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures")
PATHS = sorted(glob.glob(os.path.join(FIX, "horizons_*.csv")))


def _load(path):
    text = open(path).read()
    m = re.search(r"Target: (\w+).*E-lon ([-\d.]+) deg, lat ([-\d.]+) deg", text)
    return m.group(1).lower(), float(m.group(3)), float(m.group(2)), horizons.parse_table(text)


def test_fixtures_present():
    assert len(PATHS) == 6


@pytest.mark.parametrize("path", PATHS, ids=[os.path.basename(p) for p in PATHS])
def test_matches_horizons_with_de421_orientation(path):
    target, lat, lon, rows = _load(path)
    assert len(rows) >= 35
    res = horizons.compare_rows(Site("fx", lat, lon), target, rows, "de421")
    print(f"{os.path.basename(path)}: max|dEl|={res['max_abs_el_deg']:.2e} deg, max|dAz|={res['max_abs_az_deg']:.2e} deg")
    assert res["max_abs_el_deg"] < 1e-3
    assert res["max_abs_az_deg"] < 1e-3


@pytest.mark.parametrize("path", PATHS, ids=[os.path.basename(p) for p in PATHS])
def test_iau2009_series_is_within_a_hundredth_of_a_degree(path):
    target, lat, lon, rows = _load(path)
    res = horizons.compare_rows(Site("fx", lat, lon), target, rows, "iau2009")
    assert res["max_abs_el_deg"] < 0.01
    assert res["max_abs_az_deg"] < 0.01


def test_parser_reads_native_csv_layout():
    # Synthetic sample in the layout the Horizons documentation describes for CSV observer
    # tables (date, solar-presence flag, lunar-presence flag, azimuth, elevation). Not a captured response.
    text = """header
$$SOE
 2023-Aug-20 00:00, , , 102.618968,  -6.173406,
 2023-Aug-21 12:00,*,m,  85.412815,   0.273599,
$$EOE
footer 2023-Aug-22 00:00, 1, 2,
"""
    rows = horizons.parse_table(text)
    assert len(rows) == 2
    assert rows[0][1:] == (102.618968, -6.173406)
    assert rows[1][0] - rows[0][0] == 36 * 3600


def test_url_builder():
    url = horizons.build_url("earth", -69.37, 32.32, "2023-08-20", "2023-09-08", "12h")
    assert url.startswith("https://ssd.jpl.nasa.gov/api/horizons.api?format=text")
    assert "COMMAND='399'" in url and "CENTER='coord@301'" in url
    assert "SITE_COORD='32.320000,-69.370000,0.0000'" in url and "QUANTITIES='4'" in url


def test_crosscheck_is_off_by_default(monkeypatch):
    monkeypatch.delenv("SLIPDAY_HORIZONS", raising=False)
    assert not horizons.enabled()
    with pytest.raises(RuntimeError):
        horizons.crosscheck(Site("s", 0, 0), "2026-01-01", "2026-01-02")
