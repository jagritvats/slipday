"""The API with a terrain DEM installed.  These tests use the SYNTHETIC test
fixture (slipday.dem.synthetic_south_pole_fixture); nothing here is lunar data."""
import csv
import io

import pytest
from fastapi.testclient import TestClient

from slipday import api, demstore, hindcast, moonmap, sites
from slipday.api import app

client = TestClient(app)


def _reset():
    demstore.reload()
    sites._terrain_profile.cache_clear()
    hindcast.hindcast.cache_clear()
    api._stats.cache_clear()
    moonmap._cache.clear()


@pytest.fixture()
def synthetic_dem(monkeypatch):
    monkeypatch.setenv("SLIPDAY_SYNTHETIC_DEM", "1")
    _reset()
    yield
    monkeypatch.delenv("SLIPDAY_SYNTHETIC_DEM")
    _reset()


def test_without_a_dem_everything_is_smooth_sphere_and_says_so():
    h = client.get("/api/health").json()
    assert h["terrain"]["available"] is False and "smooth sphere" in h["horizon_default"]
    j = client.post("/api/compare", json={"sites": [{"id": "shackleton"}], "start": "2027-01-01", "hours": 240}).json()
    e = j["sites"][0]
    assert e["terrain"] is False and "smooth" not in e and "profile" not in e
    assert e["metrics"]["horizon"]["model"] == "smooth sphere"
    assert client.get("/api/horizon", params={"site": "shackleton"}).status_code == 404
    assert client.get("/api/map").json()["available"] is False
    assert client.get("/api/map/image").status_code == 404
    assert client.get("/api/terrain/validation").status_code == 200


def test_synthetic_dem_is_labelled_synthetic_everywhere(synthetic_dem):
    h = client.get("/api/health").json()
    assert h["terrain"]["available"] and h["terrain"]["synthetic"] and "SYNTHETIC" in h["terrain"]["label"]
    p = client.get("/api/horizon", params={"site": "shackleton", "mast_m": 2}).json()
    assert len(p["az_deg"]) == 720 and p["dem"]["synthetic"] is True and "SYNTHETIC" in p["label"]
    assert p["site_height_m"] == pytest.approx(1500, abs=60)        # the fixture's cone under that point
    j = client.post("/api/compare", json={"sites": [{"id": "shackleton"}, {"id": "apollo11"}],
                                          "start": "2027-01-01", "hours": 240}).json()
    polar, equatorial = j["sites"]
    assert polar["terrain"] is True and polar["metrics"]["horizon"]["synthetic"] is True
    assert polar["series"]["horizon"]["model"] == "terrain" and "SYNTHETIC" in polar["series"]["horizon"]["label"]
    assert polar["smooth"]["metrics"]["horizon"]["model"] == "smooth sphere"
    assert len(polar["smooth"]["lit"]) == polar["series"]["count"] == len(polar["series"]["sun_frac"])
    assert equatorial["terrain"] is False                           # outside the polar fixture: smooth sphere
    m = client.get("/api/map").json()
    assert m["available"] and m["synthetic"] is True
    img = client.get("/api/map/image")
    assert img.status_code == 200 and img.content[:2] == b"\xff\xd8" and img.headers["content-type"] == "image/jpeg"


def test_terrain_and_smooth_sphere_are_reported_side_by_side(synthetic_dem):
    """On a 1.5 km cone at 89.45 S the horizon dips about 2 degrees, so the terrain model
    must report much more light over a year than the smooth sphere at the same point."""
    j = client.get("/api/stats", params={"site": "shackleton", "start": "2027-01-01", "days": 365}).json()
    t, s = j["terrain"], j["smooth"]
    assert t["horizon"]["model"] == "terrain" and s["horizon"]["model"] == "smooth sphere"
    assert s["centre_up_pct"] == pytest.approx(52.0, abs=0.5)
    assert t["any_light_pct"] > 90 and t["longest_dark_h"] < s["longest_dark_h"] / 5
    assert t["earth_visible_pct"] > s["earth_visible_pct"]
    for k in ("mean_disc_fraction_pct", "longest_light_h", "longest_earth_outage_h", "lit_pct"):
        assert k in t and k in s
    # switching terrain off gives the smooth numbers under the terrain key's absence
    off = client.get("/api/stats", params={"site": "shackleton", "start": "2027-01-01", "days": 365, "terrain": "false"}).json()
    assert off["terrain"] is None and off["smooth"]["centre_up_pct"] == s["centre_up_pct"]


def test_mast_height_changes_the_horizon(synthetic_dem):
    a = client.get("/api/horizon", params={"lat": -88.5, "lon": 40, "mast_m": 2}).json()
    b = client.get("/api/horizon", params={"lat": -88.5, "lon": 40, "mast_m": 10}).json()
    assert a["mast_m"] == 2 and b["mast_m"] == 10
    assert b["mean_el_deg"] < a["mean_el_deg"]                      # higher observer, lower horizon
    assert a["max_el_deg"] > 0.5                                    # the fixture's hill at 88 S 90 E shows


def test_earth_margin_and_sun_rule_parameters(synthetic_dem):
    base = {"site": "shackleton", "start": "2027-01-01", "days": 200}
    e0 = client.get("/api/stats", params=base).json()["terrain"]["earth_visible_pct"]
    e3 = client.get("/api/stats", params=dict(base, earth_margin_deg=3)).json()["terrain"]["earth_visible_pct"]
    assert e3 < e0
    any_part = client.get("/api/stats", params=dict(base, min_sun_fraction=0)).json()["terrain"]["lit_pct"]
    whole = client.get("/api/stats", params=dict(base, min_sun_fraction=1)).json()["terrain"]["lit_pct"]
    half = client.get("/api/stats", params=base).json()["terrain"]["lit_pct"]
    assert whole <= half <= any_part and whole < any_part


def test_slip_grid_rows_carry_both_models(synthetic_dem):
    g = client.post("/api/slipgrid", json={"sites": [{"id": "shackleton"}, {"id": "blueghost1"}],
                                           "start": "2027-04-20", "n_dates": 30, "window_days": 14}).json()
    polar, mid = g["rows"]
    assert polar["horizon"]["model"] == "terrain" and "smooth" in polar and "smooth" not in mid
    assert sum(polar["smooth"]["sunlit"]) == 0          # the reviewer's case: weeks of zeros on the smooth sphere
    assert sum(polar["sunlit"]) > 0                     # the elevated site still gets light in the terrain model


def test_csv_exports_label_every_row(synthetic_dem):
    body = {"sites": [{"id": "shackleton"}, {"id": "blueghost1"}], "start": "2027-01-01", "n_dates": 10, "window_days": 7}
    r = client.post("/api/export/slipgrid.csv", json=body)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    text = r.text
    head = [ln for ln in text.splitlines() if ln.startswith("#")]
    assert any("SYNTHETIC TEST DEM" in ln for ln in head) and any("DE421" in ln for ln in head)
    rows = list(csv.DictReader(io.StringIO("\n".join(ln for ln in text.splitlines() if not ln.startswith("#")))))
    assert len(rows) == 10 * 3                           # terrain + smooth for the polar site, smooth only for the other
    assert {r["horizon_model"] for r in rows} == {"terrain", "smooth sphere"}
    assert all(r["horizon_label"] for r in rows)
    body = {"sites": [{"id": "shackleton"}], "start": "2027-01-01", "hours": 48}
    c = client.post("/api/export/compare.csv", json=body)
    crow = list(csv.DictReader(io.StringIO("\n".join(ln for ln in c.text.splitlines() if not ln.startswith("#")))))
    assert [r["horizon_model"] for r in crow] == ["terrain", "smooth sphere"]
    assert float(crow[0]["sunlit_share"]) >= 0 and crow[0]["site"].startswith("Shackleton")
    s = client.post("/api/export/series.csv", json=body)
    srow = list(csv.DictReader(io.StringIO("\n".join(ln for ln in s.text.splitlines() if not ln.startswith("#")))))
    assert len(srow) == 49 and {"sun_disc_fraction_visible", "sun_up_smooth_sphere"} <= set(srow[0])


def test_hindcast_reports_both_models_when_terrain_covers_the_site(synthetic_dem):
    h = client.get("/api/hindcast").json()
    im1 = [m for m in h["missions"] if m["id"] == "im1"][0]
    bg = [m for m in h["missions"] if m["id"] == "blueghost1"][0]
    assert set(im1["checks"][0]["models"]) == {"smooth sphere", "terrain"}
    assert set(bg["checks"][0]["models"]) == {"smooth sphere"}
    assert im1["checks"][0]["models"]["smooth sphere"]["size"] == "off by 3.3 days"
