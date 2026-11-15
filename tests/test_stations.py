"""Deep Space Network view of the Moon (slipday.stations).

Runs offline.  The JPL Horizons tables are the raw API responses saved under
fixtures/stations/ (URLs and sha256 in fixtures/stations/SOURCES.md).
"""
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from slipday import stations
from slipday.horizons import parse_table

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "stations"
TAGS = ("2026nov", "2034jun")

# Largest difference measured against Horizons on 2026-11-15: 0.00060 degrees
# (Goldstone, June 2034).  The tolerance is twice that.
HORIZONS_TOL_DEG = 0.0012


def _year(year: int) -> np.ndarray:
    a = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp())
    b = int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp())
    return np.arange(a, b, 3600, dtype=float)


def _fixture_text(complex_id: str, tag: str) -> str:
    return (FIXTURES / f"horizons_moon_{complex_id}_{tag}.txt").read_text(encoding="utf-8")


YEARS = {y: _year(y) for y in (2027, 2034, 2043)}


# ---------------------------------------------------------------- inputs

def test_complexes_are_goldstone_madrid_canberra_with_cited_coordinates():
    assert [c["id"] for c in stations.COMPLEXES] == ["goldstone", "madrid", "canberra"]
    keys = {"id", "name", "antenna", "lat_deg", "lon_deg", "height_m", "source", "source_url"}
    for c in stations.COMPLEXES:
        assert keys <= set(c)
        assert -90 < c["lat_deg"] < 90 and -180 < c["lon_deg"] <= 180
        assert c["source_url"].startswith("https://deepspace.jpl.nasa.gov/")
        assert "810-005" in c["source"]
    g, m, cb = stations.COMPLEXES
    assert g["lat_deg"] > 0 and g["lon_deg"] < -100          # California, west
    assert m["lat_deg"] > 0 and -10 < m["lon_deg"] < 0       # Spain, just west of Greenwich
    assert cb["lat_deg"] < 0 and cb["lon_deg"] > 140         # Australia, south and east


@pytest.mark.parametrize("index", [0, 1, 2])
def test_coordinates_match_the_site_line_in_the_horizons_header(index):
    """Horizons prints the geodetic position of its own DSS-14/63/43 sites;
    the handbook figures used here must be the same place."""
    c = stations.COMPLEXES[index]
    text = _fixture_text(c["id"], "2026nov")
    number = c["antenna"].split()[1]                          # "14", "63", "43"
    assert re.search(rf"Center-site name: DSS-{number} \(70-m\)", text)
    m = re.search(r"Center geodetic\s*:\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)", text)
    elon, lat, alt_km = (float(x) for x in m.groups())
    assert c["lon_deg"] % 360.0 == pytest.approx(elon, abs=2e-7)
    assert c["lat_deg"] == pytest.approx(lat, abs=2e-7)
    assert c["height_m"] == pytest.approx(alt_km * 1000.0, abs=0.01)


def test_station_cartesian_position_matches_handbook_table_2():
    """810-005 module 301 Rev. P, Table 2 (Cartesian, ITRF93, metres), read in
    the same PDF as the geodetic Table 5: the two must describe one point."""
    table2_m = np.array([
        [-2353621.420, -4641341.472, +3677052.318],   # DSS 14
        [+4849092.518, -360180.3480, +4115109.251],   # DSS 63
        [-4460894.917, +2682361.507, -3674748.152],   # DSS 43
    ])
    assert np.abs(stations.station_ecef_km() * 1000.0 - table2_m).max() < 0.05


def test_mask_constants_and_describe():
    assert isinstance(stations.MASK_DEG, float) and stations.MASK_DEG == 10.0
    assert stations.MASK_CITED is True
    assert "10.0 degrees for low-power transmit" in stations.MASK_SOURCE
    assert stations.MASK_URL.startswith("https://deepspace.jpl.nasa.gov/dsndocs/810-005/")
    d = stations.describe()
    assert [c["id"] for c in d["complexes"]] == ["goldstone", "madrid", "canberra"]
    assert d["mask_deg"] == stations.MASK_DEG and d["mask_cited"] is True
    assert d["mask_source"] == stations.MASK_SOURCE and d["mask_url"] == stations.MASK_URL
    assert "at or above 10 degrees at one or more of the three" in d["rule"]
    d["complexes"][0]["lat_deg"] = 0.0                        # a copy, not the module's own list
    assert stations.COMPLEXES[0]["lat_deg"] != 0.0


# ------------------------------------------------------- Horizons agreement

@pytest.mark.parametrize("index", [0, 1, 2])
def test_elevation_agrees_with_jpl_horizons(index):
    c = stations.COMPLEXES[index]
    diffs = []
    for tag in TAGS:
        rows = np.array(parse_table(_fixture_text(c["id"], tag)), dtype=float)
        assert len(rows) == 49                                # 48 hours, both ends
        assert np.all(np.diff(rows[:, 0]) == 3600.0)
        diffs.append(stations.moon_elevation_deg(rows[:, 0])[index] - rows[:, 2])
    d = np.abs(np.concatenate(diffs))
    assert d.size == 98
    assert d.max() < HORIZONS_TOL_DEG
    assert d.mean() < HORIZONS_TOL_DEG / 2


def test_horizons_rows_would_expose_a_wrong_longitude_sign():
    """The check has teeth: Goldstone's table does not fit Madrid's or Canberra's site."""
    rows = np.array(parse_table(_fixture_text("goldstone", "2026nov")), dtype=float)
    el = stations.moon_elevation_deg(rows[:, 0])
    assert np.abs(el[1] - rows[:, 2]).max() > 10.0
    assert np.abs(el[2] - rows[:, 2]).max() > 10.0


# ------------------------------------------------------------ interface

def test_shapes_and_dtypes():
    u = YEARS[2027][:500]
    el = stations.moon_elevation_deg(u)
    assert el.shape == (3, 500) and el.dtype == np.float64
    assert np.all(np.isfinite(el)) and el.min() > -90 and el.max() < 90
    iv = stations.in_view(u)
    assert iv.shape == (3, 500) and iv.dtype == np.bool_
    av = stations.any_in_view(u)
    assert av.shape == (500,) and av.dtype == np.bool_
    car = stations.carrier(u)
    assert car.shape == (500,) and car.dtype == np.int8
    assert stations.moon_elevation_deg(float(u[0])).shape == (3, 1)     # a single instant
    assert stations.carrier(int(u[0])).shape == (1,)
    assert stations.moon_elevation_deg(np.array([])).shape == (3, 0)
    assert stations.carrier(np.array([])).shape == (0,)


def test_default_mask_is_the_module_mask_and_a_lower_mask_only_adds_hours():
    u = YEARS[2034]
    el = stations.moon_elevation_deg(u)
    assert np.array_equal(stations.in_view(u), el >= stations.MASK_DEG)
    assert np.array_equal(stations.in_view(u), stations.in_view(u, stations.MASK_DEG))
    low, high = stations.in_view(u, 6.0), stations.in_view(u, 10.0)
    assert np.all(low[high]) and low.sum() > high.sum()
    assert np.array_equal(stations.any_in_view(u, 6.0), low.any(axis=0))


@pytest.mark.parametrize("year", [2027, 2034, 2043])
def test_carrier_is_minus_one_exactly_where_nothing_is_in_view(year):
    u = YEARS[year]
    for mask in (None, 6.0, 25.0):
        car, av, iv = stations.carrier(u, mask), stations.any_in_view(u, mask), stations.in_view(u, mask)
        assert np.array_equal(car == -1, ~av)
        assert set(np.unique(car)) <= {-1, 0, 1, 2}
        seen = car >= 0
        cols = np.flatnonzero(seen)
        assert np.all(iv[car[seen], cols])                    # the carrier itself is in view
        el = stations.moon_elevation_deg(u)
        assert np.array_equal(el[car[seen], cols], el[:, seen].max(axis=0))   # and stands highest


def test_irregular_times_match_the_grid_and_the_cache_is_not_corrupted_by_callers():
    u = YEARS[2027][:240]
    el = stations.moon_elevation_deg(u)
    order = np.random.default_rng(7).permutation(u.size)
    assert np.allclose(stations.moon_elevation_deg(u[order]), el[:, order], atol=1e-12)
    el[:] = 99.0                                              # scribble on the returned array
    again = stations.moon_elevation_deg(u)
    assert again.max() < 90.0
    assert not stations.in_view(u).all()


def test_times_outside_the_ephemeris_are_refused():
    with pytest.raises(ValueError):
        stations.moon_elevation_deg(datetime(2060, 1, 1, tzinfo=timezone.utc).timestamp())
    with pytest.raises(ValueError):
        stations.carrier(np.array([np.nan]))


def test_163000_hourly_samples_are_fast():
    start = datetime(2027, 1, 1, tzinfo=timezone.utc).timestamp() + 1800.0   # a grid no other test uses
    u = start + 3600.0 * np.arange(163_000)
    t0 = time.perf_counter()
    car = stations.carrier(u)
    took = time.perf_counter() - t0
    assert car.shape == (163_000,)
    assert took < 5.0                                         # measured 0.2 s


# ------------------------------------------------------------- physics

@pytest.mark.parametrize("year", [2027, 2034, 2043])
def test_one_complex_or_more_sees_the_moon_most_of_the_time_and_never_all_three(year):
    u = YEARS[year]
    iv = stations.in_view(u)
    assert stations.any_in_view(u).mean() > 0.95
    assert not iv.all(axis=0).any()
    assert iv.sum(axis=0).max() == 2
    # with the 6-degree receive limit the gaps nearly close
    assert stations.any_in_view(u, 6.0).mean() > 0.995
    assert not stations.in_view(u, 6.0).all(axis=0).any()


@pytest.mark.parametrize("year", [2027, 2034, 2043])
def test_each_complex_sees_the_moon_between_30_and_55_percent_of_a_year(year):
    share = stations.in_view(YEARS[year]).mean(axis=1)
    assert share.shape == (3,)
    assert np.all(share > 0.30) and np.all(share < 0.55)


def test_moon_rises_and_sets_about_once_a_lunar_day_at_each_complex():
    el = stations.moon_elevation_deg(YEARS[2027])
    for row in el:
        rises = np.count_nonzero((row[:-1] < 0) & (row[1:] >= 0))
        # 365 days / 1.0351 days per lunar day = 352.6 moonrises
        assert 350 <= rises <= 355


def test_lunar_declination_range_is_narrow_in_2034_and_wide_in_2043():
    """The Moon's orbit is tilted 5.145 degrees to the ecliptic and its node
    turns once in 18.6 years, so the yearly declination extreme swings between
    23.44 - 5.145 = 18.3 degrees (2034) and 23.44 + 5.145 = 28.6 degrees
    (2043).  The highest the Moon climbs at a station follows it."""
    top34 = stations.moon_elevation_deg(YEARS[2034]).max(axis=1)
    top43 = stations.moon_elevation_deg(YEARS[2043]).max(axis=1)
    gain = top43 - top34
    assert np.all(gain > 8.5) and np.all(gain < 11.5)         # 2 x 5.145 = 10.3 degrees
    for c, hi34, hi43 in zip(stations.COMPLEXES, top34, top43):
        colat = 90.0 - abs(c["lat_deg"])
        # culmination height = 90 - |lat| + declination, less up to 0.4 degrees of parallax
        assert colat + 18.3 - 1.2 < hi34 < colat + 18.3 + 0.3
        assert colat + 28.6 - 1.2 < hi43 < colat + 28.6 + 0.3
