"""Add-on "Chance of a safe touchdown".  The router is mounted in a small app here, so api.py is not touched.
Real LOLA 5 m grids are read in place; tests that need them skip when they are not installed."""
import base64
import math

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday.addons import safety, safetouch as st
from slipday.dem import PolarStereoDEM
from slipday.robust import LANDER_CLASSES

NAMES = [n for n, _l, _g in safety.grids()]
HAVE_5 = "ldem_site01_5m" in NAMES and "ldem_site07_5m" in NAMES
needs_5 = pytest.mark.skipif(not HAVE_5, reason="the LOLA 5 m site models are not installed (data/dem5)")
needs_store = pytest.mark.skipif(st.store() is None, reason="data/addons/safetouch/sites.json is not built")

OPENING = (-89.0098, 122.76389)
C1 = (-89.4398, -137.17)
IM1 = (-80.13, 1.44)

app = FastAPI()
app.include_router(st.router)
client = TestClient(app)


def _cls(r, cid):
    return next(c for c in r["classes"] if c["id"] == cid)


@pytest.fixture(scope="module")
def opening():
    return st.compute(*OPENING, name="opening", with_slip=False)


@pytest.fixture(scope="module")
def c1():
    return st.compute(*C1, name="C1", with_slip=False)


# ---------------- the method ----------------

def test_lander_classes_are_the_entrys_own():
    assert st.lander_classes() is LANDER_CLASSES
    sizes = {c["id"]: (c["sigma_major_m"], c["sigma_minor_m"]) for c in LANDER_CLASSES}
    assert sizes == {"precision": (33.0, 33.0), "clps": (250.0, 250.0), "wide": (670.0, 400.0)}


def test_draws_are_fixed_and_the_right_size():
    d = st.draws()
    for c in LANDER_CLASSES:
        x = d[c["id"]]
        n = st.N_ROUND if c["sigma_major_m"] == c["sigma_minor_m"] else st.N_PER_DIRECTION * len(st.DIRECTIONS)
        assert len(x["dx"]) == len(x["dy"]) == n
        # spread: the root mean square distance of a 2-D Gaussian is sqrt(a^2 + b^2)
        rms = math.sqrt(float(np.mean(x["dx"] ** 2 + x["dy"] ** 2)))
        assert rms == pytest.approx(math.hypot(c["sigma_major_m"], c["sigma_minor_m"]), rel=0.02)
    st.draws.cache_clear()
    again = st.draws()
    assert np.array_equal(again["clps"]["dx"], d["clps"]["dx"])


def test_unguided_draws_follow_the_long_axis():
    d = st.draws()["wide"]
    for k, th in enumerate(st.DIRECTIONS):
        m = d["direction"] == k
        t = math.radians(th)
        along = d["dx"][m] * math.sin(t) + d["dy"][m] * math.cos(t)
        across = d["dx"][m] * math.cos(t) - d["dy"][m] * math.sin(t)
        assert np.std(along) == pytest.approx(670.0, rel=0.06)
        assert np.std(across) == pytest.approx(400.0, rel=0.06)


def test_wilson_range():
    assert st.wilson(50, 100) == (40.4, 59.6)
    assert st.wilson(20000, 20000)[1] == 100.0 and st.wilson(20000, 20000)[0] >= 99.9
    assert st.wilson(0, 10) == (0.0, 27.8)
    assert st.wilson(0, 0) == (None, None)


@pytest.mark.parametrize("tilt", [0.0, 4.0, 8.0, 15.0])
def test_patch_slope_reads_back_a_tilted_plane(tilt):
    px, n, lat_c = 5.0, 41, -89.0
    g0 = PolarStereoDEM(name="plane", pixel_m=px, x0_m=0.0, y0_m=0.0, z=np.zeros((2, 2)))
    xc, yc = g0.project(lat_c, 0.0)
    x0, y0 = float(xc) - (n // 2) * px, float(yc) + (n // 2) * px
    X, Y = np.meshgrid(x0 + np.arange(n) * px, y0 - np.arange(n) * px)
    k = 2.0 / (1.0 + math.sin(math.radians(abs(lat_c))))
    Z = math.tan(math.radians(tilt)) / k * ((X - xc) * math.sin(0.6) + (Y - yc) * math.cos(0.6)) + 500.0
    g = PolarStereoDEM(name="plane", pixel_m=px, x0_m=x0, y0_m=y0, z=Z)
    S, r0, c0 = st.slope_patch(g, n // 2, n // 2, 10)
    assert np.nanmax(np.abs(S - tilt)) < 0.01
    # the cells on the edge of the grid have no 3 x 3 neighbourhood: no slope
    S2, _, _ = st.slope_patch(g, 0, 0, 3)
    assert np.isnan(S2[:4, :4]).sum() > 0 and np.isfinite(S2[4:, 4:]).all()


@needs_5
@pytest.mark.parametrize("where", [OPENING, C1])
def test_patch_slope_is_the_safety_addons_slope(where):
    loc = st.locate(*where)
    g = loc["g"]
    S, r0, c0 = st.slope_patch(g, int(round(loc["row"])), int(round(loc["col"])), 300)
    rng = np.random.default_rng(7)
    ii, jj = rng.integers(0, S.shape[0], 400), rng.integers(0, S.shape[1], 400)
    lat, lon = g.unproject(g.x0_m + (c0 + jj) * g.pixel_m, g.y0_m - (r0 + ii) * g.pixel_m)
    s, base = safety.slope_on(g, lat, lon)
    assert base == 10.0
    assert np.nanmax(np.abs(s - S[ii, jj])) < 1e-9


# ---------------- where it runs ----------------

def test_80m_place_gets_no_number():
    r = st.compute(*IM1, name="IM-1")
    assert r["available"] is False
    assert "80 m" in r["reason"] and "too coarse" in r["reason"]
    assert "classes" not in r


@needs_5
def test_named_sites_are_on_5m():
    assert st.locate(*OPENING)["name"] == "ldem_site07_5m"
    assert st.locate(*C1)["name"] == "ldem_site01_5m"


@needs_5
def test_a_class_is_left_out_when_its_spread_leaves_the_5m_grid():
    g = next(gg for n, _l, gg in st.five_m_grids() if n == "ldem_site07_5m")
    lat, lon = g.unproject(g.x0_m + 40 * g.pixel_m, g.y0_m - 1600 * g.pixel_m)     # 200 m from the west edge
    r = st.compute(float(lat), float(lon), with_slip=False)
    assert r["available"]
    assert _cls(r, "precision")["available"] is True
    for cid in ("clps", "wide"):
        c = _cls(r, cid)
        assert c["available"] is False and c["outside_5m_pct"] > 1.0 and "off the 5 m terrain" in c["why"]


# ---------------- the measured numbers ----------------

@needs_5
def test_opening_example_numbers(opening):
    p, c, w = (_cls(opening, k) for k in ("precision", "clps", "wide"))
    assert (p["p8"], p["p5"]) == (100.0, 90.0)
    assert (c["p8"], c["p5"]) == (93.7, 70.9)
    assert (w["p8"], w["p5"]) == (82.9, 57.6)
    assert w["p8_direction_span"] == [78.1, 87.4]
    for x in (p, c, w):
        assert x["outside_5m_pct"] == 0.0


@needs_5
def test_rounded_100_is_not_every_draw(opening):
    # the opening example's precision figure rounds to 100.0 % but 7 of 20,000 draws are steeper than 8 degrees;
    # the counts let the page say "over 99.9 %" instead of "100 %"
    p = _cls(opening, "precision")
    assert p["p8"] == 100.0 and p["p8_count"] == 19993 and p["draws_used"] == 20000


@needs_5
def test_c1_numbers(c1):
    p, c, w = (_cls(c1, k) for k in ("precision", "clps", "wide"))
    assert (p["p8"], p["p5"]) == (99.9, 98.4)
    assert (c["p8"], c["p5"]) == (80.7, 53.8)
    assert (w["p8"], w["p5"]) == (50.8, 27.0)


@needs_5
@pytest.mark.parametrize("where,fx", [(OPENING, "opening"), (C1, "c1")])
def test_independent_sampling_agrees(where, fx, request):
    # a different route to the same number: touchdown points placed with the entry's own great-circle step
    # (terrain.destination) and the safety add-on's own slope function, another seed
    from slipday.dem import MOON_RADIUS_M
    from slipday.terrain import destination
    r = request.getfixturevalue(fx)
    rng = np.random.default_rng(99)
    for cid, sig in (("precision", 33.0), ("clps", 250.0)):
        d = np.hypot(*rng.standard_normal((2, 20000))) * sig
        b = rng.uniform(0, 2 * np.pi, 20000)
        lat, lon = destination(where[0], where[1], b, d / MOON_RADIUS_M)
        s = safety.slope_finest(lat, lon)["slope"]
        assert 100 * np.mean(s <= 8.0) == pytest.approx(_cls(r, cid)["p8"], abs=1.5)
        assert 100 * np.mean(s <= 5.0) == pytest.approx(_cls(r, cid)["p5"], abs=1.5)


@needs_5
def test_wider_spread_never_helps_at_these_sites(opening, c1):
    for r in (opening, c1):
        p8 = [_cls(r, k)["p8"] for k in ("precision", "clps", "wide")]
        assert p8[0] >= p8[1] >= p8[2]


@needs_5
def test_uncertainty_brackets_the_answer(opening, c1):
    for r in (opening, c1):
        for c in r["classes"]:
            for k in ("p8", "p5"):
                assert c[k + "_if_steeper"] <= c[k] <= c[k + "_if_flatter"]
                lo, hi = c[k + "_range"]
                assert lo <= c[k] <= hi


@needs_5
def test_planned_aim_scores_the_same_in_the_search(opening):
    # the candidate search reuses the same draws; at zero shift it must give the headline figure
    loc = st.locate(*OPENING)
    g = loc["g"]
    half = int(round(st.PATCH_HALF_M / g.pixel_m))
    S, r0, c0 = st.slope_patch(g, int(round(loc["row"])), int(round(loc["col"])), half)
    row, col = st._class_cells(loc, "clps", r0, c0)
    cnt = st._count(S, row, col, 0, 0)
    v = cnt["s"][cnt["ok"]]
    assert round(100.0 * (v <= 8.0).mean(), 1) == _cls(opening, "clps")["p8"]


@needs_5
def test_picture_bytes(opening):
    for k in ("near", "wide"):
        p = opening["picture"][k]
        a = np.frombuffer(base64.b64decode(p["data"]), dtype=np.uint8)
        assert a.size == p["n"] ** 2
        assert p["n"] == int(2 * p["half_m"] / p["step_m"]) + 1
    near = np.frombuffer(base64.b64decode(opening["picture"]["near"]["data"]), dtype=np.uint8)
    assert (near < 255).all()                         # the near picture is all on 5 m terrain


# ---------------- the store and the suggestion ----------------

@needs_5
@needs_store
@pytest.mark.parametrize("sid,fx", [("robust_pick", "opening"), ("shackleton", "c1")])
def test_store_matches_a_fresh_computation(sid, fx, request):
    fresh = request.getfixturevalue(fx)
    kept = st.store()["sites"][sid]
    keys = ("p8", "p5", "p8_range", "p5_range", "p8_if_steeper", "p8_if_flatter", "p5_if_steeper", "p5_if_flatter",
            "outside_5m_pct", "draws_used")
    for a, b in zip(kept["classes"], fresh["classes"]):
        assert {k: a[k] for k in keys} == {k: b[k] for k in keys}
    assert kept["picture"]["near"]["data"] == fresh["picture"]["near"]["data"]


@needs_store
def test_suggestion_keeps_the_slip_verdict_or_is_not_offered():
    for sid, r in st.store()["sites"].items():
        planned = r["slip_planned"]
        assert planned and planned["verdict"] in ("yes", "not sure", "no")
        for c in r["classes"]:
            s = c.get("suggestion")
            if not c["available"]:
                continue
            assert s is not None
            assert len(s.get("tried", [])) <= st.AIM_TRIES
            for t in s.get("tried", []):
                assert t["distance_m"] <= st.AIM_RADIUS_M + 1e-6
                same = t["slip"]["verdict"] == planned["verdict"] and t["slip"]["slip_margin_days"] >= planned["slip_margin_days"]
                assert t["keeps_slip_verdict"] == same
            if s["offered"]:
                assert s["slip_checked"] and s["keeps_slip_verdict"]
                assert s["p8"] - c["p8"] >= st.AIM_MIN_GAIN_PP and s["p8_range"][0] > c["p8_range"][1]
                assert "not a site study" in s["note"]
            else:
                assert s["why"]


@needs_store
def test_measured_slip_and_suggestions():
    sites = st.store()["sites"]
    assert sites["robust_pick"]["slip_planned"]["verdict"] == "yes" and sites["robust_pick"]["slip_planned"]["slip_margin_days"] == 8
    assert sites["shackleton"]["slip_planned"]["verdict"] == "yes" and sites["shackleton"]["slip_planned"]["slip_margin_days"] == 7
    clps = _cls(sites["robust_pick"], "clps")["suggestion"]
    assert clps["offered"] is False and len(clps["tried"]) == st.AIM_TRIES     # better slope, but each loses slip margin
    assert not any(c["suggestion"]["offered"] for r in sites.values() for c in r["classes"] if c["available"])


# ---------------- the endpoints ----------------

@needs_store
def test_endpoint_named_site_comes_from_the_store():
    r = client.get("/api/addons/safetouch/site", params={"id": "robust_pick"}).json()
    assert r["available"] and r["from_store"] and r["grid"]["cell_m"] == 5.0
    r2 = client.get("/api/addons/safetouch/site", params={"lat": C1[0], "lon": C1[1] + 360.0, "name": "C1 here"}).json()
    assert r2["from_store"] and r2["site"]["name"] == "C1 here"
    assert _cls(r2, "precision")["p8"] == 99.9


def test_endpoint_coarse_place_and_errors():
    r = client.get("/api/addons/safetouch/site", params={"id": "im1"})
    assert r.status_code == 200 and r.json()["available"] is False and "too coarse" in r.json()["reason"]
    assert client.get("/api/addons/safetouch/site", params={"id": "nowhere"}).status_code == 404
    assert client.get("/api/addons/safetouch/site").status_code == 422
    assert client.get("/api/addons/safetouch/site", params={"lat": -95, "lon": 0}).status_code == 422


def test_endpoint_about():
    a = client.get("/api/addons/safetouch/about").json()
    assert a["limit_deg"] == 8.0 and a["goal_deg"] == 5.0 and a["uncertainty_deg"] == 2.0
    assert a["aim_radius_m"] == 200.0 and len(a["classes"]) == 3
    assert any("Boulders" in t for t in a["limits"]) and any("assumptions" in t for t in a["limits"])


@needs_5
def test_endpoint_live_point_on_5m():
    # 500 m from C1 on the same 5 m model: not stored, worked out live (with the slip check)
    g = st.locate(*C1)["g"]
    x, y = g.project(*C1)
    lat, lon = g.unproject(float(x) + 500.0, float(y))
    r = client.get("/api/addons/safetouch/site", params={"lat": float(lat), "lon": float(lon)}).json()
    assert r["available"] and r["from_store"] is False
    assert r["slip_planned"]["verdict"] in ("yes", "not sure", "no")
    for c in r["classes"]:
        assert c["available"] and 0.0 <= c["p8"] <= 100.0 and c["p5"] <= c["p8"]
