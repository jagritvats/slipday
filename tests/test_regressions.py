"""One test per bug found in the v1 review (reviews/slipday/REVIEW.md)."""
import pytest
from fastapi.testclient import TestClient

from slipday import ephem, horizons
from slipday.api import app
from slipday.metrics import series, site_summary, slip_grid
from slipday.sites import custom_site, get_site, normalise_lon

client = TestClient(app)


def test_time_to_sunset_and_lunar_day_use_one_event_list():
    """Review (medium): 'Time to sunset: none before Jan 13' sat beside 'Sunlight left: 29.5 d'.
    The chart's event list now looks 200 days past the charted span, like the summary does."""
    site = get_site("shackleton", use_terrain=False)
    s = series(site, "2026-11-14T00:00:00Z", 1440)
    chart_end = s["start_unix"] + 1440 * 3600
    at = "2027-01-12T00:00:00Z"
    m = site_summary(site, at)
    assert m["now"]["sun_up"] and m["next_sunset"] is not None
    later = [e for e in s["events"] if e["type"] == "sunset" and e["unix"] > chart_end]
    assert later, "the series must list the sunset that falls after the charted span"
    assert later[0]["utc"] == m["next_sunset"]["utc"]
    assert m["lunar_day"]["sunlight_hours_remaining"] == m["next_sunset"]["hours_from_now"]
    assert m["lunar_day"]["sunlight_hours_remaining"] == pytest.approx(29.5 * 24, abs=30)


def test_horizons_check_with_a_bad_date_is_422_not_500(monkeypatch):
    """Review (low): /api/horizons/check?start=bad returned HTTP 500."""
    monkeypatch.setattr(horizons, "enabled", lambda: True)
    for params in ({"site": "im1", "start": "bad", "stop": "2027-01-01"},
                   {"site": "im1", "start": "2027-01-01", "stop": "also bad"},
                   {"site": "im1", "start": "2027-01-05", "stop": "2027-01-01"}):
        r = client.get("/api/horizons/check", params=params)
        assert r.status_code == 422, r.text


def test_dates_in_late_2049_are_accepted():
    """Review (low): metrics at 2049-12-01 and a slip grid from 2049-11-14 were rejected as out of span."""
    r = client.get("/api/metrics", params={"site": "apollo11", "at": "2049-12-01T00:00:00Z"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["search_truncated_at_ephemeris_end"] is True and j["search_days"] < 32
    assert j["next_sunset"] is not None or j["next_sunrise"] is not None
    r = client.get("/api/series", params={"site": "apollo11", "start": "2049-12-20", "hours": 720})
    assert r.status_code == 200 and r.json()["truncated_at_ephemeris_end"] is True
    g = client.post("/api/slipgrid", json={"sites": [{"id": "apollo11"}], "start": "2049-11-14T00:00:00Z",
                                           "n_dates": 60, "window_days": 14})
    assert g.status_code == 200, g.text
    row = g.json()["rows"][0]["total"]
    assert row[0] is not None and row[-1] is None            # windows that would pass 2050-01-01 are blank, not wrong
    assert g.json()["truncated_at_ephemeris_end"] is True
    # still refused where it should be
    assert client.get("/api/metrics", params={"site": "apollo11", "at": "2050-01-02T00:00:00Z"}).status_code == 422
    assert client.get("/api/metrics", params={"site": "apollo11", "at": "1899-06-01T00:00:00Z"}).status_code == 422


def test_longitude_180_stays_east():
    """Review (low): longitude 180 became -180 and was shown as 180.000 W."""
    assert normalise_lon(180) == 180.0 and normalise_lon(-180) == 180.0 and normalise_lon(540) == 180.0
    assert normalise_lon(190) == -170.0 and normalise_lon(360) == 0.0 and normalise_lon(-10) == -10.0
    assert custom_site("x", 0, 180).lon == 180.0
    j = client.get("/api/series", params={"lat": 0, "lon": 180, "start": "2026-01-01", "hours": 24}).json()
    assert j["site"]["lon"] == 180.0


def test_oversized_requests_are_refused_and_the_cache_is_bounded():
    """Review (low): one request could build a 290,000-sample table; 64 tables were cached."""
    r = client.post("/api/slipgrid", json={"sites": [{"id": "im1"}], "start": "2000-01-01", "n_dates": 400,
                                           "date_step_hours": 720})
    assert r.status_code == 422 and "too large" in r.json()["detail"]
    for k in range(12):
        ephem.cached_table(ephem.grid_start(ephem.parse_utc("2001-01-01")) + k * 3600, 150_000, 3600)
    assert ephem.cache_samples() <= 900_000


def test_no_sunrise_ahead_is_not_reported_as_a_missing_sunset():
    """Review (low): with the Sun down and no sunrise ahead the page said 'no sunset within 62 days'.
    The summary now states which event is missing and how far it searched."""
    m = site_summary(get_site("southpole", use_terrain=False), "2027-05-10T00:00:00Z", search_days=60)
    assert m["now"]["sun_up"] is False and m["next_sunrise"] is None
    assert m["lunar_day"]["state"] == "next" and m["lunar_day"]["sunrise_utc"] is None
    assert m["search_days"] == pytest.approx(60, abs=0.1)


def test_favicon_and_licence_exist():
    import os
    assert client.get("/favicon.ico").status_code == 200
    root = os.path.join(os.path.dirname(__file__), "..")
    assert os.path.exists(os.path.join(root, "LICENSE"))


def test_slip_grid_fast_path_matches_a_plain_loop():
    """The vectorised 'unbroken hours' must equal the obvious loop."""
    import numpy as np
    from slipday.ephem import cached_table, grid_start, parse_utc
    from slipday.geometry import track
    from slipday.metrics import usable_mask
    site = get_site("im1", use_terrain=False)
    g = slip_grid([site], "2026-11-14", 40, 24, 14.0)
    table = cached_table(grid_start(parse_utc("2026-11-14")), 39 * 24 + 336 + 1, 3600)
    ok = usable_mask(track(site, table))
    for k in range(40):
        run = 0
        while run < 336 and ok[k * 24 + run]:
            run += 1
        assert g["rows"][0]["continuous"][k] == run
        assert g["rows"][0]["total"][k] == int(np.sum(ok[k * 24:k * 24 + 336]))


def test_sun_above_a_low_skyline_counts_even_at_negative_elevation():
    """Found while looking at the winter slip grid on real terrain: the default minimum Sun
    elevation of 0 deg threw away every hour when the Sun sat at -1 deg above a -2 deg skyline,
    so a ridge that is lit 60 % of May 2027 showed zero usable hours.  SYNTHETIC -2 deg skyline."""
    import numpy as np
    from slipday.geometry import Horizon, Site
    from slipday.metrics import Criteria
    az = np.arange(0, 360, 1.0)
    ridge = Site("ridge", -89.44, -137.17, horizon=Horizon(profile_az_deg=az, profile_el_deg=np.full(360, -2.0),
                                                           source="SYNTHETIC -2 deg"))
    g = slip_grid([ridge], "2027-05-01", 30, 24, 14.0)
    row = g["rows"][0]
    assert max(row["sunlit"]) > 100 and max(row["total"]) > 50      # v2-before-fix gave total == 0 everywhere
    assert min(row["sun_el_at_landing"]) < 0                         # and the Sun really is below the level horizon
    strict = slip_grid([ridge], "2027-05-01", 30, 24, 14.0, crit=Criteria(min_sun_el=0.0))["rows"][0]
    assert max(strict["total"]) == 0                                 # the extra rule still works when asked for
    r = client.post("/api/slipgrid", json={"sites": [{"id": "apollo11"}], "start": "2027-05-01", "n_dates": 5})
    assert r.json()["criteria"]["min_sun_el"] is None
