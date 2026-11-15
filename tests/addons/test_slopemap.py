"""Add-on slope guide for the close-up: GET /api/addons/slopemap.  The router is mounted in a small app here, and
also checked as registered in the real app."""
import math

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday.addons import safety, slopemap

PTS = slopemap.map_points()
NAMES = [n for n, _l, _g in safety.grids()]
pytestmark = pytest.mark.skipif(PTS is None or "ldem_pole_20m" not in NAMES,
                                reason="the slip-map points or the LOLA 20 m crop are not installed")

app = FastAPI()
app.include_router(slopemap.router)
client = TestClient(app)


@pytest.fixture(scope="module")
def ans():
    r = client.get("/api/addons/slopemap")
    assert r.status_code == 200
    return r.json()


def test_every_map_point_is_covered(ans):
    n = ans["n"] * ans["n"]
    assert ans["available"] and ans["points"] == n == 14400
    for k in ("class", "steepest_deg", "target_deg", "points_passing", "points_meeting_goal", "grid_m", "coarsest_grid_m"):
        assert len(ans[k]) == n, k
    assert ans["points_known"] == n
    assert all(v is not None for v in ans["steepest_deg"])
    # the close-up lies inside the 20 m crop: 5 m where the site models are, 20 m elsewhere, no 80 m needed
    assert set(ans["grid_m"]) <= {5.0, 20.0} and set(ans["coarsest_grid_m"]) <= {5.0, 20.0}
    assert sum(ans["points_by_coarsest_grid_m"].values()) == n
    assert sum(ans["counts"].values()) == n


def test_points_are_the_page_cells_in_page_order():
    """Map point i = row * n + col sits at the centre of the page's cell (row 0 at +y), as app.js where() assumes."""
    n, half, st = PTS["n"], PTS["half_km"], PTS["step_m"] / 1000
    g = safety.grids()[0][2]
    x, y = g.project(PTS["lat"], PTS["lon"])
    i = np.arange(n * n)
    xe = (-half + (i % n + 0.5) * st) * 1000
    ye = (half - (i // n + 0.5) * st) * 1000
    assert np.max(np.hypot(x - xe, y - ye)) < 1.0                  # metres


def test_class_rule_matches_the_card_rule(ans):
    for c, s, p, gl in zip(ans["class"], ans["steepest_deg"], ans["points_passing"], ans["points_meeting_goal"]):
        # steepest_deg is rounded to 0.01 in the answer, so a value just over a limit can read as the limit
        if c == 2:
            assert s <= 5.0 and gl == 13
        elif c == 1:
            assert 5.0 <= s <= 8.0 and p == 13 and gl < 13
        else:
            assert c == 0 and s >= 8.0 and p < 13


def test_agrees_with_the_site_card_at_sample_points(ans):
    n = ans["n"]
    rng = np.random.default_rng(20261115)
    for i in rng.choice(n * n, 25, replace=False):
        r = safety.site_slopes(float(PTS["lat"][i]), float(PTS["lon"][i]), 100.0)
        assert abs(r["steepest"]["slope_deg"] - ans["steepest_deg"][i]) < 0.011
        assert r["points_passing"] == ans["points_passing"][i]
        assert r["points"][0]["grid_m"] == ans["grid_m"][i]
        assert max(p["grid_m"] for p in r["points"]) == ans["coarsest_grid_m"][i]


def test_agrees_with_the_existing_map_layer_where_both_exist(ans):
    sl = safety.map_point_slopes()
    if sl is None:
        pytest.skip("the scatter skylines are not built")
    idx = sl["stored"]
    a = np.array([ans["steepest_deg"][i] for i in idx])
    d = np.abs(a - sl["steepest"][idx])
    # The existing layer uses the stored touchdown points (data/scatterfield), which sit up to about 0.3 m from
    # robust.scatter_points; on rough ground that can move a point into the next 2 x 2 cells.  Measured
    # 15 Nov 2026: 2,355 of 2,407 within 0.011 deg, median 0.003 deg, pass or fail differs at 3.
    assert len(idx) > 2000 and np.median(d) < 0.01 and (d <= 0.011).mean() > 0.97
    assert ((a <= 8.0) != (sl["steepest"][idx] <= 8.0)).sum() <= 0.005 * len(idx)


def test_stored_file_equals_a_fresh_run():
    d = slopemap.load()
    if not d["stored"]:
        pytest.skip("no stored file matches the current inputs (run python -m slipday.addons.slopemap)")
    fresh = slopemap.compute(PTS)
    for k, v in fresh.items():
        np.testing.assert_allclose(np.asarray(d["val"][k], dtype=float), np.asarray(v, dtype=float), atol=1e-9, equal_nan=True)


@pytest.mark.skipif("ldem_80s_80m" not in NAMES, reason="the LOLA 80 m grid is not installed")
def test_falls_back_to_80_m_and_says_not_known_off_the_grids():
    lat = np.array([-85.0, -70.0])
    lon = np.array([30.0, 30.0])
    v = slopemap.compute({"lat": lat, "lon": lon})
    assert v["grid_m"][0] == 80.0 and v["cls"][0] in (0, 1, 2) and math.isfinite(v["steepest_deg"][0])
    assert v["cls"][1] == -1 and math.isnan(v["steepest_deg"][1]) and math.isnan(v["grid_m"][1])


def test_registered_in_the_real_app():
    """api.py's optional-router loop mounts it (this FastAPI keeps included routers nested, so ask, don't list)."""
    from slipday import api
    r = TestClient(api.app).get("/api/addons/slopemap")
    assert r.status_code == 200 and r.json()["points"] == 14400
