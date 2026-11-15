"""Further checks of the terrain model, added in round 3.  Run after scripts/validate_terrain.py.

    python3 scripts/validate_more.py <folder with the LOLA reference maps> [--only a,b,c,d,e,f,s]

  a  well-lit ridge pixels: the sunlit share at a seeded sample of pixels the 60 m LOLA map rates above
     60 %, where the 0.8-point average agreement does not hold
  b  how firm the published-point match at the connecting ridge (C1, 2 m) is: 20 m and 40 m shifts,
     other observer heights, a finer near-field sampling
  c  ground-level (0 m) crest values against the distance of the first ray sample
  d  what blocks the Sun during the longest computed darkness at C1
  e  Earth visibility at the same 400 seeded points as the Sun check.  The model side is always
     computed and stored; the comparison runs when the LOLA team's Earth maps
     (AVGVISIB_*_201608_EARTH as .TIF, .IMG+.LBL or .JP2+.LBL) are in the folder.
  f  Earth visibility at the 60 well-lit ridge pixels of check a, against the 60 m Earth map
  s  checks a and f again on two more seeds (the original seed + 1 and + 2, fixed before any result was
     seen), so the ridge-pixel figures are printed as a range and not as one draw

Check e also reports the Earth agreement a second time without the points where the map and the model
are both exactly 0 or both exactly 1 (the Earth never rises, or never sets, on both sides): those points
agree trivially and pull the mean difference down.

Results go to data/validation/more_validation.json and are merged into
data/validation/terrain_validation.json (headline tiles and tables), which the app shows.
"""
from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from slipday import demstore, refmaps, terrain  # noqa: E402
from slipday.dem import MOON_RADIUS_M  # noqa: E402
from slipday.ephem import cached_table, grid_start, iso, parse_utc  # noqa: E402
from slipday.geometry import Horizon, Site, disc_fraction, track  # noqa: E402
from slipday.metrics import longest_run  # noqa: E402
from slipday.robust import SCATTER_LAYOUT  # noqa: E402

CYCLE_START = "2016-08-01T00:00:00Z"
CYCLE_DAYS = 18.6 * 365.25
CYCLE_STEP_H = 3
OUT = os.path.join(HERE, "data", "validation", "more_validation.json")
MAIN = os.path.join(HERE, "data", "validation", "terrain_validation.json")
C1 = (-89.4398, 222.83 - 360.0)
C1_0M = (-89.4505, 222.84 - 360.0)
C2_0M = (-89.3157, 245.94 - 360.0)
MAPS = [("60 m map, 85 S to the pole", "85S_060M", 2.0, 148.0), ("120 m map, 80 S to 85 S", "75S_120M", 152.0, 298.0)]
RULES = ("earth_centre", "earth_any_part", "earth_whole_disc", "earth_mean_disc_fraction")
RIDGE_SEED = 20261115                                  # the seed of checks a and f
# Check s: the next nine integers.  + 1 and + 2 were run first (4.42 and 4.25 points); a seed takes about
# 20 s, so + 3 to + 9 were added the same evening, before their results were seen, to print a wider range.
EXTRA_SEEDS = tuple(RIDGE_SEED + k for k in range(1, 10))
STALE_EARTH_SENTENCE = "The LOLA team's own Earth-visibility maps could not be obtained."
EARTH_SENTENCE = ("The Earth side is checked against the LOLA team's own Earth-visibility maps instead, where they are "
                  "installed: see the Earth tile above and its table below.")


def cycle_table():
    t0 = grid_start(parse_utc(CYCLE_START))
    return cached_table(t0, int(CYCLE_DAYS * 24 / CYCLE_STEP_H), CYCLE_STEP_H * 3600)


def glaser_table():
    """2017-01-01 for 20 years, hourly: the period of Glaser et al. 2018."""
    t0 = grid_start(parse_utc("2017-01-01T00:00:00Z"))
    n = 20 * 365 * 24 + 5 * 24                      # the span scripts/validate_terrain.py uses (7,305 days)
    return [cached_table(t0 + i0 * 3600, min(17520, n - i0), 3600) for i0 in range(0, n, 17520)]


def site_of(lat, lon, mast, min_step=None):
    dem = demstore.get_dem()
    p = terrain.horizon_profile(dem, lat, lon, mast, min_step_m=min_step)
    return Site("p", lat, lon, horizon=Horizon(profile_az_deg=p.az_deg, profile_el_deg=p.el_deg)), p


def unproject(x, y):
    r = np.hypot(x, y)
    return -(90.0 - np.rad2deg(2.0 * np.arctan(r / (2.0 * MOON_RADIUS_M)))), np.rad2deg(np.arctan2(x, y))


def random_points(rng, n, r_min_km, r_max_km):
    """Uniform in area between two distances from the pole (the sampling of validate_terrain.py)."""
    r = np.sqrt(rng.uniform((r_min_km / r_max_km) ** 2, 1.0, n)) * r_max_km * 1000.0
    a = rng.uniform(0, 2 * np.pi, n)
    return unproject(r * np.sin(a), r * np.cos(a))


def stats(calc, ref):
    d = calc - ref
    return {"n": int(len(d)), "published_mean_pct": round(float(ref.mean()) * 100, 2),
            "computed_mean_pct": round(float(calc.mean()) * 100, 2), "bias_pts": round(float(d.mean()) * 100, 2),
            "mae_pts": round(float(np.abs(d).mean()) * 100, 2),
            "p95_abs_pts": round(float(np.percentile(np.abs(d), 95)) * 100, 2),
            "max_abs_pts": round(float(np.abs(d).max()) * 100, 2),
            "within_5_pts_pct": round(float((np.abs(d) <= 0.05).mean()) * 100, 1),
            "correlation": round(float(np.corrcoef(calc, ref)[0, 1]), 4) if np.std(calc) > 0 and np.std(ref) > 0 else None}


def earth_reference(path, lat, lon, res) -> dict:
    """The four Earth rules against one reference map: at every point inside the map, and again without the
    points where the map and the model's any-part value are both exactly 0 or both exactly 1.

    "Exactly" is to the four decimals the per-point values are stored with (under 0.005 % of the time).
    Such points are places where the Earth never rises, or never sets, on both sides; they agree trivially,
    so the figure without them is the fairer one for ground where the question is open."""
    rm = refmaps.load(path)
    ref = rm.nearest(lat, lon)
    res = np.round(np.asarray(res, dtype=float), 4)
    ok = np.isfinite(ref)
    zero = ok & (ref == 0.0) & (res[:, 1] == 0.0)
    one = ok & (ref >= 0.99999) & (res[:, 1] >= 1.0)
    keep = ok & ~zero & ~one
    return {"file": os.path.basename(path), "product_id": rm.product_id, "description": rm.description,
            "points_inside_map": int(ok.sum()),
            "by_rule": {name: stats(res[ok, j], ref[ok]) for j, name in enumerate(RULES)},
            "both_exactly_zero": int(zero.sum()), "both_exactly_one": int(one.sum()),
            "without_trivial": {name: stats(res[keep, j], ref[keep]) for j, name in enumerate(RULES)}}


def ridge_pixels(m, seed: int, n: int = 60):
    """A seeded sample of the pixels a Sun map rates above 60 % (the selection of checks a and f)."""
    rows, cols = np.nonzero(np.asarray(m.z) * m.scale > 0.60)
    pick = np.random.default_rng(seed).choice(len(rows), size=n, replace=False)
    return unproject(m.x0_m + cols[pick] * m.pixel_m, m.y0_m - rows[pick] * m.pixel_m)


# ---------------------------------------------------------------- workers (one skyline each)

def _sun_any(args):
    lat, lon = args
    s, _ = site_of(lat, lon, 0.0)
    return float((track(s, cycle_table()).sun_frac > 0).mean())


def _earth_all(args):
    """Share of the cycle with the Earth's centre / any part / the whole disc above the skyline, and any Sun."""
    lat, lon = args
    s, _ = site_of(lat, lon, 0.0)
    tr = track(s, cycle_table())
    ef = disc_fraction(s.horizon, tr.earth_az, tr.earth_el, tr.earth_radius_deg)
    return [float((tr.earth_clear > 0).mean()), float((ef > 0).mean()), float((ef >= 0.999).mean()),
            float(ef.mean()), float((tr.sun_frac > 0).mean())]


def _glaser(args):
    lat, lon, mast, min_step = args
    s, _ = site_of(lat, lon, mast, min_step)
    frac = np.concatenate([track(s, t).sun_frac for t in glaser_table()])
    return [round(float(frac.mean()) * 100, 2), round(float((frac > 0).mean()) * 100, 2), float(longest_run(frac <= 0))]


def shifted(lat, lon, d_m, bearing_deg):
    la, lo = terrain.destination(lat, lon, np.deg2rad(bearing_deg), np.array(d_m / MOON_RADIUS_M))
    return float(la), float(lo)


# ---------------------------------------------------------------- the checks

def check_a(src, pool):
    path = refmaps.find(src, "85S_060M", earth=False)
    if not path:
        return None
    m = refmaps.load(path)
    rows, cols = np.nonzero(np.asarray(m.z) * m.scale > 0.60)
    rng = np.random.default_rng(20261115)
    pick = rng.choice(len(rows), size=60, replace=False)
    x = m.x0_m + cols[pick] * m.pixel_m
    y = m.y0_m - rows[pick] * m.pixel_m
    lat, lon = unproject(x, y)
    ref = m.nearest(lat, lon)
    calc = np.array(pool.map(_sun_any, list(zip(lat, lon))))
    st = stats(calc, ref)
    st.update({"pixels_above_60pct": int(len(rows)), "share_of_map_pct": round(100.0 * len(rows) / m.z.size, 4),
               "seed": 20261115, "sampled": 60, "map": os.path.basename(path)})
    return st


def check_b(pool):
    base = _glaser((C1[0], C1[1], 2.0, None))
    jobs, labels = [], []
    for d in (20.0, 40.0):
        for b in range(0, 360, 45):
            la, lo = shifted(C1[0], C1[1], d, b)
            jobs.append((la, lo, 2.0, None)); labels.append(("shift", d))
    for frac, b in SCATTER_LAYOUT:
        la, lo = shifted(C1[0], C1[1], 100.0 * frac, b)
        jobs.append((la, lo, 2.0, None)); labels.append(("scatter", 100.0))
    for mast in (1.5, 2.5, 3.0):
        jobs.append((C1[0], C1[1], mast, None)); labels.append(("mast", mast))
    for step in (40.0, 20.0):
        jobs.append((C1[0], C1[1], 2.0, step)); labels.append(("first_sample", step))
    res = pool.map(_glaser, jobs)
    out = {"published": [88.0, 92.1, 112.0], "at_point": base, "variants": []}
    for kind, val in sorted(set(labels), key=lambda t: (t[0], t[1])):
        vals = np.array([r for r, l in zip(res, labels) if l == (kind, val)])
        out["variants"].append({"kind": kind, "value": val, "n": int(len(vals)),
                                "avg_illumination_pct": [float(vals[:, 0].min()), float(vals[:, 0].max())],
                                "visibility_pct": [float(vals[:, 1].min()), float(vals[:, 1].max())],
                                "longest_dark_h": [float(vals[:, 2].min()), float(vals[:, 2].max())]})
    return out


def check_c(pool):
    jobs = [(p[0], p[1], 0.0, st) for p in (C1_0M, C2_0M) for st in (None, 40.0, 20.0, 10.0)]
    res = pool.map(_glaser, jobs)
    out = []
    for i, (name, pub) in enumerate((("Connecting ridge C1, 0 m", 76.0), ("Connecting ridge C2, 0 m", 75.6))):
        out.append({"point": name, "published_avg_illumination_pct": pub,
                    "avg_illumination_pct_by_first_sample_m": {"80": res[4 * i][0], "40": res[4 * i + 1][0],
                                                               "20": res[4 * i + 2][0], "10": res[4 * i + 3][0]}})
    return out


def check_d():
    s, prof = site_of(C1[0], C1[1], 2.0)
    tabs = glaser_table()
    tr = [track(s, t) for t in tabs]
    frac = np.concatenate([t.sun_frac for t in tr])
    unix = np.concatenate([t.unix for t in tr])
    az = np.concatenate([t.sun_az for t in tr])
    el = np.concatenate([t.sun_el for t in tr])
    rad = np.concatenate([t.sun_radius_deg for t in tr])
    dark = frac <= 0
    edges = np.diff(np.concatenate([[0], dark.astype(np.int8), [0]]))
    starts, ends = np.nonzero(edges == 1)[0], np.nonzero(edges == -1)[0]
    lengths = ends - starts
    k = int(np.argmax(lengths))
    sl = slice(starts[k], ends[k])
    idx = np.round(az[sl] / 0.5).astype(int) % 720
    dist = prof.dist_km[idx]
    below = prof.el_deg[idx] - (el[sl] + rad[sl])           # how far the upper limb is under the skyline
    top10 = sorted((int(v) for v in lengths), reverse=True)[:10]
    return {"longest_dark_h": int(lengths[k]), "start_utc": iso(unix[starts[k]]), "end_utc": iso(unix[ends[k] - 1]),
            "blocker_distance_km": {"median": round(float(np.median(dist)), 2), "p10": round(float(np.percentile(dist, 10)), 2),
                                    "p90": round(float(np.percentile(dist, 90)), 2),
                                    "share_within_1km_pct": round(float((dist < 1.0).mean()) * 100, 1)},
            "upper_limb_below_skyline_deg": {"median": round(float(np.median(below)), 2), "max": round(float(below.max()), 2)},
            "ten_longest_dark_runs_h": top10}


def check_e(src, pool):
    out = {"definition_note": "The LOLA team's Earth maps carry their own definition in the label; three candidate "
                              "rules are computed here so the one that matches can be reported.", "maps": []}
    for mi, (mlabel, region, r0, r1) in enumerate(MAPS):
        rng = np.random.default_rng(20261114 + mi)             # the same points as the Sun check
        lat, lon = random_points(rng, 200, r0, r1)
        res = np.array(pool.map(_earth_all, list(zip(lat, lon))))
        entry = {"map": mlabel, "region": region, "n": 200,
                 "model_mean_pct": {"earth_centre": round(float(res[:, 0].mean()) * 100, 2),
                                    "earth_any_part": round(float(res[:, 1].mean()) * 100, 2),
                                    "earth_whole_disc": round(float(res[:, 2].mean()) * 100, 2),
                                    "earth_mean_disc_fraction": round(float(res[:, 3].mean()) * 100, 2),
                                    "sun_any_part": round(float(res[:, 4].mean()) * 100, 2)},
                 "never_sees_earth_pct": round(float((res[:, 1] == 0).mean()) * 100, 1),
                 "always_sees_earth_centre_pct": round(float((res[:, 0] >= 0.999).mean()) * 100, 1),
                 "points": [[round(float(a), 5), round(float(b), 5)] + [round(float(v), 4) for v in r]
                            for a, b, r in zip(lat, lon, res)],
                 "reference": None}
        path = refmaps.find(src, region, earth=True) if src else None
        if path:
            entry["reference"] = earth_reference(path, lat, lon, res)
        out["maps"].append(entry)
    return out


def check_f(src, pool):
    """Earth visibility at the well-lit ridge pixels of check a (same seed, same 60 pixels of the 60 m Sun
    map above 60 %), against the 60 m Earth map.  Runs only when both maps are in the folder."""
    sun_path = refmaps.find(src, "85S_060M", earth=False)
    earth_path = refmaps.find(src, "85S_060M", earth=True)
    if not sun_path or not earth_path:
        return None
    m = refmaps.load(sun_path)
    rows, cols = np.nonzero(np.asarray(m.z) * m.scale > 0.60)
    rng = np.random.default_rng(20261115)
    pick = rng.choice(len(rows), size=60, replace=False)
    lat, lon = unproject(m.x0_m + cols[pick] * m.pixel_m, m.y0_m - rows[pick] * m.pixel_m)
    ref = refmaps.load(earth_path).nearest(lat, lon)
    res = np.array(pool.map(_earth_all, list(zip(lat, lon))))
    return {"sampled": 60, "seed": 20261115, "map": os.path.basename(earth_path),
            "selected_on": os.path.basename(sun_path) + " above 60 % sunlit (the pixels of check a)",
            "by_rule": {name: stats(res[:, j], ref) for j, name in
                        enumerate(("earth_centre", "earth_any_part", "earth_whole_disc", "earth_mean_disc_fraction"))}}


def check_s(src, pool, seeds=EXTRA_SEEDS):
    """Checks a (Sun) and f (Earth) on other seeds: 60 pixels the 60 m Sun map rates above 60 %, per seed.

    The seeds are the original one + 1 and + 2, fixed before any result was seen.  One skyline per pixel
    gives both sides, so each seed costs 60 skylines."""
    sun_path = refmaps.find(src, "85S_060M", earth=False)
    earth_path = refmaps.find(src, "85S_060M", earth=True)
    if not sun_path:
        return None
    m = refmaps.load(sun_path)
    em = refmaps.load(earth_path) if earth_path else None
    runs = []
    for seed in seeds:
        t0 = time.time()
        lat, lon = ridge_pixels(m, seed)
        res = np.array(pool.map(_earth_all, list(zip(lat, lon))))
        run = {"seed": int(seed), "sampled": 60, "sun_any_part": stats(res[:, 4], m.nearest(lat, lon))}
        if em is not None:
            eref = em.nearest(lat, lon)
            run["earth_by_rule"] = {name: stats(res[:, j], eref) for j, name in enumerate(RULES)}
        run["seconds"] = round(time.time() - t0, 1)
        runs.append(run)
        print("s", run, flush=True)
    return {"seed_rule": f"the seed of checks a and f ({RIDGE_SEED}) and the next {len(seeds)} integers after it, a rule "
                         "fixed before those runs were made",
            "sun_map": os.path.basename(sun_path), "earth_map": os.path.basename(earth_path) if earth_path else None,
            "runs": runs}


# ---------------------------------------------------------------- merge into what the app shows

def merge(more: dict) -> None:
    with open(MAIN) as fh:
        main = json.load(fh)
    main["tables"] = [t for t in main["tables"] if not t.get("id", "").startswith("more-")]
    head = [h for h in main["headline"] if not h.get("id", "").startswith("more-")]
    a, b, c, d, e = (more.get(k) for k in "abcde")
    mc = main["results"]["map_check"][0]
    # Every tile names the rule its number uses (local review, bugs 7 and 8).
    sun_rule = ("Rule: any part of the solar disc above the skyline, as the map's label states; the mission card's "
                "default asks for half the disc, which is stricter.")
    f_run = more.get("f")
    seed_runs = (more.get("s") or {}).get("runs") or []          # checks a and f again on other seeds
    for t in main["tables"]:                                     # a sentence from before the Earth maps were attached
        if STALE_EARTH_SENTENCE in t.get("note", ""):
            t["note"] = (t["note"].replace(STALE_EARTH_SENTENCE + " What is tested:", EARTH_SENTENCE + " Also tested:")
                         .replace(STALE_EARTH_SENTENCE, EARTH_SENTENCE))
    if a:
        head[0]["k"] = "Sunlit share against the LOLA team's published map: ordinary terrain"
        head[0]["s"] = (f"mean |difference| at {mc['n']} random points within 5° of the pole, correlation {mc['correlation']}; "
                        f"smooth sphere at the same points: ±{main['results']['map_check'][4]['mae_pts']} pts. " + sun_rule +
                        " Most of these points are poorly lit; see the next tile for ridges.")
        sun_runs = [(a["seed"], a)] + [(r["seed"], r["sun_any_part"]) for r in seed_runs]
        maes = [st["mae_pts"] for _, st in sun_runs]
        cors = [st["correlation"] for _, st in sun_runs]
        if seed_runs:
            # one draw of 60 pixels is not a stable figure: print the range over the seeds, whatever it is
            ridge_v = f"±{min(maes):.2f} to {max(maes):.2f} pts"
            ridge_s = (f"mean |difference| at {a['sampled']} seeded pixels the 60 m map rates above 60 %: the range over "
                       f"{len(sun_runs)} random draws (median {float(np.median(maes)):.1f}), correlation {min(cors):.2f} to "
                       f"{max(cors):.2f}. First draw (seed {a['seed']}): ±{a['mae_pts']:.1f}, mean difference "
                       f"{a['bias_pts']:+.1f}, {a['within_5_pts_pct']:.0f} % within 5 points. Rule: any part of the solar disc "
                       "above the skyline. An 80 m grid cannot hold a crest a few tens of metres wide.")
        else:
            ridge_v = f"±{a['mae_pts']:.1f} pts"
            ridge_s = (f"mean |difference| at {a['sampled']} seeded pixels the 60 m map rates above 60 % (one seed, {a['seed']}; "
                       f"other seeds not run on this installation); mean difference {a['bias_pts']:+.1f}, correlation "
                       f"{a['correlation']:.2f}, {a['within_5_pts_pct']:.0f} % within 5 points. Rule: any part of the solar disc "
                       "above the skyline. An 80 m grid cannot hold a crest a few tens of metres wide.")
        head.insert(1, {"id": "more-a", "k": "The same check on well-lit ridge pixels, where landers would go",
                        "v": ridge_v, "s": ridge_s, "tag": "terrain (LOLA, 80 m/px)"})
        if seed_runs:
            rows = []
            for seed, st in sun_runs:
                er = (f_run or {}).get("by_rule") if seed == a["seed"] else \
                    next((r.get("earth_by_rule") for r in seed_runs if r["seed"] == seed), None)
                rows.append([seed, st["n"], st["mae_pts"], st["bias_pts"], st["correlation"], st["within_5_pts_pct"],
                             st["max_abs_pts"]]
                            + ([er["earth_any_part"]["mae_pts"], er["earth_any_part"]["correlation"],
                                er["earth_centre"]["bias_pts"]] if er else [None, None, None]))
            seed_table = {
                "id": "more-s", "collapsed": True,
                "title": "Well-lit ridge pixels on " + str(len(sun_runs)) + " seeds: a range, not one draw (real data)",
                "note": "The ridge-pixel check repeated with other random draws of 60 pixels from the same "
                        f"{a['pixels_above_60pct']} pixels the 60 m Sun map rates above 60 %. Seeds: {more['s']['seed_rule']}. "
                        "Sun columns: any part of the solar disc, against the 60 m Sun map. Earth columns: the same pixels "
                        "against the 60 m Earth map, with the map's rule (any part of the disc) and with the mission card's "
                        "rule (the Earth's centre). Differences are in percentage points, model minus map. A single pixel "
                        "that is far off moves a 60-pixel mean and its correlation a good deal: read the Sun figure on "
                        "ridges as this range.",
                "columns": ["Seed", "Pixels", "Sun: mean |difference|", "Sun: mean difference", "Sun: correlation",
                            "Sun: within 5 points %", "Sun: largest |difference|", "Earth, any part: mean |difference|",
                            "Earth, any part: correlation", "Earth's centre (the card's rule): mean difference"],
                "rows": rows}
        main["tables"].append({
            "id": "more-a", "title": "Well-lit ridge pixels: where the average agreement does not hold (real data)",
            "note": f"The 60 m LOLA map rates {a['pixels_above_60pct']} pixels ({a['share_of_map_pct']} % of the map) above 60 % sunlit. "
                    f"A seeded sample of {a['sampled']} of them (seed {a['seed']}) was computed exactly as in the table above "
                    "(0 m, any part of the disc, one 18.6-year cycle in 3-hour steps). Selecting on a high published value "
                    "pulls the computed mean down by itself, so part of the negative mean difference is selection; the scatter is real."
                    + (" This row is the first random draw; the next table repeats it on other seeds." if seed_runs else ""),
            "columns": ["Pixels sampled", "Published mean %", "Computed mean %", "Mean difference", "Mean |difference|",
                        "95th pct |difference|", "Within 5 points %", "Correlation"],
            "rows": [[a["sampled"], a["published_mean_pct"], a["computed_mean_pct"], a["bias_pts"], a["mae_pts"],
                      a["p95_abs_pts"], a["within_5_pts_pct"], a["correlation"]]]})
        if seed_runs:
            main["tables"].append(seed_table)
    if b:
        sc = next(v for v in b["variants"] if v["kind"] == "scatter")
        for h in head:
            if h["k"].startswith("Shackleton connecting ridge"):
                h["v"] = f"{b['at_point'][1]:.1f}%"
                h["s"] = (f"published 92.1% (Glaser et al. 2018, 20 m DEM). The match is not firm: within 100 m of the point the "
                          f"model gives {sc['visibility_pct'][0]:.1f} to {sc['visibility_pct'][1]:.1f}%. Smooth sphere at the same point 55.6%. "
                          "Rule: any part of the solar disc above the skyline.")
        names = {"shift": "moved {v:g} m (8 directions)", "scatter": "13-point landing scatter, {v:g} m", "mast": "observer at {v:g} m",
                 "first_sample": "first ray sample at {v:g} m"}
        rng = lambda r, f="{:.1f}": (f.format(r[0]) if r[0] == r[1] else f.format(r[0]) + " to " + f.format(r[1]))  # noqa: E731
        rows = [["as published (20 m DEM)", "88.0", "92.1", "112"],
                ["this build, at the stated point, 2 m, first sample 80 m", f"{b['at_point'][0]:.1f}", f"{b['at_point'][1]:.1f}", f"{b['at_point'][2]:.0f}"]]
        for v in b["variants"]:
            rows.append([names[v["kind"]].format(v=v["value"]), rng(v["avg_illumination_pct"]), rng(v["visibility_pct"]),
                         rng(v["longest_dark_h"], "{:.0f}")])
        main["tables"].append({
            "id": "more-b", "title": "How firm is the match at the connecting ridge (C1, 2 m)? Not very (real data)",
            "note": "The same computation as the ridge-top table (2017-01-01, 20 years, hourly), repeated with the point moved, "
                    "the observer raised or lowered, and the nearest ground sampled more finely. Each cell is the range over the "
                    "variants. The agreement at the stated point is real but sits at the top of this range.",
            "columns": ["Variant", "Average illumination %", "Any Sun visible %", "Longest darkness (h)"], "rows": rows})
    if c:
        main["tables"].append({
            "id": "more-c", "collapsed": True,
            "title": "Ground-level (0 m) crest values depend on how the nearest ground is sampled (real data)",
            "note": "Average illumination at two published 0 m points against the distance of the first ray sample. The app uses one "
                    "grid spacing (80 m), the node-to-node convention of the LOLA team's maps: a grid holds no information about "
                    "nearer ground, and sampling the interpolated surface closer measures the interpolation. The agreement of the "
                    "0 m rows in the ridge-top table rests on that convention. The page offers 2 m and 10 m only.",
            "columns": ["Point", "Published %", "First sample 80 m (app)", "40 m", "20 m", "10 m"],
            "rows": [[r["point"], r["published_avg_illumination_pct"]] + [r["avg_illumination_pct_by_first_sample_m"][k]
                                                                        for k in ("80", "40", "20", "10")] for r in c]})
    if d:
        main["tables"].append({
            "id": "more-d", "collapsed": True,
            "title": "What sets the longest darkness at C1 (198 h here, 112 h published): ground a few hundred metres away",
            "note": "During the longest computed dark run the Sun's upper limb stays just under a skyline set by nearby terrain, "
                    "which an 80 m grid resolves poorly. Longest darkness on a ridge site is therefore indicative only.",
            "columns": ["Run", "Length (h)", "Median distance of the blocking terrain (km)", "10th to 90th percentile (km)",
                        "Share of hours blocked from under 1 km", "Sun's upper limb below the skyline, median (deg)",
                        "Ten longest dark runs (h)"],
            "rows": [[d["start_utc"][:10] + " to " + d["end_utc"][:10], d["longest_dark_h"], d["blocker_distance_km"]["median"],
                      f"{d['blocker_distance_km']['p10']} to {d['blocker_distance_km']['p90']}",
                      f"{d['blocker_distance_km']['share_within_1km_pct']} %", d["upper_limb_below_skyline_deg"]["median"],
                      ", ".join(str(x) for x in d["ten_longest_dark_runs_h"])]]})
    if e:
        have = [m for m in e["maps"] if m["reference"]]
        if have:
            # The tile reports the rule the map's own label states, not whichever rule fits best.
            desc = (have[0]["reference"]["description"] or "").lower()
            if "any fraction" in desc or "any part" in desc:
                rule, rule_words, from_label = "earth_any_part", "any part of the Earth's disc above the skyline", True
            else:                                  # the label does not say: fall back to the best fit and say so
                rule = min(have[0]["reference"]["by_rule"].items(), key=lambda kv: kv[1]["mae_pts"])[0]
                rule_words, from_label = rule.replace("_", " "), False
            best_rule = min(have[0]["reference"]["by_rule"].items(), key=lambda kv: kv[1]["mae_pts"])[0]
            ref0 = have[0]["reference"]
            st0 = ref0["by_rule"][rule]

            def trivial(ref):
                """(count, words) for the points of one map that agree trivially (see ``earth_reference``)."""
                z, o = ref.get("both_exactly_zero", 0), ref.get("both_exactly_one", 0)
                if z and o:
                    return z + o, f"{z + o} points where the map and the model are both exactly 0 or both exactly 1"
                if o:
                    return o, f"{o} points where the map and the model are both exactly 1"
                return z, f"{z} points where the map and the model are both exactly zero"

            def other_map(m):
                r = m["reference"]
                txt = f"{m['map'].split(',')[0]}: ±{r['by_rule'][rule]['mae_pts']} pts, correlation {r['by_rule'][rule]['correlation']}"
                n_tr, words = trivial(r)
                if n_tr and "without_trivial" in r:
                    wt = r["without_trivial"][rule]
                    txt += f" (±{wt['mae_pts']} pts, correlation {wt['correlation']} without {words})"
                return txt

            others = "; ".join(other_map(m) for m in have[1:])
            f = more.get("f")
            if f and rule in f["by_rule"]:
                fr = f["by_rule"][rule]
                others += (("; " if others else "") + f"on {f['sampled']} well-lit ridge pixels: ±{fr['mae_pts']} pts, "
                           f"mean difference {fr['bias_pts']:+.1f}, correlation {fr['correlation']}")
                more_e = [r["earth_by_rule"][rule]["mae_pts"] for r in seed_runs if rule in r.get("earth_by_rule", {})]
                if more_e:
                    others += f" (±{min(more_e):.2f} to ±{max(more_e):.2f} pts on {len(more_e)} other random draws)"
            # Both figures (local review, bug 8): at every point, and without the points that agree trivially.
            n_tr0, words0 = trivial(ref0)
            both = ""
            if n_tr0 and "without_trivial" in ref0:
                wt0 = ref0["without_trivial"][rule]
                both = (f" Without the {words0} (the Earth never rises there): ±{wt0['mae_pts']} pts at {wt0['n']} points, "
                        f"correlation {wt0['correlation']}.")
            # The card's rule (local review, bug 7): the tile checks the map's rule, the card counts the centre.
            card = ""
            if rule != "earth_centre" and "earth_centre" in ref0["by_rule"]:
                c_all = ref0["by_rule"]["earth_centre"]["bias_pts"]
                card = (" The mission card does not use this rule: it counts the Earth's centre, which is stricter and reads "
                        f"{abs(c_all):.1f} points {'lower' if c_all < 0 else 'higher'} than this map at the same points")
                if n_tr0 and "without_trivial" in ref0:
                    c_wt = ref0["without_trivial"]["earth_centre"]["bias_pts"]
                    card += f" ({abs(c_wt):.1f} without those {n_tr0})"
                card += "."
            head.insert(2, {"id": "more-e", "k": "Earth in view against the LOLA team's Earth-visibility map",
                            "v": f"±{st0['mae_pts']:.1f} pts",
                            "s": f"mean |difference| at {st0['n']} of the same random points within 5° of the pole "
                                 f"(±{st0['mae_pts']} pts to two decimals), correlation {st0['correlation']}." + both
                                 + f" Rule: {rule_words}, "
                                 + ("the rule the map's own label states" if from_label else "the best-fitting rule (the label names none)")
                                 + ("" if best_rule == rule else f"; the best-fitting rule is {best_rule.replace('_', ' ')}")
                                 + "." + card + (f" {others}." if others else ""),
                            "tag": "terrain (LOLA, 80 m/px)"})
            more["e"]["tile_rule"] = {"rule": rule, "from_label": from_label, "best_fitting_rule": best_rule}
            rows = []
            for m in have:
                for r, st in m["reference"]["by_rule"].items():
                    rows.append([m["map"], r.replace("_", " ") + (" (the map's rule)" if r == rule and from_label else ""),
                                 st["n"], st["published_mean_pct"], st["computed_mean_pct"],
                                 st["bias_pts"], st["mae_pts"], st["p95_abs_pts"], st["correlation"]])
            if f:
                for r, st in f["by_rule"].items():
                    rows.append([f"60 m map, {f['sampled']} well-lit ridge pixels (the Sun map above 60 %, seed {f['seed']})",
                                 r.replace("_", " ") + (" (the map's rule)" if r == rule and from_label else ""),
                                 st["n"], st["published_mean_pct"], st["computed_mean_pct"],
                                 st["bias_pts"], st["mae_pts"], st["p95_abs_pts"], st["correlation"]])
            main["tables"].append({
                "id": "more-e", "title": "Earth visibility against the LOLA team's Earth maps (real data)",
                "note": "Same 400 seeded points as the Sun check, observer at 0 m, one 18.6-year cycle in 3-hour steps. The map's own "
                        "definition, from its label: " + (have[0]["reference"]["description"] or "not found in the file") + " "
                        "The label names no observer height and no time span; the maps are computed from the 60 m and 120 m LOLA "
                        "grids, this build from the 80 m mosaic. Four rules are computed here so the definition can be seen to "
                        "matter: only the row marked as the map's rule is the check. The mission card counts Earth contact by "
                        "the Earth's centre, a stricter rule than the map's, so it reports fewer hours than this map would.",
                "columns": ["Published map", "Rule computed here", "Points", "Published mean %", "Computed mean %",
                            "Mean difference", "Mean |difference|", "95th pct |difference|", "Correlation"], "rows": rows})
            if all("without_trivial" in m["reference"] for m in have):
                rows2 = []
                for m in have:
                    r = m["reference"]
                    n_tr, words = trivial(r)
                    for label, key, z, o in (("every point inside the map", "by_rule", 0, 0),
                                             ("without the points that agree trivially", "without_trivial",
                                              r["both_exactly_zero"], r["both_exactly_one"])):
                        for rl, who in ((rule, "the map's own rule, checked on the tile"),
                                        ("earth_centre", "the mission card's rule, stricter")):
                            st = r[key][rl]
                            rows2.append([m["map"], label, st["n"], z, o, rl.replace("_", " ") + ": " + who,
                                          st["bias_pts"], st["mae_pts"], st["correlation"]])
                main["tables"].append({
                    "id": "more-e2", "collapsed": True,
                    "title": "The Earth check with and without the points that agree trivially, and the mission card's rule (real data)",
                    "note": "At some of the random points the map and the model are both exactly 0 (the Earth never rises there) "
                            "or both exactly 1 (it never sets). Those points agree by construction and pull the mean "
                            "difference down, so each map is listed twice: with every point, and without them. \"Exactly\" "
                            "is to the four decimals stored for each point (under 0.005 % of the time). The any-part rule is "
                            "the one the maps' labels state and the one the tile reports. The centre rule is what the mission "
                            "card counts as Earth contact; it has no published reference of its own, and its rows show how "
                            "far below the map it reads. Differences are in percentage points, model minus map.",
                    "columns": ["Published map", "Points used", "Points", "Left out: both exactly 0", "Left out: both exactly 1",
                                "Rule computed here", "Mean difference", "Mean |difference|", "Correlation"], "rows": rows2})
        else:
            m0 = e["maps"][0]["model_mean_pct"]
            head.insert(2, {"id": "more-e", "pending": True, "k": "Earth in view against the LOLA team's Earth-visibility maps",
                            "v": "not run yet",
                            "s": "Needs official data download: the Earth maps could not be fetched here. This build's side is ready at "
                                 f"the same 400 points (within 5° of the pole the Earth's centre is in view {m0['earth_centre']:.1f} % of the "
                                 f"time on average, any part of it {m0['earth_any_part']:.1f} %). See LOCAL_PASS.md.",
                            "tag": "needs official data download"})
            main["tables"].append({
                "id": "more-e", "collapsed": True,
                "title": "Earth visibility: this build's side of the check, waiting for the LOLA team's Earth maps (needs official data download)",
                "note": "Share of one 18.6-year cycle (3-hour steps, observer at 0 m) with the Earth above the terrain skyline, averaged "
                        "over the same 200 seeded points per region as the Sun check. No reference is attached yet: run "
                        "fetch_on_your_machine.sh and scripts/validate_more.py on a machine that can reach the LOLA archive.",
                "columns": ["Region", "Points", "Earth's centre in view %", "Any part of the Earth in view %", "Whole Earth in view %",
                            "Points that never see the Earth %", "Any Sun (same points) %"],
                "rows": [[m["map"].split(",")[1].strip(), m["n"], m["model_mean_pct"]["earth_centre"], m["model_mean_pct"]["earth_any_part"],
                          m["model_mean_pct"]["earth_whole_disc"], m["never_sees_earth_pct"], m["model_mean_pct"]["sun_any_part"]]
                         for m in e["maps"]]})
    extra = (" Read the C1 rows with the two tables that follow: the 2 m match sits at the top of the range found within "
             "100 m of the point, and the 0 m rows rest on the near-field sampling convention.")
    for t in main["tables"]:
        if t["title"].startswith("Published ridge-top results") and extra not in t.get("note", ""):
            t["note"] = t.get("note", "") + extra
    main["headline"] = head
    main["more_generated_utc"] = more["generated_utc"]
    with open(MAIN, "w") as fh:
        json.dump(main, fh, indent=1)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ""
    only = "abcdefs"
    for i, a in enumerate(sys.argv):
        if a == "--only":
            only = sys.argv[i + 1].replace(",", "")
    more = {}
    if os.path.exists(OUT):
        with open(OUT) as fh:
            more = json.load(fh)
    t0 = time.time()
    with Pool(int(os.environ.get("PROCS", "2"))) as pool:
        if "a" in only and src:
            more["a"] = check_a(src, pool); print("a", more["a"], flush=True)
        if "b" in only:
            more["b"] = check_b(pool); print("b", json.dumps(more["b"]), flush=True)
        if "c" in only:
            more["c"] = check_c(pool); print("c", more["c"], flush=True)
        if "d" in only:
            more["d"] = check_d(); print("d", more["d"], flush=True)
        if "e" in only:
            old = more.get("e")
            if old and old["maps"] and all(len(m.get("points", [])) == 200 for m in old["maps"]) and "--recompute" not in sys.argv:
                # the model side is already stored: only (re)attach the reference maps
                for m in old["maps"]:
                    pts = np.array(m["points"])
                    path = refmaps.find(src, m["region"], earth=True) if src else None
                    m["reference"] = earth_reference(path, pts[:, 0], pts[:, 1], pts[:, 2:6]) if path else None
                more["e"] = old
            else:
                more["e"] = check_e(src, pool)
            print("e", [{k: v for k, v in m.items() if k != "points"} for m in more["e"]["maps"]], flush=True)
        if "f" in only and src:
            more["f"] = check_f(src, pool); print("f", more["f"], flush=True)
        if "s" in only and src:
            more["s"] = check_s(src, pool)
    more["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    more["seconds"] = round(time.time() - t0, 1)
    more["dems"] = demstore.status()["dems"]
    merge(more)                                    # also records which rule the Earth tile reports
    with open(OUT, "w") as fh:
        json.dump(more, fh, indent=1)
    print("wrote", OUT, "and merged into", MAIN, "in", more["seconds"], "s")


if __name__ == "__main__":
    main()
