"""Round 3, logic that needs no terrain data: mission card, slip-map statistics, long-span statistics in
blocks, reference-map readers, memory guards, stated claims."""
import json
import os
import threading
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from slipday import demstore, field, load, refmaps, robust
from slipday.api import app
from slipday.ephem import cached_table, grid_start, parse_utc
from slipday.geometry import Horizon, Site
from slipday.metrics import Criteria, _track, earth_up, slip_grid, span_stats, sun_up
from slipday.sites import custom_site, get_site

client = TestClient(app)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MAPS = [os.path.join(_HERE, "data", "reference"),                                   # scripts/fetch_on_your_machine.sh
         os.path.join(os.path.dirname(os.path.dirname(_HERE)), "realdata", "lunar", "data")]   # the build sandbox
REAL = os.environ.get("SLIPDAY_REALDATA_DIR") or next(
    (d for d in _MAPS if os.path.exists(os.path.join(d, "AVGVISIB_85S_060M_201608.TIF"))), _MAPS[0])
needs_maps = pytest.mark.skipif(not os.path.exists(os.path.join(REAL, "AVGVISIB_85S_060M_201608.TIF")),
                                reason="LOLA reference maps not available")


def test_scatter_pattern_is_12_points_at_the_stated_distances():
    pts = robust.scatter_points(-89.4398, -137.17, 100.0)
    assert len(pts) == 12 and len(set(pts)) == 12
    a = Site("a", -89.4398, -137.17)
    d = [_gc_m(a.lat, a.lon, la, lo) for la, lo in pts]
    assert sum(abs(x - 100.0) < 1.0 for x in d) == 8
    assert sum(abs(x - 50.0) < 1.0 for x in d) == 4


def _gc_m(la1, lo1, la2, lo2):
    a, b, c, d = map(np.deg2rad, (la1, lo1, la2, lo2))
    h = np.sin((c - a) / 2) ** 2 + np.cos(a) * np.cos(c) * np.sin((d - b) / 2) ** 2
    return float(2 * 1737400.0 * np.arcsin(np.sqrt(h)))


def test_smooth_sphere_site_has_no_band():
    s = Site("flat", 10.0, 20.0)
    grid, raw = robust.banded_slip_grid([s], "2027-01-01", 10, 24, 14.0, Criteria(), 0.0, 2.0, 100.0)
    assert "band" not in grid["rows"][0] and len(raw[0]["rows"]) == 1


def test_mission_logic_on_a_smooth_sphere_site():
    s = Site("Mare test", 18.56, 61.81)
    m = robust.mission_card(s, "2025-03-02T08:00:00Z", 240, 100, 14.0, Criteria(), 0.0, 2.0)
    v = [d["verdict"] for d in m["days"]]
    assert set(v) <= {"yes", "no"}                 # one member only: never "not sure"
    assert m["verdict"] == v[0] == "yes"
    assert m["slip_margin_days"] == v.index("no") - 1
    first_bad = m["slip_margin_days"] + 1
    assert all(d > m["days"][first_bad]["landing_utc"] for d in m["next_good_dates"])
    assert all(m["days"][[x["landing_utc"] for x in m["days"]].index(d)]["verdict"] == "yes" for d in m["next_good_dates"])
    assert m["days"][first_bad]["reasons"], "a failing day must say why"
    assert "survives a slip of up to" in " ".join(m["sentences"])
    # every stated pass really meets the stated need
    for d in m["days"]:
        if d["verdict"] == "yes":
            assert d["sunlit_h"] >= 240 and d["earth_h"] >= 100


def test_mission_with_no_need_and_no_touchdown_rule_is_always_yes():
    s = Site("anywhere", -40.0, 100.0)
    m = robust.mission_card(s, "2027-06-01", 0, 0, 14.0, Criteria(), 0.0, 2.0, sun_at_touchdown=False,
                            earth_at_touchdown=False, slip_days=30)
    assert m["good_dates"] == 30 and m["slip_margin_days"] == 29 and m["next_good_dates"] == []


def test_mission_impossible_need_is_always_no_with_reason():
    s = Site("far side", 0.0, 180.0)                      # never sees the Earth
    m = robust.mission_card(s, "2027-06-01", 10, 10, 14.0, Criteria(), 0.0, 2.0, slip_days=20)
    assert m["verdict"] == "no" and m["good_dates"] == 0 and m["slip_margin_days"] == -1
    assert any("Earth" in r for r in m["days"][0]["reasons"])
    assert "No landing date" in " ".join(m["sentences"])


def test_mission_api_input_errors():
    assert client.post("/api/mission", json={"site": {"id": "nope"}, "landing": "2027-01-01"}).status_code == 404
    assert client.post("/api/mission", json={"site": {"id": "apollo11"}, "landing": "soon"}).status_code == 422
    assert client.post("/api/mission", json={"site": {"id": "apollo11"}, "landing": "2027-01-01", "need_sun_h": -1}).status_code == 422
    r = client.post("/api/mission", json={"site": {"id": "apollo11"}, "landing": "2049-12-20", "slip_days": 30})
    assert r.status_code == 200 and r.json()["days"][-1]["verdict"] == "n/a"


def test_replays_are_real_sites_each_with_its_own_labelled_need():
    r = client.get("/api/replays").json()
    assert "published" in r["note"] and "illustrative" in r["note"]
    ids = {s["id"] for s in client.get("/api/sites").json()["sites"]}
    assert len(r["missions"]) == 4 and all(m["site"] in ids for m in r["missions"])
    for m in r["missions"]:
        assert m["landing"][:13] == m["landed_utc"][:13] and m["landing"].endswith(":00:00Z")
        assert m["need_kind"] in ("published plan", "illustrative") and m["need_source"].startswith("https://")
        assert "illustrative" in m["need_note"]          # the Earth-contact figure is never the mission's own
    by = {m["id"]: m for m in r["missions"]}
    # planned surface durations: IM-1 about 7 days, IM-2 about 10, Blue Ghost 14; Chandrayaan-3 has no hour figure
    assert (by["im1"]["need_sun_h"], by["im2"]["need_sun_h"], by["blueghost1"]["need_sun_h"]) == (168, 240, 336)
    assert by["chandrayaan3"]["need_kind"] == "illustrative"
    assert "10 days" in by["im1"]["need_note"]           # the conflicting NASA press-kit figure is not hidden


def test_slipgrid_reports_earth_hours_and_touchdown_flags():
    g = client.post("/api/slipgrid", json={"sites": [{"id": "apollo11"}], "start": "2027-01-01", "n_dates": 30}).json()
    row = g["rows"][0]
    assert len(row["earth"]) == 30 and row["earth"][0] == 336          # near side: the Earth never sets
    assert set(row["sun_up_at_landing"]) == {True, False}
    for i in range(30):
        assert row["total"][i] <= min(row["sunlit"][i], row["earth"][i])


def test_field_statistics_logic():
    sun = np.array([[300, 300, 100, 300], [100, 300, 300, 300], [300, 300, 300, 300]], dtype=np.int16)
    pd = {"valid": np.ones(4, dtype=bool), "sunlit": sun, "earth": np.full((3, 4), 200, dtype=np.int16),
          "total": sun // 2, "sun0": np.ones((3, 4), dtype=bool), "earth0": np.ones((3, 4), dtype=bool)}
    st = field.statistics(pd, 240, 100)
    assert st["margin"].tolist() == [1, -1, 3] and st["good"].tolist() == [3, 3, 4]
    assert st["worst_sun"].tolist() == [100, 100, 300] and st["dates"] == 4
    pd["earth0"][2, 0] = False
    assert field.statistics(pd, 240, 100)["margin"].tolist() == [1, -1, -1]
    assert field.statistics(pd, 240, 100, earth_at_touchdown=False)["margin"].tolist() == [1, -1, 3]


def test_slipmap_says_so_when_the_field_is_missing(monkeypatch):
    monkeypatch.setattr(field, "load", lambda: None)
    r = client.post("/api/slipmap", json={"start": "2026-11-18"}).json()
    assert r["available"] is False and "build_field" in r["reason"]


def test_span_stats_in_blocks_equals_one_block(monkeypatch):
    import slipday.metrics as mt
    s = Site("s", -85.0, 30.0, horizon=Horizon(profile_az_deg=np.arange(0, 360, 10.0),
                                               profile_el_deg=1.5 * np.sin(np.deg2rad(np.arange(0, 360, 10.0)))))
    whole = span_stats(s, "2027-01-01", 400, 60)
    monkeypatch.setattr(mt, "SPAN_BLOCK", 1000)
    parts = span_stats(s, "2027-01-01", 400, 60)
    assert whole == parts


def test_span_stats_refuses_oversized_requests():
    with pytest.raises(ValueError):
        span_stats(Site("s", 0.0, 0.0), "2000-01-01", 7300, 10)


def test_unvalidated_grids_say_so():
    north = custom_site("n", 89.5, 10.0).horizon.describe()
    assert north.get("validated") is False or north["kind"] != "profile"


def test_bad_dates_get_a_readable_message():
    for url in ("/api/metrics?site=apollo11&at=notadate", "/api/series?site=apollo11&start=notadate"):
        r = client.get(url)
        assert r.status_code == 422 and "not a date or time" in r.json()["detail"]
    assert client.post("/api/slipgrid", json={"sites": [{"id": "apollo11"}], "start": "x"}).status_code == 422


def test_pds_label_parser():
    kv = refmaps.parse_label('PDS_VERSION_ID = "PDS3"\nDESCRIPTION = "two\n  lines"\n  LINES = 12\n  LINE_SAMPLES = 10\n'
                             ' MAP_SCALE = 240 <m/pix>\n LINE_PROJECTION_OFFSET = 5.5 <pix>\nSCALING_FACTOR = 0.00004\n')
    assert kv["LINES"] == "12" and kv["MAP_SCALE"] == "240" and kv["LINE_PROJECTION_OFFSET"] == "5.5"
    assert kv["DESCRIPTION"] == "two lines"


@needs_maps
def test_geotiff_reader_reproduces_the_manifest_values():
    m = refmaps.load(os.path.join(REAL, "AVGVISIB_85S_060M_201608.TIF"))
    assert m.pixel_m == 60.0 and m.z.shape == (5058, 5058) and m.product_id == "AVGVISIB_85S_060M_201608"
    assert abs(float(m.nearest(-89.4632, 222.8233)) - 0.769) < 0.001          # connecting ridge CR1, scout's manifest
    assert float(m.nearest(-89.67, 129.78)) == 0.0                            # Shackleton floor: permanent shadow
    assert np.isnan(m.nearest(np.array([-80.0]), np.array([0.0]))[0])         # outside the map: refused, not wrapped
    assert refmaps.find(REAL, "85S_060M", earth=False).endswith(".TIF")
    earth = refmaps.find(REAL, "85S_060M", earth=True)
    if earth is None:                      # the Earth maps were not in the build sandbox; the local pass downloads them
        return
    e = refmaps.load(earth)
    assert e.z.shape == (5058, 5058) and e.pixel_m == 60.0 and e.product_id == "AVGVISIB_85S_060M_201608_EARTH"
    assert e.x0_m == m.x0_m and e.y0_m == m.y0_m and e.scale == 4e-5         # same grid as the Sun map
    assert "any fraction of the Earth disc" in e.description                  # the map's own rule, from its label
    assert float(e.nearest(-89.67, 129.78)) == 0.0                            # Shackleton floor never sees the Earth
    half = e.z.shape[0] // 2                                                  # the Earth-facing half (longitude 0, top rows)
    assert np.asarray(e.z[:half]).mean() > 1.5 * np.asarray(e.z[half:]).mean()


@needs_maps
def test_pds_img_and_jp2_readers_on_the_real_240m_product(tmp_path):
    """The Earth maps come as .IMG + .LBL.  The same container is exercised here with the real Sun map:
    its JPEG2000 is decoded and written back as the raw .IMG its own label describes."""
    jp2 = os.path.join(REAL, "AVGVISIB_65S_240M_201608.JP2")
    if not os.path.exists(jp2):
        pytest.skip("AVGVISIB_65S_240M_201608.JP2 not downloaded (scripts/fetch_on_your_machine.sh)")
    m = refmaps.load(jp2)
    assert m.z.shape == (6420, 6420) and m.pixel_m == 240.0 and m.scale == 4e-5
    assert "any fraction of the solar" in m.description
    assert abs(float(m.nearest(-89.45, 222.69)) - 0.9348) < 0.0001            # Mazarico et al. 2011 best site
    np.asarray(m.z).astype("<i2").tofile(tmp_path / "AVGVISIB_65S_240M_201608_EARTH.IMG")   # container test only
    with open(os.path.join(REAL, "AVGVISIB_65S_240M_201608_JP2.LBL"), errors="replace") as fh:
        (tmp_path / "AVGVISIB_65S_240M_201608_EARTH.LBL").write_text(fh.read())
    path = refmaps.find(str(tmp_path), "65S_240M", earth=True)
    assert path and path.endswith(".IMG")
    m2 = refmaps.load(path)
    assert np.array_equal(np.asarray(m2.z), np.asarray(m.z)) and m2.x0_m == m.x0_m and m2.y0_m == m.y0_m
    assert abs(float(m2.nearest(-89.45, 222.69)) - 0.9348) < 0.0001


def test_img_without_label_is_refused(tmp_path):
    (tmp_path / "AVGVISIB_85S_060M_201608_EARTH.IMG").write_bytes(b"\0" * 64)
    with pytest.raises(ValueError):
        refmaps.load(str(tmp_path / "AVGVISIB_85S_060M_201608_EARTH.IMG"))


def test_stored_validation_states_its_limits():
    v = client.get("/api/terrain/validation").json()
    if not v.get("available"):
        pytest.skip("validation results not stored")
    keys = " | ".join(h["k"] for h in v["headline"])
    assert "ordinary terrain" in keys and "ridge pixels" in keys
    text = json.dumps(v)
    assert "not firm" in text                      # the C1 match is presented with its sensitivity
    earth = [h for h in v["headline"] if "Earth" in h["k"]]
    assert earth, "the Earth check must be visible, run or not"
    if earth[0].get("pending"):
        assert earth[0]["tag"] == "needs official data download"
    assert "ran_on" in v and isinstance(v["same_grid"], bool)


def test_docs_do_not_repeat_the_corrected_claims():
    for name in ("README.md", "LIMITATIONS.md", "REALDATA.md", "SUBMISSION_DRAFT.md", "TEST_REPORT.md"):
        with open(os.path.join(ROOT, name)) as fh:
            text = fh.read()
        assert "distant peak" not in text, name
        assert "512 MB instance" not in text, name


def test_heavy_lets_two_computations_run_at_a_time():
    running, peak = [0], [0]
    lock = threading.Lock()

    def job():
        with load.heavy():
            with lock:
                running[0] += 1
                peak[0] = max(peak[0], running[0])
            time.sleep(0.05)
            with lock:
                running[0] -= 1

    threads = [threading.Thread(target=job) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert peak[0] == 2
    assert load.rss_mb().get("VmRSS", 1) > 0


def test_field_can_be_thinned_for_a_slow_host(monkeypatch):
    if field.load() is None:
        pytest.skip("skyline field not built")
    full = field.load()["meta"]
    monkeypatch.setattr(field, "STRIDE", 2)
    field.reload()
    try:
        thin = field.load()
        assert thin["meta"]["n"] == full["n"] // 2 and thin["meta"]["step_m"] == full["step_m"] * 2
        assert len(thin["lat"]) == thin["meta"]["n"] ** 2 == thin["el"].shape[0]
        r = client.post("/api/slipmap", json={"start": "2026-11-18", "n_dates": 10}).json()
        assert r["available"] and len(r["layers"]["margin"]) == thin["meta"]["n"] ** 2 and r["step_m"] == full["step_m"] * 2
    finally:
        monkeypatch.setattr(field, "STRIDE", 1)
        field.reload()
