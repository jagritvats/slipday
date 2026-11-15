"""Add-on: learned instant estimate, GET /api/addons/estimate (model trained by scripts/addons/train_estimate.py).

Checks the router in a small app, the stored accuracy report (held-out tests, compared with nearest neighbour),
the model size, the speed of one estimate, and that the estimate agrees with the stored layer at grid points."""
import json
import os
import time

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday.addons import estimate

LOADED = estimate.load_model()
pytestmark = pytest.mark.skipif(LOADED is None, reason="the estimate model has not been built (scripts/addons/)")

app = FastAPI()
app.include_router(estimate.router)
client = TestClient(app)
REP = LOADED["report"] if LOADED else {}


def test_endpoint_answers_with_label_and_accuracy():
    r = client.get("/api/addons/estimate", params={"lat": -89.45, "lon": -137.31})
    assert r.status_code == 200
    a = r.json()
    assert a["available"] is True
    assert a["label"] == "a learned estimate; the full check follows"
    assert a["verdict"] in ("yes", "no")
    assert 0.0 <= a["chance_yes"] <= 1.0
    assert (a["margin_days_estimate"] is None) == (a["verdict"] == "no")
    acc = a["measured_accuracy"]
    for k in ("verdict_accuracy", "margin_error_days_mean", "false_yes_share_of_true_no",
              "nearest_grid_point_verdict_accuracy"):
        assert k in acc


def test_bad_and_outside_points():
    assert client.get("/api/addons/estimate", params={"lat": 10, "lon": 0}).status_code == 422
    assert client.get("/api/addons/estimate", params={"lat": -85}).status_code == 422
    a = client.get("/api/addons/estimate", params={"lat": -75.0, "lon": 45.0}).json()   # beyond the 80 m map's corner
    assert a["available"] is False and "outside" in a["reason"]


def test_projection_matches_the_map_builder():
    # the inverse used by scripts/addons/build_fullmap.py
    x, y = np.array([12345.0, -250000.0, 1000.0]), np.array([-54321.0, 100000.0, 290000.0])
    r = np.hypot(x, y)
    lat = -(90.0 - np.rad2deg(2.0 * np.arctan(r / (2.0 * estimate.MOON_R))))
    lon = np.rad2deg(np.arctan2(x, y))
    px, py = estimate.project(lat, lon)
    assert np.allclose(px, x, atol=0.01) and np.allclose(py, y, atol=0.01)


def test_features_shape_and_speed():
    f = estimate.features([1000.0, -20000.0], [5000.0, 30000.0])
    assert f.shape == (2, len(estimate.FEATURE_NAMES)) and np.isfinite(f).all()
    estimate.estimate(-89.5, 0.0)          # warm up (memory map, grid)
    t = time.time()
    for k in range(20):
        estimate.estimate(-88.0 - k * 0.05, k * 17.0)
    assert (time.time() - t) / 20 < 0.25   # well under a second each, versus 10 to 40 s for the full check


def test_dem_is_memory_mapped_not_copied():
    assert isinstance(estimate.dem(), np.memmap)


def test_report_is_honest_and_model_small():
    assert REP["settings_fixed_before_testing"] is True
    B = REP["test_B_clicks_between_grid_points"]
    assert B["off_grid_test_points"] == 13500 and B["on_grid_same_margin"] == B["on_2km_grid"] == 900
    A = REP["test_A_spatial_blocks"]
    assert A["model"]["points"] == REP["training_points"] == 92416
    assert REP["model_file_bytes"] < 20 * 1024 * 1024
    assert os.path.getsize(os.path.join(estimate.DATA_DIR, "model.joblib")) < 20 * 1024 * 1024
    nb = B["nearest_neighbour_from_full_2km_grid"]
    served = B["terrain_plus_grid_model"] if LOADED["m"].get("uses_grid") else B["model"]
    if REP["ships_on_page"]:
        assert served["verdict_accuracy"] > nb["verdict_accuracy"]
        assert served["margin_error_days_mean"] < nb["margin_error_days_mean"]
        assert served["false_yes"] <= nb["false_yes"]
    assert REP["served_summary"]["verdict_accuracy"] == served["verdict_accuracy"]


def test_mostly_agrees_with_stored_layer_at_grid_points():
    g = estimate.grid()
    rng = np.random.default_rng(1)
    idx = np.concatenate([rng.choice(np.flatnonzero(g["margin"] >= 0), 100, replace=False),
                          rng.choice(np.flatnonzero(g["margin"] < 0), 100, replace=False)])
    r = np.hypot(g["x"][idx], g["y"][idx])
    lat = -(90.0 - np.rad2deg(2.0 * np.arctan(r / (2.0 * estimate.MOON_R))))
    lon = np.rad2deg(np.arctan2(g["x"][idx], g["y"][idx]))
    hits = sum((estimate.estimate(float(a), float(b))["verdict"] == "yes") == (g["margin"][i] >= 0)
               for a, b, i in zip(lat, lon, idx))
    assert hits >= 150      # training points, so this is a sanity check, not an accuracy claim
