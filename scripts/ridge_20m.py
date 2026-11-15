"""The headline example on the 20 m grid: what changes when the connecting ridge is sampled four times finer.

    python scripts/fetch_ldem20_crop.py      # once: 49 tiles of NASA's 20 m mosaic around the pole, about 28 MB
    python scripts/ridge_20m.py              # prints the same figures on the 80 m stack and on the 20 m stack
    python scripts/ridge_20m.py --save       # and stores the comparison in data/validation/finer_grid_check.json,
                                             # which the page shows beside the example and among the validation tiles

The 20 m crop covers 71.7 km around the pole; beyond it the 80 m grid and the coarser ones take over, as
in the app.  Everything is computed with the app's own functions (mission card, landing circles, lander
classes, year-long statistics), only the terrain stack differs.  On the 20 m stack "the coarser grid" of
the card's check is the 80 m grid.

Nothing here changes what the page serves: the page stays on the 80 m grid, because the slip-margin map,
the stored validation and the tests were all made on it.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("SLIPDAY_HORIZON_CACHE", tempfile.mkdtemp(prefix="slipday_ridge20_"))

from slipday import api, demstore, robust, sites, why  # noqa: E402
from slipday.geometry import Site  # noqa: E402
from slipday.metrics import Criteria, span_stats  # noqa: E402
from slipday.sites import get_site, horizon_for  # noqa: E402

L = "2026-11-18T00:00:00Z"
SITES = [("shackleton", "Shackleton connecting ridge C1 (the default example)"), ("ridge_c2", "Connecting ridge C2")]
if "--c1" in sys.argv:
    SITES = SITES[:1]


def run(dem_dir: str) -> dict:
    os.environ["SLIPDAY_DEM_DIR"] = dem_dir
    demstore.reload()
    sites._terrain_profile.cache_clear()
    api._stats.cache_clear()
    why._cache.clear()
    crit = Criteria()
    out = {"stack": demstore.status()["label"]}
    for sid, name in SITES:
        t0 = time.time()
        s = get_site(sid)
        card = robust.mission_card(s, L, 240.0, 100.0, 14.0, crit, 0.0, 2.0, 100.0, 60)
        year = robust.mission_card(s, L, 240.0, 100.0, 14.0, crit, 0.0, 2.0, 100.0, 365)
        circles = robust.landing_circles(s, L, 240.0, 100.0, 14.0, crit, 0.0, 2.0, 60)
        classes = robust.lander_classes(s, L, 240.0, 100.0, 14.0, crit, 0.0, 2.0, 60)
        w = why.why(s, L, 240.0, 100.0, 14.0, crit, 0.0, 2.0, 100.0, 60)
        anyc = Criteria(0.0, -90.0, -90.0, 0.0)                       # any part of the solar disc: what the papers quote
        st = span_stats(s, L, 365.0, 60, anyc)
        pts = []
        for la, lo in robust.scatter_points(s.lat, s.lon, 100.0):
            p = span_stats(Site(s.name, la, lo, horizon=horizon_for(la, lo, 0.0, 2.0, True)), L, 365.0, 60, anyc)
            pts.append((p["any_light_pct"], p["longest_dark_h"]))
        out[sid] = {
            "name": name, "site_name": s.name, "lat": s.lat, "lon": s.lon, "points": card["sure"]["points"],
            "points_passing_by_day": [d["points_passing"] for d in card["days"]],
            "grid_under_site": s.horizon.meta["dem_label"], "site_height_m": s.horizon.meta["site_height_m"],
            "skyline_deg": [s.horizon.meta["min_el_deg"], s.horizon.meta["max_el_deg"]],
            "verdict": card["verdict"], "slip_margin_days": card["slip_margin_days"], "sure": card["sure"]["text"],
            "points_passing_by_day_0_to_9": [d["points_passing"] for d in card["days"][:10]],
            "sunlit_h_and_earth_h_as_planned": [card["days"][0]["sunlit_h"], card["days"][0]["earth_h"]],
            "clear_yes_dates_of_60": card["good_dates"], "not_sure_dates_of_60": card["unsure_dates"],
            "clear_yes_dates_of_365": year["good_dates"], "not_sure_dates_of_365": year["unsure_dates"],
            "what_ends_the_margin": w["flip"]["text"] if w["flip"] else None,
            "landing_circles_planned_pct": {k["label"]: (k["planned_pct"], k["planned_range_pct"]) for k in circles["classes"] if k["resolvable"]},
            "lander_classes_planned_pct": {k["label"]: (k["planned_pct"], k["planned_range_pct"]) for k in classes["classes"] if k["resolvable"]},
            "any_sun_pct_365_days": {"at_the_point": st["any_light_pct"], "range_within_100_m": [min(p[0] for p in pts + [(st["any_light_pct"], 0)]),
                                                                                              max(p[0] for p in pts + [(st["any_light_pct"], 0)])]},
            "longest_darkness_h": {"at_the_point": st["longest_dark_h"], "range_within_100_m": [min(p[1] for p in pts), max(p[1] for p in pts)]},
            "seconds": round(time.time() - t0, 1),
        }
    return out


def main() -> None:
    d20 = os.path.join(ROOT, "data", "dem20")
    if not os.path.exists(os.path.join(d20, "ldem_pole_20m_f32.npy")):
        sys.exit("the 20 m crop is not here: run scripts/fetch_ldem20_crop.py first")
    res = {"80 m stack": run(os.path.join(ROOT, "data", "dem")), "20 m stack": run(d20)}
    print(json.dumps(res, indent=1))
    if "--save" in sys.argv:
        word = {"yes": "Yes", "not sure": "Not sure", "no": "No", "n/a": "not computed"}
        entries = []
        for sid, _ in SITES:
            a, b = res["80 m stack"][sid], res["20 m stack"][sid]
            p, n = b["points_passing_by_day"], b["points"]
            text = (f"On NASA's 20 m LOLA grid (off-line check) this example reads {word[b['verdict']]} on the planned date: "
                    f"{p[0]} of {n} touchdown points pass")
            if b["verdict"] == "yes":
                text += f", with {b['slip_margin_days']} days of slip margin"
            else:
                end = 0
                while end + 1 < len(p) and p[end + 1] == n:
                    end += 1
                if end >= 1:
                    text += f"; slips of 1 to {end} days pass at all {n}"
            text += (f". On the 80 m grid used here: {word[a['verdict']]}, {a['points_passing_by_day'][0]} of {a['points']}"
                     + (f", {a['slip_margin_days']} days of margin" if a["verdict"] == "yes" else "") + ".")
            entries.append({"site_id": sid, "lat": b["lat"], "lon": b["lon"], "landing_utc": L, "need_sun_h": 240.0,
                            "need_earth_h": 100.0, "window_days": 14.0, "scatter_m": 100.0, "text": text,
                            "fine": {k: b[k] for k in b if k not in ("name", "site_name", "lat", "lon")},
                            "used": {k: a[k] for k in a if k not in ("name", "site_name", "lat", "lon")}})
        store = {"made_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "fine_grid": res["20 m stack"]["stack"], "used_grid": res["80 m stack"]["stack"],
                 "source": "LDEM_80S_20MPP_ADJ.TIF, LOLA south-pole 20 m mosaic, NASA GSFC PGDA product 90 (Barker et al. 2023): the 71.7 km "
                           "square around the pole, fetched by range request (scripts/fetch_ldem20_crop.py); the 80 m grid and coarser ones beyond it",
                 "what": "The same example worked out with the app's own functions on a terrain stack whose finest grid is the 20 m crop. "
                         "The page itself stays on the 80 m grid: the slip-margin map, the stored validation and the tests were made on it.",
                 "entries": entries}
        path = os.path.join(ROOT, "data", "validation", "finer_grid_check.json")
        try:                                  # keep the opening-example search of scripts/pick_opening_example.py
            with open(path) as fh:
                old = json.load(fh)
            if "opening_example" in old:
                store["opening_example"] = old["opening_example"]
        except (OSError, ValueError):
            pass
        with open(path, "w") as fh:
            json.dump(store, fh, indent=1)
        print("stored", path, file=sys.stderr)


if __name__ == "__main__":
    main()
