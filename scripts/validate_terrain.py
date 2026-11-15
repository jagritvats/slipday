"""Validate the terrain horizon model against published LOLA-based results.

    python3 scripts/validate_terrain.py /path/to/realdata/lunar/data [--quick]

Reads the installed DEMs (data/dem/dems.json) and, from the folder given, the
LOLA team's average solar visibility maps (AVGVISIB_85S_060M_201608.TIF,
AVGVISIB_75S_120M_201608.TIF).  Writes data/validation/terrain_validation.json,
which the app shows in its "Can you trust it?" panel, and prints the tables.

What is compared:
 1. Map check.  At seeded random points, the share of time any part of the
    solar disc is visible from the surface (observer at 0 m), computed here
    over one 18.6-year nodal cycle, against the published map value at the
    same point.  The PDS label defines the map value as "the percentage of
    timesteps where each pixel was sunlit (by any fraction of the solar
    disc)", computed by the LOLA team as in Mazarico et al. 2011.
 2. The same check repeated with coarser DEMs, to show what resolution costs.
 3. Published single-point figures (Glaser et al., Mazarico et al.) at the
    stated coordinates and heights.
 4. Per-site year statistics by DEM resolution and for the smooth sphere.
 5. The hindcast of real landings with and without terrain.

Nothing is tuned to the references: the model has no free parameter except
the sampling settings, which are left at their defaults.
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from slipday import demstore, terrain  # noqa: E402
from slipday.dem import PolarStereoDEM  # noqa: E402
from slipday.ephem import cached_table, grid_start, parse_utc  # noqa: E402
from slipday.geometry import Horizon, Site, track  # noqa: E402
from slipday.hindcast import hindcast  # noqa: E402
from slipday.metrics import Criteria, span_stats  # noqa: E402
from slipday.sites import SITES  # noqa: E402

CYCLE_START = "2016-08-01T00:00:00Z"       # arbitrary start; the span is one full nodal cycle
CYCLE_DAYS = 18.6 * 365.25
CYCLE_STEP_H = 3

# Published single-point results, from realdata/lunar/GROUND_TRUTH.md section 2.  The scout read the tables
# through a web-fetch tool (not byte-exact).  Columns: average illumination %, solar visibility % (any part of
# the disc), longest shadow in hours.
G18 = "Glaser et al. 2018, PSS 162 (20 m LOLA DTM, 2017-2037, hourly)"
G14 = "Glaser et al. 2014, EPSC2014-136 (20 m LOLA DTM, about 19 years, hourly)"
PUBLISHED_POINTS = [
    {"name": "Connecting ridge C1", "lat": -89.4505, "lon": 222.84, "mast_m": 0.0, "avg": 76.0, "vis": 81.3, "dark_h": 268, "source": G18},
    {"name": "Connecting ridge C2", "lat": -89.3157, "lon": 245.94, "mast_m": 0.0, "avg": 75.6, "vis": 80.6, "dark_h": 166, "source": G18},
    {"name": "Shackleton rim S", "lat": -89.7849, "lon": 203.97, "mast_m": 0.0, "avg": 81.0, "vis": 85.5, "dark_h": 221, "source": G18},
    {"name": "Connecting ridge C1", "lat": -89.4398, "lon": 222.83, "mast_m": 2.0, "avg": 88.0, "vis": 92.1, "dark_h": 112, "source": G18},
    {"name": "Connecting ridge C2", "lat": -89.3130, "lon": 245.98, "mast_m": 2.0, "avg": 78.1, "vis": 82.0, "dark_h": 165, "source": G18},
    {"name": "Shackleton rim S", "lat": -89.6866, "lon": 197.19, "mast_m": 2.0, "avg": 85.5, "vis": 89.4, "dark_h": 66, "source": G18},
    {"name": "Shackleton rim S, second point", "lat": -89.7815, "lon": 204.70, "mast_m": 2.0, "avg": 82.1, "vis": 89.8, "dark_h": 65, "source": G18},
    {"name": "Connecting ridge CR1 spot 2", "lat": -89.4399, "lon": 222.8524, "mast_m": 2.0, "avg": 87.9, "vis": 92.3, "dark_h": 4.62 * 24, "source": G14},
    {"name": "Connecting ridge CR1 spot 4", "lat": -89.4544, "lon": 222.8445, "mast_m": 10.0, "avg": 91.9, "vis": 95.66, "dark_h": 3.17 * 24, "source": G14},
]
# Earth visibility per site: Bryant 2009, JPL IPN Progress Report 42-176, Goldstone radar DEM at 40 m (not LOLA;
# positions may be a few hundred metres off the LOLA frame), 2 m above ground, 2009-2028, daily steps.
# Share of time with at least 0 % / 50 % / 100 % of the Earth's disc visible, and the same for the Sun.
B09 = "Bryant 2009, JPL IPN PR 42-176 (GSSR radar DEM, 40 m, 2009-2028, daily)"
EARTH_POINTS = [
    {"name": "A1 Shackleton rim", "lat": -89.633, "lon": -160.388, "sun": (93.46, 90.36, 86.31), "earth": (62.20, 55.29, 48.37)},
    {"name": "A2 Shackleton rim", "lat": -89.723, "lon": -153.925, "sun": (92.98, 89.47, 84.83), "earth": (63.90, 56.98, 50.07)},
    {"name": "B1 connecting ridge", "lat": -89.388, "lon": -137.810, "sun": (97.01, 94.79, 91.67), "earth": (65.16, 58.24, 51.33)},
    {"name": "C1 de Gerlache rim", "lat": -88.657, "lon": -70.688, "sun": (90.01, 86.95, 83.12), "earth": (70.97, 64.05, 57.14)},
    {"name": "F peak near Shackleton", "lat": -88.813, "lon": 126.601, "sun": (89.28, 85.97, 81.77), "earth": (67.30, 60.38, 53.47)},
    {"name": "Malapert alpha", "lat": -86.037, "lon": 1.704, "sun": (82.08, 78.36, 74.49), "earth": (100.0, 100.0, 94.68)},
    {"name": "Leibnitz beta (Mons Mouton)", "lat": -84.722, "lon": 39.470, "sun": (79.06, 77.43, 75.82), "earth": (100.0, 100.0, 100.0)},
]


def site_with(dem, lat, lon, mast):
    p = terrain.horizon_profile(dem, lat, lon, mast)
    return Site("p", lat, lon, horizon=Horizon(profile_az_deg=p.az_deg, profile_el_deg=p.el_deg)), p


def cycle_table():
    t0 = grid_start(parse_utc(CYCLE_START))
    return cached_table(t0, int(CYCLE_DAYS * 24 / CYCLE_STEP_H), CYCLE_STEP_H * 3600)


def any_light_fraction(dem, lat, lon, mast, table):
    s, _ = site_with(dem, lat, lon, mast)
    tr = track(s, table)
    return float((tr.sun_frac > 0).mean()), float(tr.sun_frac.mean())


def load_map(path, pixel, corner):
    import tifffile
    z = tifffile.imread(path, key=0)
    return PolarStereoDEM(name=os.path.basename(path), z=z, pixel_m=pixel, x0_m=-corner + pixel / 2,
                          y0_m=corner - pixel / 2, scale=4e-5)


def nearest(m, lat, lon):
    x, y = m.project(np.asarray(lat, float), np.asarray(lon, float))
    col = np.clip(np.round((x - m.x0_m) / m.pixel_m).astype(int), 0, m.z.shape[1] - 1)
    row = np.clip(np.round((m.y0_m - y) / m.pixel_m).astype(int), 0, m.z.shape[0] - 1)
    return m.z[row, col].astype(float) * m.scale


def random_points(rng, n, r_min_km, r_max_km, ref):
    r = np.sqrt(rng.uniform((r_min_km / r_max_km) ** 2, 1.0, n)) * r_max_km * 1000.0
    a = rng.uniform(0, 2 * np.pi, n)
    return ref.unproject(r * np.sin(a), r * np.cos(a))


def stats(calc, ref):
    d = calc - ref
    return {"n": int(len(d)), "published_mean_pct": round(float(ref.mean()) * 100, 2),
            "computed_mean_pct": round(float(calc.mean()) * 100, 2),
            "bias_pts": round(float(d.mean()) * 100, 2), "mae_pts": round(float(np.abs(d).mean()) * 100, 2),
            "rmse_pts": round(float(np.sqrt((d ** 2).mean())) * 100, 2),
            "p95_abs_pts": round(float(np.percentile(np.abs(d), 95)) * 100, 2),
            "max_abs_pts": round(float(np.abs(d).max()) * 100, 2),
            "correlation": round(float(np.corrcoef(calc, ref)[0, 1]), 4),
            "shadow_agreement_pct": round(float(((calc == 0) == (ref == 0)).mean()) * 100, 1)}


def main(src, quick=False):
    t_start = time.time()
    full = demstore.get_dem()
    if full is None or full.synthetic:
        sys.exit("no real DEM installed; run scripts/prepare_dem.py first")
    names = [m.name for m in demstore.members()]
    stacks = [("80 m", names)]
    if "ldem_80s_80m" in names:
        for label, drop in (("240 m", {"ldem_80s_80m"}),
                            ("474 m", {"ldem_80s_80m", "ldem_75s_240m"}),
                            ("1.9 km", {"ldem_80s_80m", "ldem_75s_240m", "ldem_64_south"})):
            keep = [n for n in names if n not in drop]
            if keep and keep != stacks[-1][1]:
                stacks.append((label, keep))
    dems = [(label, demstore.stack(ns)) for label, ns in stacks]
    table = cycle_table()
    ref80 = demstore.members()[0]
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "dems": demstore.status()["dems"],
           "settings": {"cycle_start": CYCLE_START, "cycle_days": round(CYCLE_DAYS, 1), "cycle_step_hours": CYCLE_STEP_H,
                        "azimuths": 720, "max_ray_km": 300, "quick": quick},
           "tables": [], "headline": [], "results": {}}

    # ---- 1 and 2: map comparison at seeded random points, by DEM resolution
    n_pts = 40 if quick else 200
    maps = []
    p85 = os.path.join(src, "AVGVISIB_85S_060M_201608.TIF")
    p75 = os.path.join(src, "AVGVISIB_75S_120M_201608.TIF")
    if os.path.exists(p85):
        maps.append(("60 m map, 85 S to the pole", load_map(p85, 60.0, 151740.0), 2.0, 148.0))
    if os.path.exists(p75):
        maps.append(("120 m map, 80 S to 85 S", load_map(p75, 120.0, 457440.0), 152.0, 298.0))
    rows = []
    out["results"]["map_check"] = []
    for mi, (mlabel, m, r0, r1) in enumerate(maps):
        rng = np.random.default_rng(20261114 + mi)
        lat, lon = random_points(rng, n_pts, r0, r1, ref80)
        ref = nearest(m, lat, lon)
        for label, dem in dems:
            t = time.time()
            calc = np.array([any_light_fraction(dem, la, lo, 0.0, table)[0] for la, lo in zip(lat, lon)])
            st = stats(calc, ref)
            st.update({"map": mlabel, "dem": label, "seconds": round(time.time() - t, 1)})
            out["results"]["map_check"].append(st)
            rows.append([mlabel, label, st["n"], st["published_mean_pct"], st["computed_mean_pct"], st["bias_pts"],
                         st["mae_pts"], st["p95_abs_pts"], st["correlation"], st["shadow_agreement_pct"]])
            print(rows[-1], flush=True)
        # the smooth sphere at the same points
        sm = []
        for la, lo in zip(lat, lon):
            tr = track(Site("s", la, lo), table)
            sm.append(float((tr.sun_frac > 0).mean()))
        st = stats(np.array(sm), ref)
        st.update({"map": mlabel, "dem": "smooth sphere"})
        out["results"]["map_check"].append(st)
        rows.append([mlabel, "smooth sphere", st["n"], st["published_mean_pct"], st["computed_mean_pct"],
                     st["bias_pts"], st["mae_pts"], st["p95_abs_pts"], st["correlation"], st["shadow_agreement_pct"]])
        print(rows[-1], flush=True)
    if rows:
        out["tables"].append({
            "title": "Terrain model against the LOLA team's published average-sunlight maps (real data)",
            "note": f"{n_pts} seeded random points per map. Published: share of time any part of the solar disc is visible "
                    "from the surface (PDS LOLA GDR maps AVGVISIB_85S_060M_201608 and AVGVISIB_75S_120M_201608, LOLA "
                    "team, method of Mazarico et al. 2011), read at the nearest map pixel. Computed: the same quantity "
                    f"from this app's ray-cast skyline, observer at 0 m, one 18.6-year cycle from {CYCLE_START[:10]} in "
                    f"{CYCLE_STEP_H}-hour steps. Differences are in percentage points. 'DEM used here' is the grid under "
                    "the point (80 m: PGDA LDEM_80S_80MPP_ADJ; 240 m: PDS LDEM_75S_240M; 474 m: SVS ldem_64; 1.9 km: "
                    "PDS LDEM_16), with coarser grids beyond its edge. The published maps were computed on the LOLA "
                    "team's own 60 m and 120 m grids, so part of the difference is the DEM, not the method.",
            "columns": ["Published map", "DEM used here", "Points", "Published mean %", "Computed mean %",
                        "Mean difference", "Mean |difference|", "95th pct |difference|", "Correlation",
                        "Same call on permanent shadow %"],
            "rows": rows})
        best = out["results"]["map_check"][0]
        # Ordinary terrain only: most random points are poorly lit.  scripts/validate_more.py adds the figure for
        # well-lit ridge pixels (about 4 points) as its own tile and qualifies the C1 match; run it after this script.
        out["headline"].append({"k": "Sunlit share against the LOLA team's published map: ordinary terrain", "v": f"±{best['mae_pts']:.1f} pts",
                                "s": f"mean |difference| at {best['n']} random points within 5° of the pole, correlation "
                                     f"{best['correlation']:.3f}; smooth sphere at the same points: ±"
                                     f"{[r for r in out['results']['map_check'] if r['dem'].startswith('smooth') and r['map'] == best['map']][0]['mae_pts']:.1f} pts. "
                                     "Rule: any part of the solar disc above the skyline, as the map's label states; the mission "
                                     "card's default asks for half the disc, which is stricter",
                                "tag": "terrain (LOLA, 80 m/px)"})

    # ---- 3: published single-point figures (Glaser et al.), same period and step as Glaser 2018
    t20 = cached_table(grid_start(parse_utc("2017-01-01T00:00:00Z")), 20 * 365 * 24 + 5 * 24, 3600)
    rows = []
    out["results"]["published_points"] = []
    for pt in ([] if quick else PUBLISHED_POINTS):
        lon = ((pt["lon"] + 180.0) % 360.0) - 180.0

        def figures(la, lo, tab):
            s, prof = site_with(full, la, lo, pt["mast_m"])
            tr = track(s, tab)
            return (float((tr.sun_frac > 0).mean()) * 100, float(tr.sun_frac.mean()) * 100,
                    span_longest_dark_days(tr) * 24.0, prof.site_height_m)

        vis, avg, dark_h, z = figures(pt["lat"], lon, t20)
        # ridge crests are tens of metres wide: also report the best point on a 5 x 5 neighbourhood of 80 m steps
        x0, y0 = ref80.project(pt["lat"], lon)
        best = (vis, pt["lat"], lon)
        for dx in (-160, -80, 0, 80, 160):
            for dy in (-160, -80, 0, 80, 160):
                if dx == 0 and dy == 0:
                    continue
                la, lo = ref80.unproject(x0 + dx, y0 + dy)
                v = any_light_fraction(full, float(la), float(lo), pt["mast_m"], table)[0] * 100
                if v > best[0]:
                    best = (v, float(la), float(lo))
        bvis, bavg, bdark, _ = figures(best[1], best[2], t20) if best[1] != pt["lat"] else (vis, avg, dark_h, z)
        rec = dict(pt, computed_visibility_pct=round(vis, 2), computed_avg_illumination_pct=round(avg, 2),
                   computed_longest_dark_h=round(dark_h, 1), site_height_m=round(z, 1),
                   best_within_160m={"lat": round(best[1], 4), "lon": round(best[2], 4), "visibility_pct": round(bvis, 2),
                                     "avg_illumination_pct": round(bavg, 2), "longest_dark_h": round(bdark, 1)})
        out["results"]["published_points"].append(rec)
        rows.append([pt["name"], f"{pt['lat']:.4f}, {pt['lon']:.2f}", f"{pt['mast_m']:g} m",
                     f"{pt['avg']:.1f} / {pt['vis']:.1f} / {pt['dark_h']:.0f} h",
                     f"{avg:.1f} / {vis:.1f} / {dark_h:.0f} h", f"{avg - pt['avg']:+.1f} / {vis - pt['vis']:+.1f}",
                     f"{bavg:.1f} / {bvis:.1f} / {bdark:.0f} h", pt["source"].split(",")[0] + pt["source"].split(",")[1]])
        print(rows[-1], flush=True)
    if rows:
        d_avg = np.array([r["computed_avg_illumination_pct"] - r["avg"] for r in out["results"]["published_points"]])
        d_vis = np.array([r["computed_visibility_pct"] - r["vis"] for r in out["results"]["published_points"]])
        out["results"]["published_points_summary"] = {
            "n": len(rows), "mean_diff_avg_pts": round(float(d_avg.mean()), 2), "mean_abs_diff_avg_pts": round(float(np.abs(d_avg).mean()), 2),
            "mean_diff_vis_pts": round(float(d_vis.mean()), 2), "mean_abs_diff_vis_pts": round(float(np.abs(d_vis).mean()), 2)}
        c1 = [r for r in out["results"]["published_points"] if r["name"] == "Connecting ridge C1" and r["mast_m"] == 2.0]
        if c1:
            sm = track(Site("s", c1[0]["lat"], c1[0]["lon"]), t20)
            out["results"]["c1_smooth_visibility_pct"] = round(float((sm.sun_frac > 0).mean()) * 100, 2)
            out["headline"].append({"k": "Shackleton connecting ridge, 2 m above ground: time with any Sun",
                                    "v": f"{c1[0]['computed_visibility_pct']:.1f}%",
                                    "s": f"published {c1[0]['vis']:.1f}% (Glaser et al. 2018, 20 m DEM); the match is not firm "
                                         f"(a 20 to 40 m shift moves it by 1 to 4 points); smooth sphere at the same "
                                         f"point {out['results']['c1_smooth_visibility_pct']:.1f}%",
                                    "tag": "terrain (LOLA, 80 m/px)"})
        out["tables"].append({
            "title": "Published ridge-top results at the stated coordinates and heights (real data, 80 m DEM here against 20 m DEMs there)",
            "note": "Each cell: average illumination % / solar visibility % (any part of the disc) / longest shadow. Computed "
                    "with the 80 m LOLA mosaic from 2017-01-01 for 20 years in 1-hour steps, the period of Glaser et al. "
                    "2018. The published figures are each paper's best pixel on a 20 m DEM; an 80 m grid cannot place an "
                    "observer on a crest a few tens of metres wide, so single points differ by several points either way. "
                    "'Best nearby' is the best-lit point on a 5 x 5 neighbourhood of 80 m steps around the published "
                    "coordinates. Published values were read through a web-fetch tool (not byte-exact).",
            "columns": ["Point", "Lat, east lon", "Height", "Published", "Computed at the point", "Difference (avg / visibility, pts)",
                        "Computed, best nearby", "Source"],
            "rows": rows})

    # ---- 3b: Earth visibility against Bryant 2009 (radar DEM; its frame is offset from LOLA's)
    rows = []
    out["results"]["earth_points"] = []
    coarse = cached_table(grid_start(parse_utc(CYCLE_START)), int(CYCLE_DAYS * 24 / 6), 6 * 3600)

    def earth_sun(la, lo, tab):
        s, prof = site_with(full, la, lo, 2.0)
        tr = track(s, tab)
        e = [float((tr.earth_clear > -tr.earth_radius_deg).mean()) * 100, float((tr.earth_clear > 0).mean()) * 100,
             float((tr.earth_clear > tr.earth_radius_deg).mean()) * 100]
        sun = [float((tr.sun_frac > 0).mean()) * 100, float((tr.sun_frac >= 0.5).mean()) * 100,
               float((tr.sun_frac >= 0.999).mean()) * 100]
        return e, sun, prof.site_height_m

    for pt in ([] if quick else EARTH_POINTS):
        e0, sun0, z0 = earth_sun(pt["lat"], pt["lon"], table)
        # Bryant chose illumination maxima on a radar DEM whose coordinates sit some hundreds of metres from
        # the LOLA frame.  Find the best-lit point (Sun, half-disc rule) within 1.2 km on the LOLA grid and
        # report Sun and Earth there.  The search looks at sunlight only, so the Earth figure is not selected for.
        x0, y0 = ref80.project(pt["lat"], pt["lon"])
        best = (-1.0, pt["lat"], pt["lon"])
        steps = range(-1120, 1121, 160)
        for dx in steps:
            for dy in steps:
                if dx * dx + dy * dy > 1200 ** 2:
                    continue
                la, lo = ref80.unproject(x0 + dx, y0 + dy)
                s, _ = site_with(full, float(la), float(lo), 2.0)
                v = float((track(s, coarse).sun_frac >= 0.5).mean())
                if v > best[0]:
                    best = (v, float(la), float(lo))
        e, sun, z = earth_sun(best[1], best[2], table)
        moved = float(np.hypot(*(np.array(ref80.project(best[1], best[2])) - np.array([x0, y0]))))
        rec = dict(pt, at_stated_point={"earth": [round(v, 2) for v in e0], "sun": [round(v, 2) for v in sun0], "height_m": round(z0, 1)},
                   best_lit_within_1p2km={"lat": round(best[1], 4), "lon": round(best[2], 4), "moved_m": round(moved),
                                          "earth": [round(v, 2) for v in e], "sun": [round(v, 2) for v in sun],
                                          "height_m": round(z, 1)})
        out["results"]["earth_points"].append(rec)
        f3 = lambda v: " / ".join(f"{x:.1f}" for x in v)  # noqa: E731
        rows.append([pt["name"], f"{pt['lat']:.3f}, {pt['lon']:.3f}", f3(pt["earth"]), f3(e0), f3(e),
                     f"{e[1] - pt['earth'][1]:+.1f}", f3(pt["sun"]), f3(sun0), f3(sun), f"{moved:.0f} m"])
        print(rows[-1], flush=True)
    if rows:
        de = np.array([r["best_lit_within_1p2km"]["earth"][1] - r["earth"][1] for r in out["results"]["earth_points"]])
        de0 = np.array([r["at_stated_point"]["earth"][1] - r["earth"][1] for r in out["results"]["earth_points"]])
        out["results"]["earth_points_summary"] = {
            "n": len(rows), "best_lit_nearby_mean_diff_pts": round(float(de.mean()), 2),
            "best_lit_nearby_mean_abs_diff_pts": round(float(np.abs(de).mean()), 2),
            "at_stated_point_mean_abs_diff_pts": round(float(np.abs(de0).mean()), 2)}
        out["tables"].append({
            "title": 'Earth visibility: the one published per-site table found (Bryant 2009) could not be co-located, so it tests nothing',
            "collapsed": True,
            "note": "Shown so the gap is visible. Each cell: share of time with at least 0 % / 50 % / 100 % of the disc above the skyline, observer 2 m above ground. Published: Bryant 2009, JPL IPN PR 42-176, Goldstone radar DEM at 40 m, 2009-2028, daily steps. Computed here: LOLA 80 m mosaic, one 18.6-year cycle in 3-hour steps. Bryant's sites are illumination maxima on a radar DEM in a different frame. At the stated coordinates the LOLA terrain is off the crest (Sun 14 to 40 % against a published 77 to 95 %), and the best-lit point within 1.2 km on the LOLA grid (160 m search steps, chosen on sunlight only) still does not reach the published sunlight, so these are not the same places and the Earth columns cannot be compared. The Earth side is checked against the LOLA team's own Earth-visibility maps instead, where they are installed: see the Earth tile above and its table below. Also tested: the skyline (against the sunlight maps above, in every direction) and the direction of the Earth (against JPL Horizons). Published values were read through a web-fetch tool (not byte-exact).",
            "columns": ["Site (Bryant 2009)", "Stated lat, east lon", "Published Earth", "Computed Earth at stated point",
                        "Computed Earth at best-lit point nearby", "Earth difference at 50 % (pts), not meaningful", "Published Sun",
                        "Computed Sun at stated point", "Computed Sun at best-lit point nearby", "Distance moved"],
            "rows": rows})

    # ---- 4: per-site year statistics by resolution
    rows = []
    out["results"]["sites_by_resolution"] = []
    polar = [s for s in SITES if s["group"] == "South pole"]
    crit = Criteria()
    for s in polar[: (4 if quick else len(polar))]:
        variants = list(dems) + [("smooth sphere", None)]
        for label, dem in variants:
            if dem is None:
                site = Site(s["name"], s["lat"], s["lon"])
            else:
                site, _ = site_with(dem, s["lat"], s["lon"], 2.0)
            st = span_stats(site, "2027-01-01T00:00:00Z", 365, 60, crit)
            rec = {"site": s["name"], "dem": label, "any_light_pct": st["any_light_pct"], "lit_pct": st["lit_pct"],
                   "longest_dark_days": round(st["longest_dark_h"] / 24, 1),
                   "longest_light_days": round(st["longest_light_h"] / 24, 1),
                   "earth_visible_pct": st["earth_visible_pct"],
                   "longest_earth_outage_days": round(st["longest_earth_outage_h"] / 24, 1)}
            out["results"]["sites_by_resolution"].append(rec)
            rows.append([s["name"] if label == variants[0][0] else "", label, rec["any_light_pct"], rec["lit_pct"],
                         rec["longest_dark_days"], rec["longest_light_days"], rec["earth_visible_pct"],
                         rec["longest_earth_outage_days"]])
    out["tables"].append({
        "collapsed": True,
        "title": "How the answer changes with DEM resolution: calendar year 2027, observer 2 m above ground",
        "note": "Each site computed four times from real LOLA grids of different resolution, then on the smooth sphere. "
                "Hourly samples. 'Sunlit' uses the half-disc rule; darkness means no part of the Sun visible.",
        "columns": ["Site", "DEM at the site", "Any Sun visible %", "Sunlit % (half disc)", "Longest darkness (d)",
                    "Longest light (d)", "Earth in view %", "Longest Earth outage (d)"],
        "rows": rows})

    # ---- 5: hindcast with and without terrain
    hc = hindcast()
    out["results"]["hindcast"] = [
        {"mission": m["mission"], "event": c["label"], "reported_utc": c["reported_utc"],
         "models": c["models"]} for m in hc["missions"] for c in m["checks"]]

    out["seconds"] = round(time.time() - t_start, 1)
    path = os.path.join(HERE, "data", "validation", "terrain_validation.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1)
    print("wrote", path, "in", out["seconds"], "s")
    for t in out["tables"]:
        print("\n" + t["title"])
        print(" | ".join(t["columns"]))
        for r in t["rows"]:
            print(" | ".join(str(x) for x in r))


def span_longest_dark_days(tr):
    from slipday.metrics import longest_run
    step_h = (tr.unix[1] - tr.unix[0]) / 3600.0
    return longest_run(tr.sun_frac <= 0) * step_h / 24.0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], quick="--quick" in sys.argv)
