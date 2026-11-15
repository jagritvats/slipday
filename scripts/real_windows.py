"""Rule R10 (DEEP_PASS.md): next launch windows for two real south-pole missions, and the Earth's drift between
windows for the default page's sites.  Prints the tables and writes data/validation/real_windows.json.

    python scripts/real_windows.py

Sources (data/reference/sources/, URL and sha256 in DOWNLOADS.tsv): IM-1's monthly 3 to 6 day windows and the
landing pinned to the Sun and the Earth at the site (Spaceflight Now, 27 Oct 2023; Space.com, Feb 2024); VIPER's
100-day mission and "a landing by late 2027" (NASA, 19 Sep 2025); VIPER's area "west of Nobile crater" (NASA SVS
4937).  The VIPER point and window phase are assumptions, labelled as such in the output.
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from slipday import sites, windows  # noqa: E402
from slipday.metrics import Criteria  # noqa: E402

CRIT = Criteria(stations=True)
OUT = os.path.join(ROOT, "data", "validation", "real_windows.json")


def show(title, res):
    print(title)
    for r in res["rows"]:
        extra = ""
        if "long" in r:
            lg = r["long"]
            extra = (f" | 100 d: Sun {lg['sunlit_h_min']} h, Earth {lg['earth_h_min']} h, both {lg['sun_and_earth_h_min']} h, "
                     f"longest night {lg['night_met_h_max']} h")
        print(f"  k={r.get('k', '-'):>2} {r['landing_utc'][:16]} {r['verdict']:>8} margin {r['slip_margin_days']:>2} "
              f"({r['points_passing']}/{r['points']}) sun {r['sunlit_h']} earth {r['earth_h']} | night met {r['night_met_h']} h, "
              f"outage met {r['outage_met_h']} h{extra}", flush=True)


def main() -> None:
    t0 = time.time()
    doc = {"rule": "R10 in DEEP_PASS.md", "made_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    # IM-1, retrospective: the flown window and the one it missed
    im1 = sites.get_site("im1")
    r = windows.next_windows(im1, "2024-02-22T23:00:00Z", [-1, 0, 1, 2], 168, 100, 14, CRIT, 0.0, 2.0, 100.0)
    r["mission"] = {"name": "IM-1 Odysseus", "flown_k": 0, "need": "168 sunlit hours in 14 days (published plan of about seven days); 100 hours of Earth contact (illustrative)",
                    "sources": ["Spaceflight Now 27 Oct 2023 (monthly 3 to 6 day windows; NET 12 Jan 2024)", "Space.com Feb 2024 (three-day window to land on 22 Feb)"]}
    doc["im1"] = r
    show("IM-1 at Malapert A, windows k = -1 (January, missed), 0 (flown), +1, +2:", r)
    # IM-1's published January window, day by day (rule R12): opening NET 12 Jan 2024, landing 5 to 7 days after launch
    jan = []
    for d in range(17, 26):
        L = "2024-01-%02dT10:00:00Z" % d
        j = windows.judge(im1, L, 168, 100, 14, CRIT, 0.0, 2.0, 100.0)
        jan.append({"landing_utc": L, "verdict": j["verdict"], "margin": j["slip_margin_days"], "fails_on": j["fails_on"], "sunlit_h": j["sunlit_h"]})
        print(f"  IM-1 January {L[:16]}: {j['verdict']} {j['slip_margin_days']} {j['fails_on']}")
    doc["im1_january"] = {"rule": "R12 in DEEP_PASS.md", "rows": jan,
                          "source": "Spaceflight Now 27 Oct 2023: window opening NET 12 Jan 2024, 3 to 6 days a month, landing about five to seven days after launch"}
    # VIPER, prospective: west rim of Nobile, landings after local sunrise, Sep to Dec 2027, 100-day totals
    la, lo = windows.rim_point(-85.2752, 53.2725, 79.27233, 270.0)
    viper = sites.custom_site("Nobile crater west rim (illustrative point for VIPER)", la, lo)
    lands = [x for x in windows.sunrise_windows(viper, "2027-08-25T00:00:00Z", "2027-12-31T23:00:00Z", CRIT)
             if "2027-09-01" <= x[:10] <= "2027-12-31"]
    rows = []
    for k, L in enumerate(lands):
        jr = windows.judge(viper, L, 240, 100, 14, CRIT, 0.0, 2.0, 100.0, long_days=100)
        jr["k"] = k
        rows.append(jr)
    v = {"available": True, "site": {"name": viper.name, "lat": la, "lon": lo}, "rows": rows,
         "mission": {"name": "VIPER on Blue Moon MK1", "need": "card defaults, 240 sunlit and 100 Earth hours in 14 days (illustrative); 100-day totals beside (published mission length)",
                     "deadline": "a landing by late 2027 (NASA, 19 Sep 2025)",
                     "assumptions": ["the point is on Nobile crater's west rim from the gazetteer, not VIPER's landing ellipse",
                                     "each window lands 24 h after the Sun first counts as up in that lunar day at the point"]}}
    doc["viper"] = v
    show(f"VIPER, Nobile west rim point {la}, {lo}, landings 24 h after local sunrise, Sep to Dec 2027:", v)
    # the Earth's drift between windows for the default page's sites
    drift = {}
    for sid in ("robust_pick", "shackleton", "im2", "im1"):
        s = sites.get_site(sid)
        d = windows.next_windows(s, "2026-11-18T00:00:00Z", [0, 1, 2, 3], 240, 100, 14, CRIT, 0.0, 2.0, 100.0)
        drift[sid] = d
        show(f"{sid}: windows 0 to 3 from 18 Nov 2026 (240 / 100 h in 14 d):", d)
    doc["drift"] = drift
    doc["seconds"] = round(time.time() - t0, 1)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print(f"wrote {OUT} ({doc['seconds']} s)")


if __name__ == "__main__":
    main()
