"""Add-on: slip-tolerant atlas, 2027 to 2035.  The router is mounted in a small app here, so api.py is not touched."""
import json
import os
import re

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday import demstore, regions, sites
from slipday.addons import atlas, atlas_build
from slipday.ephem import cached_table, parse_utc

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")
HAVE_80 = os.path.exists(os.path.join(REAL_DEM, "ldem_80s_80m_f32.npy")) and os.path.exists(os.path.join(REAL_DEM, "dems.json"))
needs_80 = pytest.mark.skipif(not HAVE_80, reason="the 80 m grid is not installed (run scripts/fetch_grid80.py)")
BUILT = os.path.exists(atlas_build.JSON_PATH) and os.path.exists(atlas_build.FLAGS_PATH)
needs_atlas = pytest.mark.skipif(not BUILT, reason="the atlas has not been built (python -m slipday.addons.atlas_build)")
NASA_ORDER = [n for _, n in regions.REGIONS]

app = FastAPI()
app.include_router(atlas.router)
client = TestClient(app)


@pytest.fixture(scope="module")
def doc():
    return json.load(open(atlas_build.JSON_PATH, encoding="utf-8"))


@pytest.fixture(scope="module")
def flags():
    return atlas_build.load_flags()


@pytest.fixture(scope="module")
def grid():
    h0, starts, _ = atlas_build._grid()
    years = np.array([int(t) for t in np.datetime_as_string((h0 + starts * 3600).astype("datetime64[s]"), unit="Y")])
    months = np.array([int(t[5:7]) for t in np.datetime_as_string((h0 + starts * 3600).astype("datetime64[s]"), unit="M")])
    return h0, starts, years, months


@needs_atlas
def test_the_rule_is_the_existing_calendars_rule_over_nine_years(doc):
    r = doc["rule"]
    assert r["step_hours"] == regions.STEP_H == 6 and r["stay_hours"] == regions.STAY_H == 150
    assert r["need_earth_h"] == regions.NEED_EARTH_H == 100 and r["scatter_m"] == 100.0
    assert r["first"] == "2027-01-01T00:00:00Z" and r["last"] == "2035-12-31T18:00:00Z"
    assert r["n_times"] == 13148 == 4 * (365 * 9 + 2)          # two leap days in 2027-2035: 2028 and 2032
    assert doc["years"] == list(range(2027, 2036))
    assert doc["n_sites"] == {"published": 78, "curated": 14} and doc["members_per_site"] == [15]


@needs_atlas
def test_flags_file_holds_every_site_and_landing_time(flags):
    assert len(flags["keys"]) == 92 and flags["yes"].shape == (92, 13148)
    assert set(int(x) for x in flags["points"]) == {13}
    # a clear Yes is always also a sunlight-only Yes, and fragile is a kind of Yes
    assert not (flags["yes"] & ~flags["yes_sun_only"]).any()
    assert not (flags["fragile"] & ~flags["yes"]).any()
    assert not (flags["fragile_sun_only"] & ~flags["yes_sun_only"]).any()


@needs_atlas
def test_2027_to_2030_agree_with_the_existing_calendar_time_by_time(flags):
    """Recomputed here from the flags, not read from the atlas's own check."""
    old = regions.load()
    assert old is not None and old["n_times"] == 5844
    for variant in ("main", "sun_only"):
        _, _, robust, frag, _ = atlas_build.open_arrays(flags, variant)
        for r, reg in enumerate(old[variant]["regions"]):
            assert reg["region"] == NASA_ORDER[r]
            assert np.array_equal(regions.decode(reg["robust_sites"]), robust[r][:5844]), (variant, reg["region"])
            assert np.array_equal(regions.decode(reg["fragile_sites"]), frag[r][:5844]), (variant, reg["region"])


@needs_atlas
def test_stored_overlap_check_says_identical(doc):
    ov = doc["overlap"]
    assert ov["available"] and ov["n_times"] == 5844
    for v in ("main", "sun_only"):
        assert ov["variants"][v]["all_identical"]
        assert ov["variants"][v]["any_open_existing"] == ov["variants"][v]["any_open_atlas"]


@needs_atlas
def test_heat_strip_and_year_table_follow_from_the_flags(doc, flags, grid):
    _, _, years, months = grid
    for variant in ("main", "sun_only"):
        reg, cur, _, _, _ = atlas_build.open_arrays(flags, variant)
        v = doc["variants"][variant]
        assert [r["name"] for r in v["heat"]["regions"]] == NASA_ORDER
        for r in (0, 5, 8):
            for yi, y in ((0, 2027), (6, 2033), (8, 2035)):
                for m in (1, 7, 12):
                    sel = (years == y) & (months == m)
                    assert v["heat"]["regions"][r]["months"][yi][m - 1] == pytest.approx(reg[r, sel].mean(), abs=6e-4)
        assert v["heat"]["curated"][0]["months"][3][2] == pytest.approx(cur[0, (years == 2030) & (months == 3)].mean(), abs=6e-4)
        for yi, row in enumerate(v["per_year"]):
            o = reg[:, years == row["year"]]
            assert row["all_nine"] == pytest.approx(o.any(axis=0).mean(), abs=1e-4)
            shares = [b["share"] for b in row["best"]]
            assert shares == sorted(shares) and shares[-1] <= row["all_nine"] + 1e-9
            # the best set is found by trying every set: no pair beats the stored best pair
            best_pair = max(o[[i, j]].any(axis=0).mean() for i in range(9) for j in range(i + 1, 9))
            assert shares[1] == pytest.approx(best_pair, abs=1e-4)
            k = row["regions_to_match_all_nine"]
            all9 = o.any(axis=0).mean()
            assert atlas_build.best_set(o, k)[1] == pytest.approx(all9, abs=1e-12)
            if k > 1:
                assert atlas_build.best_set(o, k - 1)[1] < all9 - 1e-12
        ranked = sorted(v["per_year"], key=lambda r: (r["all_nine"], r["best"][2]["share"]))
        assert v["worst_year"] == ranked[0]["year"] and v["best_year"] == ranked[-1]["year"]
    # sunlight only can never be harder than sunlight plus Earth contact
    for a, b in zip(doc["variants"]["main"]["per_year"], doc["variants"]["sun_only"]["per_year"]):
        assert b["all_nine"] >= a["all_nine"]


def _made_up(period_days, month_days=None, phase=100.0, a=0.6, b=0.8, cut=0.2):
    """A made-up open / closed series on the atlas's landing times: a season of known length, and optionally a
    monthly pattern on top, as real sunlight has."""
    h0 = int(parse_utc("2027-01-01T00:00:00Z").timestamp())
    _, starts, _ = atlas_build._grid()
    t = starts / 24.0
    x = a * np.cos(2 * np.pi * (t - phase) / period_days)
    if month_days:
        x = x + b * np.cos(2 * np.pi * t / month_days)
    return x > cut, h0 + starts * 3600


@pytest.mark.parametrize("period", [330.0, 346.62, 360.0])
@pytest.mark.parametrize("month", [None, 29.530589, 27.2122])
def test_season_drift_recovers_a_known_season_length(period, month):
    """A 29.53-day pattern (sunlight) drops out exactly; a 27.21-day one (the Earth's nodding, which the monthly
    pieces do not cancel) leaves an error of up to about 2 days (measured: 1.1 and 1.6 days at 330 and 360)."""
    x, tu = _made_up(period, month)
    d = atlas_build.season_drift(x, tu)
    tol = 2.0 if month == 27.2122 else 0.6
    assert d["season_period_days"] == pytest.approx(period, abs=tol)
    assert d["earlier_per_year_days"] == pytest.approx(365.25 - period, abs=tol)


def test_first_try_drift_is_fooled_by_the_monthly_pattern():
    """Why the first measure was replaced: with a monthly pattern on top of an 18.6-day season drift it reads the
    monthly pattern's drift (about 11 to 12 days) instead."""
    x, tu = _made_up(346.62)
    assert atlas_build.atlas_drift(x, tu)["mean_earlier_per_year_days"] == pytest.approx(18.6, abs=0.5)
    x, tu = _made_up(346.62, 29.530589)
    assert atlas_build.atlas_drift(x, tu)["mean_earlier_per_year_days"] < 14


@needs_atlas
def test_drift_is_measured_and_close_to_the_expected_value(doc):
    sd = doc["subsolar_drift"]
    assert sd["expected_days"] == 18.63 and len(sd["years"]) == 9
    assert sd["same_fit_as_atlas"]["season_period_days"] == pytest.approx(346.62, abs=0.6)
    for v in ("main", "sun_only"):
        d = doc["variants"][v]
        assert d["season_drift"]["months_used"] == 111 and d["first_try_drift"]["measures_the_season"] is False
        assert len(d["season_drift_by_region"]) == 9


@needs_80
@needs_atlas
def test_one_site_rejudged_from_scratch_in_2033_matches_the_stored_flags(flags):
    old = os.environ.get("SLIPDAY_DEM_DIR")
    # rejudge on the stack the atlas was built on: the live one (5 m, the full 20 m mosaic, 80 m) when installed
    live = os.path.join(ROOT, "data", "dem_live")
    os.environ["SLIPDAY_DEM_DIR"] = live if os.path.exists(os.path.join(live, "dems.json")) else REAL_DEM
    demstore.reload()
    sites._terrain_profile.cache_clear()
    try:
        s = [x for x in regions.load_sites() if x["name"] == "MMA_K2023"][0]
        mem, npts = regions.members_of(s["lat"], s["lon"], s["name"])
        h0, starts, _ = atlas_build._grid()
        a = int((parse_utc("2033-10-01T00:00:00Z").timestamp() - h0) // 3600) // 6
        sl = starts[a:a + 4 * 40]
        h1 = h0 + int(sl[0]) * 3600
        tab = cached_table(h1, int(sl[-1] - sl[0]) + regions.STAY_H + 1, 3600)
        f = regions.site_flags(mem, npts, tab, sl - sl[0])
        i = flags["keys"].index("w:MMA_K2023")
        assert np.array_equal(f["yes"], flags["yes"][i, a:a + 160])
        assert np.array_equal(f["yes_sun_only"], flags["yes_sun_only"][i, a:a + 160])
        assert f["yes_sun_only"].any()
    finally:
        if old is not None:
            os.environ["SLIPDAY_DEM_DIR"] = old
        demstore.reload()
        sites._terrain_profile.cache_clear()


@needs_atlas
def test_router_endpoints():
    s = client.get("/api/addons/atlas").json()
    assert s["available"] and s["rule"]["step_hours"] == 6 and s["years"][0] == 2027 and s["years"][-1] == 2035
    assert set(s["variants"]) == {"main", "sun_only"} and len(s["variants"]["main"]["per_year"]) == 9
    h = client.get("/api/addons/atlas/heat", params={"variant": "sun_only"}).json()
    assert h["variant"] == "sun_only" and len(h["regions"]) == 9 and len(h["regions"][0]["months"]) == 9
    assert all(len(m) == 12 for m in h["regions"][0]["months"]) and len(h["curated"]) == 14
    assert client.get("/api/addons/atlas/heat", params={"variant": "other"}).status_code == 422
    y = client.get("/api/addons/atlas/year/2031").json()
    assert y["year"] == 2031 and y["main"]["year"] == 2031 and len(y["main"]["region_share"]) == 9
    assert client.get("/api/addons/atlas/year/2040").status_code == 404


def test_router_says_so_when_the_atlas_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(atlas, "JSON_PATH", str(tmp_path / "none.json"))
    for url in ("/api/addons/atlas", "/api/addons/atlas/heat", "/api/addons/atlas/year/2030"):
        r = client.get(url).json()
        assert r["available"] is False and "atlas_build" in r["reason"]


def test_front_end_module_is_self_contained_and_states_its_limits():
    js = open(os.path.join(ROOT, "static", "addons", "atlas.js"), encoding="utf-8").read()
    assert "'addon-atlas'" in js and "/api/addons/atlas" in js
    assert not re.search(r"https?://", js), "no external requests"
    assert "not real launch opportunities" in js and "every 6 hours" in js
    assert "example figure" in js and "Sunlight only" in js and "18.6-year cycle" in js
    assert "@media (max-width:480px)" in js


def test_builder_never_writes_the_entrys_skyline_cache():
    import inspect
    src = inspect.getsource(atlas_build.main)
    assert "gettempdir()" in src and "SLIPDAY_HORIZON_CACHE" in src
    assert atlas_build.OUT_DIR.endswith(os.path.join("data", "addons", "atlas"))
