"""Add-on "Relay satellites: contact when the Earth is hidden".  The router is mounted in a small app here, so
api.py is not touched.  Tests that need the real LOLA 80 m grid skip when it is not installed."""
import hashlib
import math
import os

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday import demstore, sites
from slipday.addons import relay as R
from slipday.ephem import _PA_TO_ME, MOON_RADIUS_KM, parse_utc, rotation, unix_to_jd_tdb
from slipday.geometry import Horizon, Site
from slipday.metrics import Criteria, slip_grid

app = FastAPI()
app.include_router(R.router)
client = TestClient(app)

REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")
HAVE_80 = (os.path.exists(os.path.join(REAL_DEM, "ldem_80s_80m_f32.npy"))
           and os.path.exists(os.path.join(REAL_DEM, "dems.json")))
needs_80 = pytest.mark.skipif(not HAVE_80, reason="the 80 m grid is not installed (run scripts/fetch_grid80.py)")

LANDING = "2026-11-18T00:00:00Z"
T0 = parse_utc(R.EPOCH_UTC).timestamp()


def _smooth(lat, lon, name="smooth"):
    return Site(name, lat, lon, horizon=Horizon())


# ---------------- the source ----------------

def test_source_files_are_stored_with_the_recorded_sha256():
    for fname, sha in R.SOURCE["sha256"].items():
        path = os.path.join(R.DATA_DIR, fname)
        assert os.path.exists(path), fname
        assert hashlib.sha256(open(path, "rb").read()).hexdigest() == sha


def test_source_text_holds_the_numbers_used():
    txt = open(os.path.join(R.DATA_DIR, "LCRNS_Reference_Constellation_White_Paper_03_2025.docx.txt"),
               encoding="utf-8").read()
    for k, st in R.STATES.items():
        for v in st:
            assert f"{v:.6f}" in txt, (k, v)
    for k, el in R.TABLE1.items():
        for v in el:
            assert f"{v:.6f}" in txt, (k, v)
    assert "approximately 30 hours on average" in txt
    assert "This reference design is not final" in txt
    assert "March 01, 2027 00:00:00.000 UTC" in txt


def test_label_says_representative_not_live():
    assert "representative relay orbit" in R.LABEL and "not a live service" in R.LABEL


# ---------------- geometry ----------------

def test_gm_moon_from_de421():
    assert R.gm_moon() == pytest.approx(4902.80, abs=0.01)


def test_start_state_is_reproduced_at_the_epoch():
    for k, st in R.STATES.items():
        p = R.positions_icrf(k, np.array([T0]))[0]
        assert np.linalg.norm(p - np.array(st[:3])) < 1e-6


def test_period_from_propagated_positions_matches_the_source():
    """Time between closest approaches, read off the propagated positions at 10 s steps."""
    u = T0 + np.arange(0, 5 * 31 * 3600, 10.0)
    for k in R.STATES:
        r = np.linalg.norm(R.positions_icrf(k, u), axis=1)
        i = np.nonzero((r[1:-1] < r[:-2]) & (r[1:-1] < r[2:]))[0] + 1
        assert len(i) >= 4
        period_h = float(np.mean(np.diff(u[i]))) / 3600.0
        assert period_h == pytest.approx(30.0, abs=0.1)                      # source: "approximately 30 hours"
        a = R.TABLE1[k][0]
        kepler_h = 2 * math.pi * math.sqrt(a ** 3 / R.gm_moon()) / 3600.0
        assert period_h == pytest.approx(kepler_h, abs=0.01)


def test_apolune_and_perilune_against_table1():
    u = T0 + np.arange(0, 31 * 3600, 30.0)
    for k in R.STATES:
        a, e = R.TABLE1[k][0], R.TABLE1[k][1]
        r = np.linalg.norm(R.positions_icrf(k, u), axis=1)
        assert r.max() == pytest.approx(a * (1 + e), rel=1e-4)
        assert r.min() == pytest.approx(a * (1 - e), rel=1e-4)
        assert r.max() - MOON_RADIUS_KM == pytest.approx(17409, abs=10)       # altitude at apolune, km
        assert r.min() - MOON_RADIUS_KM == pytest.approx(1748, abs=10)        # altitude at perilune, km


def test_table2_matches_table1_in_the_moon_frame_at_j2000():
    """Table 1 is 'in the Moon-centered Principal Axis Frame, referenced to the J2000 Epoch'."""
    m = _PA_TO_ME.T @ rotation(np.array([2451545.0]))[0]
    for k, st in R.STATES.items():
        r, v = m @ np.array(st[:3]), m @ np.array(st[3:])
        h = np.cross(r, v)
        inc = math.degrees(math.acos(h[2] / np.linalg.norm(h)))
        node = np.cross([0.0, 0.0, 1.0], h)
        raan = math.degrees(math.atan2(node[1], node[0])) % 360
        ev = np.cross(v, h) / R.gm_moon() - r / np.linalg.norm(r)
        aop = math.degrees(math.acos(node @ ev / np.linalg.norm(node) / np.linalg.norm(ev)))
        aop = aop if ev[2] >= 0 else 360 - aop
        sma, ecc, inc1, raan1, aop1, _ta = R.TABLE1[k]
        assert inc == pytest.approx(inc1, abs=0.01)
        assert raan == pytest.approx(raan1, abs=0.01)
        assert aop == pytest.approx(aop1, abs=0.01)
        el = R.elements(st)
        assert el["a_km"] == pytest.approx(sma, rel=1e-4) and el["e"] == pytest.approx(ecc, abs=1e-5)


def test_apolune_is_far_south_and_perilune_far_north():
    u = T0 + np.arange(0, 31 * 3600, 60.0)
    p = R.positions_icrf("SV-1", u)
    bf = R._to_fixed(u, p)
    r = np.linalg.norm(bf, axis=1)
    lat = np.degrees(np.arcsin(bf[:, 2] / r))
    assert -63 < lat[np.argmax(r)] < -59
    assert 59 < lat[np.argmin(r)] < 63


def test_the_two_relays_share_one_plane_half_an_orbit_apart():
    e1, e2 = R.elements(R.STATES["SV-1"]), R.elements(R.STATES["SV-2"])
    assert math.degrees(math.acos(min(1.0, float(e1["W"] @ e2["W"])))) < 0.5
    assert abs(((e2["M0"] - e1["M0"]) % (2 * math.pi)) - math.pi) < 1e-3
    assert R.CONFIGS["two"] == ("SV-1", "SV-2") and R.CONFIGS["one"] == ("SV-1",)


def test_line_of_sight_to_earth_is_blocked_by_the_moon():
    earth = np.array([[384400.0, 0.0, 0.0]] * 3)
    relay = np.array([[-5000.0, 0.0, 0.0], [5000.0, 0.0, 0.0], [-5000.0, 3000.0, 0.0]])
    assert R._earth_clear_of_moon(relay, earth).tolist() == [False, True, True]


def test_relay_seen_from_the_pole_most_of_the_time_on_a_smooth_sphere():
    """From near the south pole, an orbit with apolune far south is above the level horizon most of each orbit."""
    s = _smooth(-89.9, 0.0)
    u = T0 + 3600.0 * np.arange(24 * 14)
    from slipday.ephem import compute_table
    tab = compute_table(u)
    vis = R.relay_visible(s, u, tab.earth, ("SV-1",), rotation(unix_to_jd_tdb(u)))
    assert 0.6 < vis.mean() < 1.0
    north = _smooth(89.9, 0.0)
    vis_n = R.relay_visible(north, u, tab.earth, ("SV-1",), rotation(unix_to_jd_tdb(u)))
    assert vis_n.mean() < vis.mean()


# ---------------- the counts ----------------

def _check_shape(d):
    h = d["hours"]
    assert len(d["code"]) == d["window_hours"] == 336
    assert h["either"] == h["earth_only"] + h["relay_only"] + h["both"]
    assert h["either"] + h["none"] == 336
    assert h["earth"] == h["earth_only"] + h["both"] and h["relay"] == h["relay_only"] + h["both"]
    assert h["either"] >= max(h["earth"], h["relay"])
    assert d["slip"]["margin_either_days"] >= d["slip"]["margin_earth_days"]


@pytest.mark.parametrize("stations", [True, False])
def test_earth_hours_are_the_apps_own(stations):
    s = _smooth(-89.0098, 122.76389)
    d = R.analyse(s, LANDING, "two", spread=False, stations=stations)
    _check_shape(d)
    g = slip_grid([s], LANDING, R.SLIP_DAYS, 24, R.WINDOW_DAYS, Criteria(stations=stations))["rows"][0]
    assert d["slip"]["earth_h_by_day"] == g["earth"]
    assert d["slip"]["sunlit_h_by_day"] == g["sunlit"]


def test_spread_brackets_the_as_published_count():
    d = R.analyse(_smooth(-89.4398, -137.17), LANDING, "one", spread=True)
    sp = d["spread"]
    assert sp["runs"] == 144
    assert sp["relay_h"]["lowest"] <= sp["relay_h"]["highest"]
    assert sp["either_h"]["lowest"] >= d["hours"]["earth"]
    assert sp["either_h"]["highest"] <= 336


def test_more_relays_never_give_fewer_hours():
    s = _smooth(-85.295, 36.9168)
    one = R.analyse(s, LANDING, "one", spread=False)
    two = R.analyse(s, LANDING, "two", spread=False)
    assert two["hours"]["relay"] >= one["hours"]["relay"]
    assert two["hours"]["earth"] == one["hours"]["earth"]


# ---------------- the router ----------------

def test_info_route():
    r = client.get("/api/addons/relay")
    assert r.status_code == 200
    j = r.json()
    assert j["label"] == R.LABEL and j["source"]["record_url"].endswith("20250002698")
    assert j["satellites"]["SV-1"]["two_body_period_h"] == pytest.approx(30.0, abs=0.1)


def test_window_route_smooth_sphere():
    r = client.get("/api/addons/relay/window", params={"lat": -89.0098, "lon": 122.76389, "landing": LANDING,
                                                       "spread": "false"})
    assert r.status_code == 200
    j = r.json()
    _check_shape(j)
    assert j["config"] == "two" and j["one_relay"]["hours"]["earth"] == j["hours"]["earth"]
    assert j["stations"] is True


def test_window_route_refuses_bad_input():
    assert client.get("/api/addons/relay/window", params={"landing": "not a date"}).status_code == 422
    assert client.get("/api/addons/relay/window", params={"config": "five"}).status_code == 422
    assert client.get("/api/addons/relay/window", params={"lat": -89.0}).status_code == 422
    assert client.get("/api/addons/relay/window", params={"site": "nowhere"}).status_code == 404
    assert client.get("/api/addons/relay/window", params={"landing": "2049-12-20T00:00:00Z"}).status_code == 422


# ---------------- the real terrain (the numbers in ADDON_relay.md) ----------------

@pytest.fixture()
def real_dem():
    old = os.environ.get("SLIPDAY_DEM_DIR")
    os.environ["SLIPDAY_DEM_DIR"] = REAL_DEM
    demstore.reload()
    sites._terrain_profile.cache_clear()
    yield
    if old is not None:
        os.environ["SLIPDAY_DEM_DIR"] = old
    demstore.reload()
    sites._terrain_profile.cache_clear()


EXPECTED = {   # site: (Earth h, one relay: relay h, either h; two relays: either h; margin Earth, one, two)
    "robust_pick": (311, 292, 333, 336, 8, 11, 11),
    "shackleton": (295, 292, 332, 336, 8, 12, 59),
    "nr101": (336, 292, 336, 336, 14, 17, 59),
}


def _real_site(key):
    if key == "nr101":
        return sites.custom_site("Nobile Rim 1, site NR101", -85.295, 36.9168)
    return sites.get_site(key)


@needs_80
@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_the_three_sites_on_the_80m_grid(real_dem, key):
    s = _real_site(key)
    assert s.horizon.is_terrain
    e_h, r1, x1, x2, m_e, m1, m2 = EXPECTED[key]
    one = R.analyse(s, LANDING, "one", spread=False)
    two = R.analyse(s, LANDING, "two", spread=False)
    _check_shape(one)
    _check_shape(two)
    assert one["hours"]["earth"] == two["hours"]["earth"] == e_h
    assert (one["hours"]["relay"], one["hours"]["either"], two["hours"]["either"]) == (r1, x1, x2)
    assert one["slip"]["margin_earth_days"] == two["slip"]["margin_earth_days"] == m_e
    assert (one["slip"]["margin_either_days"], two["slip"]["margin_either_days"]) == (m1, m2)
    g = slip_grid([s], LANDING, R.SLIP_DAYS, 24, R.WINDOW_DAYS, Criteria(stations=True))["rows"][0]
    assert two["slip"]["earth_h_by_day"] == g["earth"]


@needs_80
def test_opening_example_margin_is_ended_by_earth_then_by_sunlight(real_dem):
    d = R.analyse(sites.get_site("robust_pick"), LANDING, "two", spread=False)
    assert d["slip"]["earth_ends_because"] == ["only 95 hours of Earth contact of the 100 needed"]
    assert d["slip"]["either_ends_because"] == ["only 229 sunlit hours of the 240 needed"]
