"""Mission-card verdicts for the review's six cases, on whatever grids the DEM dir provides.

    python measure_cards.py <entry root> [--scatter 100,150,200] [--label text]

Uses a private horizon cache so the shipped one is not touched.
"""
import json
import os
import sys
import tempfile
import time

root = sys.argv[1]
sys.path.insert(0, root)
os.environ.setdefault("SLIPDAY_HORIZON_CACHE", tempfile.mkdtemp(prefix="slipday_measure_cache_"))
scatters = [100.0]
label = ""
for i, a in enumerate(sys.argv):
    if a == "--scatter":
        scatters = [float(x) for x in sys.argv[i + 1].split(",")]
    if a == "--label":
        label = sys.argv[i + 1]

from fastapi.testclient import TestClient  # noqa: E402

from slipday import demstore  # noqa: E402
from slipday.api import app  # noqa: E402

client = TestClient(app)
print(label, "| grids:", demstore.status()["label"], "| not installed:", demstore.status()["not_installed"])
CASES = [("shackleton", "2026-11-18"), ("malapert_earth", "2026-11-18"), ("ridge_c2", "2026-11-18"),
         ("shackleton_rim", "2026-11-18"), ("im2", "2025-03-06T17:00:00Z"), ("im1", "2024-02-22T23:00:00Z")]
extra = {}
for i, a in enumerate(sys.argv):
    if a == "--need":
        s, e = sys.argv[i + 1].split(",")
        extra = {"need_sun_h": float(s), "need_earth_h": float(e)}
for sc in scatters:
    for sid, when in CASES:
        t0 = time.time()
        m = client.post("/api/mission", json={"site": {"id": sid}, "landing": when, "scatter_m": sc, **extra}).json()
        d0 = m["days"][0]
        print(json.dumps({"site": sid, "landing": when, "scatter_m": sc, "sure_scatter_m": m["sure"].get("scatter_m"),
                          "verdict": m["verdict"], "margin": m["slip_margin_days"], "target_margin": m["target_only_margin_days"],
                          "yes": m["good_dates"], "not_sure": m["unsure_dates"], "pts": f"{d0['points_passing']}/{d0['points']}",
                          "sun_h": d0["sunlit_h"], "earth_h": d0["earth_h"], "smooth_yes": m["smooth_sphere"]["good_dates"],
                          "grid": m["horizon"].get("dem_label", "").split(";")[0], "s": round(time.time() - t0, 1)}))
