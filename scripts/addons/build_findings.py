"""Build the "What we found" science panel data: data/addons/findings/findings.json.

    .venv\\Scripts\\python scripts\\addons\\build_findings.py            # everything (about 5 minutes)
    .venv\\Scripts\\python scripts\\addons\\build_findings.py --no-ridge # skip the two year-long ridge runs

Every number is recomputed here from Slipday's stored data or its own code; nothing is copied from the documents.
The documents' figures are kept beside ours (``doc_says``) only so the page and the tests can show where they differ.

1. Coarse terrain is optimistic: the 20 m re-check of the slip-margin map for 14 weekly dates (``slipday.finer20``
   counting on the stored 20 m skylines), the Shackleton ridge longest darkness on the 80 m and 20 m stacks
   (``metrics.span_stats``), and which places the 5 m site models cover (``data/dem_live/dems.json``).
2. How many regions must stay open: exhaustive best sets of 1 to 9 regions from the atlas flags
   (``data/addons/atlas/atlas_flags.npz``), with and without the illustrative 100-hour Earth need.
3. Checks: the season drift from the ephemeris, the LOLA team's Earth maps (stored points) and JPL Horizons
   (stored tables in ``fixtures/``).
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from itertools import combinations

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT_DIR = os.path.join(ROOT, "data", "addons", "findings")
OUT = os.path.join(OUT_DIR, "findings.json")
KM_PER_DEG = math.pi / 180.0 * 1737.4
RIDGE_START = "2026-11-18T00:00:00Z"


# ------------------------------------------------------------------ 1a. 80 m against 20 m, 14 weekly dates

def twenty_metre_check() -> dict:
    from slipday import finer20
    from slipday.metrics import Criteria
    if not finer20.available():
        return {"available": False}
    pts = np.load(os.path.join(ROOT, "data", "field", "pole_points.npz"))
    lat, lon = pts["lat"], pts["lon"]
    crit = Criteria(stations=True)
    starts = [(datetime(2026, 11, 18, tzinfo=timezone.utc) + timedelta(days=7 * k)).strftime("%Y-%m-%dT%H:%M:%SZ")
              for k in range(14)]
    rows, per_point = [], {}
    for s in starts:
        r = finer20.cells(s, 60, 14.0, crit, 0.0, 240.0, 100.0, True, True) or {"cells": {}}
        c = r["cells"]
        opt = sum(1 for m20, ok in c.values() if not ok and m20 < 0)      # 80 m keeps a margin, 20 m loses it
        pes = sum(1 for m20, ok in c.values() if not ok and m20 >= 0)     # 80 m loses it, 20 m keeps it
        rows.append({"start": s[:10], "points": len(c), "agree": len(c) - opt - pes,
                     "coarse_yes_fine_no": opt, "coarse_no_fine_yes": pes})
        for k, (m20, ok) in c.items():
            p = per_point.setdefault(int(k), [0, 0, 0])
            p[0] += 1
            if not ok:
                p[1 if m20 < 0 else 2] += 1
        print(f"  {s[:10]}: {len(c)} points, coarse-yes/fine-no {opt}, coarse-no/fine-yes {pes}", flush=True)
    tot = {k: sum(r[k] for r in rows) for k in ("points", "agree", "coarse_yes_fine_no", "coarse_no_fine_yes")}
    dis = tot["coarse_yes_fine_no"] + tot["coarse_no_fine_yes"]
    pts_out = []
    for i, (n, o, p) in sorted(per_point.items()):
        r_km = (90.0 + float(lat[i])) * KM_PER_DEG
        a = math.radians(float(lon[i]))
        pts_out.append([round(r_km * math.sin(a), 2), round(r_km * math.cos(a), 2), n, o, p])
    return {"available": True, "dates": rows, "dates_with_points": sum(1 for r in rows if r["points"]),
            "totals": tot, "disagreements": dis,
            "agree_share": round(tot["agree"] / max(tot["points"], 1), 4),
            "optimistic_share_of_disagreements": round(tot["coarse_yes_fine_no"] / max(dis, 1), 4),
            "map_points": {"columns": ["x_km", "y_km", "dates_checked", "coarse_yes_fine_no", "coarse_no_fine_yes"],
                           "note": "x towards 90 E, y towards 0 E, km from the pole (polar view)", "rows": pts_out},
            "rule": "Page default need: 240 sunlit hours and 100 hours of Earth contact (illustrative) in 14 days, "
                    "Earth only with a NASA ground station 10 degrees up, 13 touchdown points within 100 m, 60 landing "
                    "dates. A point agrees when both grids give the same answer to 'do all 13 touchdown points pass "
                    "on the planned date'.",
            "doc_says": {"agree": 2922, "points": 3376, "coarse_yes_fine_no": 452, "disagreements": 454}}


# ------------------------------------------------------------------ 1b. Shackleton ridge longest darkness

def _ridge_child(dem_dir: str) -> None:
    os.environ["SLIPDAY_DEM_DIR"] = dem_dir
    os.environ["SLIPDAY_HORIZON_CACHE"] = tempfile.mkdtemp(prefix="slipday_findings_")
    from slipday import demstore
    from slipday.metrics import Criteria, span_stats
    from slipday.sites import get_site
    demstore.reload()
    s = get_site("shackleton")
    st = span_stats(s, RIDGE_START, 365.0, 60, Criteria(0.0, -90.0, -90.0, 0.0))
    print(json.dumps({"stack": demstore.status().get("label"), "lat": s.lat, "lon": s.lon,
                      "longest_dark_h": st["longest_dark_h"], "any_light_pct": st["any_light_pct"]}))


def ridge_check() -> dict:
    out = {}
    for key, d in (("coarse_80m", "dem"), ("fine_20m", "dem20"), ("live_finest", "dem_live")):
        p = os.path.join(ROOT, "data", d)
        if not os.path.exists(os.path.join(p, "dems.json")):
            continue
        t = time.time()
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--ridge-child", p], capture_output=True,
                           text=True, cwd=ROOT, timeout=900)
        line = [x for x in r.stdout.splitlines() if x.startswith("{")]
        if not line:
            out[key] = {"error": (r.stderr or r.stdout)[-400:]}
            continue
        out[key] = json.loads(line[-1])
        out[key]["seconds"] = round(time.time() - t, 1)
        print(f"  ridge {key}: {out[key]['longest_dark_h']} h, any Sun {out[key]['any_light_pct']} %", flush=True)
    return {"available": "coarse_80m" in out and "fine_20m" in out, "point": "Shackleton connecting ridge C1",
            "span": f"365 days from {RIDGE_START[:10]}, hourly; dark = no part of the Sun's disc above the skyline",
            "published_h": 112,
            "published_note": "Published longest darkness at this point, as cited in the entry's validation notes "
                              "(not recomputed: it is the literature value we check against).",
            "stacks": out, "doc_says": {"coarse_80m": 194, "fine_20m": 110}}


# ------------------------------------------------------------------ 1c. 5 m coverage

def five_metre_coverage() -> dict:
    p = os.path.join(ROOT, "data", "dem_live", "dems.json")
    if not os.path.exists(p):
        return {"available": False}
    dems = json.load(open(p, encoding="utf-8"))["dems"]
    five = [d for d in dems if 0 < float(d.get("pixel_m") or 0) <= 5.0]
    return {"available": True, "count": len(five),
            "models": [{"name": d["name"], "product": d.get("product", "")} for d in five]}


# ------------------------------------------------------------------ 2. regions to keep open

def region_coverage() -> dict:
    from slipday import regions
    z = np.load(os.path.join(ROOT, "data", "addons", "atlas", "atlas_flags.npz"))
    keys = [str(k) for k in z["keys"]]
    n_all = 13148                                   # 2027-01-01 to 2035-12-31 18:00, every 6 h
    n_4y = 5844                                     # 2027 to 2030
    unpack = lambda a: np.unpackbits(z[a], axis=1)[:, :n_all].astype(bool)  # noqa: E731
    site_region = {s["name"]: s["region"] for s in regions.load_sites()}
    names = [(code, name) for code, name in regions.REGIONS]
    out = {"n_times": {"2027-2030": n_4y, "2027-2035": n_all}, "step_hours": 6, "variants": {}}
    for var, yk, fk in (("earth_need", "yes", "fragile"), ("sunlight_only", "yes_sun_only", "fragile_sun_only")):
        ok = unpack(yk) & ~unpack(fk)
        rows = []
        for code, _ in names:
            idx = [i for i, k in enumerate(keys) if k.startswith("w:") and site_region.get(k[2:]) == code]
            rows.append(ok[idx].any(axis=0))
        reg = np.array(rows)
        res = {}
        for period, n in (("2027-2030", n_4y), ("2027-2035", n_all)):
            r = reg[:, :n]
            curve = []
            for k in range(1, len(names) + 1):
                best, cov = None, -1
                for c in combinations(range(len(names)), k):
                    v = int(r[list(c)].any(axis=0).sum())
                    if v > cov:
                        best, cov = c, v
                curve.append({"k": k, "share": round(cov / n, 4), "times": cov, "regions": [names[i][1] for i in best]})
            res[period] = {"curve": curve, "single": sorted(
                [{"region": names[i][1], "share": round(float(r[i].mean()), 4)} for i in range(len(names))],
                key=lambda x: -x["share"])}
        out["variants"][var] = res
    out["sites"] = sum(1 for k in keys if k.startswith("w:"))
    out["rule"] = ("A region is open at a landing time when at least one of its published candidate sites (Wueller et "
                   "al. 2026) is a clear Yes that is not fragile: a 6.25-day stay with the Sun up every hour, checked "
                   "at 13 touchdown points within 100 m. 'Earth need' adds 100 hours of Earth contact with a NASA "
                   "ground station; the 100 hours are illustrative, not a NASA requirement. Best sets are found by "
                   "trying every combination. Shares are of landing times every 6 hours, not of launch opportunities.")
    out["doc_says"] = {"earth_need_2027-2030": {"1": 0.26, "3": 0.37, "9": 0.399},
                       "sunlight_only_2027-2030": {"1": 0.448, "3": 0.894, "9": 0.911}}
    return out


# ------------------------------------------------------------------ 3. checks

def season_drift() -> dict:
    from slipday.ephem import compute_table, iso, parse_utc
    from slipday.geometry import sub_point
    years = list(range(2025, 2036))
    t0 = int(parse_utc(f"{years[0]}-01-01T00:00:00Z").timestamp())
    days = np.arange(0, (len(years) + 1) * 366)
    lat, _ = sub_point(compute_table(t0 + days * 86400.0).sun)
    rows, doy = [], []
    for y in years:
        a = int((parse_utc(f"{y}-01-01T00:00:00Z").timestamp() - t0) // 86400)
        b = int((parse_utc(f"{y + 1}-01-01T00:00:00Z").timestamp() - t0) // 86400)
        lo = int(np.argmin(lat[a:b]))
        rows.append({"year": y, "lowest_on": iso(t0 + (a + lo) * 86400)[:10], "day_of_year": lo + 1,
                     "subsolar_lat_deg": round(float(lat[a + lo]), 3)})
        doy.append(a + lo)                          # days since 2025-01-01: no wrap problem
    # the date of the season in each year, taken as days since that year's 1 January, then unwrapped
    d_in_year = np.array([r["day_of_year"] for r in rows], dtype=float)
    steps = ((np.diff(d_in_year) + 182.625) % 365.25) - 182.625
    unwrapped = np.concatenate([[d_in_year[0]], d_in_year[0] + np.cumsum(steps)])
    slope = float(np.polyfit(np.array(years, dtype=float), unwrapped, 1)[0])
    k8 = years.index(2032) + 1
    slope8 = float(np.polyfit(np.array(years[:k8], dtype=float), unwrapped[:k8], 1)[0])
    # second measure: fit one sine wave to the daily sub-solar latitude for every period 300 to 400 days
    span = days[:int((parse_utc("2036-01-01T00:00:00Z").timestamp() - t0) // 86400)].astype(float)
    y = lat[:span.size]
    best = None
    for P in np.round(np.arange(300.0, 400.0001, 0.05), 2):
        A = np.c_[np.ones(span.size), np.cos(2 * np.pi * span / P), np.sin(2 * np.pi * span / P)]
        rss = float(np.sum((A @ np.linalg.lstsq(A, y, rcond=None)[0] - y) ** 2))
        if best is None or rss < best[0]:
            best = (rss, float(P))
    eclipse_year = 346.62
    return {"years": rows, "measured_earlier_per_year_days": round(-slope, 2),
            "measured_2025_2032_days": round(-slope8, 2),
            "sine_fit_period_days": best[1], "sine_fit_earlier_per_year_days": round(365.25 - best[1], 2),
            "expected_earlier_per_year_days": round(365.25 - eclipse_year, 2),
            "expected_note": "365.25 days minus the eclipse year (346.62 days): the Moon's tilted orbit turns once in "
                             "18.6 years, so the polar summer comes back about 18.6 days earlier each calendar year.",
            "how": "Slipday's own ephemeris, daily: the day each year when the Sun stands furthest south of the "
                   "lunar equator, then a straight-line fit (2025 to 2035, and 2025 to 2032 like the region calendar); and a sine wave fitted to the daily sub-solar latitude, whose best period is the season cycle.",
            "doc_says": {"region_calendar": 18.4, "expected": 18.63}}


def lola_maps() -> dict:
    from slipday import refmaps
    d = json.load(open(os.path.join(ROOT, "data", "validation", "more_validation.json"), encoding="utf-8"))
    out = []
    for m in d["e"]["maps"]:
        p = np.array(m["points"], dtype=float)
        # stored per point: lat, lon, then the model's Earth-in-view share for centre, any part, whole disc, mean
        # disc fraction, and the Sun.  The published value is read here from the LOLA map file itself.
        ref = refmaps.load(os.path.join(ROOT, "data", "reference", m["reference"]["file"]))
        pub = ref.nearest(p[:, 0], p[:, 1])
        if np.nanmax(pub) > 1.5:                    # percent maps
            pub = pub / 100.0
        good = np.isfinite(pub)
        p, pub = p[good], pub[good]
        mod = p[:, 3]
        out.append({"map": m["map"], "points": int(len(p)), "rule": "any part of the Earth's disc (the maps' own label)",
                    "mean_abs_diff_pts": round(float(np.abs(mod - pub).mean()) * 100, 2),
                    "correlation": round(float(np.corrcoef(mod, pub)[0, 1]), 4),
                    "published_mean_pct": round(float(pub.mean()) * 100, 2),
                    "model_mean_pct": round(float(mod.mean()) * 100, 2),
                    "pairs": [[round(float(a), 4), round(float(b), 4)] for a, b in zip(pub, mod)]})
    return {"maps": out, "what": "Share of time the Earth is in view at seeded points, Slipday's model against the LOLA "
            "team's Earth-visibility maps (PGDA AVGVISIB ... EARTH).",
            "doc_says": {"60 m": [0.97, 0.9946], "120 m": [0.69, 0.9984]}}


def horizons_check() -> dict:
    from slipday import horizons
    from slipday.geometry import Site
    raw = os.path.join(ROOT, "fixtures")
    rows = []
    for f in sorted(os.listdir(raw)):
        if not (f.startswith("horizons_") and f.endswith(".csv")):
            continue
        text = open(os.path.join(raw, f), encoding="utf-8", errors="replace").read()
        m = re.search(r"Target: (\w+).*E-lon ([-\d.]+) deg, lat ([-\d.]+) deg", text)
        if not m:
            continue
        tab = horizons.parse_table(text)
        r = horizons.compare_rows(Site("fx", float(m.group(3)), float(m.group(2))), m.group(1).lower(), tab, "de421")
        rows.append({"file": f, "target": r["target"], "rows": r["rows"], "max_abs_el_deg": r["max_abs_el_deg"],
                     "max_abs_az_deg": r["max_abs_az_deg"]})
    return {"tables": rows, "rows": sum(r["rows"] for r in rows),
            "max_abs_el_deg": max((r["max_abs_el_deg"] for r in rows), default=None),
            "max_abs_az_deg": max((r["max_abs_az_deg"] for r in rows), default=None),
            "what": "Sun and Earth elevation and azimuth from JPL Horizons (stored tables for three real landing "
                    "sites) against Slipday's own ephemeris."}


def main(argv=None) -> dict:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--ridge-child"]:
        _ridge_child(argv[1])
        return {}
    t = time.time()
    print("1a. 20 m check", flush=True)
    f20 = twenty_metre_check()
    print("1b. Shackleton ridge", flush=True)
    ridge = ridge_check() if "--no-ridge" not in argv else {"available": False}
    if "--no-ridge" in argv and os.path.exists(OUT):                     # keep the stored ridge result
        ridge = json.load(open(OUT, encoding="utf-8"))["coarse_is_optimistic"].get("ridge", ridge)
    print("2. regions", flush=True)
    reg = region_coverage()
    print("3. checks", flush=True)
    doc = {
        "what": "What we found: findings recomputed from Slipday's own stored data and code.",
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coarse_is_optimistic": {"twenty_m": f20, "ridge": ridge, "five_m": five_metre_coverage()},
        "regions": reg,
        "checks": {"season_drift": season_drift(), "lola_earth_maps": lola_maps(), "horizons": horizons_check()},
    }
    doc["seconds"] = round(time.time() - t, 1)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print(f"wrote {OUT} in {doc['seconds']} s")
    return doc


if __name__ == "__main__":
    main()
