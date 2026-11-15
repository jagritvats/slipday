"""Time /api/robust-sites on a running server and print the rows.  python -I call_robust.py <base url> [start] [candidates]"""
import json
import sys
import time
import urllib.request

base = sys.argv[1].rstrip("/")
start = sys.argv[2] if len(sys.argv) > 2 else "2026-11-18T00:00:00Z"
cand = int(sys.argv[3]) if len(sys.argv) > 3 else 12
body = {"start": start, "n_dates": 60, "need_sun_h": 240, "need_earth_h": 100, "window_days": 14, "scatter_m": 100, "candidates": cand}
for attempt in ("first", "second"):
    t0 = time.time()
    req = urllib.request.Request(base + "/api/robust-sites", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        out = json.loads(r.read())
    print(attempt, "call:", round(time.time() - t0, 2), "s")
print("start", out["start_utc"], "| candidates", out["candidates"], "| stay yes", out["stay_yes"], "| notes", out["notes"])
for x in out["rows"]:
    print(json.dumps({k: x[k] for k in ("lat", "lon", "verdict", "slip_margin_days", "map_margin_days", "good_dates", "unsure_dates",
                                         "map_good_dates", "points_passing", "points", "sunlit_h", "earth_h", "grid")}))
