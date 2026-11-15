"""Local pass 4 (15 Nov 2026): survival across slip days (rule R5), the naming rule (R7), the year ribbon under
the station rule, the link-margin note and the 3-D time label.  Figures as printed in LOCAL_PASS_2_RESULTS.md,
pass 4.  Tests that need the REAL 80 m grid, the skyline field or the scatter skylines skip without them."""
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from slipday import api, demstore, gazetteer, hindcast, moonmap, scatterfield, shadowsites, sites, survival, why, field
from slipday.api import app
from slipday.metrics import Criteria, span_stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
client = TestClient(app)
REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")
HAVE_DEM = os.path.exists(os.path.join(REAL_DEM, "dems.json"))
HAVE_80 = os.path.exists(os.path.join(REAL_DEM, "ldem_80s_80m_f32.npy"))
needs_80 = pytest.mark.skipif(not (HAVE_DEM and HAVE_80), reason="the 80 m grid is not installed (run scripts/fetch_grid80.py)")
needs_scatter = pytest.mark.skipif(not os.path.exists(os.path.join(field.FIELD_DIR, "scatter_field.json")) or field.load() is None,
                                   reason="skyline field or scatter skylines not built")
L = "2026-11-18T00:00:00Z"
OPEN = {"site": {"id": "robust_pick"}, "landing": L, "earth_stations": True}


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
    shadowsites.reload()
    survival._cache.clear()


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


# ------------------------------------------------------------------ the run-length code (no data needed)

def test_longest_run_inside_windows_is_cut_at_the_window_and_flagged():
    f = np.array([0, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 0], dtype=bool)
    best, past = survival.longest_in_windows(f, [0, 4, 6], 5)
    assert best[0].tolist() == [3, 3, 5]          # [0,5): 1 1 1 | [4,9): 0 0 1 1 1 | [6,11): 1 1 1 1 1
    # window [4, 9) holds 0 0 1 1 1 and the run goes on at hour 9: 3 hours, flagged
    best2, past2 = survival.longest_in_windows(f, [4], 5)
    assert best2[0, 0] == 3 and past2[0, 0]
    assert survival.longest_run_hours(f) == 5


def test_a_night_going_on_at_touchdown_counts_from_touchdown():
    f = np.array([1, 1, 1, 1, 0, 0], dtype=bool)
    best, past = survival.longest_in_windows(f, [2], 3)
    assert best[0, 0] == 2 and not past[0, 0]


# ------------------------------------------------------------------ R5 on real data

@needs_80
def test_ride_through_hours_for_the_opening_example():
    r = client.post("/api/survival", json=OPEN).json()
    assert r["available"] and r["verdict"] == "yes" and r["margin_days"] == 8 and r["points"] == 13
    nights = [d["night_h"] for d in r["days"]]
    outs = [d["outage_h"] for d in r["days"]]
    assert nights[:9] == [20, 20, 20, 20, 20, 20, 20, 20, 21]
    assert outs[:9] == [27, 51, 75, 99, 123, 147, 171, 195, 219]
    assert r["days"][8]["night_past_window"] and r["days"][8]["outage_past_window"]
    # deep pass, rule R8: the headline is the whole run the lander meets, not the part inside the window
    assert [d["night_full_h"] for d in r["days"][:9]] == [20, 20, 20, 20, 20, 20, 20, 20, 179]
    assert [d["outage_full_h"] for d in r["days"][:9]] == [323] * 9
    assert r["night_sentence"] == "slip 8 days and the longest night grows from 20 to 179 hours"
    assert r["outage_sentence"] == "slip 8 days and the longest Earth outage stays at 323 hours"
    assert r["worst_over_passing_days"] == {"night_h": 179, "outage_h": 323}
    for d in r["days"]:                                   # the worst point is never better than the target
        assert d["night_h"] >= d["night_target_h"] and d["outage_h"] >= d["outage_target_h"]


@needs_80
def test_the_run_length_code_reproduces_the_existing_longest_darkness_figure_at_c1():
    s = sites.get_site("shackleton")
    st = span_stats(s, L, 365.0)
    from slipday.ephem import cached_table, grid_start, parse_utc
    from slipday.geometry import track
    t0 = grid_start(parse_utc(L), 3600)
    fa = np.concatenate([track(s, cached_table(t0 + i0 * 3600, 4380, 3600), 0.5).sun_frac > 0 for i0 in (0, 4380)])
    assert survival.longest_run_hours(~fa) == int(st["longest_dark_h"]) == 194


@needs_80
@needs_scatter
def test_the_night_layer_follows_rule_r5():
    r = client.post("/api/survival-map", json={"start": L, "n_dates": 60, "earth_stations": True}).json()
    assert r["available"] and r["points"] == 574
    assert sum(c["points"] for c in r["classes"]) == 574
    # deep pass, rule R8: whole nights, so the layer is no longer capped by the need (pass 4: 10 to 96 h)
    # follow-up, rule R14: lunar-day bands; still 556 of 574 in the top band, so the page draws no map of it
    assert [c["label"] for c in r["classes"]] == ["under 1 day", "1 to 3 days", "3 to 7 days", "7 to 12 days", "12 days or more"]
    assert [c["points"] for c in r["classes"]] == [1, 1, 6, 10, 556]
    assert (r["night_smallest_h"], r["night_largest_h"]) == (14, 468)
    night = r["layers"]["night"]
    assert night[11150] == 179 and r["layers"]["night_day0"][11150] == 20 and r["layers"]["outage"][11150] == 323
    rm = client.post("/api/robust-map", json={"start": L, "n_dates": 60, "earth_stations": True}).json()
    robust = rm["layers"]["robust"]
    assert all((night[i] >= 0) == (robust[i] >= 0) for i in range(len(robust)))   # coloured exactly where a margin is kept
    assert all(night[i] >= r["layers"]["night_day0"][i] for i in range(len(night)) if night[i] >= 0)
    ten = client.post("/api/survival-map", json={"start": L, "n_dates": 60, "mast_m": 10}).json()
    assert ten["available"] is False


# ------------------------------------------------------------------ R7 naming, year ribbon, page text

def test_naming_rule_inside_rim_and_none():
    sh = gazetteer.containing(-89.67, 129.78)
    assert sh["relation"] == "inside" and sh["phrase"] == "inside Shackleton crater"
    blk = gazetteer.containing(-85.996, 19.485)          # the ground that ends the opening margin
    # final fixes: the point is also on Malapert crater's rim line, and the phrase says both
    assert blk["phrase"] == "inside Mons Mouton, on the rim of Malapert crater" and 0.7 < blk["share_of_radius"] < 0.9
    assert blk["rim_also"]["name"] == "Malapert" and 0.9 < blk["rim_also"]["share_of_radius"] <= 1.1
    from slipday.terrain import destination
    f = [x for x in gazetteer.features() if x["name"] == "Shackleton"][0]
    for share, rel in ((0.95, "rim"), (1.05, "rim")):
        la, lo = destination(f["lat"], f["lon"], 1.0, np.array(f["diameter_km"] * 500.0 * share / 1737400.0))
        hit = gazetteer.containing(float(la), float(lo))
        assert hit is not None and hit["name"] == "Shackleton" and hit["relation"] == rel and hit["phrase"] == "on the rim of Shackleton crater"
    la, lo = destination(f["lat"], f["lon"], 1.0, np.array(f["diameter_km"] * 500.0 * 1.2 / 1737400.0))
    hit = gazetteer.containing(float(la), float(lo))
    assert hit is None or hit["name"] != "Shackleton"


@needs_80
def test_year_ribbon_reads_41_and_3_with_the_station_rule_and_42_and_2_without():
    on = client.post("/api/year-ribbon", json=OPEN).json()["verdicts"]
    off = client.post("/api/year-ribbon", json={**OPEN, "earth_stations": False}).json()["verdicts"]
    assert (on.count("y"), on.count("u")) == (41, 3) and (off.count("y"), off.count("u")) == (42, 2)


def test_docs_carry_the_corrected_figures_and_names():
    for f in ("SUBMISSION_DRAFT.md", "demo/SLIDES.md", "demo/STORYBOARD.md", "LIMITATIONS.md"):
        t = open(os.path.join(ROOT, f), encoding="utf-8").read()
        assert "42 clear-yes dates of 365, 2 not sure" not in t and "42 clear yes of 365 (2 not sure)" not in t, f
        assert "inside Malapert (crater" not in t, f
    y = open(os.path.join(ROOT, "render.yaml"), encoding="utf-8").read()
    assert "peaks at 431 MB" not in y and "1 GB" in y


def test_the_page_carries_the_pass_4_pieces():
    js = open(os.path.join(ROOT, "static", "app.js"), encoding="utf-8").read()
    v3 = open(os.path.join(ROOT, "static", "view3d.js"), encoding="utf-8").read()
    for piece in ("function loadSurvival", "function renderSurvival", "/api/survival-map", "Ride-through: slip ", "A real link would want more than",
                  "JPL IPN 42-243", "No map of these hours is drawn", "nightLegend"):
        assert piece in js, piece
    assert "label(fmtTime(timeAt(Math.round(st.pos)))" in v3          # the label shows the frame drawn, not the in-between time


DATES = os.path.join(ROOT, "data", "validation", "finer_map_dates.json")


@needs_80
@needs_scatter
@pytest.mark.skipif(not os.path.exists(DATES), reason="the 20 m map check for more dates has not been run (scripts/finer_map_dates.py)")
def test_the_20_m_mark_covers_fourteen_weekly_dates_and_is_served_for_them():
    import json
    d = json.load(open(DATES, encoding="utf-8"))
    starts = [x["start"][:10] for x in d["dates"]]
    assert starts[0] == "2026-11-18" and len(starts) == 14 and starts[-1] == "2027-02-17"
    for x in d["dates"]:
        v = list(x["cells"].values())
        assert x["points"] == len(v) and x["agree"] == sum(1 for c in v if c[2])
        assert x["keeps_on_80m_loses_on_20m"] + x["loses_on_80m_keeps_on_20m"] == x["points"] - x["agree"]
    second = d["dates"][2]["start"]
    on = client.post("/api/robust-map", json={"start": second, "n_dates": 60, "earth_stations": True}).json()
    assert on["finer"]["agree"] == d["dates"][2]["agree"] and on["finer"]["dates_checked"][0] == "2026-11-18"
    robust = on["layers"]["robust"]
    assert all(robust[int(k)] >= 0 or robust[int(k)] == scatterfield.LOST for k in on["finer"]["cells"])
    off = client.post("/api/robust-map", json={"start": second, "n_dates": 60, "earth_stations": False}).json()
    assert "finer" not in off                                        # computed with the station rule only
