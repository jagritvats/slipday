"""Add-on "Planner checks": descent lighting, joint chance per lander class, alternatives at the slipped date.
The router is mounted in a small app here.  Tests that need the LOLA 5 m grids skip when they are not installed."""
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday.addons import planner as P, safety

NAMES = [n for n, _l, _g in safety.grids()]
HAVE_5 = "ldem_site01_5m" in NAMES and "ldem_site07_5m" in NAMES
needs_5 = pytest.mark.skipif(not HAVE_5, reason="the LOLA 5 m site models are not installed (data/dem5)")

OPENING = (-89.0098, 122.76389)
C1 = (-89.4398, -137.17)
IM1 = (-80.13, 1.44)
LANDING = "2026-11-18T00:00:00Z"

REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")


@pytest.fixture(scope="module", autouse=True)
def real_dem():
    """The real LOLA stack for this module (conftest starts every test with no terrain)."""
    from slipday import demstore, sites
    old = os.environ.get("SLIPDAY_DEM_DIR")
    if REAL_DEM and os.path.isdir(REAL_DEM):
        os.environ["SLIPDAY_DEM_DIR"] = REAL_DEM
        demstore.reload()
        sites._terrain_profile.cache_clear()
    yield
    if old is not None:
        os.environ["SLIPDAY_DEM_DIR"] = old
    demstore.reload()
    sites._terrain_profile.cache_clear()


app = FastAPI()
app.include_router(P.router)
client = TestClient(app)


def test_relative_angle():
    assert P._rel(0, 0) == 0
    assert P._rel(350, 10) == 20
    assert P._rel(180, 0) == 180
    assert P._rel(90, 0) == 90
    assert P._rel(270, 0) == 90


@pytest.fixture(scope="module")
def light_open():
    return P.lighting(*OPENING, LANDING, 0, 0.0, "opening")


@needs_5
def test_lighting_opening(light_open):
    r = light_open
    assert r["touchdown_utc"] == LANDING
    assert 0.0 < r["sun"]["el_deg"] < 5.0                  # south pole: the Sun stays near the horizon
    assert 0.0 <= r["sun"]["az_deg"] < 360.0
    assert r["approach"]["illustrative"] and r["camera"]["illustrative"]
    assert r["approach"]["sun_from_behind_deg"] == pytest.approx(P._rel(r["sun"]["az_deg"], 0.0), abs=0.1)
    sh = r["shadow"]
    assert sh["available"], sh
    # the finest grid installed for this test run (the app's own stack has the 5 m site model here; the test stack
    # may hold 80 m only)
    assert float(sh["terrain_resolution_m"]) <= 80.0
    assert all(c["grid_m"] == float(sh["terrain_resolution_m"]) for c in sh["classes"])
    for c in sh["classes"]:
        assert c["available"] and 0.0 <= c["in_shadow_pct"] <= 100.0
    # the wider the spread, the more of it reaches the shadowed ground around the ridge point (measured)
    p = [c["in_shadow_pct"] for c in sh["classes"]]
    assert p[0] <= p[1] <= p[2]


@needs_5
def test_heading_changes_relative_angle_only():
    a = P.lighting(*OPENING, LANDING, 0, 0.0, "x", with_shadow=False)
    b = P.lighting(*OPENING, LANDING, 0, 180.0, "x", with_shadow=False)
    assert a["sun"] == b["sun"]
    assert a["approach"]["sun_from_behind_deg"] + b["approach"]["sun_from_behind_deg"] == pytest.approx(180.0, abs=0.2)


@needs_5
def test_slip_moves_touchdown():
    r = P.lighting(*OPENING, LANDING, 5, 0.0, "x", with_shadow=False)
    assert r["touchdown_utc"] == "2026-11-23T00:00:00Z" and r["slip_days"] == 5


@needs_5
@pytest.mark.parametrize("where", [OPENING, C1])
def test_joint_is_bounded(where):
    r = P.joint(*where, LANDING, 0, "x")
    assert r["available"]
    for c in r["classes"]:
        if not c["available"]:
            continue
        assert c["joint_pct"] <= min(c["plan_holds_pct"], c["flat_pct"]) + 1e-9
        assert c["joint_pct"] >= c["plan_holds_pct"] + c["flat_pct"] - 100.0 - 0.11
        assert c["joint_range"][0] <= c["joint_pct"] <= c["joint_range"][1]
        assert c["draws_used"] >= 0.99 * c["draws"]


def test_joint_needs_5m():
    r = P.joint(*IM1, LANDING, 0, "IM-1")
    assert r["available"] is False and "5 m" in r["reason"]


def test_endpoints_validate():
    assert client.get("/api/addons/planner/lighting").status_code == 422
    assert client.get("/api/addons/planner/lighting", params={"lat": -89, "lon": 0, "landing": "soon"}).status_code == 422
    assert client.get("/api/addons/planner/joint", params={"id": "nope"}).status_code == 404
    assert client.get("/api/addons/planner/about").json()["camera"]["illustrative"] is True


@needs_5
def test_endpoint_lighting_by_id():
    r = client.get("/api/addons/planner/lighting", params={"id": "shackleton", "landing": LANDING, "shadow": "false"})
    assert r.status_code == 200
    j = r.json()
    assert j["site"]["lat"] == pytest.approx(C1[0]) and "shadow" not in j


@pytest.mark.skipif(os.environ.get("PLANNER_FAST") == "1", reason="alternatives take about 20 s")
def test_alternatives_ranked():
    r = client.get("/api/addons/planner/alternatives",
                   params={"landing": LANDING, "slip_days": 10, "lat": OPENING[0], "lon": OPENING[1]}).json()
    assert r["touchdown_utc"] == "2026-11-28T00:00:00Z"
    rows = r["rows"]
    assert rows and [x["rank"] for x in rows] == list(range(1, len(rows) + 1))
    order = {"yes": 0, "not sure": 1, "no": 2, "n/a": 3}
    assert [order[x["verdict"]] for x in rows] == sorted(order[x["verdict"]] for x in rows)
    # the plan's own site is left out
    assert not any(abs(x["lat"] - OPENING[0]) < 0.003 and abs(x["lon"] - OPENING[1]) < 0.15 for x in rows)
    assert r["sites_yes"] == sum(x["verdict"] == "yes" for x in rows)
