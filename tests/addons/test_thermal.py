"""Add-on "Temperature (NASA Diviner)".  The router is mounted in a small app here, so api.py is not touched.
Uses the compact Diviner files under data/addons/thermal (built from the PDS products, see ADDON_thermal.md)."""
import os

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday.addons import thermal as T

app = FastAPI()
app.include_router(T.router)
client = TestClient(app)

HAVE = (os.path.exists(os.path.join(T.DATA_DIR, "prp_south_84.npz"))
        and os.path.exists(os.path.join(T.DATA_DIR, "night_min_240m.npy")))
needs = pytest.mark.skipif(not HAVE, reason="Diviner compact files not installed")


@needs
def test_opening_example_values():
    r = client.get("/api/addons/thermal", params={"lat": -89.010, "lon": 122.764})
    assert r.status_code == 200
    d = r.json()
    assert d["measured_by"] == "Diviner"
    assert d["max_k"] == pytest.approx(217.8, abs=0.2)
    assert d["min_k"] == pytest.approx(43.6, abs=0.2)
    assert d["coldest_night_k"] == pytest.approx(47.2, abs=0.2)
    assert d["cold_trap"]["in"] is False and d["cold_trap"]["near"] is False
    assert "Diviner" in d["source"]["instrument"]


@needs
def test_c1_ridge_is_warm_not_a_cold_trap():
    d = client.get("/api/addons/thermal", params={"lat": -89.4398, "lon": -137.17}).json()
    assert d["max_k"] == pytest.approx(245.8, abs=0.2)
    assert d["min_k"] == pytest.approx(54.0, abs=0.2)
    assert d["cold_trap"]["in"] is False


@needs
def test_published_lcross_site_check():
    # Paige et al. 2010, Science 330:479: at the LCROSS impact site Diviner measured summer-solstice
    # daytime 46.7 K and night 38.7 K; annual average surface temperature "close to 38 K".
    d = T.thermal_at(-84.675, -48.703)
    assert abs(d["max_k"] - 46.7) < 3.0
    assert abs(d["avg_k"] - 38.0) < 3.0
    assert d["cold_trap"]["in"] is True


@needs
def test_permanently_shadowed_craters_are_cold_traps():
    for lat, lon in [(-89.67, 129.78), (-87.18, 84.31)]:  # Shackleton, Faustini floors
        d = T.thermal_at(lat, lon)
        assert d["max_k"] < 110 and d["cold_trap"]["in"]
        assert d["min_k"] < d["max_k"]


@needs
def test_grid_orientation_matches_prp():
    # The 240 m night maps and the polar resource product must agree on where cold ground is.
    z = np.load(os.path.join(T.DATA_DIR, "prp_south_84.npz"))
    g = np.load(os.path.join(T.DATA_DIR, "night_min_240m.npy"))
    k = np.random.default_rng(1).choice(len(z["lat"]), 5000, replace=False)
    v, a = [], []
    for i in k:
        r, c = T.gdr_index(float(z["lat"][i]), float(z["lon"][i]))
        if 0 <= r < g.shape[0] and 0 <= c < g.shape[1] and g[r, c] != T.MISSING:
            v.append(g[r, c] * T.GDR_DN)
            a.append(z["temp_avg"][i])
    assert np.corrcoef(v, a)[0, 1] > 0.7


def test_rejects_non_polar_sites():
    assert client.get("/api/addons/thermal", params={"lat": 10, "lon": 0}).status_code == 422
    assert client.get("/api/addons/thermal", params={"lat": -95, "lon": 0}).status_code == 422


@needs
def test_longitude_wraps():
    a = client.get("/api/addons/thermal", params={"lat": -89.4398, "lon": -137.17}).json()
    b = client.get("/api/addons/thermal", params={"lat": -89.4398, "lon": 222.83}).json()
    assert a["max_k"] == b["max_k"] and a["min_k"] == b["min_k"]


def test_js_card_is_self_contained():
    js = os.path.join(T.ROOT, "static", "addons", "thermal.js")
    src = open(js, encoding="utf-8").read()
    assert "addon-thermal" in src and "/api/addons/thermal" in src
    assert "Temperature (NASA Diviner)" in src and "var(--surface" in src


@needs
def test_compact_files_small():
    for f in ("prp_south_84.npz", "night_min_240m.npy", "night_count_240m.npy"):
        assert os.path.getsize(os.path.join(T.DATA_DIR, f)) < 50 * 1024 * 1024
