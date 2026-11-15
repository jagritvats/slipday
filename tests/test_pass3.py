"""Local pass 3 (15 Nov 2026): the Earth-mask sweep on the card, slip-robust sites beside permanent shadow,
Earth contact as Deep Space Network station visibility, names for the ground that ends the margin, and the
refusal to answer another observer height with skylines stored for 2 m.  The figures held here are the ones
printed in LOCAL_PASS_2_RESULTS.md, pass 3 (rules R1 to R3 were written there before they were computed).
Tests that need the REAL 80 m grid, the skyline field or the scatter skylines skip without them."""
import hashlib
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from slipday import (api, contact, demstore, field, gazetteer, hindcast, moonmap, robust, scatterfield, shadowsites,
                     sites, stations, why)
from slipday.api import app
from slipday.metrics import Criteria
from slipday.sites import get_site

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
client = TestClient(app)
REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")
HAVE_DEM = os.path.exists(os.path.join(REAL_DEM, "dems.json"))
HAVE_80 = os.path.exists(os.path.join(REAL_DEM, "ldem_80s_80m_f32.npy"))
needs_80 = pytest.mark.skipif(not (HAVE_DEM and HAVE_80), reason="the 80 m grid is not installed (run scripts/fetch_grid80.py)")
needs_field = pytest.mark.skipif(field.load() is None, reason="skyline field not built (run scripts/build_field.py)")
needs_scatter = pytest.mark.skipif(not os.path.exists(os.path.join(field.FIELD_DIR, "scatter_field.json")),
                                   reason="scatter skylines not built (run scripts/build_scatter_field.py)")
needs_psr = pytest.mark.skipif(not os.path.exists(os.path.join(field.FIELD_DIR, "psr_pole_60m.npz")),
                               reason="permanent-shadow mask not cut (run scripts/prepare_psr.py)")
L = "2026-11-18T00:00:00Z"
OPEN = {"site": {"id": "robust_pick"}, "landing": L}
MAP = {"start": L, "n_dates": 60}


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


# ------------------------------------------------------------------ R1: the Earth-mask sweep

@needs_80
def test_earth_mask_sweep_of_the_opening_example_matches_the_results_file():
    r = client.post("/api/earth-mask", json=OPEN).json()
    assert r["available"] and r["verdict_at_zero"] == "yes" and r["margin_days_at_zero"] == 8
    assert r["yes_up_to_deg"] == pytest.approx(0.60) and r["not_sure_from_deg"] == pytest.approx(0.65)
    assert r["no_from_deg"] == pytest.approx(0.70)
    assert r["clearance_at_touchdown_deg"] == pytest.approx(0.64, abs=0.006)
    assert r["thinnest_day"] == 0                       # the planned date is the thinnest of the yes-days
    # no lander-side mask could be cited: every non-zero mask on the page is illustrative
    assert r["published_mask"] is None and api.PUBLISHED_MASK is None
    at = {round(x["mask_deg"], 2): x for x in r["at"]}
    assert at[0.0]["verdict"] == "yes" and all(at[m]["verdict"] == "no" and at[m]["points_passing"] == 0 for m in (1.0, 2.0, 5.0))


@needs_80
def test_the_sweep_is_monotone_and_the_card_agrees_with_it_at_its_own_mask():
    r = client.post("/api/earth-mask", json=OPEN).json()
    order = {"yes": 2, "not sure": 1, "no": 0}
    v = [order[x] for x in r["verdict_planned"]]
    assert all(a >= b for a, b in zip(v, v[1:]))       # tightening the rule never improves the answer
    for mask in (0.0, 0.65, 0.75):
        card = client.post("/api/mission", json={**OPEN, "earth_margin_deg": mask}).json()
        at = r["verdict_planned"][int(round(mask / 0.1))] if abs(mask * 10 - round(mask * 10)) < 1e-9 else None
        expect = {0.0: "yes", 0.65: "not sure", 0.75: "no"}[mask]
        assert card["verdict"] == expect
        if at is not None:
            assert at == expect


# ------------------------------------------------------------------ R2: slip-robust sites beside permanent shadow

@needs_field
@needs_scatter
@needs_psr
def test_shadow_sites_follow_rule_r2_and_match_the_results_file():
    r = client.post("/api/shadow-sites", json=MAP).json()
    assert r["available"]
    c = r["counts"]
    assert c["survive_a_slip_1_or_more"] == {"all": 343, "beside_shadow": 27, "beside_shadow_not_on_it": 20, "beside_shadow_but_on_it": 7}
    assert c["margin_5_or_more"]["beside_shadow"] == 0 and r["qualifying"] == 20
    best = r["best"]
    assert best["name"] == "89.572 S, 19.134 E" and best["surviving_margin_days"] == 4
    assert best["shadow_area_ha_within_reach"] == pytest.approx(10.4) and best["nearest_shadow_m"] == 221
    rows = r["rows"]
    assert len(rows) == 12
    # the rule as written: margin >= 1, area >= 10 ha, not on shadow, ranked by margin then area, >= 1 km apart
    assert all(x["surviving_margin_days"] >= 1 and x["shadow_area_ha_within_reach"] >= 10 and not x["own_pixel_shadowed"] for x in rows)
    keys = [(-x["surviving_margin_days"], -x["shadow_area_ha_within_reach"]) for x in rows]
    assert keys == sorted(keys)
    xy = [shadowsites._xy(x["lat"], x["lon"]) for x in rows]
    assert all(np.hypot(a[0] - b[0], a[1] - b[1]) >= 1000 - 1 for i, a in enumerate(xy) for b in xy[i + 1:])
    assert all(x["surviving_margin_days"] >= 1 for x in r["on_shadow_itself"])
    assert "not where ice is" in r["note"]
    assert sum(1 for v in r["layer"] if v == 1) == 20 and sum(1 for v in r["layer"] if v == 2) == 7


@needs_psr
def test_the_permanent_shadow_mask_is_a_plain_cut_of_the_official_map():
    psr = shadowsites.load()
    assert psr is not None and psr["pixel_m"] == 60.0
    meta = psr["meta"]
    assert meta["source_file"] == "AVGVISIB_85S_060M_201608.TIF"
    assert meta["source_sha256"].startswith("ccf67d4f39e0a970")
    assert int(psr["mask"].sum()) == meta["zero_pixels"] == 178727


@needs_field
def test_another_observer_height_is_not_answered_with_skylines_stored_for_2_m():
    for ep in ("/api/robust-map", "/api/shadow-sites"):
        r = client.post(ep, json={**MAP, "mast_m": 10}).json()
        assert r["available"] is False and "not available for 10 m" in r["reason"], ep


# ------------------------------------------------------------------ R3: Earth contact as station visibility

def test_station_rule_reads_the_cited_handbook_figures():
    d = stations.describe()
    assert d["mask_deg"] == 10.0 and d["mask_cited"] is True
    assert "10.0 degrees for low-power transmit" in d["mask_quote"]
    assert "deepspace.jpl.nasa.gov/dsndocs/810-005/301/301P.pdf" in d["mask_url"]
    src = open(os.path.join(ROOT, "fixtures", "stations", "SOURCES.md"), encoding="utf-8").read()
    for name in sorted(os.listdir(os.path.join(ROOT, "fixtures", "stations"))):
        if name.endswith(".txt"):
            with open(os.path.join(ROOT, "fixtures", "stations", name), "rb") as fh:
                assert hashlib.sha256(fh.read()).hexdigest() in src, name
    assert "53d8c28eddde48a2212b403422689a11fc0ff75fcab830a1e2ec00cdf8a4e160" in src      # the handbook read
    dl_path = os.path.join(ROOT, "data", "reference", "DOWNLOADS.tsv")                    # git-ignored folder
    if os.path.exists(dl_path):
        assert "53d8c28eddde48a2212b403422689a11fc0ff75fcab830a1e2ec00cdf8a4e160" in open(dl_path, encoding="utf-8").read()


@needs_80
def test_station_contact_for_the_opening_example():
    r = client.post("/api/stations", json={**OPEN, "window_days": 14}).json()
    assert r["available"] and r["mask_deg"] == 10.0
    sp = r["window"]["split"]
    assert sp == {"earth_above_skyline": 311, "goldstone": 104, "madrid": 122, "canberra": 85, "none_in_view": 0, "station_contact": 311}
    assert len(r["window"]["code"]) == 336 and r["window"]["longest_gap_h"] == 0
    rows = r["cycle"]["rows"]
    assert [x["year"] for x in rows] == list(range(2026, 2045))
    for x in rows:
        tot = x["goldstone_share"] + x["madrid_share"] + x["canberra_share"] + x["none_in_view_share"]
        assert tot == pytest.approx(1.0, abs=0.003)
        assert 0.0 <= x["none_in_view_share"] < 0.02
    cg = [x["canberra_share"] for x in rows]
    assert max(cg) - min(cg) > 0.1                       # the split moves over the cycle


@needs_80
def test_the_station_rule_does_not_change_the_opening_verdict_or_margin_but_does_bite_when_tightened():
    a = client.post("/api/mission", json=OPEN).json()
    b = client.post("/api/mission", json={**OPEN, "earth_stations": True}).json()
    assert (a["verdict"], a["slip_margin_days"]) == (b["verdict"], b["slip_margin_days"]) == ("yes", 8)
    assert "Deep Space Network" in b["criteria"]["earth_rule"]
    old = stations.MASK_DEG
    try:                                                 # a 40-degree limit leaves too few hours: the rule is live
        stations.MASK_DEG = 40.0
        stations._cache.clear()
        c = client.post("/api/mission", json={**OPEN, "earth_stations": True, "need_earth_h": 99}).json()
        assert c["verdict"] == "no"
    finally:
        stations.MASK_DEG = old
        stations._cache.clear()


def test_hours_are_credited_to_the_complex_where_the_moon_is_highest():
    u = 1794960000.0 + 3600.0 * np.arange(48)
    el = stations.moon_elevation_deg(u)
    car = stations.carrier(u)
    for k in range(len(u)):
        if el[:, k].max() >= 10.0:
            assert car[k] == int(np.argmax(el[:, k]))
        else:
            assert car[k] == -1


# ------------------------------------------------------------------ names for the ground that ends the margin

def test_a_name_is_given_only_where_a_named_feature_contains_the_point():
    sh = gazetteer.containing(-89.67, 129.78)
    assert sh is not None and sh["name"] == "Shackleton" and sh["km_from_centre"] == 0.0
    assert gazetteer.containing(-89.9, 0.0) is None or gazetteer.containing(-89.9, 0.0)["km_from_centre"] <= gazetteer.containing(-89.9, 0.0)["diameter_km"] / 2
    for f in gazetteer.features()[:50]:                  # strictly inside: a point just beyond the rim gets another name or none
        from slipday.terrain import destination
        la, lo = destination(f["lat"], f["lon"], 0.3, np.array(f["diameter_km"] * 1000.0 * 0.51 / 1737400.0))
        hit = gazetteer.containing(float(la), float(lo))
        # pass 4, rule R7: just beyond the rim circle a feature is at most "on the rim of" / "near", never "inside"
        assert hit is None or hit["name"] != f["name"] or hit["relation"] in ("rim", "near")


@needs_80
def test_the_ground_that_ends_the_opening_margin_is_named_from_the_gazetteer():
    w = client.post("/api/why", json={**OPEN, "day": 0}).json()
    t = w["flip"]["stretch"]["terrain"]
    # pass 4, rule R7: "inside" only within 90 % of a radius; the point is at 98.6 % of Malapert crater's (its rim)
    # and at 78 % of Mons Mouton's, so it is named inside Mons Mouton (pass 3 said "inside Malapert")
    assert t["named"]["name"] == "Mons Mouton" and t["named"]["relation"] == "inside"
    assert t["named"]["km_from_centre"] <= 0.9 * t["named"]["diameter_km"] / 2
    assert "inside Mons Mouton (130 km across" in w["flip"]["text"] and "on the rim of Malapert crater (72.4 km)" in w["flip"]["text"]


# ------------------------------------------------------------------ what the page carries

def test_the_page_carries_the_pass_3_controls():
    html = open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8").read()
    js = open(os.path.join(ROOT, "static", "app.js"), encoding="utf-8").read()
    assert 'id="earthStations" type="checkbox" checked' in html
    assert 'id="contactPanel"' in html and 'id="shadowBtn"' in html and 'id="shadowSites"' in html
    for fn in ("function loadEarthMask", "function renderEarthLine", "function loadContact", "function renderContact",
               "function loadShadow", "function renderShadow", "masks illustrative", "earth_stations"):
        assert fn in js, fn
    assert "fixed example" in js


def test_the_opening_map_is_never_evicted_from_memory():
    from collections import OrderedDict
    from slipday.ephem import grid_start, parse_utc
    k_open = field._key(grid_start(parse_utc(L), 3600), 60, 24, 336, Criteria(stations=True), 0.0)
    assert field.pinned(k_open) and field.pinned(field._key(grid_start(parse_utc(L), 3600), 60, 24, 336, Criteria(), 0.0))
    cache = OrderedDict([(k_open, 1)])
    for d in range(1, 8):
        cache[field._key(grid_start(parse_utc(L), 3600) + d * 86400, 60, 24, 336, Criteria(), 0.0)] = d
        field.evict(cache, 3)
    assert k_open in cache and len(cache) == 3


FINER_MAP = os.path.join(ROOT, "data", "validation", "finer_map_check.json")


@needs_field
@needs_scatter
@needs_80
@pytest.mark.skipif(not os.path.exists(FINER_MAP), reason="the 20 m map check has not been run (scripts/finer_map_check.py)")
def test_the_20_m_mark_is_given_for_its_own_scenario_only_and_is_consistent():
    r = client.post("/api/robust-map", json=MAP).json()
    f = r.get("finer")
    assert f is not None
    assert f["agree"] + f["disagree"] == f["points_done"] == len(f["cells"]) and 0 < f["share_done"] <= 1
    robust = r["layers"]["robust"]
    for k, (m20, agrees) in f["cells"].items():
        m80 = robust[int(k)]
        assert m80 >= 0 or m80 == scatterfield.LOST          # only re-checked points are marked
        assert agrees == ((m20 >= 0) == (m80 >= 0))
    assert sum(1 for k, (m20, _) in f["cells"].items() if m20 == max(robust[int(k)], -1)) == f["equal_margins"]
    other = client.post("/api/robust-map", json={**MAP, "start": "2026-12-01T00:00:00Z"}).json()
    assert "finer" not in other


@needs_field
@needs_scatter
def test_the_station_rule_changes_no_point_of_the_default_map():
    """The 20 m mark was computed with the skyline-only Earth rule; the page applies the station rule. They may
    share the mark only because, for this scenario, the station rule changes no map point (measured here)."""
    a = client.post("/api/robust-map", json=MAP).json()
    b = client.post("/api/robust-map", json={**MAP, "earth_stations": True}).json()
    assert a["layers"]["robust"] == b["layers"]["robust"] and a["layers"]["single"] == b["layers"]["single"]
