"""One live JPL Horizons cross-check through the app's own endpoint (what the page button does).

    python horizons_live.py <entry root>
"""
import json
import os
import sys

root = sys.argv[1]
sys.path.insert(0, root)
os.environ["SLIPDAY_HORIZONS"] = "1"
from fastapi.testclient import TestClient  # noqa: E402

from slipday.api import app  # noqa: E402

client = TestClient(app)
for site, start, stop in (("shackleton", "2026-11-18T00:00:00Z", "2026-11-28T00:00:00Z"),
                          ("im1", "2024-02-22T23:00:00Z", "2024-03-03T23:00:00Z")):
    r = client.get("/api/horizons/check", params={"site": site, "start": start, "stop": stop})
    print(site, r.status_code)
    body = r.json()
    if r.status_code != 200:
        print(body)
        continue
    for x in body["results"]:
        print(json.dumps({k: x[k] for k in ("target", "rows", "max_abs_el_deg", "max_abs_az_deg", "rms_el_deg", "first_utc", "last_utc")}))
        print("   ", x["url"])
