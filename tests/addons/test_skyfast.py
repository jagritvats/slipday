"""Add-on: nearest precomputed skyline, GET /api/addons/skyfast."""
import time

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday.addons import skyfast

SETS = skyfast._sets()
pytestmark = pytest.mark.skipif(not SETS, reason="no stored skylines installed")
CLIENT = TestClient((lambda a: (a.include_router(skyfast.router), a)[1])(FastAPI()))


def _set(name):
    s = next((s for s in SETS if s["name"] == name), None)
    if s is None:
        pytest.skip(f"{name} skylines not installed")
    return s


def test_shape_matches_why_skyline():
    r = CLIENT.get("/api/addons/skyfast", params={"lat": -89.6, "lon": 30.0})
    assert r.status_code == 200
    j = r.json()
    sk = j["skyline"]
    assert set(sk) == {"az_deg", "el_deg", "dist_km", "site_height_m", "mast_m"}   # the keys why.py writes
    assert len(sk["az_deg"]) == len(sk["el_deg"]) == len(sk["dist_km"]) == 720
    assert sk["az_deg"][0] == 0.0 and sk["az_deg"][1] == 0.5 and sk["az_deg"][-1] == 359.5
    assert sk["mast_m"] == 2.0
    assert j["label"] == "approximate: nearest precomputed point" and j["approximate"] is True
    assert {"lat", "lon"} <= set(j["point"]) and j["distance_m"] >= 0
    assert j["grid"]["name"] in ("close-up", "close-up scatter", "whole map")


@pytest.mark.parametrize("name,i", [("close-up", 0), ("close-up", 7321), ("whole map", 40000)])
def test_stored_point_returns_its_own_row(name, i):
    s = _set(name)
    j = skyfast.nearest(float(s["lat"][i]), float(s["lon"][i]))
    assert j["distance_m"] < 1.0 and j["grid"]["name"] == name
    want = np.asarray(s["el"][i], dtype=float) * s["scale"]
    assert np.allclose(j["skyline"]["el_deg"], want, atol=1e-3)


def test_close_up_click_uses_close_up_grid():
    j = skyfast.nearest(-89.7, 100.0)
    assert j["grid"]["name"].startswith("close-up") and j["distance_m"] <= 360.0


def test_far_from_any_stored_point_is_404():
    r = CLIENT.get("/api/addons/skyfast", params={"lat": -60.0, "lon": 0.0})
    assert r.status_code == 404


def test_bad_args_422():
    assert CLIENT.get("/api/addons/skyfast", params={"lat": -95, "lon": 0}).status_code == 422
    assert CLIENT.get("/api/addons/skyfast", params={"lat": -89}).status_code == 422


def test_fast():
    rng = np.random.default_rng(1)
    CLIENT.get("/api/addons/skyfast", params={"lat": -89.5, "lon": 0})
    ts = []
    for _ in range(30):
        t = time.perf_counter()
        r = CLIENT.get("/api/addons/skyfast", params={"lat": rng.uniform(-90, -80.5), "lon": rng.uniform(-180, 180)})
        ts.append(time.perf_counter() - t)
        assert r.status_code == 200
    assert max(ts) < 0.05, ts


def test_memory_mapped():
    for s in SETS:
        assert isinstance(s["el"], np.memmap)
