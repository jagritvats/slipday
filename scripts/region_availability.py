"""How many of NASA's nine south-pole landing regions must stay open, on the published sites of Wueller et al. 2026.

    SLIPDAY_HORIZON_CACHE=<scratch dir> python scripts/region_availability.py

Rule in slipday/regions.py and DEEP_PASS_3.md (F2).  For each of the 78 published sites in the nine regions,
every 6 hours from 2027 to 2030: clear Yes / fragile with the card's 13-point check, a 6.25-day stay, the Sun up
the whole stay, 100 hours of Earth contact.  Then per region: open (a non-fragile clear Yes at one of its sites
or more) and fragile-only; coverage of the best k regions (greedy, and the best set by trying all sets).

Also: (1) a sample of (site, time) pairs re-judged with robust.mission_card itself; (2) the cross-check against
the paper's SunDaysYY (longest run of Sun-visible days in each midsummer period, 12-hour steps, any part of the
disc), at each site centre on the 80 m skyline; (3) the yearly drift of the season from the ephemeris (subsolar
latitude), against the paper's Table 2.

Writes data/validation/region_availability.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from slipday import regions  # noqa: E402
from slipday.ephem import cached_table, compute_table, iso, parse_utc  # noqa: E402
from slipday.geometry import Site, sub_point  # noqa: E402
from slipday.robust import mission_card  # noqa: E402

CHECK_YEARS = (2027, 2028, 2029, 2030)
N_SAMPLE = 48
SEED = 20261115


def subsolar_drift():
    """Daily subsolar latitude 2025-2032 from the ephemeris; per year the midsummer period (latitude at or below
    -1.5 degrees, the paper's threshold) and the day of the lowest latitude."""
    t0 = int(parse_utc("2025-01-01T00:00:00Z").timestamp())
    days = np.arange(0, 8 * 366)
    tab = compute_table(t0 + days * 86400.0)
    lat, _ = sub_point(tab.sun)
    out = []
    for y in range(2025, 2033):
        a = int((parse_utc(f"{y}-01-01T00:00:00Z").timestamp() - t0) // 86400)
        b = int((parse_utc(f"{y + 1}-01-01T00:00:00Z").timestamp() - t0) // 86400)
        la = lat[a:b]
        idx = np.nonzero(la <= -1.5)[0]
        lo = int(np.argmin(la))
        day = lambda i: iso(t0 + (a + int(i)) * 86400)[:10]  # noqa: E731
        # the main run of days at or below -1.5 (the longest contiguous run, joining gaps of up to 3 days)
        runs, cur = [], []
        for i in idx:
            if cur and i - cur[-1] > 3:
                runs.append(cur)
                cur = []
            cur.append(int(i))
        if cur:
            runs.append(cur)
        main = max(runs, key=len) if runs else []
        out.append({"year": y, "lowest_subsolar_lat_deg": round(float(la[lo]), 3), "lowest_on": day(lo),
                    "midsummer_first": day(main[0]) if main else None, "midsummer_last": day(main[-1]) if main else None,
                    "days_at_or_below_1p5S": len(idx),
                    "paper_first": regions.MIDSUMMER[y][0], "paper_last": regions.MIDSUMMER[y][1]})
    lows = [parse_utc(r["lowest_on"] + "T00:00:00Z") for r in out]
    doy = [(d - datetime(d.year, 1, 1, tzinfo=timezone.utc)).days for d in lows]
    return {"years": out, "lowest_day_of_year": doy,
            "shift_per_year_days": [doy[i] - doy[i + 1] for i in range(len(doy) - 1)],
            "mean_shift_per_year_days": round(float(np.polyfit(np.arange(len(doy)), doy, 1)[0]) * -1, 2),
            "eclipse_year_days": 346.62, "expected_shift_days": round(365.25 - 346.62, 2)}


def main():
    t_all = time.time()
    sites = regions.load_sites()
    h0 = int(parse_utc(regions.START).timestamp())
    n_land = int((parse_utc(regions.END).timestamp() - h0) // 3600) // regions.STEP_H + 1
    starts = np.arange(n_land) * regions.STEP_H
    n_tab = int(starts[-1]) + regions.STAY_H + 1
    tab = cached_table(h0, n_tab, 3600)
    # the cross-check needs the midsummer periods, which lie inside 2027-2030; the same hourly table covers them
    res, cross = [], []
    members_cache = {}
    for k, s in enumerate(sites):
        t = time.time()
        mem, npts = regions.members_of(s["lat"], s["lon"], s["name"])
        members_cache[s["name"]] = (mem, npts)
        f = regions.site_flags(mem, npts, tab, starts)
        res.append(f)
        row = {"name": s["name"], "region": s["region"]}
        for y in CHECK_YEARS:
            a, b = regions.MIDSUMMER[y]
            row[str(y)] = {"ours": regions.longest_lit_run_days(mem[0], tab, h0, a, b), "paper": s["sun_days"][str(y)]}
        cross.append(row)
        print(f"{k + 1:>2}/{len(sites)} {s['name']:<10} yes {int(f['yes'].sum()):>4} fragile {int(f['fragile'].sum()):>4} "
              f"sun-only {int(f['yes_sun_only'].sum()):>4} | " + " ".join(f"{y}: {row[str(y)]['ours']:g}/{row[str(y)]['paper']}" for y in CHECK_YEARS)
              + f" ({time.time() - t:.1f} s)", flush=True)

    times = [iso(h0 + int(h) * 3600) for h in starts]
    doc = {"what": "How many of NASA's nine south-pole landing regions (chosen for the first crewed landing, now planned for Artemis IV, early 2028) must stay open: availability on the published landing sites "
                   "of Wueller et al. 2026, 2027 to 2030",
           "citation": regions.CITATION,
           "nasa_quote": ("End-to-end mission availability analyses demonstrate that individual regions typically provide limited "
                          "viable opportunities when all constraints are simultaneously satisfied. To support acceptable annual "
                          "mission availability and increase flexibility in launch timing, more than one landing regions must be "
                          "maintained for Artemis III specifically."),
           "nasa_source": "George, Rubio, Lawrence, Curell, LPSC 2026 abstract, NTRS 20250011660 (data/reference/sources/artemis3_update_lpsc2026.docx)",
           "rule": {"step_hours": regions.STEP_H, "first": times[0], "last": times[-1], "n_times": len(times),
                    "stay_days": regions.STAY_DAYS, "stay_hours": regions.STAY_H, "need_earth_h": regions.NEED_EARTH_H,
                    "sun": "Sun up (half the disc above the skyline) every hour of the stay", "stations": True,
                    "check": "13 touchdown points within 100 m, the coarser grid, the near-field sampling; 2 m mast",
                    "fragile": "at a touchdown point the Sun's centre within 0.27 deg of the skyline during the stay, or the Earth's at touchdown",
                    "open": "at least one published site of the region is a clear Yes that is not fragile",
                    "greedy": "first the region open most often, then each time the region that adds the most times not yet covered"},
           "first_time": times[0], "step_hours": regions.STEP_H, "n_times": len(times)}

    variants = {}
    for vname, ykey, fkey in (("main", "yes", "fragile"), ("sun_only", "yes_sun_only", "fragile_sun_only")):
        regs = []
        open_ = []
        for code, name in regions.REGIONS:
            idx = [i for i, s in enumerate(sites) if s["region"] == code]
            robust = np.sum([res[i][ykey] & ~res[i][fkey] for i in idx], axis=0)
            frag = np.sum([res[i][fkey] for i in idx], axis=0)
            op = robust > 0
            fo = (robust == 0) & (frag > 0)
            open_.append(op)
            regs.append({"code": code, "region": name, "sites": [sites[i]["name"] for i in idx], "n_sites": len(idx),
                         "share_open": round(float(op.mean()), 4), "share_fragile_only": round(float(fo.mean()), 4),
                         "open_by_year": {str(y): round(float(op[[t[:4] == str(y) for t in times]].mean()), 4) for y in CHECK_YEARS},
                         "robust_sites": regions.encode(robust), "fragile_sites": regions.encode(frag)})
        open_ = np.array(open_)
        order = regions.greedy(open_)
        bests = regions.best_sets(open_)
        curve = []
        for k in range(1, len(order) + 1):
            ch = order[:k]
            by_year = {}
            for y in CHECK_YEARS:
                m = np.array([t[:4] == str(y) for t in times])
                by_year[str(y)] = round(float(open_[ch][:, m].any(axis=0).mean()), 4)
            curve.append({"k": k, "regions": [regions.REGIONS[r][1] for r in ch], "added": regions.REGIONS[order[k - 1]][1],
                          "coverage": round(regions.coverage(open_, ch), 4), "by_year": by_year,
                          "best_set": [regions.REGIONS[r][1] for r in bests[k - 1][0]], "best_coverage": round(bests[k - 1][1], 4)})
        variants[vname] = {"regions": regs, "curve": curve,
                           "any_open": round(float(open_.any(axis=0).mean()), 4),
                           "fragile_yes_site_times": int(sum(int(r[fkey].sum()) for r in res)),
                           "yes_site_times": int(sum(int(r[ykey].sum()) for r in res))}
        print(vname, "coverage by k:", [c["coverage"] for c in curve], "best:", [c["best_coverage"] for c in curve])
        print("  greedy order:", [c["added"] for c in curve])
    doc["main"], doc["sun_only"] = variants["main"], variants["sun_only"]

    # (1) re-judge a sample with mission_card itself
    rng = np.random.default_rng(SEED)
    agree, sample = 0, []
    yes_pairs = [(i, j) for i in range(len(sites)) for j in np.nonzero(res[i]["yes"])[0][::97]]
    no_pairs = [(int(i), int(j)) for i, j in zip(rng.integers(0, len(sites), 4 * N_SAMPLE), rng.integers(0, len(times), 4 * N_SAMPLE))]
    pick = [yes_pairs[int(x)] for x in rng.choice(len(yes_pairs), N_SAMPLE // 2, replace=False)] + no_pairs[:N_SAMPLE // 2]
    for i, j in pick:
        mem, _ = members_cache[sites[i]["name"]]
        m = mission_card(mem[0], times[j], regions.STAY_H, regions.NEED_EARTH_H, regions.STAY_DAYS, regions.CRIT,
                         regions.MASK_DEG, regions.MAST_M, regions.SCATTER_M, 1)
        a, b = m["verdict"] == "yes", bool(res[i]["yes"][j])
        agree += int(a == b)
        sample.append({"site": sites[i]["name"], "landing_utc": times[j], "mission_card": m["verdict"], "vectorised_yes": b})
    doc["sample_check"] = {"pairs": len(pick), "agree": agree, "rows": sample}
    print(f"sample check against mission_card: {agree} of {len(pick)} agree")

    # (2) cross-check against SunDaysYY
    diffs = {y: np.array([r[str(y)]["ours"] - r[str(y)]["paper"] for r in cross]) for y in CHECK_YEARS}
    summ = {}
    for y in CHECK_YEARS:
        d = diffs[y]
        ours = np.array([r[str(y)]["ours"] for r in cross])
        pap = np.array([r[str(y)]["paper"] for r in cross])
        summ[str(y)] = {"sites": int(d.size), "within_0p5_day": int((np.abs(d) <= 0.5).sum()), "within_1_day": int((np.abs(d) <= 1.0).sum()),
                        "within_3_days": int((np.abs(d) <= 3.0).sum()), "median_diff_days": round(float(np.median(d)), 2),
                        "ours_longer": int((d > 1).sum()), "ours_shorter": int((d < -1).sum()),
                        "both_at_least_10": int(((ours >= 10) & (pap >= 10)).sum()), "both_under_10": int(((ours < 10) & (pap < 10)).sum()),
                        "disagree_on_10": int(((ours >= 10) != (pap >= 10)).sum()),
                        "correlation": round(float(np.corrcoef(ours, pap)[0, 1]), 3) if ours.std() > 0 and pap.std() > 0 else None}
        print(y, summ[str(y)])
    doc["cross_check"] = {"what": ("Longest run of consecutive days with any part of the Sun above the skyline in each midsummer period, "
                                   "12-hour samples at 00 and 12 UTC, at each published site's centre on our 80 m skyline (2 m), against "
                                   "the paper's SunDaysYY (60 m QuickMap TerrainShadows, 12-hour steps, 2 m)"),
                          "summary": summ, "rows": cross}

    # (3) the yearly drift of the season
    doc["drift"] = subsolar_drift()
    print("drift:", doc["drift"]["shift_per_year_days"], "mean", doc["drift"]["mean_shift_per_year_days"])
    for r in doc["drift"]["years"]:
        print("  ", r)
    doc["times"] = {"first": times[0], "step_hours": regions.STEP_H, "n": len(times)}
    doc["seconds"] = round(time.time() - t_all, 1)
    json.dump(doc, open(regions.OUT_PATH, "w", encoding="utf-8"), indent=1)
    print("wrote", regions.OUT_PATH, doc["seconds"], "s")


if __name__ == "__main__":
    main()
