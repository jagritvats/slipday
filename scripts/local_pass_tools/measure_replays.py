"""Mission card for the four real landings under several candidate needs.  python measure_replays.py <entry root>"""
import json
import os
import sys
import tempfile

root = sys.argv[1]
sys.path.insert(0, root)
os.environ.setdefault("SLIPDAY_HORIZON_CACHE", tempfile.mkdtemp(prefix="slipday_measure_cache_"))
from fastapi.testclient import TestClient  # noqa: E402

from slipday import demstore  # noqa: E402
from slipday.api import app  # noqa: E402

client = TestClient(app)
print("grids:", demstore.status()["label"])
CASES = {"im1": ("2024-02-22T23:00:00Z", [(168, 100), (240, 100), (168, 168), (144, 100)]),
         "im2": ("2025-03-06T17:00:00Z", [(240, 100), (240, 240)]),
         "chandrayaan3": ("2023-08-23T12:00:00Z", [(240, 100), (288, 100), (312, 100), (336, 100)]),
         "blueghost1": ("2025-03-02T08:00:00Z", [(240, 100), (336, 100), (336, 336)])}
for sid, (when, needs) in CASES.items():
    for sun, earth in needs:
        m = client.post("/api/mission", json={"site": {"id": sid}, "landing": when, "need_sun_h": sun,
                                              "need_earth_h": earth, "scatter_m": 100}).json()
        d0 = m["days"][0]
        print(json.dumps({"site": sid, "need": [sun, earth], "verdict": m["verdict"], "margin": m["slip_margin_days"],
                          "sun_h": d0["sunlit_h"], "sun_rng": d0.get("sunlit_range_h"), "earth_h": d0["earth_h"],
                          "pts": f"{d0['points_passing']}/{d0['points']}", "scatter_used": m["sure"]["scatter_m"],
                          "yes": m["good_dates"], "not_sure": m["unsure_dates"], "smooth_yes": m["smooth_sphere"]["good_dates"],
                          "smooth_planned": m["smooth_sphere"]["verdict_planned"],
                          "grid": m["horizon"].get("dem_label", "").split(";")[0],
                          "next": [x[:10] for x in m["next_good_dates"][:2]],
                          "why": (d0.get("reasons") or d0.get("unsure_because") or [])[:2]}))
