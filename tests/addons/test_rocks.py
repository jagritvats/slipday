"""Add-on "rocks": no public rock/boulder product covers the south pole, so the router must say so and never
return a value.  Runs offline; api.py is not touched."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from slipday.addons import rocks as R

app = FastAPI()
app.include_router(R.router)
client = TestClient(app)


def test_info_reports_not_available_with_checked_urls():
    r = client.get("/api/addons/rocks")
    assert r.status_code == 200
    j = r.json()
    assert j["available"] is False
    assert "80 S" in j["why"]
    assert len(j["checked"]) >= 3
    assert all(c["url"].startswith("https://") for c in j["checked"])
    assert not any(c["covers_sites"] for c in j["checked"])


def test_site_never_returns_a_value():
    for params in ({"site": "robust_pick"}, {"site": "shackleton"}, {"lat": -89.44, "lon": -137.17}, {}):
        j = client.get("/api/addons/rocks/site", params=params).json()
        assert j["available"] is False
        assert j["value"] is None
        assert j["result"] == "no coverage here"
