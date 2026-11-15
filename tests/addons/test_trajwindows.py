"""Add-on "Launch windows from orbital mechanics".  The router is mounted in a small app here, so api.py is not
touched.  Smooth-horizon sites need no DEM; the terrain test skips when no DEM is installed."""
import math
import os

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday.addons import trajwindows as T
from slipday.ephem import parse_utc
from slipday.geometry import Horizon, Site

app = FastAPI()
app.include_router(T.router)
client = TestClient(app)

LANDING = "2026-11-18T00:00:00Z"


def _smooth(lat, lon, name="smooth"):
    return Site(name, lat, lon, horizon=Horizon())


def test_describe_lists_labelled_assumptions():
    r = client.get("/api/addons/trajwindows")
    assert r.status_code == 200
    d = r.json()
    assert d["compares_with"]["days"] == pytest.approx(29.530589)
    keys = {a["key"] for a in d["assumptions"]}
    assert {"model", "transfer_days", "sun_band_deg", "azimuth_deg", "frames"} <= keys
    assert all(a["label"] in ("assumption", "illustrative") for a in d["assumptions"])


def test_gmst_matches_the_j2000_reference_value():
    # GMST at 2000-01-01 12:00 UT1 is 280.46061837 degrees by definition of the expression
    u = parse_utc("2000-01-01T12:00:00Z").timestamp()
    assert math.degrees(float(T.gmst_rad(u))) == pytest.approx(280.46061837, abs=1e-6)
    # one sidereal day later the angle repeats
    assert math.degrees(float(T.gmst_rad(u + 86164.0905))) == pytest.approx(280.46061837, abs=1e-3)


def test_moon_distance_and_declination_are_physical():
    u = parse_utc(LANDING).timestamp() + np.arange(0, 28 * 86400, 6 * 3600)
    m = T.moon_geocentric(u)
    r = np.linalg.norm(m, axis=1)
    assert r.min() > 350_000 and r.max() < 410_000
    dec = T.declination_deg(m)
    assert dec.max() > 15 and dec.min() < -15 and np.abs(dec).max() < 29.5


def test_launch_plane_contains_site_and_moon():
    # a target straight over the site's own meridian plane: due-east launch gives inclination = latitude
    u = np.array([parse_utc(LANDING).timestamp()])
    phi = 28.573
    th = float(T.gmst_rad(u)[0]) + math.radians(-80.649)
    # a direction 90 degrees east of the site along its own latitude-tangent great circle (the equator if phi=0)
    s = np.array([math.cos(math.radians(phi)) * math.cos(th), math.cos(math.radians(phi)) * math.sin(th),
                  math.sin(math.radians(phi))])
    east = np.array([-math.sin(th), math.cos(th), 0.0])
    az, inc = T.launch_geometry(u, east[None, :], phi, -80.649)
    assert az[0] == pytest.approx(90.0, abs=1e-6)
    assert inc[0] == pytest.approx(phi, abs=1e-6)
    _ = s


def test_i_max_from_azimuth_limits():
    # cos i = cos(lat) sin(az): at 28.573 N the 35 degree azimuth gives about 59.7 degrees
    assert T._i_max(28.573) == pytest.approx(59.7, abs=0.2)


def test_mid_latitude_smooth_site_repeats_close_to_synodic_month():
    out = T.analyse(_smooth(-45.0, 0.0), LANDING, months=3)
    assert len(out["windows"]) >= 3
    for st in out["steps_days"]:
        assert abs(st - T.SYNODIC_DAYS) < 1.5
    for w in out["windows"]:
        assert w["launch_periods"], w["window_open"]
        assert w["declination_check"]["ok"]
        for p in w["launch_periods"]:
            assert T.AZ_MIN_DEG <= p["best_azimuth_deg"] <= T.AZ_MAX_DEG
            launch = parse_utc(p["best_launch"]).timestamp()
            land = parse_utc(p["landing_at_best"]).timestamp()
            assert (land - launch) / 86400 == pytest.approx(T.TRANSFER_DAYS, abs=1e-3)


def test_launch_periods_are_about_two_a_day():
    out = T.analyse(_smooth(-45.0, 0.0), LANDING, months=1)
    w = out["windows"][0]
    span_days = (parse_utc(w["landing_band"][1]).timestamp() - parse_utc(w["landing_band"][0]).timestamp()) / 86400
    assert 1 <= len(w["launch_periods"]) <= 2 * math.ceil(span_days) + 2


def test_landing_sun_is_inside_the_band():
    out = T.analyse(_smooth(-45.0, 0.0), LANDING, months=2)
    for w in out["windows"]:
        assert 0.0 <= w["sun_clearance_at_open_deg"] <= T.SUN_BAND_MAX_DEG


def test_endpoint_with_lat_lon_and_errors():
    r = client.get("/api/addons/trajwindows/windows", params={"lat": -45, "lon": 0, "months": 1,
                                                             "landing": LANDING})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["synodic_rule_days"] == pytest.approx(29.530589)
    assert d["launch_site"]["label"] == "Kennedy (default)"
    assert client.get("/api/addons/trajwindows/windows", params={"landing": "nope"}).status_code == 422
    assert client.get("/api/addons/trajwindows/windows", params={"site": "no_such_site"}).status_code == 404
    assert client.get("/api/addons/trajwindows/windows", params={"lat": -45}).status_code == 422


REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")      # set by tests/conftest.py from SLIPDAY_DEM_DIR
HAVE_DEM = bool(REAL_DEM) and os.path.exists(os.path.join(REAL_DEM, "dems.json"))


@pytest.fixture()
def real_dem():
    from slipday import demstore, sites
    old = os.environ.get("SLIPDAY_DEM_DIR")
    os.environ["SLIPDAY_DEM_DIR"] = REAL_DEM
    demstore.reload()
    sites._terrain_profile.cache_clear()
    yield
    if old is not None:
        os.environ["SLIPDAY_DEM_DIR"] = old
    demstore.reload()
    sites._terrain_profile.cache_clear()


@pytest.mark.skipif(not HAVE_DEM, reason="no DEM installed (set SLIPDAY_DEM_DIR to a folder with dems.json)")
def test_real_terrain_robust_pick(real_dem):
    from slipday.sites import get_site
    s = get_site("robust_pick")
    assert s.horizon.is_terrain
    out = T.analyse(s, LANDING, months=2)
    assert out["site"]["terrain"]
    assert out["windows"]
    for w in out["windows"]:
        assert w["launch_periods"]
        assert 0.0 <= w["sun_clearance_at_open_deg"] <= T.SUN_BAND_MAX_DEG
