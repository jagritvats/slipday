"""Add-on: upcoming missions board, who this helps, open data (ADDON_impact.md)."""
import csv
import hashlib
import html
import io
import json
import os
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday import demstore, regions, sites
from slipday.addons import impact, impact_build

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = impact_build.SRC_DIR
REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")
HAVE_80 = os.path.exists(os.path.join(REAL_DEM, "ldem_80s_80m_f32.npy")) and os.path.exists(os.path.join(REAL_DEM, "dems.json"))
needs_80 = pytest.mark.skipif(not HAVE_80, reason="the 80 m grid is not installed (run scripts/fetch_grid80.py)")
BUILT = os.path.exists(impact.JSON_PATH)
needs_board = pytest.mark.skipif(not BUILT, reason="the board has not been built (python -m slipday.addons.impact_build)")
MISSIONS_JS = os.path.join(ROOT, "static", "addons", "missions.js")

app = FastAPI()
app.include_router(impact.router)
client = TestClient(app)


def page_text(fname):
    path = os.path.normpath(os.path.join(SRC_DIR, fname))
    if path.endswith(".docx"):
        import zipfile
        t = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t))
    t = open(path, encoding="utf-8", errors="replace").read()
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", t)))


@pytest.fixture(scope="module")
def doc():
    return json.load(open(impact.JSON_PATH, encoding="utf-8"))


def test_router_is_registered_in_the_app():
    from slipday import api
    paths = set(api.app.openapi()["paths"])
    assert "/api/addons/impact" in paths and "/api/addons/impact/missions.csv" in paths


@needs_board
def test_board_lists_the_published_missions(doc):
    ids = [m["id"] for m in doc["missions"]]
    assert ids == ["griffin1", "im4", "viper", "artemis4"]
    r = client.get("/api/addons/impact").json()
    assert r["available"] and len(r["missions"]) == 4 and r["who"] and r["open_data"]


@needs_board
def test_every_quote_is_in_the_saved_first_hand_page(doc):
    srcs = impact_build.SRC
    for m in doc["missions"]:
        for q in m["quotes"]:
            assert q["text"] in page_text(srcs[q["source"]][2]), (m["id"], q["text"])
    for x, raw in zip(doc["listed_without_a_point"], impact_build.LISTED):
        if raw["quote"][1]:
            assert raw["quote"][1] in page_text(impact_build.SRC[raw["quote"][0]][2]), x["name"]


@needs_board
def test_source_hashes_match_the_files_and_the_download_log(doc):
    log = {}
    for line in open(os.path.join(SRC_DIR, "DOWNLOADS.tsv"), encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 5 and p[2] == "200":
            log[p[0]] = (p[1], p[4])
    for line in open(os.path.join(ROOT, "data", "reference", "DOWNLOADS.tsv"), encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 4 and p[0].startswith("sources/"):
            log[p[0].split("/", 1)[1]] = (p[3].split(" ")[0], p[2])
    for k, s in doc["sources"].items():
        fname = os.path.basename(s["file"])
        h = hashlib.sha256(open(os.path.join(ROOT, s["file"]), "rb").read()).hexdigest()
        assert s["sha256"] == h
        assert log[fname] == (s["url"], h), fname


@needs_board
def test_artemis_iii_is_left_out_because_it_no_longer_lands(doc):
    a3 = [x for x in doc["listed_without_a_point"] if x["name"] == "Artemis III"][0]
    assert "low Earth orbit" in a3["quote"] and "No landing" in a3["why"]


@needs_board
def test_counts_and_shares_are_consistent(doc):
    for m in doc["missions"]:
        assert 0 <= m["good_times"] <= m["landing_times"]
        for k in ("slip_week", "slip_month"):
            s = m[k]
            assert s["of"] == m["good_times"] and 0 <= s["still_yes"] <= s["of"]
            assert s["lost"]["times"] == s["of"] - s["still_yes"]
            assert 0 <= s["lost"]["any_other_open"] <= s["lost"]["times"]
        assert m["months_with_a_good_time"] == len(m["months"]) <= m["months_in_span"]
        assert m["home_sites"] == len(m["per_site"])
        assert "Approximate" in m["label"]


@needs_board
def test_the_card_agrees_with_the_board_on_every_month_shown(doc):
    """The first good time each month is found by the vectorised check and then re-run through mission_card."""
    for m in doc["missions"]:
        for r in m["months"]:
            assert r["agrees_with_card"] and r["verdict"] == "yes", (m["id"], r["month"], r["verdict"])
            assert r["landing_utc"][:7] == r["month"]


@needs_board
def test_mission_endpoint_and_404(doc):
    r = client.get("/api/addons/impact/mission/viper").json()
    assert r["available"] and r["long_days"] == 100
    assert client.get("/api/addons/impact/mission/nothing").status_code == 404


@needs_board
def test_csv_download_has_one_row_per_mission_month(doc):
    r = client.get("/api/addons/impact/missions.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == impact.CSV_COLS
    assert len(rows) - 1 == sum(len(m["months"]) for m in doc["missions"])
    assert client.get("/api/addons/impact/missions.json").status_code == 200


def test_who_this_helps_points_at_real_places_on_the_page():
    page = open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8").read()
    js = open(MISSIONS_JS, encoding="utf-8").read()
    w = client.get("/api/addons/impact/who").json()["who"]
    assert len(w) >= 4
    for line in w:
        assert line["where"]
        for x in line["where"]:
            assert f'id="{x["id"]}"' in page or f"'{x['id']}'" in js or f'id="{x["id"]}"' in js or x["id"] in js, x["id"]
    text = json.dumps(w)
    assert "more than one landing regions must be maintained" in text          # the LPSC 2026 line
    assert "Nobody has tested it with a real screen reader yet" in text


def test_open_data_endpoints_exist_in_the_app():
    from slipday import api
    paths = set(api.app.openapi()["paths"])
    od = client.get("/api/addons/impact/open-data").json()
    for e in od["endpoints"]:
        assert e["path"] in paths, e["path"]
    for d in od["downloads"]:
        if d["path"].startswith("/api/"):
            assert d["path"] in paths, d["path"]


def test_no_mention_of_rivals_or_competition():
    files = [MISSIONS_JS, os.path.join(ROOT, "slipday", "addons", "impact.py"),
             os.path.join(ROOT, "slipday", "addons", "impact_build.py")]
    if BUILT:
        files.append(impact.JSON_PATH)
    for f in files:
        t = open(f, encoding="utf-8").read().lower()
        for word in ("rival", "competitor", "competition", "other entries", "hackathon"):
            assert word not in t, (f, word)


def test_missing_board_is_reported_not_crashed(monkeypatch, tmp_path):
    monkeypatch.setattr(impact, "JSON_PATH", str(tmp_path / "none.json"))
    r = client.get("/api/addons/impact").json()
    assert r["available"] is False and r["who"]
    assert client.get("/api/addons/impact/missions.csv").status_code == 404


@needs_80
@needs_board
def test_one_month_rejudged_from_scratch_matches(doc):
    old = os.environ.get("SLIPDAY_DEM_DIR")
    # rejudge on the stack the board was built on: the live one (5 m, the full 20 m mosaic, 80 m) when installed
    live = os.path.join(ROOT, "data", "dem_live")
    os.environ["SLIPDAY_DEM_DIR"] = live if os.path.exists(os.path.join(live, "dems.json")) else REAL_DEM
    demstore.reload()
    sites._terrain_profile.cache_clear()
    try:
        m = [x for x in doc["missions"] if x["id"] == "im4"][0]
        r = m["months"][0]
        rec = [s for s in regions.load_sites() if s["name"] == r["site"]][0]
        chk = impact_build.card_check(rec, r["landing_utc"], impact_build.CARD)
        assert chk["verdict"] == r["verdict"] and chk["slip_margin_days"] == r["slip_margin_days"]
        assert chk["week_later"]["verdict"] == r["week_later"]["verdict"]
        assert chk["month_later"]["verdict"] == r["month_later"]["verdict"]
    finally:
        if old is not None:
            os.environ["SLIPDAY_DEM_DIR"] = old
        demstore.reload()
        sites._terrain_profile.cache_clear()
