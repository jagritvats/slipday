"""Metrics, slip grid and API shapes."""
import pytest
from fastapi.testclient import TestClient

from slipday.api import app
from slipday.metrics import Criteria, site_summary, slip_grid
from slipday.sites import SITES, custom_site, get_site

client = TestClient(app)


def test_summary_at_chandrayaan3_landing():
    s = site_summary(get_site("chandrayaan3"), "2023-08-23T12:33:00Z")
    assert s["now"]["sun_up"] and s["now"]["earth_up"]
    assert s["next_sunset"]["utc"].startswith("2023-09-04")
    assert s["next_earthset"] is None                      # Earth never sets there within the search span
    assert s["window"]["earth_visible_share"] == 1.0
    assert 300 < s["window"]["sunlit_hours"] < 400


def test_far_side_has_no_usable_hours():
    s = site_summary(get_site("change6"), "2024-06-02T00:00:00Z")
    assert s["window"]["earth_visible_share"] == 0.0 and s["window"]["usable_hours"] == 0.0


def test_slip_grid_invariants():
    sites = [get_site("im1"), get_site("blueghost1"), get_site("change6")]
    g = slip_grid(sites, "2026-11-14", 60, 24, 14.0)
    assert len(g["dates"]) == 60 and g["window_hours"] == 336
    for row in g["rows"]:
        assert len(row["total"]) == len(row["continuous"]) == len(row["sunlit"]) == 60
        for c, t, s in zip(row["continuous"], row["total"], row["sunlit"]):
            assert 0 <= c <= t <= s <= 336
    assert sum(g["rows"][2]["total"]) == 0
    assert max(g["rows"][0]["total"]) > 200
    # a landing one day into the lunar night scores zero unbroken hours but non-zero total
    assert any(c == 0 and t > 0 for c, t in zip(g["rows"][1]["continuous"], g["rows"][1]["total"]))


def test_stricter_minimum_elevations_never_add_hours():
    sites = [get_site("im1")]
    loose = slip_grid(sites, "2026-11-14", 30, 24, 14.0)["rows"][0]["total"]
    strict = slip_grid(sites, "2026-11-14", 30, 24, 14.0,
                       crit=Criteria(min_sun_el=5.0, min_earth_el=5.0))["rows"][0]["total"]
    assert all(b <= a for a, b in zip(loose, strict)) and sum(strict) < sum(loose)


def test_custom_longitude_wraps():
    assert custom_site("x", 10, 350).lon == pytest.approx(-10)


def test_api_health_and_sites():
    assert client.get("/api/health").json()["status"] == "ok"
    sites = client.get("/api/sites").json()["sites"]
    assert len(sites) == len(SITES) >= 20
    assert {"id", "name", "group", "lat", "lon", "confidence", "source"} <= set(sites[0])


def test_api_series_shape():
    r = client.get("/api/series", params={"site": "blueghost1", "start": "2025-03-01T00:00:00Z", "hours": 480})
    assert r.status_code == 200
    j = r.json()
    assert j["count"] == 481 == len(j["sun_el"]) == len(j["earth_el"]) == len(j["sun_az"]) == len(j["earth_az"])
    assert j["horizon"]["kind"] == "smooth-sphere"
    in_chart = [e["type"] for e in j["events"] if e["unix"] <= j["start_unix"] + 480 * 3600]
    assert in_chart == ["sunrise", "sunset"]


def test_api_metrics_with_typed_coordinates_and_mask():
    r = client.get("/api/metrics", params={"lat": -85.4, "lon": 31.6, "name": "Typed", "at": "2026-11-14T00:00:00Z", "mask_deg": 2})
    assert r.status_code == 200
    j = r.json()
    assert j["site"]["name"] == "Typed" and j["horizon"]["kind"] == "flat-mask"
    assert {"now", "next_sunset", "next_sunrise", "next_earthset", "next_earthrise", "lunar_day", "window"} <= set(j)


def test_api_compare_and_slipgrid():
    body = {"sites": [{"id": "im1"}, {"lat": 0, "lon": 0, "name": "Zero"}], "start": "2026-11-14T00:00:00Z", "hours": 720}
    j = client.post("/api/compare", json=body).json()
    assert len(j["sites"]) == 2 and j["sites"][1]["series"]["site"]["name"] == "Zero"
    assert j["sites"][0]["series"]["count"] == 721 and "window" in j["sites"][0]["metrics"]
    g = client.post("/api/slipgrid", json={"sites": body["sites"], "start": "2026-11-14T00:00:00Z", "n_dates": 30, "window_days": 7}).json()
    assert len(g["rows"]) == 2 and len(g["rows"][0]["total"]) == 30 and g["window_hours"] == 168


def test_api_hindcast_and_validation():
    h = client.get("/api/hindcast").json()
    assert [m["id"] for m in h["missions"]] == ["chandrayaan3", "im1", "blueghost1"]
    v = client.get("/api/validation").json()
    assert v["rows"] == 218 and v["max_abs_el_deg"] < 1e-3


def test_api_errors():
    assert client.get("/api/series", params={"site": "nope", "start": "2026-01-01"}).status_code == 404
    assert client.get("/api/series", params={"lat": 95, "lon": 0, "start": "2026-01-01"}).status_code == 422
    assert client.get("/api/series", params={"start": "2026-01-01"}).status_code == 422
    assert client.get("/api/series", params={"site": "im1", "start": "not-a-date"}).status_code == 422
    assert client.get("/api/series", params={"site": "im1", "start": "2090-01-01"}).status_code == 422
    five = {"sites": [{"id": "im1"}] * 5, "start": "2026-11-14"}
    assert client.post("/api/compare", json=five).status_code == 422
    assert client.get("/api/horizons/check", params={"site": "im1", "start": "2026-01-01", "stop": "2026-01-05"}).status_code == 503


def test_front_end_is_served():
    r = client.get("/")
    assert r.status_code == 200 and "Slipday" in r.text
    assert client.get("/static/app.js").status_code == 200
