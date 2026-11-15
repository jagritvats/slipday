"""Local pass (14 Nov 2026) on the REAL LOLA grids: scatter widening on the 240 m fallback, each replay's
own need, the landing circles, the slip-robust site list and the Earth-map tile.  Skipped when the grids
are not installed; the tests that need the 231 MB 80 m grid skip without it."""
import json
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from slipday import api, demstore, field, hindcast, moonmap, replay, robust, sites
from slipday.api import app
from slipday.sites import get_site

client = TestClient(app)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(REAL_DEM, "dems.json")),
                                reason="real LOLA grids are not installed (run scripts/prepare_dem.py)")
HAVE_80 = os.path.exists(os.path.join(REAL_DEM, "ldem_80s_80m_f32.npy"))
needs_80 = pytest.mark.skipif(not HAVE_80, reason="the 80 m grid is not installed (run scripts/fetch_grid80.py)")
needs_field = pytest.mark.skipif(field.load() is None, reason="skyline field not built (run scripts/build_field.py)")


def _reset():
    demstore.reload()
    sites._terrain_profile.cache_clear()
    hindcast.hindcast.cache_clear()
    api._stats.cache_clear()
    moonmap._cache.clear()
    moonmap._layer_cache.clear()


@pytest.fixture(scope="module", autouse=True)
def real_dem():
    old = os.environ.get("SLIPDAY_DEM_DIR")
    os.environ["SLIPDAY_DEM_DIR"] = REAL_DEM
    os.environ.pop("SLIPDAY_SKIP_DEMS", None)
    _reset()
    yield demstore.get_dem()
    os.environ["SLIPDAY_DEM_DIR"] = old
    os.environ.pop("SLIPDAY_SKIP_DEMS", None)
    _reset()


@pytest.fixture
def fallback_240m():
    """The small-host configuration: the 80 m grid treated as not installed."""
    os.environ["SLIPDAY_SKIP_DEMS"] = "ldem_80s_80m"
    _reset()
    yield
    os.environ.pop("SLIPDAY_SKIP_DEMS", None)
    _reset()


def _card(site, landing, **kw):
    r = client.post("/api/mission", json={"site": {"id": site}, "landing": landing, **kw})
    assert r.status_code == 200
    return r.json()


# ------------------------------------------------------------------ the 240 m fallback is no longer overconfident

def test_fallback_widens_the_scatter_to_one_cell_and_says_so(fallback_240m):
    assert demstore.status()["not_installed"] == ["ldem_80s_80m"] or "ldem_80s_80m" in demstore.status()["not_installed"]
    s = get_site("malapert_earth")
    assert s.horizon.meta["resolution_m"] == 240.0
    assert robust.effective_scatter_m(s, 100.0) == 240.0 and robust.effective_scatter_m(s, 0.0) == 0.0
    # round-3 review: these two read "Yes" with 7 and 8 days of margin on the 240 m grid at a 100 m scatter,
    # where the 80 m grid says "Not sure".  With the scatter spread to one 240 m cell they are "Not sure" too.
    for sid in ("malapert_earth", "ridge_c2"):
        m = _card(sid, "2026-11-18")
        assert m["verdict"] == "not sure" and m["slip_margin_days"] == -1
        assert m["sure"]["scatter_m"] == 240.0 and m["sure"]["scatter_requested_m"] == 100.0
        assert m["sure"]["scatter_widened"] is True and "widened from 100 m to 240 m" in m["sure"]["text"]
        assert "within 240 m" in m["sure"]["assumes"]
        assert 0 < m["days"][0]["points_passing"] < m["days"][0]["points"] == 13
    g = client.post("/api/slipgrid", json={"sites": [{"id": "ridge_c2"}], "start": "2026-11-18", "n_dates": 5,
                                           "scatter_m": 100}).json()
    assert g["rows"][0]["band"]["scatter_m"] == 240.0 and g["rows"][0]["band"]["scatter_requested_m"] == 100.0


@needs_80
def test_scatter_is_not_widened_on_the_80m_grid_and_the_card_states_its_assumption():
    m = _card("shackleton", "2026-11-18")
    assert m["verdict"] == "yes" and m["slip_margin_days"] == 7 and m["target_only_margin_days"] == 8
    assert m["sure"]["scatter_m"] == 100.0 and m["sure"]["scatter_widened"] is False
    assert "widened" not in m["sure"]["text"]
    assert m["sure"]["assumes"].startswith("This answer assumes the lander comes down within 100 m of the target")
    # a request below one cell is raised to the cell: 50 m asked for on the 80 m grid is computed at 80 m
    assert _card("shackleton", "2026-11-18", scatter_m=50)["sure"]["scatter_m"] == 80.0
    # the round-3 review's scatter sensitivity at this site and date: not a clear yes at 150 m
    assert _card("shackleton", "2026-11-18", scatter_m=150)["verdict"] == "not sure"


def test_skip_dems_changes_nothing_else():
    names = [d["label"] for d in demstore.status()["dems"]]
    os.environ["SLIPDAY_SKIP_DEMS"] = "ldem_80s_80m"
    _reset()
    try:
        after = [d["label"] for d in demstore.status()["dems"]]
    finally:
        os.environ.pop("SLIPDAY_SKIP_DEMS", None)
        _reset()
    assert after == [n for n in names if not n.startswith("LOLA, 80 m")]


# ------------------------------------------------------------------ replays carry their own need

@needs_80
def test_im1_replay_with_its_own_need_is_a_yes_and_with_ten_days_a_no():
    x = {m["id"]: m for m in replay.MISSIONS}["im1"]
    m = _card("im1", x["landing"], need_sun_h=x["need_sun_h"], need_earth_h=x["need_earth_h"])
    assert x["need_sun_h"] == 168
    assert m["verdict"] == "yes" and m["slip_margin_days"] == 1
    assert m["days"][0]["sunlit_h"] == 208 and m["days"][0]["earth_h"] == 336
    assert m["smooth_sphere"]["good_dates"] > m["good_dates"]        # a flat horizon finds more good dates than terrain
    ten_days = _card("im1", x["landing"], need_sun_h=240, need_earth_h=100)
    assert ten_days["verdict"] == "no" and "208" in " ".join(ten_days["sentences"])


@needs_80
def test_the_other_replays_do_not_contradict_what_happened():
    by = {m["id"]: m for m in replay.MISSIONS}
    for mid in ("im2", "chandrayaan3", "blueghost1"):
        x = by[mid]
        m = _card(x["site"], x["landing"], need_sun_h=x["need_sun_h"], need_earth_h=x["need_earth_h"])
        assert m["verdict"] == "yes", mid
    # a full-lunar-day plan has no slip margin by construction
    bg = _card("blueghost1", by["blueghost1"]["landing"], need_sun_h=336, need_earth_h=100)
    assert bg["slip_margin_days"] == 0 and "no slip margin" in " ".join(bg["sentences"])
    assert bg["sure"]["scatter_m"] == 1896.0 and bg["sure"]["validated"] is False     # one cell of the 1.9 km grid
    circles = client.post("/api/landing-circles", json={"site": {"id": "blueghost1"}, "landing": by["blueghost1"]["landing"],
                                                        "need_sun_h": 336}).json()
    assert not any(c["resolvable"] for c in circles["classes"])                        # every circle is inside one cell


# ------------------------------------------------------------------ landing circles

@needs_80
def test_landing_circles_on_the_80m_grid():
    r = client.post("/api/landing-circles", json={"site": {"id": "shackleton"}, "landing": "2026-11-18"}).json()
    assert r["available"] and r["grid_resolution_m"] == 80.0 and r["points"] == 93
    assert [c["radius_m"] for c in r["classes"]] == [100.0, 250.0, 500.0, 1000.0]
    assert [c["points"] for c in r["classes"]] == [17, 37, 61, 93]
    for c in r["classes"]:
        assert c["resolvable"] and len(c["share_pct"]) == 60
        assert all(0.0 <= p <= 100.0 for p in c["share_pct"])
        assert c["planned_pct"] == c["share_pct"][0]
        assert -1 <= c["margin_90_days"] < 60
        if c["margin_90_days"] >= 0:
            assert all(p >= 90.0 for p in c["share_pct"][:c["margin_90_days"] + 1])
    # the card's Yes is for 100 m; a wider circle on this knife-edge ridge passes at fewer touchdown points
    assert r["classes"][0]["planned_pct"] > r["classes"][-1]["planned_pct"]
    assert "not a dispersion model" in r["assumption"]
    # the ring points are the mission card's own scatter points where the two overlap
    ring100 = {(round(la, 5), round(lo, 5)) for la, lo in robust.scatter_points(-89.4398, -137.17, 100.0)[:8]}
    assert len(ring100) == 8


def test_landing_circles_on_the_fallback_and_without_terrain(fallback_240m):
    r = client.post("/api/landing-circles", json={"site": {"id": "shackleton"}, "landing": "2026-11-18"}).json()
    assert r["grid_resolution_m"] == 240.0
    small, rest = r["classes"][0], r["classes"][1:]
    assert small["resolvable"] is False and "240 m cell" in small["why"]      # a 100 m circle is inside one cell
    assert all(c["resolvable"] for c in rest)
    flat = client.post("/api/landing-circles", json={"site": {"id": "shackleton"}, "landing": "2026-11-18",
                                                     "terrain": False}).json()
    assert flat["available"] is False
    assert client.post("/api/landing-circles", json={"site": {"id": "nope"}, "landing": "2026-11-18"}).status_code == 404
    assert client.post("/api/landing-circles", json={"site": {"id": "shackleton"}, "landing": "soon"}).status_code == 422


def test_circle_weights_are_area_shares():
    # a site where every touchdown point passes must read 100 % and one where none passes 0 %
    always = client.post("/api/landing-circles", json={"site": {"id": "apollo11"}, "landing": "2027-01-05",
                                                       "need_sun_h": 0, "need_earth_h": 0, "sun_at_touchdown": False,
                                                       "earth_at_touchdown": False}).json()
    never = client.post("/api/landing-circles", json={"site": {"id": "shackleton_floor"}, "landing": "2026-11-18"}).json()
    for r, want in ((always, 100.0), (never, 0.0)):
        for c in r["classes"]:
            if c["resolvable"]:
                assert set(c["share_pct"]) == {want}


# ------------------------------------------------------------------ slip-robust sites

@needs_field
@needs_80
def test_robust_sites_recheck_the_best_map_points():
    body = {"start": "2026-11-18", "n_dates": 30, "candidates": 4}
    r = client.post("/api/robust-sites", json=body).json()
    assert r["available"] and r["candidates"] == 4 and len(r["rows"]) == 4
    assert r["stay_yes"] == sum(x["verdict"] == "yes" for x in r["rows"])
    for x in r["rows"]:
        assert x["map_margin_days"] >= 0 and x["points"] == 13
        assert x["slip_margin_days"] <= x["map_margin_days"]      # the ensemble can only shorten a single-point margin
        m = client.post("/api/mission", json={"site": {"lat": x["lat"], "lon": x["lon"]}, "landing": "2026-11-18",
                                              "slip_days": 30}).json()
        assert (m["verdict"], m["slip_margin_days"]) == (x["verdict"], x["slip_margin_days"])
    # candidates are different places
    pts = [(x["lat"], x["lon"]) for x in r["rows"]]
    assert len(set(pts)) == 4
    assert client.post("/api/robust-sites", json={**body, "candidates": 99}).status_code == 422


# ------------------------------------------------------------------ the Earth-map tile reports the map's own rule

def test_earth_tile_reports_the_rule_in_the_maps_label():
    path = os.path.join(ROOT, "data", "validation", "terrain_validation.json")
    with open(path) as fh:
        v = json.load(fh)
    tile = [h for h in v["headline"] if h.get("id") == "more-e"][0]
    if tile.get("pending"):
        pytest.skip("the Earth maps have not been attached on this installation (LOCAL_PASS.md step 2)")
    assert "the rule the map's own label states" in tile["s"] and "any part of the Earth's disc" in tile["s"]
    table = [t for t in v["tables"] if t.get("id") == "more-e"][0]
    marked = [r for r in table["rows"] if "(the map's rule)" in r[1]]
    # one marked row per map, and one more when the ridge-pixel run (check f) is stored
    assert len(marked) in (2, 3) and all(r[1].startswith("earth any part") for r in marked)
    assert tile["v"] == f"±{marked[0][6]:.1f} pts"
    assert "any fraction of the Earth disc" in table["note"]
    ridge = [r for r in marked if "ridge pixels" in r[0]]
    if ridge:                                   # the ridge figure is on the tile too, not only in the table
        assert f"±{ridge[0][6]} pts" in tile["s"] and "well-lit ridge pixels" in tile["s"]


def test_health_reports_the_arena_limit():
    h = client.get("/api/health").json()
    assert "malloc_arena_limit" in h and h["malloc_arena_limit"]
    assert np.isfinite(len(h["terrain"]["dems"]))
