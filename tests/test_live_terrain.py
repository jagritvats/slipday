"""Live finer terrain: the page's answers use the finest LOLA grid that covers the site (5 m site models, then 20 m,
then 80 m and coarser), and the API says which grid each answer used (DEEP_PASS_3.md, "Live finer terrain")."""
import os

import pytest
from fastapi.testclient import TestClient

from slipday import demstore, sites, survival, why
from slipday.api import app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.path.join(ROOT, "data", "dem_live")
HAVE_LIVE = os.path.exists(os.path.join(LIVE, "dems.json")) and os.path.exists(os.path.join(ROOT, "data", "dem5", "site07", "ldem_site07_5m_f32.npy"))
needs_live = pytest.mark.skipif(not HAVE_LIVE, reason="the live finer stack is not installed (scripts/build_live_stack.py)")
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def live_dem():
    old = os.environ.get("SLIPDAY_DEM_DIR")
    if HAVE_LIVE:
        os.environ["SLIPDAY_DEM_DIR"] = LIVE
        demstore.reload()
        sites._terrain_profile.cache_clear()
        why._cache.clear()
        survival._cache.clear()
    yield
    if old is not None:
        os.environ["SLIPDAY_DEM_DIR"] = old
    demstore.reload()
    sites._terrain_profile.cache_clear()
    why._cache.clear()
    survival._cache.clear()


def test_the_default_stack_is_the_live_one_when_installed(monkeypatch):
    monkeypatch.delenv("SLIPDAY_DEM_DIR", raising=False)
    expect = LIVE if HAVE_LIVE else os.path.join(ROOT, "data", "dem")
    assert os.path.normpath(demstore.dem_dir()) == os.path.normpath(expect)


@needs_live
def test_finest_grid_first_and_reported():
    names = [m.name for m in demstore.members()]
    assert names[:2] == ["ldem_site07_5m", "ldem_site01_5m"] and names[2].startswith("ldem_") and "20m" in names[2]
    assert names.index("ldem_80s_80m") == 3
    g = demstore.grid_at(-89.0098, 122.76389)
    assert g["resolution_m"] == 5.0 and g["name"] == "ldem_site07_5m"
    assert demstore.grid_at(-89.4398, -137.17)["name"] == "ldem_site01_5m"
    assert demstore.grid_at(-80.13, 1.44)["resolution_m"] in (20.0, 80.0)        # IM-1: 20 m once the full mosaic is in


@needs_live
def test_the_opening_example_and_c1_on_the_live_terrain():
    body = {"site": {"id": "robust_pick"}, "landing": "2026-11-18T00:00:00Z", "earth_stations": True}
    m = client.post("/api/mission", json=body).json()
    assert m["terrain_grid"]["resolution_m"] == 5.0
    assert (m["verdict"], m["slip_margin_days"], m["sure"]["points_passing"]) == ("yes", 8, 13)
    assert m["days"][0]["sunlit_h"] == 306 and m["days"][0]["earth_h"] == 311
    w = client.post("/api/why", json=dict(body, day=0)).json()
    assert w["terrain_grid"]["name"] == "ldem_site07_5m"
    c = client.post("/api/mission", json=dict(body, site={"id": "shackleton"})).json()
    assert (c["verdict"], c["sure"]["points_passing"]) == ("not sure", 12)


@needs_live
def test_the_map_keeps_the_wide_80_m_extent_and_its_layers():
    # finer grids near the pole change the skylines, not the map: 80 S to the pole, 608 km across, with its layers
    m = client.get("/api/map").json()
    assert m["available"] and round(m["half_width_km"]) == 304 and abs(m["edge_lat"] + 80.0) < 0.01
    assert [x["id"] for x in m["layers"]] == ["avgvis"]
