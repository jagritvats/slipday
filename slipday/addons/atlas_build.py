"""Builds the slip-tolerant atlas, 2027 to 2035 (add-on).

    python -m slipday.addons.atlas_build [--procs 4] [--cache <dir for skylines>]

For every landing time every 6 hours from 2027-01-01 00:00 to 2035-12-31 18:00 UTC it judges, with the entry's own
code (``regions.members_of`` and ``regions.site_flags``, the vectorised form of the mission card), each of the 78
published candidate sites in NASA's nine south-pole landing regions (Wueller et al. 2026) and the 14 curated south-pole
sites of ``sites.py``.  The rule is the one of the existing 2027 to 2030 region calendar, unchanged: a 6.25-day stay,
the Sun up for the whole stay, 100 hours of Earth contact, 13 touchdown points within 100 m plus the coarser grid and
the near-field sampling; a region is open when one of its sites is a clear Yes that is not fragile.

Writes data/addons/atlas/atlas_flags.npz (per site and landing time, bit-packed) and data/addons/atlas/atlas.json
(everything the page and the router serve).  Data files are read in place and never written.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from itertools import combinations
from multiprocessing import Pool

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(ROOT, "data", "addons", "atlas")
FLAGS_PATH = os.path.join(OUT_DIR, "atlas_flags.npz")
JSON_PATH = os.path.join(OUT_DIR, "atlas.json")

START = "2027-01-01T00:00:00Z"
END = "2035-12-31T18:00:00Z"
YEARS = list(range(2027, 2036))
OVERLAP_YEARS = (2027, 2028, 2029, 2030)
SMOOTH_DAYS = 31            # first version of the drift measure (kept for the record, see atlas_drift)
SYNODIC_DAYS = 29.530589    # one synodic month: new Moon to new Moon, one cycle of sunlight at the pole
MAX_LAG_DAYS = 60
KEYS = ("yes", "fragile", "yes_sun_only", "fragile_sun_only")


def _grid():
    from slipday import regions
    from slipday.ephem import parse_utc
    h0 = int(parse_utc(START).timestamp())
    n = int((parse_utc(END).timestamp() - h0) // 3600) // regions.STEP_H + 1
    starts = np.arange(n) * regions.STEP_H
    return h0, starts, int(starts[-1]) + regions.STAY_H + 1


_TAB = None


def _work(job):
    """One site: its check members and its four flag arrays over every landing time."""
    global _TAB
    from slipday import regions
    from slipday.ephem import cached_table
    h0, starts, n_tab = _grid()
    if _TAB is None:
        _TAB = cached_table(h0, n_tab, 3600)
    key, lat, lon, name = job
    t = time.time()
    mem, npts = regions.members_of(lat, lon, name)
    f = regions.site_flags(mem, npts, _TAB, starts)
    return key, {k: np.asarray(f[k], dtype=bool) for k in KEYS}, len(mem), npts, round(time.time() - t, 1)


def _jobs():
    from slipday import regions, sites
    out = [("w:" + s["name"], s["lat"], s["lon"], s["name"]) for s in regions.load_sites()]
    out += [("c:" + s["id"], s["lat"], s["lon"], s["name"]) for s in sites.SITES if s["group"] == "South pole"]
    return out


def compute(procs: int) -> dict:
    jobs = _jobs()
    res = {}
    with Pool(procs) as pool:
        for k, (key, flags, nmem, npts, sec) in enumerate(pool.imap_unordered(_work, jobs)):
            res[key] = (flags, nmem, npts)
            print(f"{k + 1:>3}/{len(jobs)} {key:<28} members {nmem:>2} yes {int(flags['yes'].sum()):>5} "
                  f"sun-only {int(flags['yes_sun_only'].sum()):>5} ({sec} s)", flush=True)
    keys = [j[0] for j in jobs]
    np.savez_compressed(FLAGS_PATH, keys=np.array(keys),
                        members=np.array([res[k][1] for k in keys]), points=np.array([res[k][2] for k in keys]),
                        **{f: np.packbits(np.array([res[k][0][f] for k in keys]), axis=1) for f in KEYS})
    return load_flags()


def load_flags(path: str = FLAGS_PATH) -> dict:
    z = np.load(path)
    _, starts, _ = _grid()
    n = starts.size
    return {"keys": [str(k) for k in z["keys"]], "members": z["members"], "points": z["points"],
            **{f: np.unpackbits(z[f], axis=1)[:, :n].astype(bool) for f in KEYS}}


# ------------------------------------------------------------------ summaries

def best_set(open_: np.ndarray, k: int) -> tuple:
    """The k regions that together cover the most times, trying every set (ties: first in NASA's order)."""
    best, cov = None, -1.0
    for c in combinations(range(open_.shape[0]), k):
        v = float(open_[list(c)].any(axis=0).mean()) if open_.shape[1] else 0.0
        if v > cov + 1e-12:
            best, cov = c, v
    return list(best), cov


def open_arrays(fl: dict, variant: str) -> tuple:
    """(region rows, curated-site rows): open (clear Yes, not fragile) per landing time."""
    from slipday import regions
    yk, fk = ("yes", "fragile") if variant == "main" else ("yes_sun_only", "fragile_sun_only")
    ok = fl[yk] & ~fl[fk]
    keys = fl["keys"]
    site_region = {s["name"]: s["region"] for s in regions.load_sites()}
    reg_rows, reg_robust, reg_frag = [], [], []
    for code, _ in regions.REGIONS:
        idx = [i for i, k in enumerate(keys) if k.startswith("w:") and site_region[k[2:]] == code]
        reg_robust.append(ok[idx].sum(axis=0))
        reg_frag.append(fl[fk][idx].sum(axis=0))
        reg_rows.append(ok[idx].any(axis=0))
    cur_idx = [i for i, k in enumerate(keys) if k.startswith("c:")]
    return np.array(reg_rows), ok[cur_idx], np.array(reg_robust), np.array(reg_frag), cur_idx


def subsolar_drift(years) -> dict:
    """Same measure as the existing calendar (scripts/region_availability.py): per calendar year the day of the Sun's
    lowest sub-solar latitude, from the ephemeris, then a straight-line fit; here for 2027 to 2035."""
    from slipday.ephem import compute_table, iso, parse_utc
    from slipday.geometry import sub_point
    t0 = int(parse_utc(f"{years[0]}-01-01T00:00:00Z").timestamp())
    days = np.arange(0, (len(years) + 1) * 366)
    lat, _ = sub_point(compute_table(t0 + days * 86400.0).sun)
    rows, doy = [], []
    for y in years:
        a = int((parse_utc(f"{y}-01-01T00:00:00Z").timestamp() - t0) // 86400)
        b = int((parse_utc(f"{y + 1}-01-01T00:00:00Z").timestamp() - t0) // 86400)
        lo = int(np.argmin(lat[a:b]))
        rows.append({"year": y, "lowest_on": iso(t0 + (a + lo) * 86400)[:10], "lowest_subsolar_lat_deg": round(float(lat[a + lo]), 3)})
        doy.append(lo)
    # a season that crosses New Year jumps by about a year: unwrap the steps into (-182.5, 182.5]
    steps = [((doy[i + 1] - doy[i] + 182.5) % 365.25) - 182.5 for i in range(len(doy) - 1)]
    unwrapped = np.concatenate([[doy[0]], doy[0] + np.cumsum(steps)])
    span = days[:int((parse_utc(f"{years[-1] + 1}-01-01T00:00:00Z").timestamp() - t0) // 86400)]
    return {"years": rows, "step_days": [round(-s, 1) for s in steps],
            "mean_earlier_per_year_days": round(float(-np.polyfit(np.arange(len(doy)), unwrapped, 1)[0]), 2),
            "same_fit_as_atlas": season_drift(lat[:span.size], t0 + span * 86400.0),
            "expected_days": round(365.25 - 346.62, 2)}


def season_drift(open_: np.ndarray, times_unix: np.ndarray) -> dict:
    """How much earlier the season comes each calendar year, read from the atlas.

    The landing times are cut into whole synodic months (29.53 days, one cycle of sunlight at the pole) and the share
    of open landing times is taken in each.  Because each piece holds one full month, the month-by-month pattern drops
    out and only the season is left.  A sine wave is then fitted to those monthly shares for every period from 300 to
    400 days in 0.1-day steps, and the period that fits best is the length of the season cycle.  The drift is
    365.25 days minus that period.  Checked on made-up signals with known periods (tests/addons/test_atlas.py)."""
    t = (times_unix - times_unix[0]) / 86400.0
    n = int(t[-1] // SYNODIC_DAYS)
    idx = (t // SYNODIC_DAYS).astype(int)
    s = np.array([open_[idx == i].mean() for i in range(n)])
    tc = (np.arange(n) + 0.5) * SYNODIC_DAYS
    fits = []
    for P in np.round(np.arange(300.0, 400.0001, 0.1), 1):
        A = np.c_[np.ones(n), np.cos(2 * np.pi * tc / P), np.sin(2 * np.pi * tc / P)]
        coef = np.linalg.lstsq(A, s, rcond=None)[0]
        fits.append((float(np.sum((A @ coef - s) ** 2)), float(P)))
    rss, P = min(fits)
    tot = float(np.sum((s - s.mean()) ** 2))
    return {"months_used": n, "season_period_days": P, "earlier_per_year_days": round(365.25 - P, 2),
            "share_of_variation_explained": round(1 - rss / tot, 3) if tot > 0 else None}


def atlas_drift(any_open: np.ndarray, times_unix: np.ndarray) -> dict:
    """First try at reading the drift from the atlas, kept for the record: daily shares of landing times with any
    of the nine regions open, averaged over 31 days, and for each pair of years the shift (0 to 60 days earlier) that
    best lines the next year up with this one.  It does not measure the season: a 31-day average does not cancel the
    month-by-month pattern, which comes about 11 days earlier each calendar year (365.25 days minus 12 synodic
    months), and the shift locks onto that (on a made-up signal with an 18.6-day season drift and a monthly pattern it
    reads about 12 days; tests/addons/test_atlas.py).  ``season_drift`` replaced it."""
    per_day = any_open.reshape(-1, 4).mean(axis=1)           # 4 landing times a day
    sm = np.convolve(per_day, np.ones(SMOOTH_DAYS) / SMOOTH_DAYS, mode="same")
    day0 = datetime.fromtimestamp(int(times_unix[0]), tz=timezone.utc)
    pairs = []
    for y in YEARS[:-1]:
        a = (datetime(y, 1, 1, tzinfo=timezone.utc) - day0).days
        b = (datetime(y + 1, 1, 1, tzinfo=timezone.utc) - day0).days
        seg = sm[a + SMOOTH_DAYS:b - SMOOTH_DAYS]                # inner part, clear of the smoothing edges
        best, lag = -2.0, None
        for L in range(0, MAX_LAG_DAYS + 1):
            s0 = a + SMOOTH_DAYS + (b - a) - L
            other = sm[s0:s0 + seg.size]
            if other.size < seg.size or seg.std() == 0 or other.std() == 0:
                continue
            r = float(np.corrcoef(seg, other)[0, 1])
            if r > best:
                best, lag = r, L
        pairs.append({"from": y, "to": y + 1, "earlier_days": lag, "correlation": round(best, 3)})
    lags = [p["earlier_days"] for p in pairs if p["earlier_days"] is not None]
    return {"pairs": pairs, "mean_earlier_per_year_days": round(float(np.mean(lags)), 2) if lags else None,
            "smoothing": "31 days of daily shares", "measures_the_season": False}


def summarise(fl: dict) -> dict:
    from slipday import regions, sites
    from slipday.ephem import iso
    h0, starts, _ = _grid()
    t_unix = h0 + starts * 3600
    times = [iso(int(t)) for t in t_unix]
    year = np.array([int(t[:4]) for t in times])
    month = np.array([int(t[5:7]) for t in times])
    names = [n for _, n in regions.REGIONS]
    cur_sites = [s for s in sites.SITES if s["group"] == "South pole"]
    out = {"variants": {}}
    for variant in ("main", "sun_only"):
        reg, cur, robust, frag, cur_idx = open_arrays(fl, variant)
        anyo = reg.any(axis=0)
        heat_reg = [[[round(float(reg[r, (year == y) & (month == m)].mean()), 3) for m in range(1, 13)] for y in YEARS]
                    for r in range(len(names))]
        heat_any = [[round(float(anyo[(year == y) & (month == m)].mean()), 3) for m in range(1, 13)] for y in YEARS]
        heat_cur = [[[round(float(cur[i, (year == y) & (month == m)].mean()), 3) for m in range(1, 13)] for y in YEARS]
                    for i in range(len(cur_sites))]
        per_year = []
        for y in YEARS:
            sel = year == y
            o = reg[:, sel]
            all9 = float(o.any(axis=0).mean())
            best = [best_set(o, k) for k in range(1, 4)]
            need = next(k for k in range(1, 10) if best_set(o, k)[1] >= all9 - 1e-12)
            per_year.append({"year": y, "n_times": int(sel.sum()), "all_nine": round(all9, 4),
                             "best": [{"k": k + 1, "regions": [names[i] for i in best[k][0]], "share": round(best[k][1], 4)}
                                      for k in range(3)],
                             "regions_to_match_all_nine": need,
                             "region_share": {names[r]: round(float(o[r].mean()), 4) for r in range(len(names))},
                             "curated_share": {cur_sites[i]["name"]: round(float(cur[i, sel].mean()), 4) for i in range(len(cur_sites))}})
        whole = [best_set(reg, k) for k in range(1, 4)]
        fixed = [{"k": k + 1, "regions": [names[i] for i in whole[k][0]], "share": round(whole[k][1], 4),
                  "by_year": {str(y): round(float(reg[whole[k][0]][:, year == y].any(axis=0).mean()), 4) for y in YEARS}}
                 for k in range(3)]
        ranked = sorted(per_year, key=lambda r: (r["all_nine"], r["best"][2]["share"]))
        out["variants"][variant] = {
            "heat": {"regions": [{"name": names[r], "code": regions.REGIONS[r][0], "months": heat_reg[r]} for r in range(len(names))],
                     "any_of_nine": heat_any,
                     "curated": [{"name": cur_sites[i]["name"], "id": cur_sites[i]["id"], "months": heat_cur[i]} for i in range(len(cur_sites))]},
            "per_year": per_year, "whole_span_best": fixed, "all_nine_whole_span": round(float(anyo.mean()), 4),
            "worst_year": ranked[0]["year"], "best_year": ranked[-1]["year"],
            "season_drift": season_drift(anyo, t_unix),
            "season_drift_by_region": {names[r]: season_drift(reg[r], t_unix) for r in range(len(names))},
            "first_try_drift": atlas_drift(anyo, t_unix),
            "_robust": robust, "_frag": frag}
    out["times"] = {"first": times[0], "last": times[-1], "step_hours": regions.STEP_H, "n": len(times)}
    out["_year"] = year
    return out


def overlap_check(summ: dict) -> dict:
    """Compare 2027 to 2030 with the existing calendar (data/validation/region_availability.json), landing time by
    landing time: the count of clear non-fragile sites and of fragile sites in each region."""
    from slipday import regions
    old = regions.load()
    if old is None:
        return {"available": False}
    n = old["n_times"]
    out = {"available": True, "n_times": n, "first": old["rule"]["first"], "last": old["rule"]["last"], "variants": {}}
    for variant in ("main", "sun_only"):
        v = summ["variants"][variant]
        rows = []
        for r, reg in enumerate(old[variant]["regions"]):
            rob_old, frag_old = regions.decode(reg["robust_sites"]), regions.decode(reg["fragile_sites"])
            rob_new, frag_new = v["_robust"][r][:n], v["_frag"][r][:n]
            rows.append({"region": reg["region"], "times_differing_robust": int((rob_old != rob_new).sum()),
                         "times_differing_fragile": int((frag_old != frag_new).sum()),
                         "share_open_existing": reg["share_open"], "share_open_atlas": round(float((rob_new > 0).mean()), 4)})
        out["variants"][variant] = {"rows": rows, "all_identical": all(x["times_differing_robust"] == 0 and x["times_differing_fragile"] == 0 for x in rows),
                                    "any_open_existing": old[variant]["any_open"],
                                    "any_open_atlas": round(float((v["_robust"][:, :n] > 0).any(axis=0).mean()), 4)}
    return out


def write_json(summ: dict, fl: dict, seconds: float) -> dict:
    from slipday import regions
    doc = {"what": "Slip-tolerant atlas, 2027 to 2035: when each of NASA's nine south-pole landing regions (now for Artemis IV) and each curated south-pole site has "
                   "workable landing times, and how many regions must stay open each year",
           "rule": {"step_hours": regions.STEP_H, "first": summ["times"]["first"], "last": summ["times"]["last"],
                    "n_times": summ["times"]["n"], "stay_hours": regions.STAY_H, "stay_days": regions.STAY_DAYS,
                    "need_earth_h": regions.NEED_EARTH_H, "scatter_m": regions.SCATTER_M, "mast_m": regions.MAST_M,
                    "same_as": "data/validation/region_availability.json (the existing 2027 to 2030 calendar)",
                    "code": "slipday.regions.members_of and slipday.regions.site_flags, imported unchanged"},
           "citation": regions.CITATION,
           "n_sites": {"published": sum(1 for k in fl["keys"] if k.startswith("w:")), "curated": sum(1 for k in fl["keys"] if k.startswith("c:"))},
           "members_per_site": sorted(set(int(x) for x in fl["members"])),
           "years": YEARS, "variants": {}}
    for variant, v in summ["variants"].items():
        doc["variants"][variant] = {k: val for k, val in v.items() if not k.startswith("_")}
    doc["overlap"] = overlap_check(summ)
    doc["subsolar_drift"] = subsolar_drift(YEARS)
    doc["seconds"] = round(seconds, 1)
    doc["built_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    return doc


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--procs", type=int, default=4)
    p.add_argument("--cache", default=os.path.join(tempfile.gettempdir(), "slipday_atlas_hcache"),
                   help="folder for computed skylines (default: a temporary folder, so the entry's cache is never written)")
    p.add_argument("--summary-only", action="store_true", help="rebuild atlas.json from the stored flags")
    a = p.parse_args(argv)
    os.environ["SLIPDAY_HORIZON_CACHE"] = a.cache
    os.makedirs(OUT_DIR, exist_ok=True)
    t = time.time()
    fl = load_flags() if a.summary_only else compute(max(1, min(4, a.procs)))
    summ = summarise(fl)
    doc = write_json(summ, fl, time.time() - t)
    for variant in ("main", "sun_only"):
        v = doc["variants"][variant]
        print(variant, "best year", v["best_year"], "worst year", v["worst_year"], "season drift", v["season_drift"],
              "first try", v["first_try_drift"]["mean_earlier_per_year_days"])
        print("  by region:", {k: x["earlier_per_year_days"] for k, x in v["season_drift_by_region"].items()})
        for r in v["per_year"]:
            print("  ", r["year"], "all nine", r["all_nine"], "best 1/2/3", [b["share"] for b in r["best"]],
                  [b["regions"] for b in r["best"]][0], "need", r["regions_to_match_all_nine"])
        print("  overlap identical:", doc["overlap"]["variants"][variant]["all_identical"] if doc["overlap"]["available"] else None)
    print("sub-solar drift", doc["subsolar_drift"]["mean_earlier_per_year_days"], doc["subsolar_drift"]["step_days"],
          doc["subsolar_drift"]["same_fit_as_atlas"])
    print("wrote", JSON_PATH, doc["seconds"], "s")


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    main()
