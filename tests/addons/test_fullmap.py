"""Add-on: slip margin for the whole map, GET /api/addons/fullmap (coarse grid, worked out off line).

Checks the stored layer against the close-up's own endpoint where the grids share points, recomputes a few points
from the LOLA files with the close-up's skyline and evaluation code, and checks the router in a small app and in the
real app. Works with a partly finished run too (coverage is reported, not assumed)."""
import importlib.util
import json
import os

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday.addons import fullmap

ROOT = fullmap.ROOT
D = fullmap.load()
pytestmark = pytest.mark.skipif(D is None, reason="the whole-map layer has not been built (scripts/addons/)")

app = FastAPI()
app.include_router(fullmap.router)
client = TestClient(app)

OPENING = {"start": "2026-11-18", "n_dates": 60, "need_sun_h": 240, "need_earth_h": 100, "window_days": 14,
           "sun_at_touchdown": True, "earth_at_touchdown": True}


@pytest.fixture(scope="module")
def ans():
    r = client.get("/api/addons/fullmap")
    assert r.status_code == 200
    return r.json()


def _xy(meta, n, idx):
    r, c = np.divmod(np.asarray(idx), n)
    return meta["axis_first_m"] + c * meta["step_m"], meta["axis_last_m"] - r * meta["step_m"]


def test_layers_cover_the_grid_and_coverage_is_honest(ans):
    n = ans["n"]
    assert ans["available"] and ans["grid_spacing_m"] == D["meta"]["step_m"]
    for k in ("slip_margin_days", "verdict", "good_dates", "terrain_m"):
        assert len(ans["layers"][k]) == n * n, k
    done = sum(v is not None for v in ans["layers"]["slip_margin_days"])
    cov = ans["coverage"]
    assert done == cov["done"] == len(D["idx"]) and cov["grid_points"] == n * n
    assert abs(cov["share_done"] - done / (n * n)) < 1e-3
    assert cov["complete"] == (done == n * n)
    # the map is the 80 m mosaic's square: 608 km across
    assert ans["first_centre_km"]["x"] < -300 and ans["first_centre_km"]["y"] > 300
    assert (n - 1) * ans["step_m"] > 600000


def test_verdict_follows_the_margin(ans):
    m, v, g = (np.array([np.nan if x is None else x for x in ans["layers"][k]], dtype=float)
               for k in ("slip_margin_days", "verdict", "good_dates"))
    have = ~np.isnan(m)
    assert np.array_equal(have, ~np.isnan(v))
    assert np.array_equal(v[have] == 1, m[have] >= 0)
    assert np.all(g[have] >= m[have] + 1)            # the dates up to the first failure are all good
    assert np.all(m[have] <= len(ans["dates"]) - 1) and np.all(m[have] >= -1)


def test_labels_say_spacing_and_single_position(ans):
    km = "%g km" % (ans["step_m"] / 1000.0)
    assert km in ans["label"]
    assert "own position only" in ans["how"] and "13 touchdown points" in ans["how"]
    assert any(km in s for s in ans["limits"])
    assert ans["plan"]["start"].startswith("2026-11-18") and ans["plan"]["need_sun_h"] == 240


def test_grid_hits_close_up_points_exactly():
    """Every coarse point inside the 60 km square sits on one of the close-up's 500 m points."""
    meta, n = D["meta"], D["n"]
    pts = np.load(os.path.join(ROOT, "data", "field", "pole_points.npz"))
    x, y = _xy(meta, n, np.arange(n * n))
    inside = (np.abs(x) < 30000) & (np.abs(y) < 30000)
    assert inside.sum() == round(60000 / meta["step_m"]) ** 2
    col = np.round((x[inside] + 29750) / 500).astype(int)
    row = np.round((29750 - y[inside]) / 500).astype(int)
    assert np.allclose(col * 500 - 29750, x[inside]) and np.allclose(29750 - row * 500, y[inside])
    k = row * 120 + col
    from slipday.dem import MOON_RADIUS_M
    r = np.hypot(x[inside], y[inside])
    lat = -(90.0 - np.rad2deg(2.0 * np.arctan(r / (2.0 * MOON_RADIUS_M))))
    assert np.allclose(lat, pts["lat"][k], atol=1e-9)


@pytest.fixture(autouse=True, scope="module")
def _build_module():
    """Make scripts/addons/build_fullmap.py importable as ``scripts_addons_build``."""
    import sys
    spec = importlib.util.spec_from_file_location("scripts_addons_build",
                                                  os.path.join(ROOT, "scripts", "addons", "build_fullmap.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules["scripts_addons_build"] = mod
    yield mod


def test_stored_positions_match_the_grid(_build_module):
    meta, n, idx = D["meta"], D["n"], D["idx"]
    x, y = _xy(meta, n, idx)
    lat, lon = _build_module.unproject(x, y)
    assert np.allclose(lat, D["lat"], atol=1e-9) and np.allclose(lon, D["lon"], atol=1e-9)


def test_agrees_with_the_close_up_endpoint_where_they_overlap():
    """Same plan, same points: the coarse layer must give the close-up's own /api/slipmap numbers."""
    from slipday.api import app as real
    c = TestClient(real)
    meta, n, idx = D["meta"], D["n"], D["idx"]
    x, y = _xy(meta, n, idx)
    inside = (np.abs(x) < 30000) & (np.abs(y) < 30000)
    if not inside.any():
        pytest.skip("no shared points worked out yet")
    k_close = np.round((29750 - y[inside]) / 500).astype(int) * 120 + np.round((x[inside] + 29750) / 500).astype(int)
    for stations in (True, False):
        r = c.post("/api/slipmap", json=dict(OPENING, earth_stations=stations))
        assert r.status_code == 200 and r.json()["available"]
        close = np.array(r.json()["layers"]["margin"])
        good = np.array(r.json()["layers"]["good"])
        rule = fullmap.EARTH_RULES[stations]
        mine = D["grids"][rule + "__margin"][idx[inside]]
        mine_g = D["grids"][rule + "__good"][idx[inside]]
        assert np.array_equal(mine, close[k_close]), (stations, int((mine != close[k_close]).sum()))
        assert np.array_equal(mine_g, good[k_close])
    ag = meta["agreement_with_close_up"]
    assert ag["shared_points"] == int(inside.sum())
    assert ag["stations"]["same_margin"] == ag["shared_points"]


def test_recompute_three_points_from_the_lola_files():
    """Skyline and margin of three stored points, recomputed here from data/dem with the close-up's own code."""
    from slipday import demstore, field, scatterfield, terrain
    from slipday.dem import CompositeDEM
    from slipday.ephem import cached_table, grid_start, parse_utc
    from slipday.metrics import STEP_S, Criteria
    base = os.path.join(ROOT, "data", "dem")
    with open(os.path.join(base, "dems.json")) as fh:
        cfg = json.load(fh)
    ms = sorted((demstore._build(e, base) for e in cfg["dems"] if os.path.exists(os.path.join(base, e["path"]))),
                key=lambda m: m.resolution_m)
    dem = CompositeDEM(members=ms, name="+".join(m.name for m in ms))
    assert "+".join(m.fingerprint for m in ms) == D["meta"]["dem_fingerprint"]
    rng = np.random.default_rng(7)
    pick = rng.choice(len(D["idx"]), size=min(3, len(D["idx"])), replace=False)
    lat, lon = D["lat"][pick], D["lon"][pick]
    el = []
    for la, lo in zip(lat, lon):
        p = terrain.horizon_profile(dem, float(la), float(lo), 2.0)
        el.append(np.clip(np.round(p.el_deg / field.EL_SCALE), -32000, 32000).astype(np.int16))
    el = np.array(el)
    s = grid_start(parse_utc("2026-11-18"), STEP_S)
    w = 14 * 24
    table = cached_table(s, 59 * 24 + w + 1, STEP_S)
    sv = np.arange(60) * 24
    for stations in (True, False):
        ok = scatterfield._passes(lat, lon, el, table, Criteria(0.5, -90.0, -90.0, 0.0, stations), 0.0, sv, w,
                                  240.0, 100.0, True, True)
        bad = ~ok
        margin = np.where(bad.any(axis=1), np.argmax(bad, axis=1), ok.shape[1]) - 1
        stored = D["grids"][fullmap.EARTH_RULES[stations] + "__margin"][D["idx"][pick]]
        assert np.array_equal(margin, stored), (stations, margin, stored)


def test_points_endpoint_rows():
    r = client.get("/api/addons/fullmap/points", params={"x_min_km": -40, "x_max_km": 40, "y_min_km": -40,
                                                          "y_max_km": 40, "limit": 50})
    j = r.json()
    assert r.status_code == 200 and j["available"]
    assert j["returned"] <= 50
    for row in j["points"]:
        assert set(row) >= {"lat", "lon", "slip_margin_days", "verdict", "grid_spacing_m", "terrain_m"}
        assert row["verdict"] == ("yes" if row["slip_margin_days"] >= 0 else "no")
        assert row["grid_spacing_m"] == D["meta"]["step_m"] and row["terrain_m"] in (80.0, 240.0)
        assert -40 <= row["x_km"] <= 40 and row["lat"] < -88


def test_other_plans_are_refused_not_guessed():
    j = client.get("/api/addons/fullmap", params={"start": "2026-12-01"}).json()
    assert j["available"] is False and "opening plan" in j["reason"]
    j = client.get("/api/addons/fullmap", params={"need_sun_h": 300}).json()
    assert j["available"] is False
    j = client.get("/api/addons/fullmap", params={"start": "2026-11-18", "need_sun_h": 240, "n_dates": 60}).json()
    assert j["available"] is True


def test_gzip_and_plain_answers_are_the_same(ans):
    plain = client.get("/api/addons/fullmap", headers={"Accept-Encoding": "identity"})
    zipped = client.get("/api/addons/fullmap", headers={"Accept-Encoding": "gzip"})
    assert "content-encoding" not in plain.headers and zipped.headers.get("content-encoding") == "gzip"
    assert plain.json() == zipped.json() == ans


def test_about_and_mounted_in_the_real_app():
    from slipday.api import app as real
    c = TestClient(real)
    j = c.get("/api/addons/fullmap/about").json()
    assert j["available"] and "layers" not in j and "coverage" in j and "agreement_with_close_up" in j
    assert c.get("/api/addons/fullmap", params={"earth_stations": "false"}).json()["earth_rule"] == "no_stations"
