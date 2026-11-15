"""Feature build (15 Nov 2026): how many of NASA's nine Artemis III regions must stay open, on the published landing
sites of Wueller et al. 2026.  An addition: the rest of the app keeps working for any site (DEEP_PASS_3.md)."""
import json
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from slipday import demstore, gazetteer, regions, sites, survival, why
from slipday.api import app
from slipday.ephem import cached_table, iso, parse_utc
from slipday.robust import mission_card

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
client = TestClient(app)
REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")
HAVE_80 = os.path.exists(os.path.join(REAL_DEM, "ldem_80s_80m_f32.npy")) and os.path.exists(os.path.join(REAL_DEM, "dems.json"))
needs_80 = pytest.mark.skipif(not HAVE_80, reason="the 80 m grid is not installed (run scripts/fetch_grid80.py)")
AV = regions.OUT_PATH
needs_av = pytest.mark.skipif(not os.path.exists(AV), reason="scripts/region_availability.py has not been run")
NASA_ORDER = ["Peak near Cabeus B", "Haworth", "Malapert Massif", "Mons Mouton Plateau", "Mons Mouton", "Nobile Rim 1",
              "Nobile Rim 2", "de Gerlache Rim 2", "Slater Plain"]


@pytest.fixture(scope="module", autouse=True)
def real_dem():
    old = os.environ.get("SLIPDAY_DEM_DIR")
    if HAVE_80:
        os.environ["SLIPDAY_DEM_DIR"] = REAL_DEM
        demstore.reload()
        sites._terrain_profile.cache_clear()
        why._cache.clear()
        survival._cache.clear()
    yield
    if old is not None:
        os.environ["SLIPDAY_DEM_DIR"] = old
    demstore.reload()
    sites._terrain_profile.cache_clear()


def test_published_sites_are_read_from_the_shapefile_with_their_meaning():
    d = json.load(open(regions.SITES_PATH, encoding="utf-8"))
    assert len(d["sites"]) == 130
    assert d["zip_sha256"] == "298e169afbea3c9bb157f20691af672495bfe391252b4acc798f59858ebc111f"
    nine = regions.load_sites()
    count = {c: sum(1 for s in nine if s["region"] == c) for c, _ in regions.REGIONS}
    assert count == {"PCB": 5, "HW": 11, "MMA": 5, "MMP": 11, "MMO": 10, "NR1": 9, "NR2": 9, "dGR2": 7, "SP": 11}
    assert len(nine) == 78 and [n for _, n in regions.REGIONS] == NASA_ORDER
    assert all(-90 < s["lat"] < -83 for s in nine)
    # columns whose meaning is not established are not carried
    assert set(d["sites"][0]) == {"name", "region", "lat", "lon", "sun_days", "sun_earth_days"}
    assert "10.1029/2025JE009434" in regions.CITATION and "CC BY 4.0" in regions.CITATION
    assert regions.MIDSUMMER[2027] == ("2027-10-15", "2027-11-14")


def test_greedy_and_exhaustive_coverage_on_a_small_case():
    # greedy takes the biggest region first and can miss the best pair
    o = np.array([[0, 0, 1, 1, 1, 1, 1, 1, 0, 0],
                  [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
                  [0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
                  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]], dtype=bool)
    assert regions.greedy(o) == [0, 1, 2, 3]
    assert regions.coverage(o, [0, 1]) == pytest.approx(0.8)
    best = regions.best_sets(o)
    assert best[1] == ([1, 2], pytest.approx(1.0))
    assert best[3][1] == pytest.approx(1.0) and regions.coverage(o, []) == 0.0
    assert list(regions.decode(regions.encode(np.array([0, 3, 11, 35])))) == [0, 3, 11, 35]


@needs_80
def test_vectorised_check_matches_the_card_landing_by_landing():
    s = [x for x in regions.load_sites() if x["name"] == "MMA_K2023"][0]
    mem, npts = regions.members_of(s["lat"], s["lon"], s["name"])
    assert npts == 13 and len(mem) == 15
    h0 = int(parse_utc("2027-10-10T00:00:00Z").timestamp())
    starts = np.arange(0, 20 * 24, 18)
    tab = cached_table(h0, int(starts[-1]) + regions.STAY_H + 1, 3600)
    f = regions.site_flags(mem, npts, tab, starts)
    got = []
    for j, h in enumerate(starts):
        m = mission_card(mem[0], iso(h0 + int(h) * 3600), regions.STAY_H, regions.NEED_EARTH_H, regions.STAY_DAYS,
                         regions.CRIT, regions.MASK_DEG, regions.MAST_M, regions.SCATTER_M, 1)
        got.append(m["verdict"] == "yes")
    assert list(f["yes"]) == got
    assert any(got) and not all(got)
    assert not (f["fragile"] & ~f["yes"]).any() and not (f["yes"] & ~f["yes_sun_only"]).any()


@needs_80
def test_a_custom_site_outside_every_artemis_region_still_gets_a_full_answer():
    lat, lon = -86.0, -160.0
    assert min(gazetteer._dist_km(lat, lon, x["lat"], x["lon"]) for x in regions.load_sites(nine_only=False)) > 50
    body = {"site": {"name": "typed point", "lat": lat, "lon": lon}, "landing": "2026-11-18T00:00:00Z",
            "need_sun_h": 240, "need_earth_h": 100, "window_days": 14, "earth_stations": True}
    m = client.post("/api/mission", json=body)
    assert m.status_code == 200
    m = m.json()
    assert m["verdict"] in ("yes", "no", "not sure") and m["sure"]["terrain"] and m["sure"]["points"] == 13
    assert len(m["days"]) >= 15 and m["sentences"]
    w = client.post("/api/windows", json=body).json()
    assert w["available"] and len(w["rows"]) == 4
    g = client.post("/api/slipgrid", json={"sites": [{"name": "typed point", "lat": lat, "lon": lon}], "start": "2026-11-18T00:00:00Z",
                                           "n_dates": 10}).status_code
    assert g == 200


@needs_av
def test_availability_counts_fragile_apart_and_never_as_open():
    d = json.load(open(AV, encoding="utf-8"))
    assert d["rule"]["step_hours"] == 6 and d["rule"]["stay_hours"] == 150 and d["rule"]["need_earth_h"] == 100
    assert d["rule"]["first"] == "2027-01-01T00:00:00Z" and d["rule"]["last"] == "2030-12-31T18:00:00Z" and d["n_times"] == 5844
    assert "more than one landing regions must be maintained" in d["nasa_quote"]
    for vk in ("main", "sun_only"):
        v = d[vk]
        assert [r["region"] for r in v["regions"]] == NASA_ORDER
        opens = []
        for r in v["regions"]:
            rob, frag = regions.decode(r["robust_sites"]), regions.decode(r["fragile_sites"])
            assert rob.size == frag.size == 5844 and rob.max() <= r["n_sites"]
            assert r["share_open"] == pytest.approx((rob > 0).mean(), abs=1e-4)
            assert r["share_fragile_only"] == pytest.approx(((rob == 0) & (frag > 0)).mean(), abs=1e-4)
            opens.append(rob > 0)
        opens = np.array(opens)
        cov = [c["coverage"] for c in v["curve"]]
        assert cov == sorted(cov) and cov[-1] == pytest.approx(opens.any(axis=0).mean(), abs=1e-4) == pytest.approx(v["any_open"], abs=1e-4)
        assert v["curve"][0]["added"] == NASA_ORDER[int(np.argmax(opens.mean(axis=1)))]
        for c in v["curve"]:
            assert c["best_coverage"] >= c["coverage"] - 1e-9
            assert c["coverage"] == pytest.approx(regions.coverage(opens, [NASA_ORDER.index(x) for x in c["regions"]]), abs=1e-4)
    # sunlight only can never be harder than sunlight plus Earth
    assert d["sun_only"]["any_open"] >= d["main"]["any_open"]
    assert d["sample_check"]["pairs"] == 48


@needs_av
def test_the_page_offers_the_regions_view_beside_the_rest():
    r = client.get("/api/region-availability").json()
    assert r["available"] and r["citation"] == regions.CITATION
    html = open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8").read()
    js = open(os.path.join(ROOT, "static", "app.js"), encoding="utf-8").read()
    assert 'id="regionsPanel"' in html and 'id="regionsGo"' in html and "Wueller et al. 2026" in html
    assert "function renderRegions" in js and "The regions are added one at a time" in js and "not real launch opportunities" in js
    assert "each region here is one illustrative point of ours" not in js


def test_artemis_panel_uses_the_published_sites():
    a = json.load(open(os.path.join(ROOT, "data", "validation", "artemis_regions.json"), encoding="utf-8"))
    nine = regions.load_sites()
    assert [x["region"] for x in a["anchors"]] == NASA_ORDER
    for x in a["anchors"]:
        assert x["sites"] == [s["name"] for s in nine if s["region"] == x["code"]]
    for blk in ("opening", "im1"):
        for w in a[blk]["rows"]:
            for g in w["regions"]:
                assert len(g["sites"]) == g["n_sites"]
                assert g["sites_yes"] == sum(1 for s in g["sites"] if s["best_hour"]["found"])
                assert g["best_hour"]["found"] == (g["sites_yes"] > 0)
                if g["sites_yes_not_fragile"]:
                    assert not g["best_hour"]["fragile"]


@needs_av
def test_the_figures_quoted_in_the_documents():
    d = json.load(open(AV, encoding="utf-8"))
    m, so = d["main"]["curve"], d["sun_only"]["curve"]
    assert [c["coverage"] for c in m] == [0.2805, 0.3679, 0.4011, 0.4261, 0.4362, 0.4399, 0.4405, 0.4406, 0.4406]
    assert [c["coverage"] for c in so][:3] == [0.4784, 0.7474, 0.911] and so[-1]["coverage"] == 0.9203
    assert [c["added"] for c in m][:3] == ["Nobile Rim 1", "Peak near Cabeus B", "Malapert Massif"]
    assert [c["added"] for c in so][:3] == ["Nobile Rim 1", "Peak near Cabeus B", "Slater Plain"]
    assert all(abs(c["best_coverage"] - c["coverage"]) < 1e-9 for c in m + so)          # greedy is the best set here
    assert d["sample_check"]["agree"] == d["sample_check"]["pairs"] == 48
    assert [d["cross_check"]["summary"][y]["within_1_day"] for y in ("2027", "2028", "2029", "2030")] == [40, 54, 60, 52]
    dr = d["drift"]
    assert all(y["midsummer_first"] == y["paper_first"] and y["midsummer_last"] == y["paper_last"] for y in dr["years"])
    assert dr["mean_shift_per_year_days"] == 18.4 and dr["expected_shift_days"] == 18.63
