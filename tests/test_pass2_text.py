"""Second local pass (14 Nov 2026): what the validation panel and the judged documents say.

Pins down the text fixes asked for by the local review:
  bug 5   the panel no longer says the LOLA team's Earth maps "could not be obtained"
  bug 7   the Earth tile names the rule it checks and the stricter rule the mission card uses
  bug 8   both Earth figures are served (every point, and without the points that agree trivially),
          and the ridge-pixel Sun figure is a range over seeds, not one draw
  bug 3   wherever a replay's "Yes" is quoted, the other published figure is beside it
  bug 4   the slides quote the official challenge text, not a line that is not in it
  bug 6   the README describes Slipday on its own terms, with no comparison to other projects
  bug 10  the note for the team is fenced off from the text for the form; AI use is a marked placeholder
"""
import calendar
import json
import os
import re
import shutil
import subprocess

import numpy as np
import pytest
from fastapi.testclient import TestClient

from slipday import refmaps, replay
from slipday.api import app

client = TestClient(app)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "data", "validation", "terrain_validation.json")
MORE = os.path.join(ROOT, "data", "validation", "more_validation.json")
_MAPS = [os.path.join(ROOT, "data", "reference"),
         os.path.join(os.path.dirname(os.path.dirname(ROOT)), "realdata", "lunar", "data")]
REAL = os.environ.get("SLIPDAY_REALDATA_DIR") or next(
    (d for d in _MAPS if os.path.exists(os.path.join(d, "AVGVISIB_85S_060M_201608_EARTH.IMG"))), _MAPS[0])


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
        return fh.read()


def _validation():
    v = client.get("/api/terrain/validation").json()
    if not v.get("available"):
        pytest.skip("validation results not stored on this installation")
    return v


def _earth_tile(v):
    tile = [h for h in v["headline"] if h.get("id") == "more-e"][0]
    if tile.get("pending"):
        pytest.skip("the Earth maps have not been attached on this installation (LOCAL_PASS.md step 2)")
    return tile


# ------------------------------------------------------------------ bug 5: the stale sentence

def test_panel_no_longer_says_the_earth_maps_could_not_be_obtained():
    v = _validation()
    text = json.dumps(v)
    assert "could not be obtained" not in text
    assert "Earth maps could not be fetched" not in text or _earth_tile_is_pending(v)
    # the table that carried the sentence now points at the check that uses the maps
    bryant = [t for t in v["tables"] if "Bryant 2009" in t["title"]][0]
    assert "LOLA team's own Earth-visibility maps instead" in bryant["note"]
    # and a re-run of the generating script does not bring it back
    assert "Earth-visibility maps could not be obtained" not in _read(os.path.join("scripts", "validate_terrain.py"))


def _earth_tile_is_pending(v):
    return any(h.get("id") == "more-e" and h.get("pending") for h in v["headline"])


# ------------------------------------------------------------------ bug 7: which rule each number uses

def test_every_validation_tile_names_its_rule():
    v = _validation()
    for h in v["headline"]:
        if h.get("pending"):
            continue
        assert "Rule: " in h["s"], h["k"]
    sun = v["headline"][0]
    assert "any part of the solar disc" in sun["s"] and "half the disc" in sun["s"]


def test_earth_tile_names_its_rule_and_the_cards_stricter_one():
    v = _validation()
    tile = _earth_tile(v)
    assert "any part of the Earth's disc" in tile["s"] and "the rule the map's own label states" in tile["s"]
    assert "mission card" in tile["s"] and "Earth's centre" in tile["s"] and "stricter" in tile["s"]
    m = re.search(r"reads (\d+\.\d) points lower than this map at the same points(?: \((\d+\.\d) without those (\d+)\))?", tile["s"])
    assert m, tile["s"]
    # the figure on the tile is the centre-rule row of the table underneath, not a new number
    table = [t for t in v["tables"] if t.get("id") == "more-e"][0]
    first_map = table["rows"][0][0]
    centre = [r for r in table["rows"] if r[0] == first_map and r[1].startswith("earth centre")][0]
    assert centre[5] < 0 and m.group(1) == f"{abs(centre[5]):.1f}"


# ------------------------------------------------------------------ bug 8: both Earth figures, and the ridge range

def test_both_earth_figures_are_served_and_agree_with_the_stored_points():
    v = _validation()
    tile = _earth_tile(v)
    t2 = [t for t in v["tables"] if t.get("id") == "more-e2"]
    assert t2, "the with/without table is missing"
    rows = t2[0]["rows"]
    with open(MORE) as fh:
        more = json.load(fh)
    for m in more["e"]["maps"]:
        ref = m["reference"]
        mine = [r for r in rows if r[0] == m["map"] and r[5].startswith("earth any part")]
        every, without = [r for r in mine if r[3] == 0 and r[4] == 0][0], [r for r in mine if r[3] + r[4] > 0][0]
        assert every[2] == ref["points_inside_map"] and every[7] == ref["by_rule"]["earth_any_part"]["mae_pts"]
        assert without[3] == ref["both_exactly_zero"] and without[4] == ref["both_exactly_one"]
        assert without[2] == every[2] - without[3] - without[4]
        assert without[7] == ref["without_trivial"]["earth_any_part"]["mae_pts"]
        # leaving out points that agree exactly can only raise the mean difference
        assert without[7] >= every[7]
    r0 = more["e"]["maps"][0]["reference"]
    assert f"±{r0['without_trivial']['earth_any_part']['mae_pts']} pts at {r0['without_trivial']['earth_any_part']['n']} points" in tile["s"]
    assert f"{r0['both_exactly_zero']} points where the map and the model are both exactly zero" in tile["s"]
    assert f"(±{r0['by_rule']['earth_any_part']['mae_pts']} pts to two decimals)" in tile["s"]


def test_the_without_figure_can_be_recomputed_from_the_map_itself():
    """Own arithmetic on the stored per-point model values and the LOLA team's file: not the script's helper."""
    path = os.path.join(REAL, "AVGVISIB_85S_060M_201608_EARTH.IMG")
    if not os.path.exists(path) or not os.path.exists(MORE):
        pytest.skip("LOLA Earth map or stored per-point values not available")
    with open(MORE) as fh:
        m = json.load(fh)["e"]["maps"][0]
    if not m.get("reference") or "without_trivial" not in m["reference"]:
        pytest.skip("the Earth check was stored before the with/without split")
    pts = np.array(m["points"])
    ref = refmaps.load(path).nearest(pts[:, 0], pts[:, 1])
    model = pts[:, 3]                                         # any part of the Earth's disc
    both_zero = (ref == 0.0) & (model == 0.0)
    d = np.abs(model - ref)
    assert int(both_zero.sum()) == m["reference"]["both_exactly_zero"]
    assert round(float(d.mean()) * 100, 2) == m["reference"]["by_rule"]["earth_any_part"]["mae_pts"]
    assert round(float(d[~both_zero].mean()) * 100, 2) == m["reference"]["without_trivial"]["earth_any_part"]["mae_pts"]
    assert 0 < both_zero.sum() < len(ref)


def test_ridge_sun_figure_is_a_range_over_seeds():
    v = _validation()
    with open(MORE) as fh:
        more = json.load(fh)
    runs = (more.get("s") or {}).get("runs") or []
    if not runs:
        pytest.skip("the extra ridge seeds have not been run on this installation (validate_more.py --only s)")
    tile = [h for h in v["headline"] if h.get("id") == "more-a"][0]
    maes = [more["a"]["mae_pts"]] + [r["sun_any_part"]["mae_pts"] for r in runs]
    cors = [more["a"]["correlation"]] + [r["sun_any_part"]["correlation"] for r in runs]
    assert tile["v"] == f"±{min(maes):.2f} to {max(maes):.2f} pts"
    assert f"correlation {min(cors):.2f} to {max(cors):.2f}" in tile["s"]
    assert f"{len(maes)} random draws" in tile["s"]
    # the seeds follow a rule that does not look at results: the original and the integers after it
    seeds = [more["a"]["seed"]] + [r["seed"] for r in runs]
    assert seeds == list(range(seeds[0], seeds[0] + len(seeds))) and len(seeds) >= 3
    table = [t for t in v["tables"] if t.get("id") == "more-s"][0]
    assert [r[0] for r in table["rows"]] == seeds and [r[2] for r in table["rows"]] == maes
    assert all(r[1] == 60 for r in table["rows"])


# ------------------------------------------------------------------ bug 3: both figures wherever a replay is quoted

def test_replays_give_the_other_published_figure_wherever_the_yes_is_quoted():
    by = {m["id"]: m for m in replay.MISSIONS}
    assert "10 days" in by["im1"]["need_note"] and "No" in by["im1"]["need_note"]
    assert "336" in by["chandrayaan3"]["need_note"] and "No" in by["chandrayaan3"]["need_note"]
    assert "not proof of the model" in replay.NOTE and "10" in replay.NOTE
    story = _read(os.path.join("demo", "STORYBOARD.md"))
    for caption in [ln.split("|")[4] for ln in story.splitlines() if re.match(r"\| \d+ \|", ln)]:
        if "IM-1" in caption:                       # a subtitle that quotes the Yes carries the other figure too
            assert re.search(r"ten days|10 days", caption) and re.search(r"would not|No\b", caption), caption
    for name in ("SUBMISSION_DRAFT.md", "README.md", os.path.join("demo", "SLIDES.md")):
        text = " ".join(_read(name).split())
        assert re.search(r"ten days[^.]{0,120}(No|would not)", text), name          # IM-1's other figure
        assert re.search(r"14 days[^.]{0,60}would give No", text), name             # Chandrayaan-3's other figure
        assert "not a confirmation of the model" in text, name


# ------------------------------------------------------------------ bug 4: the official words

def test_slides_quote_the_official_challenge_text():
    slides = _read(os.path.join("demo", "SLIDES.md"))
    flat = " ".join(slides.split())
    assert "fast re-planning after schedule slips" not in flat
    assert ("Hardware development challenges, launch delays, or other factors often force mission planners to "
            "reconsider their original landing date and location.") in flat
    assert ("Display the positions of the Sun and Earth relative to the horizon at a selected landing site on a "
            "chosen date.") in flat
    assert "[TEAM NAME]" in slides and "[MEMBER NAMES]" in slides
    assert len(re.findall(r"^## \d+\. ", slides, flags=re.M)) <= 7


# ------------------------------------------------------------------ bug 6: no claim about what others lack

def test_readme_states_what_slipday_does_on_its_own_terms():
    # the comparison with other projects was removed on purpose: the README says what Slipday does and does not do
    text = " ".join(_read("README.md").split())
    for word in ("found them in none", "other entries", "public entries", "not matched", "partly matched", "competitor",
                 "competition", "rival", "repositories for the challenge"):
        assert word.lower() not in text.lower(), word
    for feature in ("slip margin", "Three-state verdict", "slip-margin map", "terrain resolutions", "landing circles"):
        assert feature.lower() in text.lower(), feature
    assert "## What is on the page" in _read("README.md") and "LIMITATIONS.md" in text


# ------------------------------------------------------------------ bug 10 and the storyboard limits

def test_draft_fences_off_the_note_for_the_team_and_marks_the_ai_statement():
    draft = _read("SUBMISSION_DRAFT.md")
    assert draft.count("END OF TEXT FOR THE FORM") == 2            # once in the instructions, once as the marker
    form, notes = draft.rsplit("END OF TEXT FOR THE FORM", 1)
    assert "NOT FOR PASTING" in notes and "Note for the team" not in form.split("## Project name", 1)[1]
    assert "docker build" not in form and "which grid the public link must serve" not in form.lower()
    assert "[PARTICIPANT TO WRITE: statement of AI use]" in form
    assert "[PARTICIPANT TO WRITE: statement of AI use]" in _read("README.md")


def test_storyboard_is_29_seconds_names_the_challenge_and_reads_one_validation_number():
    """Rules, not today's wording, so the frames can be re-cut: 29 s or less in all, the challenge name in
    the first subtitle, the team placeholder in the last, and a validation subtitle that reads one number."""
    story = _read(os.path.join("demo", "STORYBOARD.md"))
    rows = [ln for ln in story.splitlines() if re.match(r"\| \d+ \|", ln)]
    assert rows, "no frame rows found"
    ends = [int(re.search(r"\| \d+-(\d+) s \|", ln).group(1)) for ln in rows]
    assert ends == sorted(ends) and ends[-1] <= 29
    captions = [ln.split("|")[4] for ln in rows]
    assert "Lunar Landing Site Navigator" in captions[0]
    assert "[TEAM NAME]" in captions[-1]
    for caption in captions:
        if "Checked against" in caption:            # the validation subtitle: one number in seven seconds, not three
            assert len(re.findall(r"\d+(?:[.,]\d+)?", caption)) <= 1, caption


# ------------------------------------------------------------------ lunar against terrestrial conditions (/api/contrast)

def _utc(*a):
    return calendar.timegm(a)


def test_earth_sun_formula_against_textbook_cases():
    from slipday.contrast import earth_sun_elevation
    # December solstice at the Earth's south pole: the Sun stands at the obliquity, 23.44 degrees
    assert abs(float(earth_sun_elevation(_utc(2026, 12, 21, 12, 0, 0), -90.0)) - 23.44) < 0.05
    # local noon at 45 N on the two solstices: 90 - 45 +/- 23.44
    assert abs(float(earth_sun_elevation(_utc(2026, 6, 21, 12, 2, 0), 45.0)) - 68.44) < 0.1
    assert abs(float(earth_sun_elevation(_utc(2026, 12, 21, 11, 58, 0), 45.0)) - 21.56) < 0.1
    # March equinox at the equator near local noon: almost overhead
    assert float(earth_sun_elevation(_utc(2026, 3, 20, 12, 7, 0), 0.0)) > 89.0


def test_contrast_puts_a_lunar_site_beside_two_places_on_earth_and_says_which_is_which():
    r = client.get("/api/contrast", params={"site": "apollo11", "start": "2026-11-18", "days": 60})
    assert r.status_code == 200, "slipday.contrast.router is not served by the app"
    c = r.json()
    m, same, town = c["moon"], c["earth"][0], c["earth"][1]
    assert c["count"] == 1441 and len(m["sun_el"]) == len(same["sun_el"]) == len(town["sun_el"]) == 1441
    # every figure says where it comes from; the Earth curves are not passed off as NASA data
    assert m["kind"] == "derived" and same["kind"] == town["kind"] == "formula"
    assert "not NASA data" in c["notes"]["earth"] and "not an observation" in c["notes"]["moon"]
    assert len(c["facts"]) >= 4 and all(f["kind"] and f["moon"] and f["earth"] for f in c["facts"])
    # one lunar day is 29.5 Earth days: two or three sunrises in 60 days, against one a day on Earth
    assert m["sunrises"] in (2, 3) and town["sunrises"] == 60
    assert m["longest_dark_h"] > 300 and town["longest_dark_h"] < 20
    # no atmosphere, no twilight; at 45 N about an hour of civil twilight a day
    assert m["civil_twilight_h_per_day"] == 0.0 and 0.5 < town["civil_twilight_h_per_day"] < 2.0
    # the lunar curve is the app's own: the same hours and heights the site cards chart
    s = client.get("/api/series", params={"site": "apollo11", "start": "2026-11-18", "hours": 1440}).json()
    assert m["sun_up"] == s["lit"] and m["sun_el"] == [round(float(v), 2) for v in s["sun_el"]]


def test_contrast_shows_the_grazing_sun_at_the_lunar_pole():
    c = client.get("/api/contrast", params={"site": "southpole", "start": "2026-11-18", "days": 60}).json()
    m, same = c["moon"], c["earth"][0]
    # at the lunar pole the Sun never leaves a band a few degrees wide around the horizon (the Moon's axis is
    # tilted 1.5 degrees); at the same latitude on Earth it circles about 20 degrees up in this season
    assert m["max_sun_el"] - m["min_sun_el"] < 5.0 and abs(m["max_sun_el"]) < 4.0
    assert same["min_sun_el"] > 15.0 and same["sunrises"] == 0 and same["sun_up_share_pct"] == 100.0
    # and the Earth hangs in one small patch of the lunar sky
    assert m["earth_in_sky"]["el_max"] - m["earth_in_sky"]["el_min"] < 20.0


def test_contrast_rejects_what_it_cannot_answer():
    assert client.get("/api/contrast", params={"site": "nowhere", "start": "2026-11-18"}).status_code == 404
    assert client.get("/api/contrast", params={"start": "2026-11-18"}).status_code == 422
    assert client.get("/api/contrast", params={"site": "apollo11", "start": "soon"}).status_code == 422
    assert client.get("/api/contrast", params={"site": "apollo11", "start": "2026-11-18", "days": 500}).status_code == 422
    assert client.get("/api/contrast", params={"lat": 95, "lon": 0, "start": "2026-11-18"}).status_code == 422
    assert client.get("/api/contrast", params={"site": "apollo11", "start": "2049-12-20", "days": 60}).status_code in (200, 422)


# ------------------------------------------------------------------ links out to QuickMap and Moon Trek

def test_links_out_use_the_formats_that_were_checked_in_a_browser():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; static/links.js cannot be run here")
    js = os.path.join(ROOT, "static", "links.js")
    code = ("const L = require(%s); console.log(JSON.stringify({s: L.urls(-89.67, 129.78), a: L.urls(0.67416, 23.47314), "
            "n: L.urls(85, 370), bad: L.urls(120, 0), h: L.html(-89.4398, -137.17, 'C1 <ridge>')}))" % json.dumps(js))
    out = json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, timeout=60, check=True).stdout)
    # Shackleton crater: both tools showed the crater in the middle of the view at x = 7686 m, y = -6398 m
    # (south polar stereographic metres), loaded by hand on 14 Nov 2026
    s = out["s"]
    assert s["projection"] == "south polar stereographic"
    m = re.search(r"#v=0\.1&x=(-?\d+)&y=(-?\d+)&z=8&p=urn%3Aogc%3Adef%3Acrs%3AIAU2000%3A%3A30120&d=$", s["moontrek"])
    assert m and abs(int(m.group(1)) - 7686) < 30 and abs(int(m.group(2)) + 6398) < 30
    q = re.search(r"\?prjExtent=(-?\d+),(-?\d+),(-?\d+),(-?\d+)&proj=17$", s["quickmap"])
    x0, y0, x1, y1 = (int(v) for v in q.groups())
    assert x1 > x0 and y1 > y0 and abs((x0 + x1) / 2 - 7686) < 30 and abs((y0 + y1) / 2 + 6398) < 30
    # Apollo 11: the equirectangular views, longitude and latitude in degrees
    a = out["a"]
    assert a["projection"] == "equirectangular"
    assert a["moontrek"].endswith("#v=0.1&x=23.47314&y=0.67416&z=8&p=urn%3Aogc%3Adef%3Acrs%3AEPSG%3A%3A104903&d=")
    e = re.search(r"\?extent=(-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)&proj=10$", a["quickmap"])
    lon0, lat0, lon1, lat1 = (float(v) for v in e.groups())
    assert abs((lon0 + lon1) / 2 - 23.47314) < 1e-3 and abs((lat0 + lat1) / 2 - 0.67416) < 1e-3
    assert a["quickmap"].startswith("https://quickmap.lroc.im-ldi.com/") and a["moontrek"].startswith("https://trek.nasa.gov/moon/")
    # longitudes are brought into -180..180; an impossible latitude gives nothing
    assert out["n"]["projection"] == "equirectangular" and "x=10.00000" in out["n"]["moontrek"] and out["bad"] is None
    # the HTML escapes the name, opens a new tab without handing over the opener, and prints the coordinates
    assert "&lt;ridge&gt;" in out["h"] and 'rel="noopener noreferrer"' in out["h"] and "89.4398 S, 137.1700 W" in out["h"]
