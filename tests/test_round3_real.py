"""Round 3 on the REAL LOLA grids: landing-scatter band, mission card, slip map, resolution ladder, site pairs.
Skipped when the grids are not installed."""
import json
import os
import threading
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from slipday import demstore, field, load, refmaps, robust
from slipday.api import app
from slipday.ephem import cached_table, grid_start, parse_utc
from slipday.geometry import Horizon, Site
from slipday.metrics import Criteria, _track, earth_up, slip_grid, span_stats, sun_up
from slipday.sites import custom_site, get_site

client = TestClient(app)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from slipday import api, hindcast, moonmap, sites

REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(REAL_DEM, "dems.json")),
                                reason="real LOLA grids are not installed (run scripts/prepare_dem.py)")
needs_field = pytest.mark.skipif(field.load() is None, reason="skyline field not built (run scripts/build_field.py)")
needs_80 = pytest.mark.skipif(not os.path.exists(os.path.join(REAL_DEM, "ldem_80s_80m_f32.npy")),
                              reason="the 80 m grid is not installed (run scripts/fetch_grid80.py); "
                                     "this test states 80 m figures")


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
    _reset()
    yield demstore.get_dem()
    os.environ["SLIPDAY_DEM_DIR"] = old
    _reset()


# ------------------------------------------------------------------ landing scatter


@needs_80
def test_ensemble_has_scatter_coarse_and_near_members():
    s = get_site("shackleton")
    ens = robust.ensemble(s, 0.0, 2.0, 100.0)
    assert len(ens["scatter"]) == 12
    assert ens["coarse"].horizon.meta["resolution_m"] == 240.0
    assert ens["near"].horizon.meta["first_sample_m"] == 40.0
    assert s.horizon.meta["first_sample_m"] == 80.0          # the documented node-to-node convention
    # the members are different computations, not copies
    assert not np.allclose(ens["coarse"].horizon._el, s.horizon._el)
    assert not np.allclose(ens["scatter"][0].horizon._el, s.horizon._el)


@needs_80
def test_band_encloses_the_stated_point_and_has_real_spread():
    s = get_site("shackleton")
    grid, _ = robust.banded_slip_grid([s], "2026-11-14", 60, 24, 14.0, Criteria(), 0.0, 2.0, 100.0)
    row = grid["rows"][0]
    bd = row["band"]
    assert bd["points"] == 13 and bd["scatter_m"] == 100.0
    for key in ("total", "sunlit", "earth"):
        lo, hi, mid = np.array(bd[key]["min"]), np.array(bd[key]["max"]), np.array(row[key])
        assert (lo <= mid).all() and (mid <= hi).all()
        assert len(bd[key]["coarse"]) == 60 and len(bd[key]["near"]) == 60
    # on this crest the sunlit hours do move within 100 m (measured: up to 85 h for usable hours)
    assert (np.array(bd["sunlit"]["max"]) - np.array(bd["sunlit"]["min"])).max() >= 24


@needs_80
def test_mission_card_im2_real_landing_date():
    """IM-2 Athena's real site and landing hour: a clear yes with two days of margin, then not sure."""
    r = client.post("/api/mission", json={"site": {"id": "im2"}, "landing": "2025-03-06T17:00:00Z",
                                          "need_sun_h": 240, "need_earth_h": 100})
    assert r.status_code == 200
    m = r.json()
    assert m["verdict"] == "yes" and m["slip_margin_days"] == 2
    assert m["days"][0]["sunlit_h"] == 315 and m["days"][0]["earth_h"] == 300
    assert m["days"][3]["verdict"] == "not sure" and m["days"][3]["points_passing"] == 12
    assert m["sure"]["points"] == 13 and m["sure"]["coarse_passes"] is True and m["sure"]["validated"] is True
    assert m["next_good_dates"][0].startswith("2025-04-05")
    # "not sure" means the members really disagree
    for d in m["days"]:
        if d["verdict"] == "not sure":
            assert d["unsure_because"]
        if d["verdict"] == "yes":
            assert d["points_passing"] == d["points"] and d["coarse_passes"] and d["near_passes"]


def test_slipgrid_band_through_the_api_and_csv():
    body = {"sites": [{"id": "shackleton"}, {"id": "apollo11"}], "start": "2026-11-14", "n_dates": 20, "scatter_m": 100}
    g = client.post("/api/slipgrid", json=body).json()
    assert g["rows"][0]["band"]["points"] == 13 and "smooth" in g["rows"][0]
    assert g["rows"][1]["band"]["points"] == 13                   # a mare site still has its 1.9 km terrain skyline
    csv = client.post("/api/export/slipgrid.csv", json=body).text
    head = [ln for ln in csv.splitlines() if not ln.startswith("#")][0]
    assert "usable_hours_min_in_scatter" in head and "earth_contact_hours" in head
    assert client.post("/api/slipgrid", json={**body, "sites": [{"id": "shackleton"}] * 12, "n_dates": 400}).status_code == 422


def test_field_evaluator_matches_the_single_site_code():
    pts = [(-89.4398, -137.17), (-89.6866, -162.81), (-89.9, 0.0), (-89.5, 60.0), (-89.7, 100.0)]
    sites = [custom_site("x", la, lo) for la, lo in pts]
    el = np.array([s.horizon._el for s in sites], dtype=np.float32)
    s0 = grid_start(parse_utc("2026-11-14T00:00:00Z"), 3600)
    tab = cached_table(s0, 1753, 3600)
    for crit in (Criteria(), Criteria(min_sun_fraction=0.0), Criteria(min_sun_fraction=1.0, earth_margin_deg=1.0)):
        lit, earth = field.evaluate_points(np.array([s.lat for s in sites]), np.array([s.lon for s in sites]), el, tab, crit)
        for i, site in enumerate(sites):
            tr = _track(site, tab, crit)
            assert (sun_up(tr) != lit[i]).sum() == 0
            assert (earth_up(tr, crit) != earth[i]).sum() == 0


@needs_field
@needs_80
def test_slipmap_agrees_with_the_mission_card_at_a_map_point():
    body = {"start": "2026-11-18", "n_dates": 30, "need_sun_h": 240, "need_earth_h": 100}
    r = client.post("/api/slipmap", json=body).json()
    assert r["available"] and len(r["layers"]["margin"]) == r["n"] ** 2 and r["dates"] == 30
    fld = field.load()
    margin = np.array(r["layers"]["margin"])
    good = np.array(r["layers"]["good"])
    assert margin.max() >= 5 and (margin < 0).mean() > 0.5        # most ground near the pole cannot host this mission
    for cell in (int(np.argmax(margin)), int(np.argmax(good)), 0):
        la, lo = float(fld["lat"][cell]), float(fld["lon"][cell])
        m = client.post("/api/mission", json={"site": {"lat": round(la, 5), "lon": round(lo, 5)}, "landing": "2026-11-18",
                                              "need_sun_h": 240, "need_earth_h": 100, "slip_days": 30, "scatter_m": 0}).json()
        assert m["target_only_margin_days"] == margin[cell]
        assert sum(d["target_passes"] for d in m["days"]) == good[cell]
        assert min(d["sunlit_h"] for d in m["days"]) == r["layers"]["worst_sun"][cell]


def test_map_close_up():
    m = client.get("/api/map?half_km=30").json()
    assert m["available"] and m["half_width_km"] == 30.0 and "half_km=30" in m["image"]
    img = client.get(m["image"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg" and len(img.content) > 20000
    assert client.get("/api/map").json()["half_width_km"] > 300


@needs_80
def test_stats_ladder_and_band():
    r = client.get("/api/stats?site=shackleton&start=2026-11-14&days=365&ladder=true&scatter_m=100").json()
    labels = [x["label"] for x in r["ladder"]]
    assert labels == ["LOLA, 80 m/px", "LOLA, 240 m/px", "LOLA, 474 m/px", "LOLA, 1.90 km/px", "smooth sphere"]
    assert r["ladder"][0]["any_light_pct"] == r["terrain"]["any_light_pct"] == 92.51     # reviewer's figure for this span
    assert r["ladder"][-1]["any_light_pct"] == r["smooth"]["any_light_pct"]
    b = r["band"]
    assert b["points"] == 13
    for k in ("any_light_pct", "longest_dark_h", "earth_visible_pct"):
        assert b[k][0] <= r["terrain"][k] <= b[k][1]
    # the published point is the best of its neighbourhood: within 100 m the sunlit share falls a long way
    assert b["any_light_pct"][1] - b["any_light_pct"][0] > 5
    assert b["coarse"]["label"].startswith("LOLA, 240 m")
    plain = client.get("/api/stats?site=shackleton&start=2026-11-14&days=365").json()
    assert "band" not in plain and "ladder" not in plain


def test_ground_level_observer_carries_a_warning():
    r = client.get("/api/stats?site=shackleton&start=2027-01-01&days=30&mast_m=0").json()
    assert "not converged" in r["warning"]
    assert "warning" not in client.get("/api/stats?site=shackleton&start=2027-01-01&days=30").json()


def test_site_pairs():
    r = client.post("/api/pairs", json={"sites": [{"id": "shackleton"}, {"id": "shackleton_rim"}, {"id": "ridge_c2"}],
                                        "start": "2026-11-14", "days": 365}).json()
    assert len(r["pairs"]) == 3 and "indicative" in r["caveat"]
    for p in r["pairs"]:
        a, b = r["sites"][p["a"]], r["sites"][p["b"]]
        assert p["either_lit_pct"] >= max(a["any_light_pct"], b["any_light_pct"])
        assert p["longest_joint_dark_h"] <= min(a["longest_dark_h"], b["longest_dark_h"])
        assert p["both_lit_pct"] <= min(a["any_light_pct"], b["any_light_pct"])
        assert 0 < p["distance_km"] < 20
    assert client.post("/api/pairs", json={"sites": [{"id": "shackleton"}], "start": "2026-11-14"}).status_code == 422


def test_real_grids_report_what_was_validated():
    assert get_site("shackleton").horizon.describe()["validated"] is True
    assert get_site("chandrayaan3").horizon.describe()["validated"] is False      # 69 S: outside the checked maps
    assert custom_site("n", 89.5, 10.0).horizon.describe()["validated"] is False  # north pole: 1.9 km grid only
