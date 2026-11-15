"""The four real-landing examples with the need each one now carries.  python measure_replays_final.py <entry root>"""
import json
import os
import sys
import tempfile

root = sys.argv[1]
sys.path.insert(0, root)
os.environ.setdefault("SLIPDAY_HORIZON_CACHE", tempfile.mkdtemp(prefix="slipday_measure_cache_"))
from fastapi.testclient import TestClient  # noqa: E402

from slipday import demstore, replay  # noqa: E402
from slipday.api import app  # noqa: E402

client = TestClient(app)
print("grids:", demstore.status()["label"])
for x in replay.MISSIONS:
    body = {"site": {"id": x["site"]}, "landing": x["landing"], "need_sun_h": x["need_sun_h"], "need_earth_h": x["need_earth_h"],
            "window_days": x["window_days"]}
    m = client.post("/api/mission", json=body).json()
    c = client.post("/api/landing-circles", json=body).json()
    d0 = m["days"][0]
    print(json.dumps({"id": x["id"], "need_sun_h": x["need_sun_h"], "kind": x["need_kind"], "verdict": m["verdict"], "margin": m["slip_margin_days"],
                      "sun_h": d0["sunlit_h"], "earth_h": d0["earth_h"], "pts": f"{d0['points_passing']}/{d0['points']}",
                      "scatter_used_m": m["sure"]["scatter_m"], "yes": m["good_dates"], "not_sure": m["unsure_dates"],
                      "smooth_yes": m["smooth_sphere"]["good_dates"], "grid": m["horizon"].get("dem_label", "").split(";")[0],
                      "validated": m["sure"]["validated"], "next": [t[:10] for t in m["next_good_dates"][:2]],
                      "circles": [(k["label"], k.get("planned_pct"), k.get("margin_90_days")) if k["resolvable"] else (k["label"], "n/r") for k in c["classes"]]}))
    print("   ", " ".join(m["sentences"])[:330])
