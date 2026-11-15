"""Local pass 2 (14 Nov 2026): the two request lanes, "why it flips", the scatter-checked slip-margin map,
the chance by lander class, the sampling range of the landing circles, the year ribbon and the
permanent-shadow layer.  The lane tests need no data; the rest run on the REAL LOLA grids and skip without
them (the tests that need the 231 MB 80 m grid, the skyline field or the scatter skylines say so)."""
import os
import threading
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from slipday import api, demstore, field, hindcast, load, moonmap, robust, scatterfield, sites, why
from slipday.api import app
from slipday.metrics import Criteria
from slipday.sites import get_site

client = TestClient(app)
REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")
HAVE_DEM = os.path.exists(os.path.join(REAL_DEM, "dems.json"))
HAVE_80 = os.path.exists(os.path.join(REAL_DEM, "ldem_80s_80m_f32.npy"))
needs_dem = pytest.mark.skipif(not HAVE_DEM, reason="real LOLA grids are not installed (run scripts/prepare_dem.py)")
needs_80 = pytest.mark.skipif(not (HAVE_DEM and HAVE_80), reason="the 80 m grid is not installed (run scripts/fetch_grid80.py)")
needs_field = pytest.mark.skipif(field.load() is None, reason="skyline field not built (run scripts/build_field.py)")
needs_scatter = pytest.mark.skipif(not os.path.exists(os.path.join(field.FIELD_DIR, "scatter_field.json")),
                                   reason="scatter skylines not built (run scripts/build_scatter_field.py)")
L = "2026-11-18T00:00:00Z"
C1 = {"site": {"id": "shackleton"}, "landing": L}


def _reset():
    demstore.reload()
    sites._terrain_profile.cache_clear()
    hindcast.hindcast.cache_clear()
    api._stats.cache_clear()
    api._year.cache_clear()
    moonmap._cache.clear()
    moonmap._layer_cache.clear()
    why._cache.clear()
    api._finer_store.cache_clear()
    scatterfield.reload()


@pytest.fixture(scope="module", autouse=True)
def real_dem():
    old = os.environ.get("SLIPDAY_DEM_DIR")
    if HAVE_DEM:
        os.environ["SLIPDAY_DEM_DIR"] = REAL_DEM
        os.environ.pop("SLIPDAY_SKIP_DEMS", None)
        _reset()
    yield
    if old is not None:
        os.environ["SLIPDAY_DEM_DIR"] = old
    os.environ.pop("SLIPDAY_SKIP_DEMS", None)
    _reset()


# ------------------------------------------------------------------ two lanes (no data needed)

def test_light_work_runs_in_the_light_lane_and_slow_work_moves_to_the_cold_lane():
    seen = []

    def stored():
        seen.append(load._mode.lane)
        return "stored"

    def new_skyline():
        seen.append(load._mode.lane)
        load.require_cold()                 # what terrain.cached_profile does on a cache miss
        return "computed"

    before = load.lanes()
    assert load.run(stored) == "stored" and seen == ["light"]
    assert load.run(new_skyline) == "computed" and seen == ["light", "light", "cold"]
    after = load.lanes()
    assert after["escalated"] == before["escalated"] + 1 and after["cold_done"] == before["cold_done"] + 1
    load.require_cold()                     # outside any lane (scripts, tests): never raises


def test_a_stored_answer_does_not_wait_behind_slow_work_and_a_full_queue_is_refused_at_once():
    """Local review, bug 1: with two slow requests in flight the stored card waited 23.5 s; with twelve, 153 s."""
    gate, started = threading.Event(), threading.Event()
    results = []

    def slow():
        load.require_cold()
        started.set()
        gate.wait(20)
        return "slow done"

    def call():
        try:
            results.append(load.run_big(slow))
        except load.Busy as exc:
            results.append(exc)

    threads = [threading.Thread(target=call) for _ in range(load.MAX_COLD + load.MAX_COLD_QUEUE)]
    for t in threads:
        t.start()
    assert started.wait(5)
    for _ in range(100):                    # until every other slow call is queued
        if load.lanes()["cold_waiting"] >= load.MAX_COLD_QUEUE:
            break
        time.sleep(0.02)
    lanes = load.lanes()
    assert lanes["cold_running"] == load.MAX_COLD and lanes["cold_waiting"] == load.MAX_COLD_QUEUE
    t0 = time.perf_counter()
    assert load.run(lambda: "stored") == "stored"            # the light lane is free while the cold lane is full
    assert time.perf_counter() - t0 < 0.5
    t0 = time.perf_counter()
    with pytest.raises(load.Busy) as exc:                    # one more big job: refused, not queued
        load.run_big(slow)
    assert time.perf_counter() - t0 < 0.5 and exc.value.retry_after_s > 0 and "try this one again" in str(exc.value)
    # a small job (a card for a new site) may still queue: one visitor's own page is not refused by itself
    assert load.MAX_COLD_QUEUE_SMALL > load.MAX_COLD_QUEUE
    small = threading.Thread(target=lambda: results.append(load.run(lambda: (load.require_cold(), "small done")[1])))
    small.start()
    for _ in range(100):
        if load.lanes()["cold_waiting"] > load.MAX_COLD_QUEUE:
            break
        time.sleep(0.02)
    assert load.lanes()["cold_waiting"] == load.MAX_COLD_QUEUE + 1
    gate.set()
    small.join(10)
    assert "small done" in results
    for t in threads:
        t.join(10)
    assert results.count("slow done") == load.MAX_COLD + load.MAX_COLD_QUEUE
    lanes = load.lanes()
    assert lanes["cold_running"] == 0 and lanes["cold_waiting"] == 0


def test_a_full_cold_lane_answers_503_with_retry_after(monkeypatch):
    def full(*a, **k):
        raise load.Busy(3, 1)
    monkeypatch.setattr(api, "run", full)
    monkeypatch.setattr(api, "run_big", full)
    r = client.post("/api/mission", json=C1)
    assert r.status_code == 503 and r.headers["retry-after"] == str(load.RETRY_AFTER_S)
    body = r.json()
    assert body["busy"] is True and body["retry_after_s"] == load.RETRY_AFTER_S and "busy" in body["detail"]
    assert "lanes" in client.get("/api/health").json()


def test_gaussian_cell_weights_add_up_to_the_analytic_mass():
    """The quadrature behind the lander classes: a circular Gaussian inside radius R holds 1 - exp(-R^2 / 2 sigma^2)."""
    radii = [0.0] + [r[0] for r in robust.RING_LAYOUT + robust.OUTER_RINGS]
    outer = radii[-1] + (radii[-1] - radii[-2]) / 2.0
    edges = [0.0] + [(radii[i] + radii[i + 1]) / 2.0 for i in range(len(radii) - 1)] + [outer]
    counts = [r[1] for r in robust.RING_LAYOUT + robust.OUTER_RINGS]
    first = [r[2] for r in robust.RING_LAYOUT + robust.OUTER_RINGS]
    for sigma in (33.0, 250.0, 800.0):
        wc, wr = robust._cell_weights(radii, edges, counts, first, sigma, sigma, 0.0)
        total = wc + sum(float(x.sum()) for x in wr)
        assert abs(total - (1.0 - np.exp(-outer ** 2 / (2 * sigma ** 2)))) < 0.005
        assert all(np.allclose(x, x[0], rtol=1e-6) for x in wr)          # circular: every point of a ring weighs the same
    # an ellipse: the points along the long axis weigh more than those across it, and turning it by 90 degrees swaps them
    wc, wr = robust._cell_weights(radii, edges, counts, first, 670.0, 400.0, 0.0)
    wc2, wr2 = robust._cell_weights(radii, edges, counts, first, 670.0, 400.0, 90.0)
    ring = len(robust.RING_LAYOUT) - 1                                    # the 1 km ring: 16 points from bearing 0
    assert wr[ring][0] > wr[ring][4] * 1.5 and abs(wr[ring][0] - wr2[ring][4]) < 1e-9 and abs(wc - wc2) < 1e-12
    assert all("ASSUMED" in c["basis"] for c in robust.LANDER_CLASSES) and "ASSUMED" in robust.CLASS_ASSUMPTION


# ------------------------------------------------------------------ real grids

@needs_80
def test_the_stored_card_stays_quick_while_a_new_landing_circle_is_worked_out():
    assert client.post("/api/mission", json=C1).status_code == 200            # stores the card's 15 skylines
    done = {}

    def cold():
        t = time.perf_counter()
        r = client.post("/api/landing-circles", json={"site": {"lat": -87.3127, "lon": 23.417}, "landing": L})
        done["status"], done["s"] = r.status_code, time.perf_counter() - t

    th = threading.Thread(target=cold)
    th.start()
    for _ in range(200):                                                      # until the cold request is running
        if load.lanes()["cold_running"]:
            break
        time.sleep(0.02)
    assert load.lanes()["cold_running"] == 1
    times = []
    for _ in range(3):
        t = time.perf_counter()
        assert client.post("/api/mission", json=C1).status_code == 200
        times.append(time.perf_counter() - t)
    still_running = load.lanes()["cold_running"] == 1
    th.join(300)
    assert done["status"] == 200
    assert still_running and max(times) < 2.0, (times, done)                  # measured 0.03 to 0.05 s; the bug was 23.5 s


@needs_80
def test_why_it_flips_at_the_default_example():
    card = client.post("/api/mission", json=C1).json()
    r = client.post("/api/why", json={**C1, "day": 0})
    assert r.status_code == 200
    w = r.json()
    d0 = card["days"][0]
    assert w["verdict"] == "yes" and w["slip_margin_days"] == card["slip_margin_days"] == 7
    # the window's hours are the card's own, and the hourly flags add up to them
    assert w["hours"]["sunlit"] == d0["sunlit_h"] and w["hours"]["earth"] == d0["earth_h"]
    t = w["track"]
    assert t["count"] == w["window_hours"] + 1 == 337 and len(t["sun_az"]) == len(t["earth_el"]) == 337
    assert sum(t["sun_lit"][:336]) == d0["sunlit_h"] and sum(t["earth_up"][:336]) == d0["earth_h"]
    # the skyline is the site's own 720-azimuth profile, with the distance of the ground that sets it
    prof = sites.terrain_profile(-89.4398, -137.17, 2.0)
    assert len(w["skyline"]["az_deg"]) == 720 and abs(w["skyline"]["el_deg"][100] - float(prof.el_deg[100])) < 1e-3
    assert abs(w["skyline"]["dist_km"][100] - float(prof.dist_km[100])) < 0.01
    td = w["touchdown"]
    assert td["sun_up"] and td["earth_up"] and td["sun_el"] - td["sun_skyline_el"] > 0
    # Sun up for the whole window (no sunset inside it); the Earth sets inside it, and the stretch says behind what
    assert td["next_sunset"] is None or td["next_sunset"]["hours_from_now"] > 336
    assert 0 < td["next_earthset"]["hours_from_now"] < 336 and not w["sun_hidden"]
    eh = w["earth_hidden"][0]
    assert eh["body"] == "earth" and eh["event"] == "goes behind" and eh["hours"] == 336 - d0["earth_h"]
    assert eh["terrain"]["kind"] == "terrain" and eh["terrain"]["dist_km"] > 50          # a far massif, not the local crest
    # what ends the margin: day 8, a touchdown point 100 m away, short of Earth contact
    f = w["flip"]
    assert f["day"] == 8 and f["verdict"] == "not sure" and f["points_passing"] == card["days"][8]["points_passing"] < 13
    assert f["member"]["kind"] == "touchdown point" and f["member"]["offset_m"] == 100 and f["body"] == "earth"
    assert f["earth_h"] < 100 and "of the 100 needed" in f["text"] and "is no longer a clear yes" in f["text"]
    assert f["stretch"]["terrain"]["az_deg"] >= 0 and "azimuth" in f["text"]
    assert "LOLA, 80 m/px" in w["labels"]["real"] and "DE421" in w["labels"]["derived"]
    # the same for a later cell of the strip, and a day that is not on the strip
    w3 = client.post("/api/why", json={**C1, "day": 8}).json()
    assert w3["day"] == 8 and w3["landing_utc"] == card["days"][8]["landing_utc"] and w3["flip"]["day"] == 8
    assert client.post("/api/why", json={**C1, "day": 60}).status_code == 422
    assert client.post("/api/why", json={**C1, "day": 500}).status_code == 422


@needs_dem
def test_why_names_the_ground_the_sun_sets_behind_at_im1_and_copes_without_terrain():
    body = {"site": {"id": "im1"}, "landing": "2024-02-22T23:00:00Z", "need_sun_h": 168}
    w = client.post("/api/why", json=body).json()
    f = w["flip"]
    assert w["verdict"] in ("yes", "not sure") and f["day"] == w["slip_margin_days"] + 1
    assert f["body"] == "sun" and f["sunlit_h"] < 168
    st = f["stretch"]
    assert st["event"] == "goes behind" and st["terrain"]["kind"] == "terrain" and st["terrain"]["dist_km"] > 0
    # the named ground is where the skyline profile says it is: same azimuth, same distance
    m = f["member"]
    prof = sites.terrain_profile(m["lat"], m["lon"], 2.0)
    k = int(round(st["terrain"]["az_deg"] / 0.5)) % 720
    assert abs(float(prof.dist_km[k]) - st["terrain"]["dist_km"]) < 0.02
    assert abs(float(prof.el_deg[k]) - st["terrain"]["skyline_el_deg"]) < 0.02
    # with terrain switched off there is no skyline to draw and no ground to name, and it says so
    w0 = client.post("/api/why", json={**body, "terrain": False}).json()
    assert w0["skyline"] is None and "smooth-sphere" in w0["labels"]["real"]
    for st0 in w0["sun_hidden"]:
        assert st0["terrain"]["kind"] == "smooth sphere"


@needs_80
def test_chance_by_lander_class_and_the_sampling_range_of_the_circles():
    r = client.post("/api/lander-classes", json=C1)
    assert r.status_code == 200
    c = r.json()
    assert c["available"] and c["points"] == 141 and "ASSUMED" in c["assumption"] and "not a model of any named lander" in c["assumption"]
    by = {k["id"]: k for k in c["classes"]}
    assert list(by) == ["precision", "clps", "wide"] and all(k["assumed"] and "ASSUMED" in k["basis"] for k in c["classes"])
    for k in c["classes"]:
        assert k["resolvable"] and len(k["chance_pct"]) == 60 and k["mass_inside_sampled_area_pct"] > 98.0
        lo, hi = k["planned_range_pct"]
        assert 0.0 <= lo <= k["planned_pct"] <= hi <= 100.0
        for a, p, b in zip(k["range_lo_pct"], k["chance_pct"], k["range_hi_pct"]):
            assert a <= p <= b
    # the card's Yes is for 100 m: a lander that precise keeps the plan, a wider dispersion mostly does not
    assert by["precision"]["planned_pct"] == 100.0 and by["precision"]["margin_90_days"] >= 7
    assert by["precision"]["planned_pct"] > by["clps"]["planned_pct"] > by["wide"]["planned_pct"]
    assert by["clps"]["planned_range_pct"][1] - by["clps"]["planned_range_pct"][0] > 2.0           # a real range, not a point
    assert by["wide"]["directions"] == 12 and by["clps"]["directions"] == 1
    assert by["wide"]["planned_direction_range_pct"][0] < by["wide"]["planned_direction_range_pct"][1]
    # landing circles: same shares as before, now with a range that brackets them
    cc = client.post("/api/landing-circles", json=C1).json()
    assert [k["points"] for k in cc["classes"]] == [17, 37, 61, 93] and "resamplings" in cc["range_note"]
    for k in cc["classes"]:
        lo, hi = k["planned_range_pct"]
        assert lo <= k["planned_pct"] <= hi and len(k["range_lo_pct"]) == len(k["share_pct"]) == 60
    k250 = cc["classes"][1]
    assert k250["planned_range_pct"][1] - k250["planned_range_pct"][0] >= 5.0                     # 62 % on 37 points is not exact
    # the same request twice gives the same range (fixed seed)
    assert client.post("/api/landing-circles", json=C1).json()["classes"][1]["planned_range_pct"] == k250["planned_range_pct"]


@needs_dem
def test_lander_classes_on_the_fallback_grid_and_without_terrain():
    os.environ["SLIPDAY_SKIP_DEMS"] = "ldem_80s_80m"
    _reset()
    try:
        c = client.post("/api/lander-classes", json=C1).json()
        by = {k["id"]: k for k in c["classes"]}
        assert c["available"] and c["grid_resolution_m"] == 240.0
        assert by["precision"]["resolvable"] is False and "240 m cell" in by["precision"]["why"]      # 100 m inside one cell
        assert by["clps"]["resolvable"] and by["wide"]["resolvable"]
        r = client.post("/api/lander-classes", json={"site": {"id": "shackleton"}, "landing": L, "terrain": False}).json()
        assert r["available"] is False and "no terrain" in r["reason"]
    finally:
        os.environ.pop("SLIPDAY_SKIP_DEMS", None)
        _reset()


@needs_80
def test_year_ribbon_is_the_cards_verdict_for_every_date_of_a_year():
    card = client.post("/api/mission", json=C1).json()
    r = client.post("/api/year-ribbon", json=C1)
    assert r.status_code == 200
    y = r.json()
    assert y["days"] == 365 == len(y["verdicts"]) == len(y["smooth_sphere"])
    assert y["yes"] + y["not_sure"] + y["no"] == 365 and y["yes"] == y["verdicts"].count("y")
    code = {"yes": "y", "not sure": "u", "no": "n"}
    assert y["verdicts"][:60] == "".join(code[d["verdict"]] for d in card["days"])       # the first 60 cells are the card's strip
    assert sum(m["dates"] for m in y["months"]) == 365 and sum(m["yes"] for m in y["months"]) == y["yes"]
    # the season the first pass measured with a script: 62 clear-yes dates of 365, none from February to June
    assert y["yes"] == 62
    assert set(y["months_without_a_yes"]) >= {"2027-02", "2027-03", "2027-04", "2027-05", "2027-06"}
    assert client.post("/api/year-ribbon", json={**C1, "days": 20}).status_code == 422


@needs_80
@needs_field
@needs_scatter
def test_scatter_checked_slip_margin_map():
    body = {"start": L, "n_dates": 60}
    r = client.post("/api/robust-map", json=body)
    assert r.status_code == 200
    m = r.json()
    assert m["available"] and m["members"] == 13 and m["scatter_m"] == 100.0 and m["n"] == 120
    single, rob, npass = (np.array(m["layers"][k]) for k in ("single", "robust", "points_passing"))
    sm = client.post("/api/slipmap", json=body).json()
    assert list(single) == sm["layers"]["margin"]                                # the same single-point map
    c = m["counts"]
    assert c["single_point_coloured"] == int((single >= 0).sum()) == 733
    assert c["re_checked"] + c["not_re_checked"] == 733 and c["not_re_checked"] == int((rob == -2).sum()) == 0
    assert c["keep_a_margin"] + c["lose_their_margin"] == c["re_checked"]
    assert c["keep_a_margin"] == int((rob >= 0).sum()) and c["lose_their_margin"] == int((rob == -3).sum())
    assert c["keep_the_same_margin"] + c["keep_a_shorter_margin"] == c["keep_a_margin"]
    assert sum(c["surviving_margin_histogram"].values()) == c["keep_a_margin"]
    # the scatter can only shorten a margin, and a point that keeps one has all 13 touchdown points passing as planned
    assert ((rob == -1) == (single < 0)).all() and (rob[rob >= 0] <= single[rob >= 0]).all()
    assert (npass[rob >= 0] == 13).all() and (npass[rob == -3] < 13).all() and (npass[rob == -3] >= 1).all()
    assert 0 < c["lose_their_margin"] < c["re_checked"] and c["largest_surviving_margin"] <= c["largest_single_point_margin"]
    # like for like against the mission card at three map points: the days on which all 13 touchdown points pass
    fld = field.load()
    crit = Criteria()
    picks = [int(np.argmax(rob)), int(np.nonzero(rob == -3)[0][0]), int(np.nonzero(rob == 0)[0][0])]
    for i in picks:
        la, lo = round(float(fld["lat"][i]), 5), round(float(fld["lon"][i]), 5)
        s = sites.custom_site("map point", la, lo)
        card = robust.mission_card(s, L, 240.0, 100.0, 14.0, crit, 0.0, 2.0, 100.0, 60)
        run = -1
        for d in card["days"]:
            if d["points_passing"] != d["points"]:
                break
            run = d["slip_days"]
        assert card["days"][0]["points"] == 13
        # identical, although the stored skylines are rounded to 0.002 deg (measured: 12 of 12 sampled points identical)
        assert (int(rob[i]) if rob[i] >= 0 else -1) == run, (i, int(rob[i]), run)
        assert int(npass[i]) == card["days"][0]["points_passing"]
    # a need nothing meets: nothing coloured, nothing to re-check
    none = client.post("/api/robust-map", json={**body, "need_sun_h": 2000}).json()
    assert none["counts"]["single_point_coloured"] == 0 and none["counts"]["keep_a_margin"] == 0
    assert client.get("/api/map").json()["scatter_field"]["available"] is True


@needs_dem
def test_permanent_shadow_layer_from_the_lola_illumination_map():
    meta = client.get("/api/map?half_km=30").json()
    ps = meta["permanent_shadow"]
    assert ps["available"] and ps["cell_m"] == 480.0 and ps["shown_km2"] > 50 and "DERIVED" in ps["note"]
    img = client.get(ps["image"])
    assert img.status_code == 200 and img.content[:8] == b"\x89PNG\r\n\x1a\n"
    # the floor of Shackleton never sees the Sun; the connecting ridge does, with shadow a few kilometres away
    floor = moonmap.nearest_permanent_shadow(-89.67, 129.78)
    assert floor["found"] and floor["site_cell_is_shadowed"] and floor["dist_km"] < 0.5
    ridge = moonmap.nearest_permanent_shadow(-89.4398, -137.17)
    assert ridge["found"] and not ridge["site_cell_is_shadowed"] and 1.0 < ridge["dist_km"] < 20.0
    assert moonmap.nearest_permanent_shadow(10.0, 20.0) is None                  # outside the layer
    w = client.post("/api/why", json={"site": {"id": "shackleton_floor"}, "landing": L}).json()
    assert w["permanent_shadow"]["site_cell_is_shadowed"] is True


# ------------------------------------------------------------------ the same example on a finer grid

FINE_DEM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "dem20")
needs_fine_store = pytest.mark.skipif(not os.path.exists(api.FINER), reason="no stored finer-grid check (run scripts/ridge_20m.py --save)")


@needs_80
@needs_fine_store
def test_the_default_example_says_what_the_20m_grid_answers():
    m = client.post("/api/mission", json=C1).json()
    store = client.get("/api/finer-grid").json()
    assert store["available"] and store["fine_grid"].startswith("LOLA, 20 m/px") and store["used_grid"].startswith("LOLA, 80 m/px")
    e = [x for x in store["entries"] if x["site_id"] == "shackleton"][0]
    # the stored 80 m side is what the page serves now, day by day
    assert e["used"]["verdict"] == m["verdict"] and e["used"]["slip_margin_days"] == m["slip_margin_days"]
    assert e["used"]["points_passing_by_day"] == [d["points_passing"] for d in m["days"]]
    # and the card carries the finer grid's answer for this very example, whatever it is
    f = m["finer_grid_check"]
    assert f["verdict"] == e["fine"]["verdict"] and f["points_passing"] == e["fine"]["points_passing_by_day"][0] and f["points"] == 13
    assert f["short"].startswith("On the 20 m grid: ") and f"({f['points_passing']} of 13 touchdown points)" in f["short"]
    assert f["agrees"] is False and f["opening_example"] is False
    assert {"yes": "Yes", "not sure": "Not sure", "no": "No"}[f["verdict"]] + " as planned" in f["short"]
    # measured on 14 Nov 2026: the 20 m grid does not confirm the planned date (11 of 13), and says so here
    assert f["verdict"] == "not sure" and f["points_passing"] == 11
    # any other date, need or rule is a different example: no note
    assert "finer_grid_check" not in client.post("/api/mission", json={**C1, "landing": "2026-11-19T00:00:00Z"}).json()
    assert "finer_grid_check" not in client.post("/api/mission", json={**C1, "need_sun_h": 200}).json()
    assert "finer_grid_check" not in client.post("/api/mission", json={**C1, "min_sun_fraction": 0.0}).json()
    assert "finer_grid_check" not in client.post("/api/mission", json={"site": {"id": "im2"}, "landing": L}).json()


@needs_80
@needs_fine_store
@pytest.mark.skipif(not os.path.exists(os.path.join(FINE_DEM, "ldem_pole_20m_f32.npy")),
                    reason="the 20 m crop is not installed (run scripts/fetch_ldem20_crop.py)")
def test_the_stored_finer_grid_check_reproduces_on_the_20m_crop():
    stored = [x for x in client.get("/api/finer-grid").json()["entries"] if x["site_id"] == "shackleton"][0]["fine"]
    os.environ["SLIPDAY_DEM_DIR"] = FINE_DEM
    _reset()
    try:
        s = get_site("shackleton")
        assert s.horizon.meta["resolution_m"] == 20.0 and s.horizon.meta["dem_label"].startswith("LOLA, 20 m/px; beyond its edge 80 m")
        card = robust.mission_card(s, L, 240.0, 100.0, 14.0, Criteria(), 0.0, 2.0, 100.0, 60)
        assert card["verdict"] == stored["verdict"] and card["slip_margin_days"] == stored["slip_margin_days"]
        assert [d["points_passing"] for d in card["days"]] == stored["points_passing_by_day"]
        assert "the coarser grid (LOLA, 80 m/px)" in card["sure"]["text"]
        # the crop sits where its georeference says: within a few metres of the 80 m grid at the site
        d20, d80 = demstore.member("ldem_pole_20m"), demstore.member("ldem_80s_80m")
        la, lo = np.array([-89.4398, -89.9, -89.62]), np.array([-137.17, 0.0, 60.0])
        assert np.abs(d20.height_m(la, lo) - d80.height_m(la, lo)).max() < 15.0
    finally:
        os.environ["SLIPDAY_DEM_DIR"] = REAL_DEM
        _reset()


@needs_80
@needs_fine_store
def test_the_page_opens_on_an_example_both_grids_support():
    """Follow-up of 15 Nov: the opening example is chosen by a written rule (LOCAL_PASS_2_RESULTS.md, H.1)."""
    store = client.get("/api/finer-grid").json()
    op = store.get("opening_example")
    if not op or not op.get("chosen"):
        pytest.skip("no opening example chosen on this installation (run scripts/pick_opening_example.py --save)")
    # every candidate tried is stored with both cards, in the rule's order, and the chosen one is the first that passes
    ranks = [c["rank"] for c in op["tried"]]
    assert ranks == list(range(1, len(ranks) + 1)) and len(ranks) <= 6 and op["candidates"] >= len(ranks)
    ok = lambda k: k["verdict"] == "yes" and k["slip_margin_days"] >= 1  # noqa: E731
    passed = [c["rank"] for c in op["tried"] if ok(c["card_80m"]) and ok(c["card_20m"])]
    assert passed and op["chosen"]["rank"] == passed[0] == ranks[-1]
    chosen = [c for c in op["tried"] if c["rank"] == op["chosen"]["rank"]][0]
    # the curated opening site is that point, and the page's own card for it is the stored 80 m card
    s = [x for x in client.get("/api/sites").json()["sites"] if x["id"] == "robust_pick"][0]
    assert abs(s["lat"] - chosen["lat"]) < 1e-5 and abs(s["lon"] - chosen["lon"]) < 1e-5 and s["confidence"] == "model-selected point"
    m = client.post("/api/mission", json={"site": {"id": "robust_pick"}, "landing": L}).json()
    assert m["verdict"] == "yes" == chosen["card_80m"]["verdict"] and m["slip_margin_days"] == chosen["card_80m"]["slip_margin_days"] >= 1
    assert [d["points_passing"] for d in m["days"]] == chosen["card_80m"]["points_passing_by_day"]
    f = m["finer_grid_check"]
    assert f["agrees"] is True and f["opening_example"] is True and f["verdict"] == "yes"
    assert f["slip_margin_days"] == chosen["card_20m"]["slip_margin_days"] >= 1 and f["points_passing"] == 13
    assert f["short"].startswith("Both grids agree. On the 20 m grid: Yes as planned (13 of 13 touchdown points), ")
    # which need ends its margin is said, with the hours
    w = client.post("/api/why", json={"site": {"id": "robust_pick"}, "landing": L}).json()
    eb = w["flip"]["ended_by"]
    assert w["flip"]["day"] == m["slip_margin_days"] + 1 and eb["kind"] in ("earth contact hours", "sunlit hours")
    assert eb["got_h"] < eb["need_h"] and eb["need_h"] == (100.0 if eb["kind"] == "earth contact hours" else 240.0)
    # the case kept beside it: the connecting ridge, where the two grids disagree
    old = client.post("/api/mission", json=C1).json()["finer_grid_check"]
    assert old["agrees"] is False and old["verdict"] == "not sure"


@needs_80
@needs_fine_store
@pytest.mark.skipif(not os.path.exists(os.path.join(FINE_DEM, "ldem_pole_20m_f32.npy")),
                    reason="the 20 m crop is not installed (run scripts/fetch_ldem20_crop.py and scripts/fetch_ldem20_tiles.py)")
def test_the_opening_example_reproduces_on_the_20m_crop():
    op = client.get("/api/finer-grid").json().get("opening_example")
    if not op or not op.get("chosen"):
        pytest.skip("no opening example chosen on this installation")
    stored = [c for c in op["tried"] if c["rank"] == op["chosen"]["rank"]][0]["card_20m"]
    os.environ["SLIPDAY_DEM_DIR"] = FINE_DEM
    _reset()
    try:
        s = get_site("robust_pick")
        if s.horizon.meta["resolution_m"] != 20.0:
            pytest.skip("the 20 m crop on this installation does not reach the opening example (run scripts/fetch_ldem20_tiles.py --rows 30 32 --cols 33 33)")
        card = robust.mission_card(s, L, 240.0, 100.0, 14.0, Criteria(), 0.0, 2.0, 100.0, 60)
        assert card["verdict"] == stored["verdict"] == "yes" and card["slip_margin_days"] == stored["slip_margin_days"] >= 1
        assert [d["points_passing"] for d in card["days"]] == stored["points_passing_by_day"]
        assert card["sure"]["coarse_passes"] and card["sure"]["near_passes"] and "the coarser grid (LOLA, 80 m/px)" in card["sure"]["text"]
    finally:
        os.environ["SLIPDAY_DEM_DIR"] = REAL_DEM
        _reset()


def test_each_assumed_lander_class_cites_the_page_its_figure_was_read_on():
    for c in robust.LANDER_CLASSES:
        assert "ASSUMED" in c["basis"] and "this project's choice" in c["basis"] and "read 15 Nov 2026" in c["basis"]
        assert c["source_url"].startswith("https://") and c["source"] and c["figure"]
    hosts = [c["source_url"].split("/")[2] for c in robust.LANDER_CLASSES]
    assert hosts == ["global.jaxa.jp", "www.nasa.gov", "www.isro.gov.in"]
