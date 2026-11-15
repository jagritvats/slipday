"""Landing-circle shares for the review's cases.  python measure_circles.py <entry root> [--sites a,b]"""
import json
import os
import sys
import tempfile
import time

root = sys.argv[1]
sys.path.insert(0, root)
os.environ.setdefault("SLIPDAY_HORIZON_CACHE", tempfile.mkdtemp(prefix="slipday_measure_cache_"))
from fastapi.testclient import TestClient  # noqa: E402

from slipday import demstore  # noqa: E402
from slipday.api import app  # noqa: E402

client = TestClient(app)
print("grids:", demstore.status()["label"])
CASES = [("shackleton", "2026-11-18", {}), ("malapert_earth", "2026-11-18", {}), ("ridge_c2", "2026-11-18", {}),
         ("im2", "2025-03-06T17:00:00Z", {"need_sun_h": 240}), ("im1", "2024-02-22T23:00:00Z", {"need_sun_h": 168})]
for i, a in enumerate(sys.argv):
    if a == "--sites":
        keep = set(sys.argv[i + 1].split(","))
        CASES = [c for c in CASES if c[0] in keep]
for sid, when, need in CASES:
    t0 = time.time()
    r = client.post("/api/landing-circles", json={"site": {"id": sid}, "landing": when, **need}).json()
    dt = time.time() - t0
    t1 = time.time()
    client.post("/api/landing-circles", json={"site": {"id": sid}, "landing": when, **need})
    print(sid, when, need, "points", r.get("points"), "res", r.get("grid_resolution_m"), f"cold {dt:.1f} s, warm {time.time() - t1:.2f} s")
    for c in r["classes"]:
        if not c["resolvable"]:
            print("   ", c["label"], "NOT RESOLVABLE:", c["why"])
        else:
            print("   ", json.dumps({"circle": c["label"], "pts": c["points"], "planned_pct": c["planned_pct"],
                                     "margin_90": c["margin_90_days"], "dates_at_90": c["dates_at_90"],
                                     "first10": c["share_pct"][:10]}))
