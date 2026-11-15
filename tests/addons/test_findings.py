"""The "What we found" panel: stored findings, the endpoint and the front-end module.

The stored file is built by scripts/addons/build_findings.py.  These tests check it against independent sources where
they exist: the earlier stored 20 m run (data/validation/finer_map_dates.json), the existing region calendar
(data/validation/region_availability.json) and a fresh count from the atlas flags.
"""
from __future__ import annotations

import json
import os
import re
from itertools import combinations

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday.addons import findings as fmod

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JS = os.path.join(ROOT, "static", "addons", "findings.js")
need = pytest.mark.skipif(not os.path.exists(fmod.JSON_PATH), reason="findings not built")


@pytest.fixture(scope="module")
def doc():
    with open(fmod.JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(fmod.router)
    return TestClient(app)


@need
def test_endpoint_serves_three_findings_with_charts_and_caveats(client):
    r = client.get("/api/addons/findings")
    assert r.status_code == 200
    d = r.json()
    assert d["available"] is True
    ids = [f["id"] for f in d["findings"]]
    assert ids == ["coarse_terrain_optimistic", "regions_to_keep_open", "checks"]
    for f in d["findings"]:
        assert f["headline"] and f["charts"] and f["numbers"] and f["caveats"]
    assert d["findings"][2]["kind"] == "check"
    assert any("illustrative" in c for c in d["findings"][1]["caveats"])


def test_endpoint_without_data_says_so(client, monkeypatch, tmp_path):
    monkeypatch.setattr(fmod, "JSON_PATH", str(tmp_path / "missing.json"))
    d = client.get("/api/addons/findings").json()
    assert d["available"] is False and "build_findings" in d["reason"]


@need
def test_20m_check_matches_the_earlier_stored_run_date_by_date(doc):
    t = doc["coarse_is_optimistic"]["twenty_m"]
    if not t.get("available"):
        pytest.skip("20 m skylines not installed")
    old = json.load(open(os.path.join(ROOT, "data", "validation", "finer_map_dates.json"), encoding="utf-8"))
    assert len(t["dates"]) == 14
    for new, o in zip(t["dates"], old["dates"]):
        assert new["start"] == o["start"][:10]
        assert new["points"] == o["points"]
        assert new["coarse_yes_fine_no"] == o["keeps_on_80m_loses_on_20m"]
        assert new["coarse_no_fine_yes"] == o["loses_on_80m_keeps_on_20m"]
    tot = t["totals"]
    assert tot["agree"] + tot["coarse_yes_fine_no"] + tot["coarse_no_fine_yes"] == tot["points"]
    assert t["optimistic_share_of_disagreements"] > 0.95
    # the map carries every re-checked point once, with its disagreements
    rows = t["map_points"]["rows"]
    assert sum(r[3] for r in rows) == tot["coarse_yes_fine_no"]
    assert sum(r[4] for r in rows) == tot["coarse_no_fine_yes"]
    assert sum(r[2] for r in rows) == tot["points"]


@need
def test_ridge_darkness_fine_grid_close_to_published_coarse_far(doc):
    r = doc["coarse_is_optimistic"]["ridge"]
    if not r.get("available"):
        pytest.skip("ridge run not stored")
    c, f = r["stacks"]["coarse_80m"]["longest_dark_h"], r["stacks"]["fine_20m"]["longest_dark_h"]
    assert c > f
    assert abs(f - r["published_h"]) < abs(c - r["published_h"])


@need
def test_five_metre_models_cover_two_sites(doc):
    assert doc["coarse_is_optimistic"]["five_m"]["count"] == 2


@need
def test_region_curve_agrees_with_the_existing_calendar_and_a_fresh_count(doc):
    reg = doc["regions"]
    cal = json.load(open(os.path.join(ROOT, "data", "validation", "region_availability.json"), encoding="utf-8"))
    for var, key in (("earth_need", "main"), ("sunlight_only", "sun_only")):
        ours = reg["variants"][var]["2027-2030"]["curve"]
        theirs = cal[key]["curve"]
        for a, b in zip(ours, theirs):
            assert a["share"] == pytest.approx(b["best_coverage"], abs=1e-4)
        for period in ("2027-2030", "2027-2035"):
            sh = [c["share"] for c in reg["variants"][var][period]["curve"]]
            assert sh == sorted(sh) and len(sh) == 9 and 0 < sh[0] < sh[-1] <= 1
    # fresh count of the best single region, 2027 to 2035, straight from the flags
    from slipday import regions
    z = np.load(os.path.join(ROOT, "data", "addons", "atlas", "atlas_flags.npz"))
    keys = [str(k) for k in z["keys"]]
    n = reg["n_times"]["2027-2035"]
    ok = np.unpackbits(z["yes"], axis=1)[:, :n].astype(bool) & ~np.unpackbits(z["fragile"], axis=1)[:, :n].astype(bool)
    site_region = {s["name"]: s["region"] for s in regions.load_sites()}
    best = max(ok[[i for i, k in enumerate(keys) if k.startswith("w:") and site_region.get(k[2:]) == code]].any(axis=0).mean()
               for code, _ in regions.REGIONS)
    assert reg["variants"]["earth_need"]["2027-2035"]["curve"][0]["share"] == pytest.approx(best, abs=1e-4)


@need
def test_checks_are_tight(doc):
    ch = doc["checks"]
    assert abs(ch["season_drift"]["sine_fit_earlier_per_year_days"] - ch["season_drift"]["expected_earlier_per_year_days"]) < 0.2
    assert ch["horizons"]["rows"] > 100 and ch["horizons"]["max_abs_el_deg"] < 1e-3 and ch["horizons"]["max_abs_az_deg"] < 1e-3
    for m in ch["lola_earth_maps"]["maps"]:
        assert m["correlation"] > 0.99 and m["mean_abs_diff_pts"] < 1.5


def test_front_end_module_is_self_contained():
    src = open(JS, encoding="utf-8").read()
    assert 'getElementById("addon-findings")' in src
    assert "/api/addons/findings" in src
    assert "var(--" in src or "getPropertyValue" in src
    assert not re.search(r"<script|https?://(?!www\.w3\.org/2000/svg)", src)
