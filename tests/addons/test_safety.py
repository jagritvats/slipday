"""Add-on "Flat enough to land?": slope at lander scale.  The router is mounted in a small app here, so api.py is
not touched.  Real LOLA grids are read in place; tests that need a grid skip when it is not installed."""
import json
import math
import os

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday import field, regions, scatterfield
from slipday.addons import safety
from slipday.dem import PolarStereoDEM

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = [n for n, _l, _g in safety.grids()]
HAVE_5 = "ldem_site01_5m" in NAMES and "ldem_site07_5m" in NAMES
HAVE_20 = "ldem_pole_20m" in NAMES
HAVE_80 = "ldem_80s_80m" in NAMES
needs_5 = pytest.mark.skipif(not HAVE_5, reason="the LOLA 5 m site models are not installed (data/dem5)")
needs_20 = pytest.mark.skipif(not HAVE_20, reason="the LOLA 20 m crop is not installed (data/dem20)")
needs_80 = pytest.mark.skipif(not HAVE_80, reason="the LOLA 80 m grid is not installed (data/dem)")
HAVE_MAP = field.load() is not None and scatterfield.load() is not None and HAVE_20
needs_map = pytest.mark.skipif(not HAVE_MAP, reason="the slip-margin map or its scatter skylines are not built")

OPENING = (-89.0098, 122.76389)
C1 = (-89.4398, -137.17)
IM1 = (-80.13, 1.44)

app = FastAPI()
app.include_router(safety.router)
client = TestClient(app)


def _plane(px: float, tilt_deg: float, azimuth_deg: float, lat_c: float = -89.0) -> PolarStereoDEM:
    """A tilted plane on a small polar-stereographic grid centred on (lat_c, 0)."""
    g = PolarStereoDEM(name="plane", pixel_m=px, x0_m=0.0, y0_m=0.0, z=np.zeros((2, 2)))
    xc, yc = g.project(lat_c, 0.0)
    n = 41
    x0, y0 = float(xc) - (n // 2) * px, float(yc) + (n // 2) * px
    xs = x0 + np.arange(n) * px
    ys = y0 - np.arange(n) * px
    X, Y = np.meshgrid(xs, ys)
    k = 2.0 / (1.0 + math.sin(math.radians(abs(lat_c))))          # map metres per ground metre near lat_c
    t = math.tan(math.radians(tilt_deg)) / k
    a = math.radians(azimuth_deg)
    Z = t * ((X - xc) * math.sin(a) + (Y - yc) * math.cos(a)) + 1000.0
    return PolarStereoDEM(name="plane", pixel_m=px, x0_m=x0, y0_m=y0, z=Z.astype(np.float64))


# ---------------- the method ----------------

@pytest.mark.parametrize("px,base", [(5.0, 10.0), (20.0, 20.0), (80.0, 80.0)])
@pytest.mark.parametrize("tilt", [0.0, 3.0, 8.0, 15.0])
def test_plane_slope_is_recovered(px, base, tilt):
    for az in (0.0, 37.0, 90.0, 200.0):
        g = _plane(px, tilt, az)
        lat, lon = g.unproject(*g.project(-89.0, 0.0))
        s, b = safety.slope_on(g, [lat], [lon])
        assert b == base
        assert s[0] == pytest.approx(tilt, abs=0.05)


def test_outside_the_grid_is_nan():
    g = _plane(5.0, 4.0, 0.0)
    s, _ = safety.slope_on(g, [-85.0], [0.0])
    assert math.isnan(s[0])


def test_rules_are_nasas_numbers():
    assert safety.LIMIT_DEG == 8.0 and safety.GOAL_DEG == 5.0
    assert safety.DEFAULT_SCATTER_M == 100.0
    assert "HLS-R-0071" in safety.SOURCE["limit"] and "8" in safety.SOURCE["limit"]
    assert "HLS-R-0021" in safety.SOURCE["accuracy"]
    assert "lean" in safety.SOURCE["limit_note"]


def test_grids_finest_first():
    px = [g.pixel_m for _n, _l, g in safety.grids()]
    assert px == sorted(px)


# ---------------- against NASA's own 5 m slope maps ----------------

@needs_5
def test_matches_nasa_5m_slope_maps():
    """NASA publishes a slope map with each 5 m site model.  Our slope, from the height grid, should match it."""
    d = json.load(open(os.path.join(HERE, "safety_nasa_slope_sample.json"), encoding="utf-8"))
    for site, gname in (("Site01", "ldem_site01_5m"), ("Site07", "ldem_site07_5m")):
        g = next(g for n, _l, g in safety.grids() if n == gname)
        rows = np.array(d[site]["rows"], dtype=float)
        ours, base = safety.slope_on(g, rows[:, 0], rows[:, 1])
        assert base == 10.0
        diff = np.abs(ours - rows[:, 2])
        assert np.isfinite(ours).all()
        assert np.median(diff) < 0.3                               # measured: 0.12 and 0.10 degrees
        assert np.percentile(diff, 90) < 1.0                       # measured: 0.54 and 0.63
        assert np.corrcoef(ours, rows[:, 2])[0, 1] > 0.99          # measured: 0.997 and 0.996


@needs_5
def test_opening_example_and_c1_agree_with_nasa_map():
    d = json.load(open(os.path.join(HERE, "safety_nasa_slope_sample.json"), encoding="utf-8"))
    for (lat, lon), site, key in ((OPENING, "Site07", "opening"), (C1, "Site01", "C1")):
        r = safety.site_slopes(lat, lon, 100.0)
        ours = [p["slope_deg"] for p in r["points"]]
        nasa = d[site][key]["nasa_slope_deg"]
        assert max(abs(a - b) for a, b in zip(ours, nasa)) < 0.5
        assert max(nasa) < safety.LIMIT_DEG


# ---------------- the sites in the hand-over ----------------

@needs_5
def test_opening_example():
    r = safety.site_slopes(*OPENING, 100.0, "opening")
    assert r["available"] and r["points_total"] == 13 and r["points_known"] == 13
    assert all(p["grid_m"] == 5.0 and p["baseline_m"] == 10.0 for p in r["points"])
    assert r["verdict"] == "flat" and r["points_passing"] == 13
    assert r["steepest"]["slope_deg"] == pytest.approx(4.9, abs=0.05)
    assert "Site07" in r["grids_used"][0]["label"]


@needs_5
def test_c1():
    r = safety.site_slopes(*C1, 100.0, "C1")
    assert r["verdict"] == "flat" and r["points_passing"] == 13
    assert all(p["grid_m"] == 5.0 for p in r["points"])
    assert r["steepest"]["slope_deg"] == pytest.approx(3.9, abs=0.05)
    assert "Site01" in r["grids_used"][0]["label"]


@needs_80
def test_im1_matches_the_published_slope():
    """LROC (26 Feb 2024) gives IM-1's local slope as 12 degrees; the lander tipped over.  80 m terrain only."""
    r = safety.site_slopes(*IM1, 100.0, "IM-1")
    assert all(p["grid_m"] == 80.0 and p["baseline_m"] == 80.0 for p in r["points"])
    assert r["points"][0]["slope_deg"] == pytest.approx(12.0, abs=1.5)      # measured 12.2
    assert r["verdict"] == "steep" and r["points_passing"] == 0


@needs_80
def test_published_artemis_sites_are_flat_at_the_target():
    """Wueller et al. 2026 picked these sites under 8 degrees on the 20 m grid; ours must not call their centres steep."""
    sites = regions.load_sites(nine_only=True)
    if not sites:
        pytest.skip("the published sites file is not installed")
    assert len(sites) == 78
    centres = safety.slope_finest([s["lat"] for s in sites], [s["lon"] for s in sites])["slope"]
    assert np.isfinite(centres).all()
    assert (centres < safety.LIMIT_DEG).all()


def test_far_from_any_polar_grid_is_unknown():
    r = safety.site_slopes(0.67416, 23.47314, 100.0, "Apollo 11")
    assert r["verdict"] == "unknown" and r["points_known"] == 0


# ---------------- the router ----------------

@needs_5
def test_site_endpoint_by_id_and_by_point():
    a = client.get("/api/addons/safety/site", params={"id": "robust_pick"}).json()
    b = client.get("/api/addons/safety/site", params={"lat": OPENING[0], "lon": OPENING[1]}).json()
    assert a["verdict"] == b["verdict"] == "flat"
    assert a["site"]["name"].startswith("Slip-robust ridge point")
    assert [p["slope_deg"] for p in a["points"]] == [p["slope_deg"] for p in b["points"]]
    assert len(a["points"]) == 13 and a["limit_deg"] == 8.0
    assert all(set(p) >= {"slope_deg", "passes", "grid_m", "baseline_m", "by_grid"} for p in a["points"])


@needs_5
def test_site_endpoint_scatter_radius():
    near = client.get("/api/addons/safety/site", params={"id": "shackleton", "scatter_m": 0}).json()
    assert {(p["lat"], p["lon"]) for p in near["points"]} == {(round(C1[0], 5), round(C1[1], 5))}
    wide = client.get("/api/addons/safety/site", params={"id": "shackleton", "scatter_m": 300}).json()
    assert wide["scatter_m"] == 300 and len(wide["points"]) == 13


def test_site_endpoint_errors():
    assert client.get("/api/addons/safety/site", params={"id": "no_such_site"}).status_code == 404
    assert client.get("/api/addons/safety/site").status_code == 422
    assert client.get("/api/addons/safety/site", params={"lat": 120, "lon": 0}).status_code == 422


def test_about_endpoint():
    a = client.get("/api/addons/safety/about").json()
    assert a["limit_deg"] == 8.0 and a["lander_baseline_m"] == 10.0
    assert any("boulder" in x for x in a["limits"])


@needs_map
def test_map_layer():
    body = {"start": "2026-11-18T00:00:00Z", "n_dates": 60, "earth_stations": True}
    r = client.post("/api/addons/safety/map-layer", json=body).json()
    assert r["available"], r
    n = r["n"] * r["n"]
    layer = np.array(r["layer"])
    assert len(layer) == n == len(r["steepest_deg"])
    assert set(np.unique(layer)) <= {2, 1, 0, -1, -2}
    assert sum(r["counts"].values()) == n
    steep = np.array([np.nan if v is None else v for v in r["steepest_deg"]], dtype=float)
    assert (steep[layer == 2] <= 8.0).all() and (steep[layer == 1] > 8.0).all()
    # slip-tolerant here is exactly "keeps at least 1 day of slip at all 13 touchdown points" on the page's own map
    from slipday.metrics import Criteria
    rm = scatterfield.robust_margin(body["start"], 60, 14.0, Criteria(0.5, -90.0, -90.0, 0.0, True), 0.0, 240.0, 100.0, True, True)
    robust = np.asarray(rm["robust"])
    assert ((layer >= 1) == (robust >= 1)).all()
    assert r["slip_tolerant"] == int((robust >= 1).sum())
    assert ((layer == -1) == (robust == -1)).all()
    # every point in a tolerant class has its slope from a grid of 20 m or finer
    assert all(g["grid_m"] <= 20.0 for g in r["grids_used"])


@needs_map
def test_map_layer_min_slip_days_and_mast():
    base = {"start": "2026-11-18T00:00:00Z", "n_dates": 60, "earth_stations": True}
    a = client.post("/api/addons/safety/map-layer", json=dict(base, min_slip_days=0)).json()
    b = client.post("/api/addons/safety/map-layer", json=dict(base, min_slip_days=3)).json()
    assert a["slip_tolerant"] >= b["slip_tolerant"]
    m = client.post("/api/addons/safety/map-layer", json=dict(base, mast_m=10.0)).json()
    assert not m["available"] and "2 m" in m["reason"]
    assert client.post("/api/addons/safety/map-layer", json={"start": "not a date"}).status_code == 422
