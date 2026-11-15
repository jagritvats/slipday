"""Upcoming south-pole missions board: precompute (add-on; see ADDON_impact.md).

    python -m slipday.addons.impact_build          # writes data/addons/impact/missions.json (about 3 to 6 minutes)

For each upcoming mission whose landing place and launch period NASA publishes (pages in
data/addons/impact/sources/, URL and sha256 in DOWNLOADS.tsv), this asks the card's own questions:

  * at the mission's published place, which landing times in its published launch period get a clear Yes;
  * of those, how many still get a Yes if the landing slips a week (7 days) or a month (29.5 days);
  * when a slip loses the home place, which of NASA's nine south-pole regions are still open.

The rule (written before the run, ADDON_impact.md section 3):

  * Places: the published candidate landing sites of Wueller et al. 2026 (CC BY 4.0) in NASA's nine regions. A
    mission whose published destination is "Mons Mouton" uses the ten sites of NASA's "Mons Mouton" region
    (MMO01 to MMO10). Artemis IV uses all nine regions. No site is picked or moved by us.
  * Landing times: every 6 hours inside the published launch period (the trip to the Moon is not modelled).
  * The robotic missions use the page's default need (240 sunlit hours and 100 hours of Earth contact in the
    14 days after landing, the Sun and the Earth in view at touchdown). It is illustrative: NASA does not publish
    a surface duration for Griffin-1 or IM-4. VIPER also gets totals over its published 100-day mission.
  * Artemis IV uses the region calendar's rule: a 6.25-day stay with the Sun up every hour, 100 hours of Earth
    contact, the Sun and the Earth in view at touchdown, not fragile (regions.py).
  * Every check is the card's: 13 touchdown points within 100 m, the coarser grid and the near-field sampling,
    Deep Space Network station rule on. A site is Yes only when all members pass.
  * For each calendar month, the first Yes landing time at the home place is re-run through the card's own code
    (robust.mission_card and windows.next_windows) to give the slip margin in days, the answer a week later and
    the answer one synodic month later.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import timedelta

import numpy as np

from .. import regions, windows
from ..ephem import available_steps, cached_table, grid_start, iso, parse_utc
from ..geometry import track
from ..metrics import STEP_S, earth_up, sun_up
from ..robust import mission_card
from ..sites import custom_site

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(ROOT, "data", "addons", "impact")
OUT_PATH = os.path.join(OUT_DIR, "missions.json")
SRC_DIR = os.path.join(OUT_DIR, "sources")

CRIT = regions.CRIT                     # Criteria(stations=True), as the region calendar and the real-missions panel
MASK, MAST, SCATTER = regions.MASK_DEG, regions.MAST_M, regions.SCATTER_M
STEP_H = 6
WEEK_STEPS = 7 * 24 // STEP_H                                  # 28
MONTH_STEPS = int(round(windows.SYNODIC_DAYS * 24 / STEP_H))   # 118 (29.5 days)

CARD = {"key": "card", "sun_h": 240, "earth_h": 100, "window_days": 14.0,
        "text": "240 sunlit hours and 100 hours of Earth contact in the 14 days after landing, the Sun and the Earth "
                "in view at touchdown (the page's default need; illustrative)"}
ARTEMIS = {"key": "artemis", "sun_h": 150, "earth_h": 100, "window_days": 6.25,
           "text": "a 6.25-day stay with the Sun up every hour, 100 hours of Earth contact, the Sun and the Earth in "
                   "view at touchdown, not fragile (the region calendar's rule; 100 hours is illustrative)"}

SRC = {
    "schedule": ("NASA launch schedule", "https://www.nasa.gov/event-type/launch-schedule/", "nasa_launches.html"),
    "clps": ("NASA CLPS deliveries", "https://science.nasa.gov/lunar-science/clps-deliveries/", "nasa_clps_deliveries.html"),
    "to20a": ("NASA TO20A page", "https://science.nasa.gov/lunar-science/clps-deliveries/to20a-astrobotic/", "clps_to20a.html"),
    "cp22": ("NASA CP-22 page", "https://science.nasa.gov/lunar-science/clps-deliveries/cp-22-science/", "clps_cp22.html"),
    "viper": ("NASA VIPER mission page", "https://science.nasa.gov/mission/viper/", "nasa_viper.html"),
    "viper_award": ("NASA release, 19 Sep 2025",
                    "https://www.nasa.gov/news-release/nasa-selects-blue-origin-to-deliver-viper-rover-to-moons-south-pole/",
                    "nasa_viper_blue_origin.html"),
    "artemis4": ("NASA Artemis IV page", "https://www.nasa.gov/mission/artemis-iv/", "nasa_artemis4.html"),
    "artemis3": ("NASA Artemis III page", "https://www.nasa.gov/mission/artemis-iii/", "nasa_artemis3.html"),
    "ct3": ("NASA CT-3 page", "https://science.nasa.gov/lunar-science/clps-deliveries/ct-3-science/", "clps_ct3.html"),
    "cs6": ("NASA CS-6 page", "https://science.nasa.gov/lunar-science/programs/clps/cs-6-science/", "clps_cs6.html"),
    "lupex": ("JAXA exploration programme page", "https://www.exploration.jaxa.jp/e/program/#lupex", "jaxa_lupex.html"),
    "cnsa": ("CNSA English home page", "http://www.cnsa.gov.cn/english/", "cnsa_en.html"),
    "lpsc": ("NASA LPSC 2026 abstract (George et al., NTRS 20250011660), saved earlier for the entry",
             "https://ntrs.nasa.gov/api/citations/20250011660/downloads/AIIIUpdateLPSC2026.docx",
             "../../../reference/sources/artemis3_update_lpsc2026.docx"),
}

# Missions with a published landing place and launch period. Quotes are copied from the saved pages.
MISSIONS = [
    {"id": "griffin1", "name": "Griffin-1", "who": "NASA CLPS task order TO20A; lander by Astrobotic, listed by NASA as Voyager Griffin-1",
     "launch_text": "Late 2026", "span": ("2026-11-15T00:00:00Z", "2026-12-31T18:00:00Z"),
     "span_note": "15 Nov (today) to 31 Dec 2026",
     "place_text": "Mons Mouton", "home": ["MMO"], "need": "card",
     "quotes": [("schedule", "Late 2026 Moon Base: Voyager Griffin-1"),
                ("to20a", "Voyager's Griffin-1 lander will deliver NASA's Lunar Retroreflector Array (LRA) to Mons Mouton (South Pole).")]},
    {"id": "im4", "name": "IM-4", "who": "NASA CLPS task order CP-22; Intuitive Machines Nova-C lander; carries ESA's PROSPECT drill",
     "launch_text": "2027", "span": ("2027-01-01T00:00:00Z", "2027-12-31T18:00:00Z"), "span_note": "all of 2027",
     "place_text": "Mons Mouton", "home": ["MMO"], "need": "card",
     "quotes": [("schedule", "2027 Moon Base: Intuitive Machines IM-4"),
                ("cp22", "The Intuitive Machines Nova-C lander (IM-4) will deliver six NASA CLPS science payloads to Mons Mouton."),
                ("cp22", "PROSPECT , developed by the European Space Agency (ESA)")]},
    {"id": "viper", "name": "VIPER on Blue Moon MK1", "who": "NASA rover, NASA CLPS task order CS-7; Blue Origin Blue Moon MK1 lander",
     "launch_text": "landing by late 2027", "span": ("2027-09-01T00:00:00Z", "2027-12-31T18:00:00Z"),
     "span_note": "1 Sep to 31 Dec 2027 (our reading of \"late 2027\")",
     "place_text": "Mons Mouton", "home": ["MMO"], "need": "card", "long_days": 100,
     "quotes": [("viper", "On September 19, 2025, NASA announced that VIPER and its instruments will be delivered to Mons Mouton by a Blue Origin Blue Moon MK-1 lander as part of task order CS-7."),
                ("viper_award", "The rover has a targeted science window for its 100-day mission that requires a landing by late 2027.")]},
    {"id": "artemis4", "name": "Artemis IV", "who": "NASA crewed landing; two crew members on the surface",
     "launch_text": "Early 2028", "span": ("2028-01-01T00:00:00Z", "2028-04-30T18:00:00Z"),
     "span_note": "1 Jan to 30 Apr 2028 (our reading of \"early 2028\")",
     "place_text": "NASA's nine candidate landing regions near the South Pole", "home": [c for c, _ in regions.REGIONS],
     "need": "artemis",
     "quotes": [("artemis4", "Mission Type Crewed Surface Landing LAUNCH Early 2028"),
                ("artemis4", "two crew members will descend to the surface and spend approximately a week near the South Pole of the Moon"),
                ("artemis4", "the agency has identified nine candidate landing regions near the lunar South Pole"),
                ("lpsc", "Surface stay duration varies approximately 5.75 to 6.25 days depending on mission epoch")]},
]

# Missions we looked for and could not place: what is published, and why there is no point.
LISTED = [
    {"name": "Artemis III", "launch_text": "2027", "why": "No landing. NASA now flies Artemis III as a test in low Earth orbit; the first crewed landing is Artemis IV.",
     "quote": ("artemis3", "On Artemis III, NASA will test one or both human landing systems in low Earth orbit, demonstrating rendezvous and docking operations.")},
    {"name": "Blue Moon MK1 first flight (CT-3)", "launch_text": "2027",
     "why": "NASA gives the destination only as \"the lunar south pole\"; no landing site on the pages read.",
     "quote": ("ct3", "The Blue Origin Blue Moon Mark 1 (MK1) lander will deliver two NASA science payloads to the lunar south pole.")},
    {"name": "Blue Ghost Mission 4 (CS-6)", "launch_text": "not on NASA's launch schedule",
     "why": "Destination given only as \"the lunar south pole\"; no site and no date on the pages read.",
     "quote": ("cs6", "The Firefly Aerospace Blue Ghost Mission 4 lander will deliver four NASA CLPS science payloads to the lunar south pole.")},
    {"name": "Nova-D (CT-4)", "launch_text": "not on NASA's launch schedule",
     "why": "Destination given only as \"the lunar south pole\"; no site and no date on the pages read.",
     "quote": ("clps", "The Intuitive Machines Nova-D lander will deliver six NASA CLPS science payloads to the lunar south pole.")},
    {"name": "LUPEX (JAXA with ISRO)", "launch_text": "No earlier than 2028",
     "why": "JAXA gives only \"lunar polar region\"; no landing site published on the page read.",
     "quote": ("lupex", "Lunar Polar Exploration Mission No earlier than 2028")},
    {"name": "Chang'e-7 (CNSA)", "launch_text": "not found first-hand",
     "why": "CNSA's English pages that we could reach give no landing site or date for it, so it is left out.",
     "quote": ("cnsa", None)},
]


def _sha(path: str) -> str | None:
    if not path or not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def sources() -> dict:
    out = {}
    for k, (title, url, fname) in SRC.items():
        p = os.path.normpath(os.path.join(SRC_DIR, fname))
        out[k] = {"title": title, "url": url, "file": os.path.relpath(p, ROOT).replace(os.sep, "/"), "sha256": _sha(p)}
    return out


def refresh_sources() -> None:
    """Rewrite only the "sources" block of the stored board (after a source entry changes)."""
    d = json.load(open(OUT_PATH, encoding="utf-8"))
    d["sources"] = sources()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)


def flags_for(members: list, n_points: int, table, starts: np.ndarray, need: dict) -> np.ndarray:
    """Clear Yes at each landing hour index in ``starts``: every member passes ``need`` (the card's rule)."""
    if need["key"] == "artemis":
        f = regions.site_flags(members, n_points, table, starts, regions.STAY_H, need["earth_h"], CRIT)
        return f["yes"] & ~f["fragile"]
    w = int(round(need["window_days"] * 24))
    ok = np.ones(starts.size, dtype=bool)
    for p in members:
        tr = track(p, table, CRIT.min_sun_fraction)
        lit = sun_up(tr)
        ev = earth_up(tr, CRIT) & (tr.earth_el >= CRIT.min_earth_el)
        ok &= (regions.window_sum(lit, w)[starts] >= need["sun_h"]) & (regions.window_sum(ev, w)[starts] >= need["earth_h"])
        ok &= lit[starts] & ev[starts]
    return ok


def _need(key: str) -> dict:
    return CARD if key == "card" else ARTEMIS


def card_check(site_rec: dict, landing: str, need: dict, long_days: float = 0.0) -> dict:
    """The card's own answer for one landing at one published site: verdict, slip margin, a week later, a month later."""
    s = custom_site(site_rec["name"], site_rec["lat"], site_rec["lon"], MASK, MAST)
    m = mission_card(s, landing, need["sun_h"], need["earth_h"], need["window_days"], CRIT, MASK, MAST, SCATTER, 15)
    wk = m["days"][7]
    nxt = windows.next_windows(s, landing, [1], need["sun_h"], need["earth_h"], need["window_days"], CRIT, MASK, MAST,
                               SCATTER)["rows"][0]
    out = {"site": site_rec["name"], "region": regions.NAME[site_rec["region"]], "lat": site_rec["lat"], "lon": site_rec["lon"],
           "landing_utc": m["landing_utc"], "verdict": m["verdict"], "slip_margin_days": int(m["slip_margin_days"]),
           "week_later": {"landing_utc": wk["landing_utc"], "verdict": wk["verdict"],
                          "fails_on": windows.fails_on(wk.get("reasons")) if wk["verdict"] != "yes" else []},
           "month_later": {"landing_utc": nxt["landing_utc"], "verdict": nxt["verdict"],
                           "slip_margin_days": int(nxt["slip_margin_days"]), "fails_on": nxt["fails_on"]},
           "points": m["sure"]["points"]}
    if long_days:
        j = windows.judge(s, landing, need["sun_h"], need["earth_h"], need["window_days"], CRIT, MASK, MAST, SCATTER,
                          long_days=long_days)
        out["long"] = j.get("long")
    return out


def build(verbose: bool = True) -> dict:
    t0 = time.time()
    sites = regions.load_sites(True)
    if not sites:
        raise SystemExit("data/regions/wueller2026_sites.json is missing")
    first = min(m["span"][0] for m in MISSIONS)
    last = max(m["span"][1] for m in MISSIONS)
    s0 = grid_start(parse_utc(first), STEP_S)
    s_last = grid_start(parse_utc(last), STEP_S)
    n_land = (s_last - s0) // 3600 // STEP_H + 1 + MONTH_STEPS + 2           # landing times incl. a month of slip
    stay = int(round(CARD["window_days"] * 24))
    n_hours = min((n_land - 1) * STEP_H + stay + 1, available_steps(s0, STEP_S))
    table = cached_table(s0, n_hours, STEP_S)
    starts = np.arange(n_land) * STEP_H
    starts = starts[starts + stay <= n_hours - 1]
    n_land = starts.size
    times = [iso(s0 + int(h) * 3600) for h in starts]
    yes = {"card": np.zeros((len(sites), n_land), dtype=bool), "artemis": np.zeros((len(sites), n_land), dtype=bool)}
    for i, rec in enumerate(sites):
        members, n_pts = regions.members_of(rec["lat"], rec["lon"], rec["name"])
        for key in yes:
            yes[key][i] = flags_for(members, n_pts, table, starts, _need(key))
        if verbose and i % 10 == 0:
            print(f"  site {i + 1}/{len(sites)} {rec['name']} ({time.time() - t0:.0f} s)", flush=True)
    codes = [c for c, _ in regions.REGIONS]
    reg_idx = {c: [i for i, r in enumerate(sites) if r["region"] == c] for c in codes}
    open_ = {k: np.array([v[reg_idx[c]].any(axis=0) for c in codes]) for k, v in yes.items()}

    srcs = sources()
    out_missions = []
    for m in MISSIONS:
        need = _need(m["need"])
        a = (grid_start(parse_utc(m["span"][0]), STEP_S) - s0) // 3600 // STEP_H
        b = (grid_start(parse_utc(m["span"][1]), STEP_S) - s0) // 3600 // STEP_H
        span = np.arange(a, b + 1)
        home_rows = [codes.index(c) for c in m["home"]]
        home_sites = [i for c in m["home"] for i in reg_idx[c]]
        home_open = open_[need["key"]][home_rows].any(axis=0)
        good = span[home_open[span]]
        wk_ok = home_open[good + WEEK_STEPS]
        mo_ok = home_open[good + MONTH_STEPS]
        others = [r for r in range(len(codes)) if r not in home_rows]
        # when the slip loses the home place: which other regions are open at the slipped time
        lost_wk = good[~wk_ok] + WEEK_STEPS
        lost_mo = good[~mo_ok] + MONTH_STEPS
        def rescue(idx):
            if idx.size == 0 or not others:
                return {"times": int(idx.size), "any_other_open": 0, "by_region": []}
            o = open_[need["key"]][others][:, idx]
            by = sorted(({"region": regions.NAME[codes[r]], "open_times": int(o[k].sum())} for k, r in enumerate(others)),
                        key=lambda x: -x["open_times"])
            return {"times": int(idx.size), "any_other_open": int(o.any(axis=0).sum()), "by_region": by}
        # site-by-site share of the span (published order)
        per_site = [{"site": sites[i]["name"], "region": regions.NAME[sites[i]["region"]], "lat": sites[i]["lat"],
                     "lon": sites[i]["lon"], "yes_share": round(float(yes[need["key"]][i, span].mean()), 3)}
                    for i in home_sites]
        # per calendar month: the first Yes landing time at the home place, re-run through the card's own code
        months = []
        seen = set()
        for t in good:
            ym = times[t][:7]
            if ym in seen:
                continue
            seen.add(ym)
            i_site = next(i for i in home_sites if yes[need["key"]][i, t])
            chk = card_check(sites[i_site], times[t], need, m.get("long_days", 0))
            chk["agrees_with_card"] = chk["verdict"] == "yes"
            months.append({"month": ym, **chk})
            if verbose:
                print(f"  {m['id']} {ym}: {chk['site']} {chk['landing_utc'][:16]} {chk['verdict']} margin {chk['slip_margin_days']} "
                      f"week {chk['week_later']['verdict']} month {chk['month_later']['verdict']}", flush=True)
        n_months_in_span = len({times[t][:7] for t in span})
        out_missions.append({
            "id": m["id"], "name": m["name"], "who": m["who"], "launch_text": m["launch_text"], "span": list(m["span"]),
            "span_note": m["span_note"], "place_text": m["place_text"],
            "home_regions": [regions.NAME[c] for c in m["home"]], "home_sites": len(home_sites),
            "need": need["text"], "long_days": m.get("long_days", 0),
            "quotes": [{"source": k, "text": q, "url": srcs[k]["url"]} for k, q in m["quotes"]],
            "landing_times": int(span.size), "good_times": int(good.size),
            "good_share": round(float(good.size / span.size), 3) if span.size else 0.0,
            "months_in_span": n_months_in_span, "months_with_a_good_time": len(months),
            "slip_week": {"still_yes": int(wk_ok.sum()), "of": int(good.size),
                          "share": round(float(wk_ok.mean()), 3) if good.size else None, "lost": rescue(lost_wk)},
            "slip_month": {"still_yes": int(mo_ok.sum()), "of": int(good.size),
                           "share": round(float(mo_ok.mean()), 3) if good.size else None, "lost": rescue(lost_mo)},
            "per_site": per_site, "months": months,
            "label": "Approximate: the place and the period are NASA's published ones (sources below); the sites are "
                     "Wueller et al. 2026's published candidates; the landing times are spread over the period. "
                     "Not the mission's own plan."})

    listed = [{"name": x["name"], "launch_text": x["launch_text"], "why": x["why"],
               "quote": x["quote"][1], "url": srcs[x["quote"][0]]["url"]} for x in LISTED]
    doc = {"what": "Upcoming south-pole missions: does the published place work in the published period, and what a "
                   "slip of a week or a month does", "made_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "rule": {"step_hours": STEP_H, "week_days": 7, "month_days": round(MONTH_STEPS * STEP_H / 24, 2),
                    "check": "the card's: 13 touchdown points within 100 m, the coarser grid, the near-field sampling; "
                             "Deep Space Network station rule on; Yes only when all agree",
                    "sites": "published candidate landing sites, Wueller et al. 2026 (CC BY 4.0), in NASA's nine regions",
                    "dates": "every 6 hours inside the published launch period; the trip to the Moon is not modelled",
                    "needs": {"card": CARD["text"], "artemis": ARTEMIS["text"]}},
           "citation": regions.CITATION, "missions": out_missions, "listed_without_a_point": listed,
           "sources": srcs, "first_time": times[0], "n_times": n_land, "seconds": None}
    doc["seconds"] = round(time.time() - t0, 1)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    if verbose:
        print(f"wrote {OUT_PATH} ({doc['seconds']} s)")
    return doc


if __name__ == "__main__":
    build()
