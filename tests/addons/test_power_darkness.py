"""Add-ons "Battery through the night" (power.py) and "Darkness check" (darkness.py).  The routers are mounted
in a small app here.  Tests run with no DEM installed (smooth horizon); the stored sources are checked by sha256."""
import hashlib
import os

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday.addons import power as P
from slipday.addons import darkness as T
from slipday.geometry import Horizon, Site

app = FastAPI()
app.include_router(P.router)
app.include_router(T.router)
client = TestClient(app)
LANDING = "2026-11-18T00:00:00Z"


def _smooth(lat=-89.0098, lon=122.76389):
    return Site("smooth", lat, lon, horizon=Horizon())


# ---------------- the panel geometry ----------------

def test_incidence_vertical_tracking_and_horizontal():
    assert P.incidence([0.0], [0.0], "vertical_tracking")[0] == pytest.approx(1.0)
    assert P.incidence([30.0], [0.0], "horizontal")[0] == pytest.approx(0.5)
    assert P.incidence([-5.0], [0.0], "vertical_tracking")[0] == 0.0          # Sun below the level horizon


def test_incidence_fixed_faces_share_the_array():
    # four faces at 0, 90, 180, 270 deg: Sun straight at one face gives that face only (a quarter of the array)
    assert P.incidence([0.0], [0.0], "vertical_fixed", 4)[0] == pytest.approx(0.25)
    # Sun between two faces: two faces at 45 deg
    assert P.incidence([0.0], [45.0], "vertical_fixed", 4)[0] == pytest.approx(2 * np.cos(np.pi / 4) / 4)


def test_unknown_panel_is_refused():
    with pytest.raises(ValueError):
        P.incidence([0.0], [0.0], "roof")


# ---------------- the battery ----------------

def test_constant_dark_empties_on_time():
    n = 200
    r = P.simulate(np.zeros(n), np.zeros(n, dtype=bool), 0, 50, 1000.0, 200.0, 100.0, 0.9)
    assert r["empty_after_h"] == 10


def test_constant_sun_with_surplus_never_empties_and_stays_full():
    n = 100
    r = P.simulate(np.full(n, 300.0), np.ones(n, dtype=bool), 0, 50, 1000.0, 200.0, 100.0, 0.9)
    assert r["empty_after_h"] is None and r["min_wh"] == pytest.approx(1000.0)
    assert r["hours"] == 50


def test_night_under_way_at_window_end_is_followed_to_its_end():
    sunlit = np.array([True] * 10 + [False] * 30 + [True] * 10)
    power = np.where(sunlit, 500.0, 0.0)
    r = P.simulate(power, sunlit, 0, 20, 10000.0, 100.0, 10.0, 1.0)
    assert r["hours"] == 40                        # 20 window hours, then on to the end of the night at hour 40
    assert r["min_wh"] == pytest.approx(10000.0 - 30 * 10.0)


def test_charge_efficiency_applies_to_surplus_only():
    sunlit = np.array([False] * 5 + [True] * 5)
    power = np.where(sunlit, 200.0, 0.0)
    r = P.simulate(power, sunlit, 0, 10, 1000.0, 100.0, 100.0, 0.5)
    assert r["curve_wh"][5] == pytest.approx(500.0)
    assert r["curve_wh"][10] == pytest.approx(500.0 + 5 * 100.0 * 0.5)


def test_analyse_smooth_site_reports_every_day_and_labels_figures():
    r = P.analyse(_smooth(), LANDING, slip_days=5)
    assert r["available"] and len(r["days"]) == 5
    for d in r["days"]:
        assert d["text"].startswith(("survives", "battery empties", "no night"))
        assert (d["empty_after_h"] is None) == d["survives"]
    for k, f in r["figures"].items():
        assert f["label"] == "illustrative" or f["source"] in P.SOURCES, k


def test_user_figures_override_and_are_reported():
    r = P.analyse(_smooth(), LANDING, slip_days=2, battery_wh=123456.0, night_load_w=1.0)
    assert r["used"]["battery_wh"] == 123456.0 and "battery_wh" in r["changed_by_user"]
    assert all(d["survives"] for d in r["days"])
    r2 = P.analyse(_smooth(), LANDING, slip_days=2, battery_wh=1.0, day_load_w=1e5, night_load_w=1e5)
    assert not any(d["survives"] for d in r2["days"]) and r2["days"][0]["empty_after_h"] == 1


# ---------------- the endpoints ----------------

def test_power_info_and_site_endpoints():
    j = client.get("/api/addons/power").json()
    assert j["available"] and "battery_wh" in j["figures"] and "Not modelled" in j["rule"]
    j = client.get("/api/addons/power/site", params={"landing": LANDING, "slip_days": 3, "battery_kwh": 5,
                                                     "night_load_w": 40}).json()
    assert j["used"]["battery_wh"] == 5000.0 and j["used"]["night_load_w"] == 40.0
    assert len(j["days"]) == 3 and len(j["day0_curve_pct"]) == j["days"][0]["hours_run"] + 1


def test_power_site_refuses_bad_input():
    assert client.get("/api/addons/power/site", params={"landing": "soon"}).status_code == 422
    assert client.get("/api/addons/power/site", params={"panel": "roof"}).status_code == 422
    assert client.get("/api/addons/power/site", params={"site": "nowhere"}).status_code == 404


def test_darkness_runs_and_limit():
    sunlit_only = T.analyse(_smooth(), LANDING, slip_days=3, limit_h=10)
    assert sunlit_only["limit_h"] == 10 and sunlit_only["limit_label"] == "set by the user"
    for d in sunlit_only["days"]:
        assert d["within_limit"] == (d["darkness_h"] <= 10)
    j = client.get("/api/addons/darkness/site", params={"landing": LANDING, "slip_days": 2, "limit_h": 0}).json()
    assert len(j["days"]) == 2
    assert client.get("/api/addons/darkness").json()["available"]


def test_darkness_darkness_on_a_smooth_mid_latitude_site_is_about_half_a_lunar_day():
    # at 45 S on a smooth Moon the Sun is fully down for about 14.5 days of each 29.5
    r = T.analyse(_smooth(-45.0, 0.0), LANDING, slip_days=20)
    assert 320 <= r["longest_over_days_h"] <= 370


# ---------------- the stored sources ----------------

def test_stored_sources_match_their_sha256():
    for mod in (P, T):
        for key, src in mod.SOURCES.items():
            for fname, sha in src.get("sha256", {}).items():
                path = os.path.join(P.DATA_DIR, fname)
                assert os.path.exists(path), fname
                assert hashlib.sha256(open(path, "rb").read()).hexdigest() == sha, fname


def test_defaults_carry_sources_where_found_and_say_none_for_a_flown_lander():
    assert "No published battery capacity" in P.NO_FLOWN
    assert P.LANDER["battery_wh"]["source"] == "compass2022" and P.LANDER["night_load_w"]["source"] == "compass2022"
    assert P.LANDER["array_w"]["source"] is None and P.LANDER["day_load_w"]["source"] is None
    assert T.LIMIT["hours"] == 96.0 and T.LIMIT["source"] == "viper2020"
    txt = open(os.path.join(P.DATA_DIR, P.SOURCES[T.CONTEXT["source"]]["text_file"]), encoding="utf-8", errors="replace").read()
    assert T.CONTEXT["quote"] in txt


def test_quotes_are_in_the_stored_text():
    for mod, items in ((P, [v for v in P.LANDER.values() if isinstance(v, dict)]), (T, [T.LIMIT])):
        for f in items:
            if f.get("source") and f.get("quote"):
                src = mod.SOURCES[f["source"]]
                txt = open(os.path.join(P.DATA_DIR, src["text_file"]), encoding="utf-8", errors="replace").read()
                norm = " ".join(txt.split())
                assert " ".join(f["quote"].split()) in norm, f["quote"]
