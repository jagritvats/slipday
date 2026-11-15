"""Numbers quoted in LOCAL_PASS_2_RESULTS.md, printed from the app's own endpoints (in-process test client).

    python scripts/local_pass_tools/measure_pass2.py

Set SLIPDAY_HORIZON_CACHE to a scratch copy of data/horizon_cache if nothing new should land in the
shipped cache (the map points checked against the mission card need new skylines).
"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from fastapi.testclient import TestClient  # noqa: E402

from slipday import field, robust, sites  # noqa: E402
from slipday.api import app  # noqa: E402
from slipday.metrics import Criteria  # noqa: E402

c = TestClient(app)
L = "2026-11-18T00:00:00Z"
CASES = [("shackleton", L, 240), ("malapert_earth", L, 240), ("ridge_c2", L, 240), ("im2", "2025-03-06T17:00:00Z", 240),
         ("im1", "2024-02-22T23:00:00Z", 168)]


def post(path, body):
    t = time.perf_counter()
    r = c.post(path, json=body)
    return r.json(), round(time.perf_counter() - t, 2)


print("== why it flips (first call, repeat call, seconds)")
for sid, landing, sun in CASES:
    body = {"site": {"id": sid}, "landing": landing, "need_sun_h": sun}
    w, t1 = post("/api/why", body)
    _, t2 = post("/api/why", body)
    td = w["touchdown"]
    print(f"{sid}: verdict {w['verdict']}, margin {w['slip_margin_days']} d, {t1} s then {t2} s; window sunlit {w['hours']['sunlit']} "
          f"(smooth {w['hours']['smooth_sunlit']}), Earth {w['hours']['earth']} (smooth {w['hours']['smooth_earth']}); "
          f"next sunset {td['next_sunset'] and td['next_sunset']['hours_from_now']} h, next Earthset {td['next_earthset'] and td['next_earthset']['hours_from_now']} h")
    print("   ", w["flip"]["text"])
    ps = w.get("permanent_shadow") or {}
    print(f"    nearest permanent shadow {ps.get('dist_km')} km at bearing {ps.get('bearing_deg')}, site cell shadowed {ps.get('site_cell_is_shadowed')}")

print("== terrain against a smooth sphere, verdict by verdict over 60 dates")
for sid, landing, sun in CASES:
    m, _ = post("/api/mission", {"site": {"id": sid}, "landing": landing, "need_sun_h": sun})
    wy = sum(1 for d in m["days"] if d["smooth_sphere_passes"] and d["verdict"] != "yes")
    wn = sum(1 for d in m["days"] if not d["smooth_sphere_passes"] and d["verdict"] == "yes")
    print(f"{sid}: terrain yes {m['good_dates']}, not sure {m['unsure_dates']}; smooth sphere yes {m['smooth_sphere']['good_dates']}; "
          f"answers differ on {wy + wn} of {len(m['days'])} dates ({wy} smooth yes where terrain is not, {wn} smooth no where terrain is yes)")

print("== chance by lander class and landing circles (planned date; range)")
for sid, landing, sun in CASES:
    body = {"site": {"id": sid}, "landing": landing, "need_sun_h": sun}
    lc, t1 = post("/api/lander-classes", body)
    cc, _ = post("/api/landing-circles", body)
    print(f"{sid} ({lc['points']} points, {t1} s):")
    for k in lc["classes"]:
        print(f"    {k['label']}: {k['planned_pct']} % ({k['planned_range_pct'][0]} to {k['planned_range_pct'][1]}); directions "
              f"{k['planned_direction_range_pct']}, resampling {k['planned_sampling_range_pct']}; 90 % or more for {k['margin_90_days']} d; "
              f"chance on days 0 to 8: {k['chance_pct'][:9]}")
    print("    circles: " + "; ".join(f"{k['label']} {k['planned_pct']} % ({k['planned_range_pct'][0]} to {k['planned_range_pct'][1]})" for k in cc["classes"] if k["resolvable"]))

print("== year ribbon")
for sid, landing, sun in CASES[:1] + CASES[3:]:
    y, t1 = post("/api/year-ribbon", {"site": {"id": sid}, "landing": landing, "need_sun_h": sun})
    print(f"{sid}: yes {y['yes']}, not sure {y['not_sure']}, no {y['no']} of {y['days']}; smooth sphere yes {y['smooth_sphere_yes']}; "
          f"{y['yes_runs']} runs of yes, longest {y['longest_yes_run_days']} d; months without a yes {y['months_without_a_yes']}; {t1} s")

print("== scatter-checked slip-margin map")
fld = field.load()
for start, sun in ((L, 240), ("2026-12-15T00:00:00Z", 240), ("2026-11-14T00:00:00Z", 240), (L, 168), ("2027-03-01T00:00:00Z", 240)):
    m, t1 = post("/api/robust-map", {"start": start, "n_dates": 60, "need_sun_h": sun})
    _, t2 = post("/api/robust-map", {"start": start, "n_dates": 60, "need_sun_h": sun})
    k = m["counts"]
    print(f"{start} need {sun} h: {k['single_point_coloured']} points pass at the map point; re-checked {k['re_checked']}, not re-checked {k['not_re_checked']}; "
          f"keep a margin {k['keep_a_margin']} (same {k['keep_the_same_margin']}, shorter {k['keep_a_shorter_margin']}), lose it {k['lose_their_margin']}; "
          f"largest margin {k['largest_single_point_margin']} -> {k['largest_surviving_margin']}; 5 days or more {k['single_margin_5_or_more']} -> {k['surviving_margin_5_or_more']}; "
          f"histogram {k['surviving_margin_histogram']}; {t1} s then {t2} s")
m, _ = post("/api/robust-map", {"start": L, "n_dates": 60})
rob, single, npass = (np.array(m["layers"][x]) for x in ("robust", "single", "points_passing"))
print("stored scatter skylines:", m["stored"]["points"], "map points, complete", m["stored"]["complete"])
print("touchdown points passing on the planned date at the points that lose their margin:",
      {int(v): int((npass[rob == -3] == v).sum()) for v in np.unique(npass[rob == -3])})
# like for like against the mission card (float skylines) at 12 map points spread over the classes
rng = np.random.default_rng(7)
pool = np.concatenate([rng.choice(np.nonzero(rob >= 3)[0], 4, replace=False), rng.choice(np.nonzero((rob >= 0) & (rob < 3))[0], 4, replace=False),
                       rng.choice(np.nonzero(rob == -3)[0], 4, replace=False)])
same = 0
for i in pool:
    la, lo = round(float(fld["lat"][i]), 5), round(float(fld["lon"][i]), 5)
    card = robust.mission_card(sites.custom_site("p", la, lo), L, 240.0, 100.0, 14.0, Criteria(), 0.0, 2.0, 100.0, 60)
    run = -1
    for d in card["days"]:
        if d["points_passing"] != d["points"]:
            break
        run = d["slip_days"]
    mine = int(rob[i]) if rob[i] >= 0 else -1
    same += int(mine == run and int(npass[i]) == card["days"][0]["points_passing"])
    print(f"   map point {i}: map says {mine} d with {int(npass[i])} of 13 passing; mission card (13 points only) {run} d with "
          f"{card['days'][0]['points_passing']} of 13; card verdict {card['verdict']} margin {card['slip_margin_days']}")
print(f"identical at {same} of {len(pool)} points")
ps = c.get("/api/map?half_km=30").json()["permanent_shadow"]
print("== permanent shadow in the 60 km close-up:", ps["shown_km2"], "km2 in", ps["cell_m"], "m cells")
