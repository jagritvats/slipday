"""Deep pass 2 (15 Nov 2026): the LOLA team's 5 m site models against 80 m and 20 m, Artemis III candidate regions
as options in missed windows (now on the published sites of Wueller et al. 2026), and plain wording on what a judge sees.  Figures as in
DEEP_PASS_2.md."""
import json
import os
import re

import pytest
from fastapi.testclient import TestClient

from slipday import api, demstore, gazetteer, sites
from slipday.api import app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
client = TestClient(app)
REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")
HAVE_80 = os.path.exists(os.path.join(REAL_DEM, "ldem_80s_80m_f32.npy")) and os.path.exists(os.path.join(REAL_DEM, "dems.json"))
needs_80 = pytest.mark.skipif(not HAVE_80, reason="the 80 m grid is not installed (run scripts/fetch_grid80.py)")
G5 = os.path.join(ROOT, "data", "validation", "grids_5m.json")
ART = os.path.join(ROOT, "data", "validation", "artemis_regions.json")
NASA_REGIONS = ["Peak near Cabeus B", "Haworth", "Malapert Massif", "Mons Mouton Plateau", "Mons Mouton", "Nobile Rim 1",
                "Nobile Rim 2", "de Gerlache Rim 2", "Slater Plain"]


@pytest.fixture(scope="module", autouse=True)
def real_dem():
    old = os.environ.get("SLIPDAY_DEM_DIR")
    if HAVE_80:
        os.environ["SLIPDAY_DEM_DIR"] = REAL_DEM
        demstore.reload()
        sites._terrain_profile.cache_clear()
        api._finer_store.cache_clear()
        api._grid5_store.cache_clear()
    yield
    if old is not None:
        os.environ["SLIPDAY_DEM_DIR"] = old
    demstore.reload()
    sites._terrain_profile.cache_clear()


def test_three_grids_for_the_opening_example_and_c1():
    d = json.load(open(G5, encoding="utf-8"))
    rows = {(r["site"], r["grid"].split(",")[1].strip()): r for r in d["rows"]}
    for g in ("80 m/px", "20 m/px", "5 m/px"):
        r = rows[("robust_pick", g)]
        assert (r["verdict"], r["slip_margin_days"]) == ("yes", 8) and r["points_passing_by_day"][:10] == [13] * 9 + [0]
    assert (rows[("shackleton", "80 m/px")]["verdict"], rows[("shackleton", "80 m/px")]["slip_margin_days"]) == ("yes", 7)
    assert rows[("shackleton", "20 m/px")]["verdict"] == "not sure" and rows[("shackleton", "20 m/px")]["points_passing_by_day"][0] == 11
    assert rows[("shackleton", "5 m/px")]["verdict"] == "not sure" and rows[("shackleton", "5 m/px")]["points_passing_by_day"][0] == 12
    for site in ("robust_pick", "shackleton"):                # the 5 m model is placed right: heights agree to about 1 m
        hs = [rows[(site, g)]["site_height_m"] for g in ("80 m/px", "20 m/px", "5 m/px")]
        assert max(hs) - min(hs) < 2.0


@needs_80
def test_the_card_adds_the_5_m_answer_under_the_verdict():
    a = client.post("/api/mission", json={"site": {"id": "robust_pick"}, "landing": "2026-11-18T00:00:00Z"}).json()["finer_grid_check"]
    assert a["short"].endswith(" 5 m: the same.") and a["grid5"]["verdict"] == "yes" and a["grid5"]["slip_margin_days"] == 8
    c = client.post("/api/mission", json={"site": {"id": "shackleton"}, "landing": "2026-11-18T00:00:00Z"}).json()["finer_grid_check"]
    assert c["short"].endswith(" 5 m: Not sure (12 of 13).") and "Site01, connecting ridge" in c["text"]


def test_artemis_regions_are_nasas_nine_on_the_published_sites():
    # feature build: the illustrative anchors (one best-lit point per region, checked here before) are replaced
    # by the published candidate landing sites of Wueller et al. 2026; the anchor figures are kept in DEEP_PASS_2.md
    from slipday import regions
    d = json.load(open(ART, encoding="utf-8"))
    assert [a["region"] for a in d["anchors"]] == NASA_REGIONS
    assert "not NASA's landing sites" in d["anchor_rule"] and "Wueller et al. 2026" in d["anchor_rule"]
    pub = {s["name"]: s for s in regions.load_sites()}
    assert sum(a["n_sites"] for a in d["anchors"]) == 78 and all(n in pub for a in d["anchors"] for n in a["sites"])
    for a in d["anchors"]:
        assert all(pub[n]["region"] == a["code"] for n in a["sites"])
    assert [r["regions_yes_within_72h"] for r in d["opening"]["rows"]] == [8, 6, 5]
    assert [r["regions_yes_not_fragile"] for r in d["opening"]["rows"]] == [6, 5, 4]
    assert [r["regions_yes_within_72h"] for r in d["im1"]["rows"]] == [9, 8, 7]
    assert [r["regions_yes_at_window"] for r in d["opening"]["rows"]] == [5, 5, 3]
    assert [g["sites_yes"] for g in d["opening"]["rows"][0]["regions"]][-1] == 0          # Slater Plain: no site in December
    r = client.get("/api/artemis-regions").json()
    assert r["available"] and len(r["anchors"]) == 9


JARGON = re.compile(r"written rule|not verifiable|pre-regist|fixed before|fixed in advance|\bR1[0-4]?\b|\bR[2-9]\b|rule R\d|"
                    r"\bpass [2-5]\b|deep pass|follow-up pass|local pass|off-line|web-fetch|independent review|DevTools|site-years?\b|chosen greedily|speed-up check", re.I)


def _form_text():
    t = open(os.path.join(ROOT, "SUBMISSION_DRAFT.md"), encoding="utf-8").read()
    return t.split("END OF TEXT FOR THE FORM")[0]


def test_no_process_jargon_where_a_judge_reads():
    texts = {"form": _form_text(), "slides": open(os.path.join(ROOT, "demo", "SLIDES.md"), encoding="utf-8").read(),
             "storyboard captions": "\n".join(ln.split("|")[4] for ln in open(os.path.join(ROOT, "demo", "STORYBOARD.md"), encoding="utf-8")
                                              if re.match(r"\| \d+ \|", ln)),
             "index.html": open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8").read()}
    js = open(os.path.join(ROOT, "static", "app.js"), encoding="utf-8").read()
    texts["page strings"] = "\n".join(m.group(0) for m in re.finditer(r"'[^'\n]{20,}'", js))
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    texts["README (before Deploy)"] = readme.split("## Deploy")[0]
    for name, t in texts.items():
        hits = [m.group(0) for m in JARGON.finditer(t)]
        assert not hits, (name, hits[:5])
