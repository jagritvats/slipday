"""NASA's nine south-pole landing regions (chosen for the first crewed landing, now planned for Artemis IV) as the option list for missed windows, on published landing sites.

    python scripts/artemis_regions.py

NASA's nine Artemis III candidate regions (NASA, 28 Oct 2024; data/reference/sources/artemis3_regions_2024.html):
Peak near Cabeus B, Haworth, Malapert Massif, Mons Mouton Plateau, Mons Mouton, Nobile Rim 1, Nobile Rim 2,
de Gerlache Rim 2, Slater Plain.  NASA publishes names, not points.  The sites are the 78 candidate landing sites of
Wueller et al. 2026 (JGR Planets, CC BY 4.0; Zenodo record 17084058) in these nine regions, 5 to 11 per region.
They replace the single illustrative point per region that earlier versions of this script chose from the LOLA
team's average-sunlight map (that version: scratch copy, DEEP_PASS_2.md E2 and "Final fixes").

For each missed window of the opening plan and of IM-1, every site is judged with the card's rules (13 touchdown
points within 100 m) at the window's landing and over landings every 6 hours within 72 hours of it.  A region's
cell shows its best site: a non-fragile clear Yes first, then the largest margin.  Writes
data/validation/artemis_regions.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from slipday import regions, sites, windows  # noqa: E402
from slipday.ephem import parse_utc  # noqa: E402
from slipday.metrics import Criteria  # noqa: E402

CRIT = Criteria(stations=True)
OUT = os.path.join(ROOT, "data", "validation", "artemis_regions.json")


def rank(bh):
    """Best site first: found, then not fragile, then the largest margin, then the earliest hour."""
    return (bh["found"], not bh.get("fragile", True), bh.get("slip_margin_days", -1))


def judge_windows(by_region, plan_landing, ks, need_sun, need_earth):
    rows = []
    t0 = parse_utc(plan_landing)
    for k in ks:
        L = windows._hour(t0 + timedelta(days=windows.SYNODIC_DAYS * k)).strftime("%Y-%m-%dT%H:%M:%SZ")
        regs = []
        for code, name in regions.REGIONS:
            per_site = []
            for st in by_region[code]:
                s = sites.custom_site(st["name"] + " (" + name + ", Wueller et al. 2026)", st["lat"], st["lon"])
                j = windows.judge(s, L, need_sun, need_earth, 14, CRIT, 0.0, 2.0, 100.0)
                bh = windows.best_hour(s, L, need_sun, need_earth, 14, CRIT, 0.0, 2.0, 100.0)
                per_site.append({"site": st["name"], "at_window": j["verdict"], "at_window_margin": j["slip_margin_days"],
                                 "fails_on": j["fails_on"], "best_hour": bh})
            best = max(per_site, key=lambda r: rank(r["best_hour"]))
            fails = []
            for r in per_site:
                for f in r["fails_on"]:
                    if f not in fails:
                        fails.append(f)
            yes_w = [r for r in per_site if r["at_window"] == "yes"]
            regs.append({"region": name, "code": code, "n_sites": len(per_site), "best_site": best["site"] if best["best_hour"]["found"] else None,
                         "best_hour": best["best_hour"],
                         "sites_yes": sum(1 for r in per_site if r["best_hour"]["found"]),
                         "sites_yes_not_fragile": sum(1 for r in per_site if r["best_hour"]["found"] and not r["best_hour"].get("fragile")),
                         "at_window": "yes" if yes_w else "no", "at_window_margin": max([r["at_window_margin"] for r in yes_w], default=-1),
                         "fails_on": [] if yes_w else fails, "sites": per_site})
            b = best["best_hour"]
            print(f"  k={k:>2} {L[:16]} {name:<20} {regs[-1]['sites_yes']:>2}/{len(per_site)} sites yes, best "
                  + (f"{best['site']} {b['landing_utc'][:16]} {b['slip_margin_days']} d{' fragile' if b['fragile'] else ''}" if b["found"] else "none"), flush=True)
        rows.append({"k": k, "landing_utc": L, "regions": regs,
                     "regions_yes_within_72h": sum(1 for r in regs if r["best_hour"]["found"]),
                     "regions_yes_not_fragile": sum(1 for r in regs if r["best_hour"]["found"] and not r["best_hour"].get("fragile")),
                     "regions_yes_at_window": sum(1 for r in regs if r["at_window"] == "yes")})
    return rows


def main():
    t = time.time()
    pub = regions.load_sites()
    by_region = {code: [s for s in pub if s["region"] == code] for code, _ in regions.REGIONS}
    doc = {"what": "NASA's nine south-pole landing regions (named 28 Oct 2024; the first crewed landing is now planned for Artemis IV, early 2028) on the published candidate landing sites of Wueller et al. 2026, judged in each missed window",
           "source": "https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/ (data/reference/sources/artemis3_regions_2024.html)",
           "sites_source": regions.CITATION,
           "anchor_rule": "every published candidate landing site of Wueller et al. 2026 in the region (5 to 11 per region); not NASA's landing sites; replaces our earlier single best-lit point per region",
           "anchors": [{"region": name, "code": code, "n_sites": len(by_region[code]), "sites": [s["name"] for s in by_region[code]]}
                       for code, name in regions.REGIONS]}
    print("opening plan, windows 1 to 3 (240 sunlit h, 100 Earth h in 14 days):")
    doc["opening"] = {"plan": "robust_pick 18 Nov 2026 00:00 UTC", "rows": judge_windows(by_region, "2026-11-18T00:00:00Z", [1, 2, 3], 240, 100)}
    print("IM-1, windows -1 (missed, modelled date), 0 (flown), +1 (168 sunlit h, 100 Earth h in 14 days):")
    doc["im1"] = {"plan": "IM-1 flown landing 22 Feb 2024 23:00 UTC", "rows": judge_windows(by_region, "2024-02-22T23:00:00Z", [-1, 0, 1], 168, 100)}
    doc["seconds"] = round(time.time() - t, 1)
    json.dump(doc, open(OUT, "w", encoding="utf-8"), indent=1)
    print("wrote", OUT, doc["seconds"], "s")


if __name__ == "__main__":
    main()
