"""Tests on the REAL LOLA grids (data/dem, written by scripts/prepare_dem.py).

Skipped when the grids are not installed.  The reference numbers are from the
data scout's manifest and ground-truth notes (realdata/lunar/MANIFEST.md and
GROUND_TRUTH.md) and from the PDS product label.
"""
import os

import numpy as np
import pytest

from slipday import api, demstore, hindcast, moonmap, sites, terrain
from slipday.ephem import cached_table, grid_start, parse_utc
from slipday.geometry import Horizon, Site, track
from slipday.metrics import span_stats

REAL = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MAPS = [os.path.join(_HERE, "data", "reference"),                                   # scripts/fetch_on_your_machine.sh
         os.path.join(os.path.dirname(os.path.dirname(_HERE)), "realdata", "lunar", "data")]   # the build sandbox
RAW = os.environ.get("SLIPDAY_REALDATA_DIR") or next(
    (d for d in _MAPS if os.path.exists(os.path.join(d, "AVGVISIB_85S_060M_201608.TIF"))), _MAPS[0])
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(REAL, "dems.json")),
                                reason="real LOLA grids are not installed (run scripts/prepare_dem.py)")
needs_80 = pytest.mark.skipif(not os.path.exists(os.path.join(REAL, "ldem_80s_80m_f32.npy")),
                              reason="the 80 m grid is not installed (run scripts/fetch_grid80.py); "
                                     "this test states 80 m figures")


def _reset():
    demstore.reload()
    sites._terrain_profile.cache_clear()
    hindcast.hindcast.cache_clear()
    api._stats.cache_clear()
    moonmap._cache.clear()


@pytest.fixture(scope="module", autouse=True)
def real_dem():
    old = os.environ.get("SLIPDAY_DEM_DIR")
    os.environ["SLIPDAY_DEM_DIR"] = REAL
    _reset()
    yield demstore.get_dem()
    os.environ["SLIPDAY_DEM_DIR"] = old
    _reset()


def h(name, lat, lon):
    m = demstore.member(name)
    if m is None:
        pytest.skip(f"{name} not installed")
    return float(m.height_m(np.array([lat]), np.array([lon]))[0])


def test_installed_grids_are_real_and_labelled(real_dem):
    st = demstore.status()
    assert st["available"] and not st["synthetic"]
    assert all(d["source"] == "LOLA" and d["provenance"] for d in st["dems"])
    assert st["label"].startswith("LOLA, ")


@pytest.mark.parametrize("name,lat,lon,expected,tol", [
    # heights from the scout's cross-check table (MANIFEST.md), metres above the 1737.4 km sphere
    ("ldem_80s_80m", -89.67, 129.78, -2788.4, 0.5),        # Shackleton crater floor
    ("ldem_80s_80m", -89.4632, 222.8233, 1948.8, 0.5),     # connecting ridge
    ("ldem_80s_80m", -85.9876, 2.0528, 5172.5, 0.5),       # Malapert massif summit
    ("ldem_80s_80m", -84.7906, 29.1957, 5321.5, 0.5),      # IM-2
    ("ldem_80s_80m", -84.675, 311.275, -3829.4, 0.5),      # LCROSS impact, Cabeus
    ("ldem_64_south", -69.3733, 32.3191, 528.3, 0.5),      # Chandrayaan-3
    ("ldem_64_south", -89.67, 129.78, -2777.2, 0.5),
    ("ldem_16", 0.67416, 23.47314, -1921.6, 0.5),          # Apollo 11
    ("ldem_16", -80.13, 1.44, 2620.0, 0.5),                # IM-1
    ("ldem_75s_240m", -89.67, 129.78, -2788.4, 6.0),       # PDS 240 m grid agrees with the 80 m mosaic
    ("ldem_75s_240m", -85.9876, 2.0528, 5172.5, 6.0),
])
def test_spot_heights_match_the_manifest(name, lat, lon, expected, tol):
    assert h(name, lat, lon) == pytest.approx(expected, abs=tol)


def test_published_lander_elevations():
    """LROC-published elevations (GROUND_TRUTH.md section 3)."""
    assert h("ldem_16", 18.5623, 61.8103) == pytest.approx(-3650, abs=10)      # Blue Ghost M1
    assert h("ldem_16", -13.3160, 25.2510) == pytest.approx(-912, abs=10)      # SLIM
    assert h("ldem_16", -41.6385, 206.0148) == pytest.approx(-5256, abs=10)    # Chang'e 6
    assert h("ldem_80s_80m", -80.13, 1.44) == pytest.approx(2579, abs=20)      # IM-1 (12 deg slope)


@needs_80
def test_grids_agree_where_they_overlap():
    rng = np.random.default_rng(5)
    lat, lon = -90 + rng.uniform(0.2, 9.5, 2000), rng.uniform(-180, 180, 2000)
    fine = demstore.member("ldem_80s_80m").height_m(lat, lon)
    for name, tol in (("ldem_75s_240m", 6.0), ("ldem_64_south", 20.0), ("ldem_16", 80.0)):
        m = demstore.member(name)
        if m is None:
            continue
        d = m.height_m(lat, lon) - fine
        assert abs(np.nanmean(d)) < 3.0 and np.nanstd(d) < tol, (name, np.nanmean(d), np.nanstd(d))


@needs_80
def test_connecting_ridge_is_mostly_lit_and_the_crater_floor_never(real_dem):
    """Glaser et al. 2018 give 92.1 % solar visibility at 2 m on the connecting ridge (20 m DEM);
    the smooth sphere gives 57 %.  The LOLA maps put Shackleton's floor in permanent shadow."""
    ridge = sites.get_site("shackleton", mast_m=2.0)
    assert ridge.horizon.is_terrain and "LOLA, 80 m" in ridge.horizon.describe()["label"]
    st = span_stats(ridge, "2027-01-01", 365)
    sm = span_stats(sites.smooth_twin(ridge), "2027-01-01", 365)
    assert 85 < st["any_light_pct"] < 97 and 55 < sm["any_light_pct"] < 59
    assert st["longest_dark_h"] < 24 * 12 and sm["longest_dark_h"] > 24 * 130
    floor = span_stats(sites.get_site("shackleton_floor"), "2027-01-01", 365)
    assert floor["any_light_pct"] == 0.0 and floor["earth_visible_pct"] == 0.0
    assert span_stats(sites.get_site("lcross"), "2027-01-01", 365)["any_light_pct"] == 0.0


def test_ten_metre_mast_sees_more_light_than_two(real_dem):
    two = span_stats(sites.get_site("shackleton", mast_m=2.0), "2027-01-01", 365)
    ten = span_stats(sites.get_site("shackleton", mast_m=10.0), "2027-01-01", 365)
    assert ten["any_light_pct"] >= two["any_light_pct"] and ten["longest_dark_h"] <= two["longest_dark_h"]


def test_earth_stays_up_on_malapert_and_bobs_at_the_ridge(real_dem):
    """Bryant 2009 (radar DEM): Earth 100 % at Malapert alpha, about 58 % (half-disc rule) on the
    connecting ridge.  In the LOLA frame the Earth-facing shoulder of the Malapert summit keeps the
    Earth all year; Bryant's own coordinates fall behind the crest here (see REALDATA.md)."""
    shoulder = span_stats(sites.get_site("malapert_earth"), "2027-01-01", 365)
    ridge = span_stats(sites.get_site("shackleton"), "2027-01-01", 365)
    assert shoulder["earth_visible_pct"] == 100.0 and shoulder["longest_earth_outage_h"] == 0
    assert 45 < ridge["earth_visible_pct"] < 65 and 10 * 24 < ridge["longest_earth_outage_h"] < 17 * 24
    summit = span_stats(sites.get_site("malapert"), "2027-01-01", 365)
    assert 70 < summit["earth_visible_pct"] < 95


def test_agreement_with_the_published_lola_sunlight_map(real_dem):
    """A small seeded sample of the full check in scripts/validate_terrain.py."""
    path = os.path.join(RAW, "AVGVISIB_75S_120M_201608.TIF")
    if not os.path.exists(path):
        pytest.skip("published map not available on this machine")
    import tifffile
    v = tifffile.imread(path, key=0)
    ref80 = demstore.member("ldem_80s_80m")
    rng = np.random.default_rng(11)
    r = np.sqrt(rng.uniform(0.3, 1.0, 16)) * 290e3
    a = rng.uniform(0, 2 * np.pi, 16)
    lat, lon = ref80.unproject(r * np.sin(a), r * np.cos(a))
    x, y = ref80.project(lat, lon)
    pub = v[np.round((457440.0 - 60.0 - y) / 120.0).astype(int), np.round((x + 457440.0 - 60.0) / 120.0).astype(int)] * 4e-5
    table = cached_table(grid_start(parse_utc("2016-08-01")), int(18.6 * 365.25 * 24 / 6), 6 * 3600)
    calc, smooth = [], []
    for la, lo in zip(lat, lon):
        p = terrain.horizon_profile(real_dem, la, lo, 0.0)
        tr = track(Site("p", la, lo, horizon=Horizon(profile_az_deg=p.az_deg, profile_el_deg=p.el_deg)), table)
        calc.append(float((tr.sun_frac > 0).mean()))
        smooth.append(float((track(Site("s", la, lo), table).sun_frac > 0).mean()))
    calc, smooth = np.array(calc), np.array(smooth)
    assert np.abs(calc - pub).mean() < 0.03            # within 3 points on average (full run: about 1)
    assert np.corrcoef(calc, pub)[0, 1] > 0.95
    assert np.abs(smooth - pub).mean() > 0.10          # the smooth sphere misses by far more


def test_hindcast_with_terrain_moves_towards_the_reports(real_dem):
    hc = {m["id"]: m for m in hindcast.hindcast()["missions"]}
    im1 = hc["im1"]["checks"][0]["models"]
    assert set(im1) == {"smooth sphere", "terrain"}
    assert im1["smooth sphere"]["predicted_minus_reported_h"] == pytest.approx(79.2, abs=0.2)
    assert 0 < im1["terrain"]["predicted_minus_reported_h"] < im1["smooth sphere"]["predicted_minus_reported_h"]
    c3 = hc["chandrayaan3"]["checks"][0]["models"]
    assert 0 < c3["terrain"]["predicted_minus_reported_h"] < c3["smooth sphere"]["predicted_minus_reported_h"]


@needs_80
def test_map_and_layer_are_served_from_real_data(real_dem):
    from fastapi.testclient import TestClient
    c = TestClient(api.app)
    m = c.get("/api/map").json()
    assert m["available"] and not m["synthetic"] and abs(m["edge_lat"] + 80.0) < 0.01
    assert c.get("/api/map/image").content[:2] == b"\xff\xd8"
    if m["layers"]:
        assert "AVGVISIB" in m["layers"][0]["label"]
        assert c.get(m["layers"][0]["image"]).status_code == 200
    j = c.get("/api/sites").json()
    polar = [s for s in j["sites"] if s["group"] == "South pole"]
    assert len(polar) >= 10 and all(s["terrain"] for s in polar)


def test_without_the_80m_file_the_240m_grid_takes_over_and_labels_say_so(real_dem, tmp_path):
    """The 231 MB grid is not shipped in git.  A clone without it must still work and say what it used."""
    import shutil
    for name in os.listdir(REAL):
        if name != "ldem_80s_80m_f32.npy":
            src = os.path.join(REAL, name)
            try:
                os.symlink(src, tmp_path / name)
            except OSError:
                shutil.copy(src, tmp_path / name)
    os.environ["SLIPDAY_DEM_DIR"] = str(tmp_path)
    _reset()
    try:
        st = demstore.status()
        assert st["available"] and st["not_installed"] == ["ldem_80s_80m"]
        assert st["label"].startswith("LOLA, 240 m/px")
        ridge = sites.get_site("shackleton")
        assert "LOLA, 240 m/px" in ridge.horizon.describe()["label"]
        year = span_stats(ridge, "2027-01-01", 365)
        assert 80 < year["any_light_pct"] < 97            # 89.2 % on the 240 m grid, 92.5 % on the 80 m grid
    finally:
        os.environ["SLIPDAY_DEM_DIR"] = REAL
        _reset()
