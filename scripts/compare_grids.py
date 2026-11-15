"""The opening example and the Shackleton ridge C1 on three terrain grids: 80 m, 20 m and the LOLA team's 5 m site
models (Site07 "Peak near Shackleton" covers the opening example, Site01 "Connecting ridge" covers C1).

    python scripts/compare_grids.py            # runs each stack in its own process; prints a table
    python scripts/compare_grids.py --one DIR SITE   (internal)

Same card as the page: landing 18 Nov 2026 00:00 UTC, 240 sunlit hours and 100 hours of Earth contact in 14 days,
Sun and Earth at touchdown, station rule on, 13 touchdown points within 100 m, 2 m observer.  Writes
data/validation/grids_5m.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = "2026-11-18T00:00:00Z"
CASES = [("robust_pick", "data/dem5/site07"), ("shackleton", "data/dem5/site01")]


def one(dem_dir: str, site_id: str) -> dict:
    os.environ["SLIPDAY_DEM_DIR"] = os.path.join(ROOT, dem_dir)
    os.environ["SLIPDAY_HORIZON_CACHE"] = tempfile.mkdtemp(prefix="slipday_g5_")
    sys.path.insert(0, ROOT)
    import numpy as np
    from slipday import demstore, sites, robust
    from slipday.metrics import Criteria
    demstore.reload()
    s = sites.get_site(site_id)
    m = robust.mission_card(s, L, 240, 100, 14, Criteria(stations=True), 0.0, 2.0, 100.0, 15)
    dem = demstore.get_dem()
    h = float(dem.height_m(np.array([s.lat]), np.array([s.lon]))[0])
    return {"grid": s.horizon.meta["dem_label"].split(";")[0], "site_height_m": round(h, 1), "verdict": m["verdict"],
            "slip_margin_days": m["slip_margin_days"], "points_passing_by_day": [d["points_passing"] for d in m["days"][:12]],
            "sunlit_h": m["days"][0]["sunlit_h"], "earth_h": m["days"][0]["earth_h"], "reasons": m["days"][0]["reasons"],
            "next_good": m["next_good_dates"][:3]}


def main() -> None:
    if "--one" in sys.argv:
        i = sys.argv.index("--one")
        print(json.dumps(one(sys.argv[i + 1], sys.argv[i + 2])))
        return
    out = {"landing": L, "need": "240 sunlit h, 100 Earth h in 14 days; Sun and Earth at touchdown; station rule on", "rows": []}
    for site, d5 in CASES:
        for d in ("data/dem", "data/dem20", d5):
            r = subprocess.run([sys.executable, __file__, "--one", d, site], capture_output=True, text=True, cwd=ROOT)
            line = [x for x in r.stdout.splitlines() if x.startswith("{")]
            res = json.loads(line[-1]) if line else {"error": r.stderr[-400:]}
            res.update({"site": site, "stack": d})
            out["rows"].append(res)
            print(site, d, "|", res.get("grid"), "| h", res.get("site_height_m"), "|", res.get("verdict"), res.get("slip_margin_days"),
                  "| points by day", res.get("points_passing_by_day"), "| sun", res.get("sunlit_h"), "earth", res.get("earth_h"),
                  res.get("error", ""), flush=True)
    json.dump(out, open(os.path.join(ROOT, "data", "validation", "grids_5m.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
