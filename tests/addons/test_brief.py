"""Tests for the review-board brief add-on (slipday/addons/brief.py, static/brief.html, static/addons/brief.js).

The browser check is separate: node tests/addons/brief_check.mjs (port 8481)."""
import os

import pytest
from fastapi.testclient import TestClient

from tests.addons.brief_app import app

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
client = TestClient(app)
OPEN = {"site": "robust_pick", "date": "2026-11-18", "slip": 3}
REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")


@pytest.fixture(scope="module", autouse=True)
def real_dem():
    """The real LOLA stack for this module (conftest starts every test with no terrain), as test_planner.py does."""
    from slipday import demstore, sites
    from slipday.addons import brief as B
    old = os.environ.get("SLIPDAY_DEM_DIR")
    if REAL_DEM and os.path.isdir(REAL_DEM):
        os.environ["SLIPDAY_DEM_DIR"] = REAL_DEM
        demstore.reload()
        sites._terrain_profile.cache_clear()
    B._CACHE.clear()
    yield
    if old is not None:
        os.environ["SLIPDAY_DEM_DIR"] = old
    demstore.reload()
    sites._terrain_profile.cache_clear()
    B._CACHE.clear()


@pytest.fixture(scope="module")
def brief():
    r = client.get("/api/addons/brief", params=OPEN)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def mission():
    r = client.post("/api/mission", json={"site": {"id": "robust_pick"}, "landing": "2026-11-18T00:00:00Z", "slip_days": 15})
    assert r.status_code == 200
    return r.json()


def test_has_every_section(brief):
    for k in ("question", "inputs", "verdict", "slip_margin", "windows", "hours", "longest_night", "slope", "lighting",
              "relay", "alternatives", "terrain", "checks", "assumptions", "sources", "answer"):
        assert k in brief, k
    assert set(brief["verdict"]) == {"power_and_contact", "ground"}
    assert "3 days" in brief["question"]
    assert brief["inputs"]["landing_utc"] == "2026-11-18T00:00:00Z" and brief["inputs"]["slip_days"] == 3


def test_numbers_match_the_mission_endpoint(brief, mission):
    assert brief["slip_margin"]["days"] == mission["slip_margin_days"]
    assert brief["verdict"]["power_and_contact"]["verdict"] == mission["verdict"]
    assert brief["hours"]["planned"]["sunlit_h"] == mission["days"][0]["sunlit_h"]
    assert brief["hours"]["at_slip"]["earth_h"] == mission["days"][3]["earth_h"]
    assert brief["hours"]["need_sunlit_h"] == mission["need"]["sunlit_h"]
    assert brief["slip_margin"]["holds"] == (mission["verdict"] == "yes" and mission["slip_margin_days"] >= 3)


def test_numbers_match_the_other_endpoints(brief):
    w = client.post("/api/windows", json={"site": {"id": "robust_pick"}, "landing": "2026-11-18T00:00:00Z", "slip_days": 15}).json()
    assert [r["verdict"] for r in brief["windows"]["rows"]] == [r["verdict"] for r in w["rows"]]
    assert [r["fails_on"] for r in brief["windows"]["rows"]] == [r["fails_on"] for r in w["rows"]]
    sv = client.post("/api/survival", json={"site": {"id": "robust_pick"}, "landing": "2026-11-18T00:00:00Z", "slip_days": 15}).json()
    assert brief["longest_night"]["at_slip_h"] == sv["days"][3]["night_h"]
    lt = client.get("/api/addons/planner/lighting", params={"id": "robust_pick", "landing": "2026-11-18T00:00:00Z", "slip_days": 3}).json()
    assert brief["lighting"]["sun"] == lt["sun"] and brief["lighting"]["touchdown_utc"] == "2026-11-21T00:00:00Z"
    st = client.get("/api/addons/safetouch/site", params={"id": "robust_pick"}).json()
    if st.get("available"):
        assert [c["flat_8deg_pct"] for c in brief["slope"]["classes"]] == [c["p8"] for c in st["classes"]]


def test_assumptions_labelled_and_sources_linked(brief):
    assert len(brief["assumptions"]) >= 5
    assert all(a["label"] in {"assumed", "illustrative", "limit", "rule"} for a in brief["assumptions"])
    assert any(a["label"] == "illustrative" for a in brief["assumptions"])
    assert brief["sources"] and all(s["url"].startswith("http") for s in brief["sources"])
    assert any("ssd.jpl.nasa.gov" in s["url"] for s in brief["sources"])
    assert brief["terrain"]["label"] or brief["terrain"]["horizon_label"]
    assert brief["checks"]


def test_long_slip_is_not_covered(mission):
    r = client.get("/api/addons/brief", params={**OPEN, "slip": mission["slip_margin_days"] + 2, "alternatives": "false"})
    assert r.status_code == 200
    b = r.json()
    assert b["slip_margin"]["holds"] is False
    assert b["answer"]["overall"] != "yes"
    assert b["alternatives"]["available"] is False


def test_lat_lon_site():
    r = client.get("/api/addons/brief", params={"lat": -89.4398, "lon": -137.17, "name": "C1", "date": "2026-11-18",
                                                 "slip": 0, "alternatives": "false"})
    assert r.status_code == 200
    assert abs(r.json()["inputs"]["site"]["lat"] + 89.4398) < 1e-6


def test_errors():
    assert client.get("/api/addons/brief", params={"site": "nope", "date": "2026-11-18"}).status_code == 404
    assert client.get("/api/addons/brief", params={"site": "robust_pick", "date": "not a date"}).status_code == 422
    assert client.get("/api/addons/brief", params={"site": "robust_pick", "slip": 500}).status_code == 422
    assert client.get("/api/addons/brief", params={"lat": -89.0}).status_code == 422


def test_static_files_served():
    page = client.get("/static/brief.html")
    assert page.status_code == 200 and "Download brief" in page.text and "@media print" in page.text
    js = client.get("/static/addons/brief.js")
    assert js.status_code == 200 and "addon-brief" in js.text and "Make a review-board brief" in js.text
