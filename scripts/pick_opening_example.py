"""Choose the page's opening example by a written rule (LOCAL_PASS_2_RESULTS.md, section H.1).

    python scripts/pick_opening_example.py --list          # the candidates in order and the 20 m tiles each needs
    python scripts/pick_opening_example.py [--max 6] [--until HH:MM] [--save]

Scenario: landing 18 Nov 2026 00:00 UTC, 240 sunlit hours and 100 hours of Earth contact in 14 days, 100 m
scatter, default rules.  Candidates: the points of the scatter-checked slip-margin map that keep 5 or more
days of margin at all 13 touchdown points on the 80 m grid, in the order of the slip-robust list (largest
surviving margin, then most good landing dates of the single-point map, then lowest map index).  For each
in turn the full mission card is worked out on the 80 m stack and on the stack whose finest grid is the
20 m crop (data/dem20).  The first whose card is a clear "Yes" with at least one day of margin on both
is the opening example.  Every candidate tried is printed, failures included.

`--save` adds every candidate tried to data/validation/finer_grid_check.json (beside the two ridge sites
that scripts/ridge_20m.py stores) and marks the chosen one.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("SLIPDAY_HORIZON_CACHE", tempfile.mkdtemp(prefix="slipday_pick_"))

from slipday import api, demstore, field, robust, scatterfield, sites, why  # noqa: E402
from slipday.metrics import Criteria  # noqa: E402

L = "2026-11-18T00:00:00Z"
NEED = dict(sun=240.0, earth=100.0, window=14.0, scatter=100.0)
R = 1737400.0
TILE_M = 512 * 20.0
NEAR_M = 10300.0


def _reset(dem_dir: str) -> None:
    os.environ["SLIPDAY_DEM_DIR"] = dem_dir
    demstore.reload()
    sites._terrain_profile.cache_clear()
    api._stats.cache_clear()
    why._cache.clear()
    scatterfield.reload()


def _xy(lat: float, lon: float) -> tuple[float, float]:
    r = 2.0 * R * np.tan(np.pi / 4 - np.deg2rad(abs(lat)) / 2)
    return float(r * np.sin(np.deg2rad(lon))), float(r * np.cos(np.deg2rad(lon)))


def _tiles(lat: float, lon: float) -> tuple[int, int, int, int]:
    """Rows and columns of the 20 m mosaic's 512-pixel tiles within NEAR_M of a point (first row, last row, first col, last col)."""
    x, y = _xy(lat, lon)
    c0, c1 = int((x - NEAR_M + 304000.0) // TILE_M), int((x + NEAR_M + 304000.0) // TILE_M)
    r0, r1 = int((304000.0 - (y + NEAR_M)) // TILE_M), int((304000.0 - (y - NEAR_M)) // TILE_M)
    return r0, r1, c0, c1


def candidates() -> list[dict]:
    _reset(os.path.join(ROOT, "data", "dem"))
    crit = Criteria()
    rm = scatterfield.robust_margin(L, 60, NEED["window"], crit, 0.0, NEED["sun"], NEED["earth"], True, True)
    pd = field.per_date(L, 60, 24, NEED["window"], crit, 0.0)
    st = field.statistics(pd, NEED["sun"], NEED["earth"], True, True)
    rob, good = rm["robust"], st["good"]
    idx = np.nonzero(rob >= 5)[0]
    order = sorted(idx.tolist(), key=lambda i: (-int(rob[i]), -int(good[i]), int(i)))
    fld = field.load()
    out = []
    for rank, i in enumerate(order, 1):
        la, lo = round(float(fld["lat"][i]), 5), round(float(fld["lon"][i]), 5)
        out.append({"rank": rank, "map_index": int(i), "lat": la, "lon": lo, "surviving_margin_days": int(rob[i]),
                    "single_point_margin_days": int(rm["single"][i]), "good_dates_single_point": int(good[i]),
                    "tiles_needed_r0_r1_c0_c1": _tiles(la, lo)})
    return out


# --earth-margin X: the same rule with the Earth's centre required X degrees above the skyline (pass 3, rule R1:
# reported beside the opening example, never used to choose it; with --earth-margin, --save is refused)
EARTH_MARGIN = float(sys.argv[sys.argv.index("--earth-margin") + 1]) if "--earth-margin" in sys.argv else 0.0


def card(dem_dir: str, lat: float, lon: float) -> dict:
    _reset(dem_dir)
    name = f"{abs(lat):.3f} S, {abs(lon):.3f} {'W' if lon < 0 else 'E'}"
    s = sites.custom_site(name, lat, lon)
    crit = Criteria(0.5, -90.0, -90.0, EARTH_MARGIN)
    m = robust.mission_card(s, L, NEED["sun"], NEED["earth"], NEED["window"], crit, 0.0, 2.0, NEED["scatter"], 60)
    w = why.why(s, L, NEED["sun"], NEED["earth"], NEED["window"], crit, 0.0, 2.0, NEED["scatter"], 60)
    return {"grid": s.horizon.meta["dem_label"].split(";")[0], "verdict": m["verdict"], "slip_margin_days": m["slip_margin_days"],
            "points": m["sure"]["points"], "points_passing_by_day": [d["points_passing"] for d in m["days"]],
            "coarse_passes": m["sure"]["coarse_passes"], "near_passes": m["sure"]["near_passes"], "sure": m["sure"]["text"],
            "sunlit_h": m["days"][0]["sunlit_h"], "earth_h": m["days"][0]["earth_h"],
            "clear_yes_dates_of_60": m["good_dates"], "not_sure_dates_of_60": m["unsure_dates"],
            "next_good_dates": m["next_good_dates"], "site_height_m": s.horizon.meta["site_height_m"],
            "what_ends_the_margin": (w["flip"] or {}).get("text"), "ended_by": (w["flip"] or {}).get("ended_by")}


def main() -> None:
    cands = candidates()
    with open(os.path.join(ROOT, "data", "dem20", "dems.json")) as fh:
        crop = json.load(fh)["dems"][0]
    arr = np.load(os.path.join(ROOT, "data", "dem20", crop["path"]), mmap_mode="r")
    col_first = int(round((crop["x0_m"] - 10.0 + 304000.0) / TILE_M))
    row_first = int(round((304000.0 - (crop["y0_m"] + 10.0)) / TILE_M))

    def have(row: int, col: int) -> bool:        # a tile is on disk when its block of the array holds heights
        i, j = (row - row_first) * 512, (col - col_first) * 512
        return bool(0 <= i < arr.shape[0] and 0 <= j < arr.shape[1] and np.isfinite(arr[i + 256, j + 256]))

    for c in cands:
        r0, r1, c0, c1 = c["tiles_needed_r0_r1_c0_c1"]
        c["tiles_on_disk"] = all(have(r, k) for r in range(r0, r1 + 1) for k in range(c0, c1 + 1))
    print(f"{len(cands)} candidates; 20 m array on disk: {arr.shape[0] // 512} tile rows from {row_first}, {arr.shape[1] // 512} tile columns from {col_first}")
    for c in cands:
        print(f"  {c['rank']:>2}. map point {c['map_index']}: {abs(c['lat']):.3f} S, {abs(c['lon']):.3f} {'W' if c['lon'] < 0 else 'E'}; "
              f"{c['surviving_margin_days']} d at all 13 points (single point {c['single_point_margin_days']} d), "
              f"{c['good_dates_single_point']} good dates; tiles {c['tiles_needed_r0_r1_c0_c1']} "
              f"{'on disk' if c['tiles_on_disk'] else 'NOT all on disk'}")
    if "--list" in sys.argv:
        return
    limit = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 6
    until = sys.argv[sys.argv.index("--until") + 1] if "--until" in sys.argv else None
    tried, chosen = [], None
    for c in cands[:limit]:
        if until and time.strftime("%H:%M") >= until and time.strftime("%H") != "23":
            print("time limit reached")
            break
        if not c["tiles_on_disk"]:
            c["skipped"] = "20 m tiles not all on disk; fetch them with scripts/fetch_ldem20_crop.py --first/--last and run again"
            tried.append(c)
            print(json.dumps(c))
            continue
        t0 = time.time()
        c["card_80m"] = card(os.path.join(ROOT, "data", "dem"), c["lat"], c["lon"])
        c["card_20m"] = card(os.path.join(ROOT, "data", "dem20"), c["lat"], c["lon"])
        ok = lambda k: k["verdict"] == "yes" and k["slip_margin_days"] >= 1  # noqa: E731
        c["passes"] = bool(ok(c["card_80m"]) and ok(c["card_20m"]))
        c["seconds"] = round(time.time() - t0, 1)
        tried.append(c)
        for g in ("card_80m", "card_20m"):
            k = c[g]
            print(f"  candidate {c['rank']} on {k['grid']}: {k['verdict']}, margin {k['slip_margin_days']} d, points passing days 0 to 9 "
                  f"{k['points_passing_by_day'][:10]}, coarse {k['coarse_passes']}, near {k['near_passes']}; {k['sunlit_h']} sunlit h, {k['earth_h']} Earth h")
        print(f"  candidate {c['rank']}: {'PASSES' if c['passes'] else 'fails'} ({c['seconds']} s)", flush=True)
        if c["passes"]:
            chosen = c
            break
    print(json.dumps({"tried": tried, "chosen_rank": chosen["rank"] if chosen else None}, indent=1))
    if "--save" in sys.argv and EARTH_MARGIN:
        sys.exit("--save is for the opening example's own rule (mask 0); the --earth-margin run is a report only")
    if "--save" in sys.argv:
        path = os.path.join(ROOT, "data", "validation", "finer_grid_check.json")
        with open(path) as fh:
            store = json.load(fh)
        store["opening_example"] = {
            "rule": "LOCAL_PASS_2_RESULTS.md section H.1", "made_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "landing_utc": L, "need_sun_h": NEED["sun"], "need_earth_h": NEED["earth"], "window_days": NEED["window"],
            "scatter_m": NEED["scatter"], "candidates": len(cands), "tried": tried,
            "chosen": {k: chosen[k] for k in ("rank", "map_index", "lat", "lon")} if chosen else None}
        with open(path, "w") as fh:
            json.dump(store, fh, indent=1)
        print("stored in", path, file=sys.stderr)


if __name__ == "__main__":
    main()
