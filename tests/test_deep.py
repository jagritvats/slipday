"""Deep pass (15 Nov 2026): whole runs (rule R8), monthly launch windows for real missions (R9, R10), the 20 m
mark worked out on request for any map date, and the documents.  Figures as in DEEP_PASS.md."""
import json
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from slipday import api, demstore, field, finer20, hindcast, moonmap, scatterfield, shadowsites, sites, survival, why, windows
from slipday.api import app
from slipday.metrics import Criteria

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
client = TestClient(app)
REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")
HAVE_80 = os.path.exists(os.path.join(REAL_DEM, "ldem_80s_80m_f32.npy")) and os.path.exists(os.path.join(REAL_DEM, "dems.json"))
needs_80 = pytest.mark.skipif(not HAVE_80, reason="the 80 m grid is not installed (run scripts/fetch_grid80.py)")
needs_scatter = pytest.mark.skipif(not os.path.exists(os.path.join(field.FIELD_DIR, "scatter_field.json")) or field.load() is None,
                                   reason="skyline field or scatter skylines not built")
needs_20 = pytest.mark.skipif(not finer20.available(), reason="the stored 20 m skylines are not installed (scripts/finer_map_store.py)")
CRIT = Criteria(stations=True)
L = "2026-11-18T00:00:00Z"


@pytest.fixture(scope="module", autouse=True)
def real_dem():
    old = os.environ.get("SLIPDAY_DEM_DIR")
    if HAVE_80:
        os.environ["SLIPDAY_DEM_DIR"] = REAL_DEM
        demstore.reload()
        sites._terrain_profile.cache_clear()
        why._cache.clear()
        scatterfield.reload()
        survival._cache.clear()
    yield
    if old is not None:
        os.environ["SLIPDAY_DEM_DIR"] = old
    demstore.reload()
    sites._terrain_profile.cache_clear()
    scatterfield.reload()


# ------------------------------------------------------------------ R8: whole runs (no data needed)

def test_whole_runs_count_to_their_end_past_the_window():
    f = np.array([0, 0, 1, 1, 1, 1, 1, 1, 0, 0], dtype=bool)
    best, open_ = survival.full_runs(f, [0, 3, 8], 3)
    assert best[0].tolist() == [6, 5, 0]          # begins inside [0,3): all 6 h; under way at 3: 5 h from touchdown; none in [8,11)
    assert not open_[0].any()
    g = np.array([0, 1, 1, 1], dtype=bool)
    b2, o2 = survival.full_runs(g, [0], 2)
    assert b2[0, 0] == 3 and o2[0, 0]                # still going at the end of the series: a lower bound, flagged


def test_a_run_that_starts_after_the_window_is_not_met():
    f = np.array([0, 0, 0, 0, 1, 1], dtype=bool)
    best, _ = survival.full_runs(f, [0], 3)
    assert best[0, 0] == 0


# ------------------------------------------------------------------ R10 on real data

@needs_80
def test_next_monthly_windows_for_the_opening_example():
    r = client.post("/api/windows", json={"site": {"id": "robust_pick"}, "landing": L, "earth_stations": True}).json()
    got = [(x["landing_utc"][:16], x["verdict"], x["slip_margin_days"]) for x in r["rows"]]
    assert got == [("2026-11-18T00:00", "yes", 8), ("2026-12-17T13:00", "yes", 6), ("2027-01-16T01:00", "no", -1),
                   ("2027-02-14T14:00", "no", -1)]
    assert [x["earth_h"] for x in r["rows"]] == [311, 253, 204, 154]
    assert r["step_days"] == pytest.approx(29.530589)


@needs_80
def test_im1_would_have_been_a_yes_in_the_window_it_missed_too():
    r = windows.next_windows(sites.get_site("im1"), "2024-02-22T23:00:00Z", [-1, 0, 1, 2], 168, 100, 14, CRIT, 0.0, 2.0, 100.0)
    got = [(x["landing_utc"][:16], x["verdict"], x["slip_margin_days"], x["night_met_h"]) for x in r["rows"]]
    assert got == [("2024-01-24T10:00", "yes", 1, 422), ("2024-02-22T23:00", "yes", 1, 431), ("2024-03-23T12:00", "yes", 1, 445),
                   ("2024-04-22T00:00", "yes", 0, 456)]


@needs_80
def test_viper_windows_follow_the_written_assumptions():
    la, lo = windows.rim_point(-85.2752, 53.2725, 79.27233, 270.0)
    assert (la, lo) == (-85.0981, 37.7891)
    v = sites.custom_site("Nobile west rim", la, lo)
    lands = [x for x in windows.sunrise_windows(v, "2027-08-25T00:00:00Z", "2027-12-31T23:00:00Z", CRIT) if "2027-09-01" <= x[:10]]
    assert [x[:16] for x in lands] == ["2027-09-01T07:00", "2027-09-30T10:00", "2027-10-29T19:00", "2027-11-28T12:00", "2027-12-28T12:00"]
    j = windows.judge(v, lands[-1], 240, 100, 14, CRIT, 0.0, 2.0, 100.0, long_days=100)
    assert j["verdict"] == "no" and "Earth is behind the skyline at touchdown" in j["reasons"] and j["next_good_utc"][:10] == "2027-12-31"
    assert j["long"]["hours"] == 2400 and j["long"]["night_met_h_max"] == 433


def test_the_stored_real_windows_carry_sources_and_assumptions():
    r = client.get("/api/real-windows").json()
    if not r.get("available"):
        pytest.skip("scripts/real_windows.py has not been run")
    assert r["im1"]["rows"][0]["k"] == -1 and r["im1"]["mission"]["flown_k"] == 0
    assert "late 2027" in r["viper"]["mission"]["deadline"] and len(r["viper"]["mission"]["assumptions"]) == 2
    src = open(os.path.join(ROOT, "data", "reference", "DOWNLOADS.tsv"), encoding="utf-8").read() if os.path.exists(
        os.path.join(ROOT, "data", "reference", "DOWNLOADS.tsv")) else ""
    if src:
        for f in ("sfn_im1_mid_january.html", "space_com_im1_feb15.html", "nasa_viper_blue_origin_2025.html", "svs_4937_viper_site.html",
                  "artemis3_regions_2024.html", "artemis3_update_lpsc2026.docx"):
            assert f in src, f


# ------------------------------------------------------------------ the 20 m mark on request

@needs_80
@needs_scatter
@needs_20
def test_the_20_m_mark_on_request_reproduces_the_stored_dates_and_covers_other_dates():
    body = {"start": L, "n_dates": 60, "earth_stations": True}
    a = client.post("/api/finer-map", json=body).json()
    assert (a["agree"], a["points_done"], a["equal_margins"]) == (639, 733, 573) and a["on_request"]
    b = client.post("/api/finer-map", json={**body, "start": "2026-12-20T00:00:00Z"}).json()
    assert (b["agree"], b["points_done"]) == (436, 523)
    assert client.post("/api/finer-map", json={**body, "mast_m": 10}).json()["available"] is False


# ------------------------------------------------------------------ page and documents

def test_the_page_carries_the_windows_and_the_real_missions_panel():
    js = open(os.path.join(ROOT, "static", "app.js"), encoding="utf-8").read()
    html = open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8").read()
    for piece in ("function loadWindows", "function renderWindows", "data-win=", "Missed the window? Next", "function renderReal",
                  "/api/real-windows", "/api/finer-map", "night_full_h", "whole runs, to their end"):
        assert piece in js, piece
    assert 'id="realPanel"' in html


def test_documents_drop_the_window_clipped_headline():
    for f in ("demo/STORYBOARD.md", "demo/SLIDES.md", "SUBMISSION_DRAFT.md", "README.md"):
        t = open(os.path.join(ROOT, f), encoding="utf-8").read()
        assert "grows from 20 to 21 hours" not in t and "from 27 to 219" not in t, f
    deep = open(os.path.join(ROOT, "DEEP_PASS.md"), encoding="utf-8").read()
    for rule in ("**R8.", "**R9.", "**R10."):
        assert rule in deep
    man = open(os.path.join(ROOT, "..", "..", "realdata", "lunar", "MANIFEST.md"), encoding="utf-8").read() if os.path.exists(
        os.path.join(ROOT, "..", "..", "realdata", "lunar", "MANIFEST.md")) else ""
    if man:
        assert "IPN_42-243A.pdf" in man and "LunaNet_Interoperability_Specification_v5.pdf" in man


# ------------------------------------------------------------------ follow-up: causes, IM-1 January by day, other options

@needs_80
def test_the_windows_name_the_need_that_fails():
    r = client.post("/api/windows", json={"site": {"id": "robust_pick"}, "landing": L, "earth_stations": True}).json()
    assert [x["fails_on"] for x in r["rows"]] == [[], [], ["sunlight"], ["Sun at touchdown", "sunlight"]]
    assert all(x["earth_h"] >= 100 for x in r["rows"])            # Earth contact is not the cause (the deep pass said it was)
    assert [x["sunlit_h"] for x in r["rows"]][2:] == [217, 151]


@needs_80
def test_im1_published_january_window_day_by_day():
    s = sites.get_site("im1")
    got = []
    for d in range(17, 26):
        j = windows.judge(s, "2024-01-%02dT10:00:00Z" % d, 168, 100, 14, CRIT, 0.0, 2.0, 100.0)
        got.append((j["verdict"], j["slip_margin_days"], j["fails_on"]))
    assert got[:4] == [("no", -1, ["Sun at touchdown"])] * 4
    assert [g[1] for g in got[4:]] == [4, 3, 2, 1, 0] and all(g[0] == "yes" for g in got[4:])


@needs_80
@needs_scatter
def test_other_sites_and_hours_in_each_missed_window():
    body = {"site": {"id": "robust_pick"}, "landing": L, "earth_stations": True,
            "alternatives": [{"id": "robust_pick"}, {"id": "shackleton"}, {"id": "im2"}, {"id": "im1"}]}
    r = client.post("/api/window-options", json=body).json()
    dec, jan, feb = r["rows"]
    # final fixes: December's 01:00 is a tie-break (the planned hour also gives 6 days)
    assert dec["best_hour"]["landing_utc"][:16] == "2026-12-17T01:00" and dec["best_hour"]["slip_margin_days"] == 6
    assert dec["best_hour"]["planned_margin_days"] == 6 and dec["best_hour"]["tie_with_planned"]
    assert not jan["best_hour"]["found"] and not feb["best_hour"]["found"]
    # the plan's own site is not counted among the alternatives; every alternative gets the same +/- 72 h search
    assert jan["sites_checked"] == 20 and jan["sites_yes_at_window_hour"] == 5 and len(jan["sites_yes"]) == 13
    fy = jan["first_yes"]
    assert fy["name"].startswith("Shackleton connecting ridge") and fy["landing_utc"][:16] == "2027-01-14T01:00"
    assert fy["slip_margin_days"] == 5 and fy["fragile"] and fy["min_clearance_deg"] < 0.27
    assert len(feb["sites_yes"]) == 5 and feb["first_yes"]["name"].startswith("IM-2")


def test_follow_up_corrections_are_in_the_page_and_the_record():
    js = open(os.path.join(ROOT, "static", "app.js"), encoding="utf-8").read()
    for piece in ("function failWords", "id=\"optGo\"", "inferred +29.5 d", "<b>Our inference</b>", "<b>our model</b>", "No map of these hours is drawn"):
        assert piece in js, piece
    assert "night: { label:" not in js
    deep = open(os.path.join(ROOT, "DEEP_PASS.md"), encoding="utf-8").read()
    assert "## F0. Correction of the record for D3" in deep and "fixed before computing (05:52)" not in deep.split("# Follow-up")[0]
    slides = open(os.path.join(ROOT, "demo", "SLIDES.md"), encoding="utf-8").read()
    assert "Earth contact there falls 311" not in slides and "217 and 148 hours against 240" in slides   # live 5 m terrain: February 151 -> 148 h
