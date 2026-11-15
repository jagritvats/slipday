"""The headline numbers of the page on one terrain stack, for comparing the 80 m stack with the live finer stack.

    SLIPDAY_DEM_DIR=<stack> SLIPDAY_HORIZON_CACHE=<dir> python scripts/live_numbers.py OUT.json

Opening example, C1 and IM-1 (its flown window): verdict, margin, touchdown points passing, sunlit and Earth
hours, the objective line's clearances, the Earth margin, what ends the margin, the next windows, the year
ribbon, and (opening example) the other-sites search.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main(out_path: str) -> None:
    from fastapi.testclient import TestClient
    from slipday.api import app
    c = TestClient(app)
    res = {"dem_dir": os.environ.get("SLIPDAY_DEM_DIR"), "sites": {}}
    plans = {"robust_pick": ("2026-11-18T00:00:00Z", 240, 100), "shackleton": ("2026-11-18T00:00:00Z", 240, 100),
             "im1": ("2024-02-22T23:00:00Z", 168, 100)}
    for sid, (L, ns, ne) in plans.items():
        body = {"site": {"id": sid}, "landing": L, "need_sun_h": ns, "need_earth_h": ne, "earth_stations": True}
        m = c.post("/api/mission", json=body).json()
        w = c.post("/api/why", json=dict(body, day=0)).json()
        em = c.post("/api/earth-mask", json=body).json()
        win = c.post("/api/windows", json=body).json()
        rib = c.post("/api/year-ribbon", json=dict(body, days=365)).json()
        td = w.get("touchdown", {})
        r = {"grid": m.get("terrain_grid"), "verdict": m["verdict"], "margin": m["slip_margin_days"],
             "points": m["sure"]["points_passing"], "sunlit_h": m["days"][0]["sunlit_h"], "earth_h": m["days"][0]["earth_h"],
             "next_good": m["next_good_dates"][:3],
             "sun_clear_deg": round(td.get("sun_el", 0) - td.get("sun_skyline_el", 0), 2),
             "earth_clear_deg": round(td.get("earth_el", 0) - td.get("earth_skyline_el", 0), 2),
             "flip": (w.get("flip") or {}).get("text", "")[:240],
             "earth_mask_yes_up_to": em.get("yes_up_to_deg"), "earth_clear_at_td": em.get("clearance_at_touchdown_deg"),
             "windows": [(x["landing_utc"][:10], x["verdict"], x["slip_margin_days"], x["fails_on"]) for x in win.get("rows", [])],
             "ribbon": {k: rib.get(k) for k in ("yes", "not_sure", "no", "days")}}
        if sid == "robust_pick":
            o = c.post("/api/window-options", json=dict(body, alternatives=[{"id": "robust_pick"}, {"id": "shackleton"}, {"id": "im2"}, {"id": "im1"}])).json()
            r["options"] = [{"window": x["landing_utc"][:10], "sites_checked": x["sites_checked"], "sites_yes": len(x["sites_yes"]),
                             "fragile": sum(1 for y in x["sites_yes"] if y["fragile"])} for x in o.get("rows", [])]
        res["sites"][sid] = r
        print(sid, json.dumps(r)[:300], flush=True)
    json.dump(res, open(out_path, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
