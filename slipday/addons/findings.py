"""What we found: the science panel (add-on router).

Serves data/addons/findings/findings.json, built by ``python scripts/addons/build_findings.py``.  It computes nothing
at request time.  Every figure in the file was recomputed by that script from Slipday's stored data and code.

    GET /api/addons/findings     the findings, each with a headline, the numbers behind its chart and the caveats
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

from fastapi import APIRouter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JSON_PATH = os.path.join(ROOT, "data", "addons", "findings", "findings.json")

router = APIRouter(prefix="/api/addons/findings", tags=["findings"])


@lru_cache(maxsize=2)
def _load_cached(mtime: float) -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def load() -> dict | None:
    if not os.path.exists(JSON_PATH):
        return None
    return _load_cached(os.path.getmtime(JSON_PATH))


def _pct(x: float, nd: int = 0) -> str:
    return f"{100 * x:.{nd}f} %"


def _curve(reg: dict, var: str, period: str) -> list:
    return [{"k": c["k"], "share": c["share"], "regions": c["regions"]} for c in reg["variants"][var][period]["curve"]]


def findings(d: dict) -> list:
    """Turn the stored numbers into findings: headline, chart data, numbers and caveats (plain words)."""
    out = []
    co = d["coarse_is_optimistic"]
    t20, ridge, five = co["twenty_m"], co["ridge"], co["five_m"]
    if t20.get("available"):
        tot = t20["totals"]
        dis = t20["disagreements"]
        st = ridge.get("stacks", {})
        r80, r20 = st.get("coarse_80m", {}).get("longest_dark_h"), st.get("fine_20m", {}).get("longest_dark_h")
        numbers = [
            {"label": "Map points re-checked (all dates)", "value": tot["points"]},
            {"label": "Same answer on both grids", "value": f"{tot['agree']} ({_pct(t20['agree_share'], 1)})"},
            {"label": "Landable on 80 m, rejected on 20 m", "value": tot["coarse_yes_fine_no"]},
            {"label": "Rejected on 80 m, landable on 20 m", "value": tot["coarse_no_fine_yes"]},
            {"label": "Dates with any passing point", "value": f"{t20['dates_with_points']} of {len(t20['dates'])}"},
        ]
        if r80 is not None and r20 is not None:
            numbers.append({"label": "Shackleton ridge, longest darkness", "value":
                            f"{r80:g} h on 80 m, {r20:g} h on 20 m, {ridge['published_h']} h published"})
            r5 = st.get("live_finest", {}).get("longest_dark_h")
            if r5 is not None:
                numbers.append({"label": "Same point on the 5 m site model", "value": f"{r5:g} h"})
        out.append({
            "id": "coarse_terrain_optimistic", "kind": "finding",
            "title": "Coarse terrain is optimistic, not noisy",
            "headline": (f"When NASA's 80 m and 20 m terrain disagree about a landing spot, the coarse grid is almost "
                         f"always the hopeful one: {tot['coarse_yes_fine_no']} of {dis} disagreements were landable on "
                         f"80 m and rejected on 20 m."),
            "charts": [{"type": "dates_bars", "data": t20["dates"]},
                       {"type": "polar_map", "data": t20["map_points"]},
                       {"type": "ridge_bars", "data": {"coarse_80m": r80, "fine_20m": r20, "published": ridge.get("published_h")}}],
            "numbers": numbers,
            "caveats": [
                "Errors that go one way are a bias, not noise: a coarse map should be read as an upper bound.",
                "One mission rule (the page default: 240 sunlit hours, 100 hours of Earth contact, which is illustrative), "
                "14 weekly start dates from 18 Nov 2026; on the other dates no map point passes at all.",
                "Only the 2,407 map points with stored 20 m skylines can be re-checked.",
                f"The finest terrain, 5 m, covers only {five.get('count', 2)} sites: "
                + ", ".join(m["product"].split("(")[-1].rstrip(")") for m in five.get("models", [])) + ".",
                "At the ridge, 20 m agrees with the published darkness; 80 m overstates it.",
            ],
            "doc_check": t20.get("doc_says"),
        })
    reg = d["regions"]
    e4, s4 = _curve(reg, "earth_need", "2027-2030"), _curve(reg, "sunlight_only", "2027-2030")
    e9, s9 = _curve(reg, "earth_need", "2027-2035"), _curve(reg, "sunlight_only", "2027-2035")
    pick = lambda c: {str(k): c[k - 1]["share"] for k in (1, 2, 3, 9)}  # noqa: E731
    k_to_match = next(c["k"] for c in s4 if c["share"] >= s4[-1]["share"] - 1e-9)
    out.append({
        "id": "regions_to_keep_open", "kind": "finding",
        "title": "How many NASA landing regions must stay open",
        "headline": (f"No single region is enough: the best one is open at {_pct(e4[0]['share'])} of landing times, "
                     f"the best three at {_pct(e4[2]['share'])} and all nine at {_pct(e4[8]['share'])} (2027 to 2030, "
                     f"with the illustrative Earth need). On sunlight alone three regions already reach "
                     f"{_pct(s4[2]['share'])}."),
        "charts": [{"type": "coverage_curve", "data": {"earth_need": {"2027-2030": e4, "2027-2035": e9},
                                                      "sunlight_only": {"2027-2030": s4, "2027-2035": s9}}}],
        "numbers": [
            {"label": "Earth need, 2027-2030 (best 1 / 2 / 3 / 9)", "value": pick(e4)},
            {"label": "Earth need, 2027-2035", "value": pick(e9)},
            {"label": "Sunlight only, 2027-2030", "value": pick(s4)},
            {"label": "Sunlight only, 2027-2035", "value": pick(s9)},
            {"label": "Best three regions", "value": ", ".join(e4[2]["regions"])},
            {"label": "Regions needed to reach the sunlight-only ceiling", "value": k_to_match},
        ],
        "caveats": [
            "The 100 hours of Earth contact are an illustrative need, not a NASA requirement; it is what holds the "
            "ceiling near 40 %.",
            "Shares of landing times every 6 hours, not of real launch opportunities.",
            f"{reg.get('sites', 78)} published candidate sites (Wueller et al. 2026); a region is open when one of its "
            "sites is a clear Yes that is not fragile.",
            "Best sets were found by trying every combination of regions.",
        ],
    })
    ch = d["checks"]
    dr, lola, hz = ch["season_drift"], ch["lola_earth_maps"], ch["horizons"]
    out.append({
        "id": "checks", "kind": "check",
        "title": "Checks, not findings",
        "headline": ("Three things we expected and confirmed, to show the model can be trusted: the season's yearly "
                     "drift, the LOLA team's Earth maps and JPL Horizons."),
        "charts": [{"type": "drift_line", "data": dr["years"]},
                   {"type": "scatter", "data": [{"map": m["map"], "pairs": m["pairs"]} for m in lola["maps"]]}],
        "numbers": [
            {"label": "Season comes earlier each year (sine fit, 2025-2035)",
             "value": f"{dr['sine_fit_earlier_per_year_days']} days (expected {dr['expected_earlier_per_year_days']})"},
            {"label": "Same, from the yearly lowest-Sun dates", "value":
             f"{dr['measured_2025_2032_days']} days (2025-2032), {dr['measured_earlier_per_year_days']} days (2025-2035)"},
            *[{"label": f"LOLA Earth map, {m['map']}", "value":
               f"{m['mean_abs_diff_pts']} points mean difference, correlation {m['correlation']} ({m['points']} points)"}
              for m in lola["maps"]],
            {"label": "JPL Horizons, Sun and Earth direction", "value":
             f"largest difference {hz['max_abs_el_deg']:.1e} deg in elevation, {hz['max_abs_az_deg']:.1e} deg in "
             f"azimuth over {hz['rows']} rows"},
        ],
        "caveats": [
            "These are validation, not discovery: the 18.6-day drift follows from the Moon's 18.6-year orbital cycle.",
            "The yearly lowest-Sun date wobbles by a few days, so a straight line through it depends on the years "
            "chosen; the sine fit uses every day.",
            "Horizons tables cover three real landing sites (IM-1, Blue Ghost 1, Chandrayaan-3) over a few weeks each.",
        ],
    })
    return out


@router.get("")
def findings_panel():
    d = load()
    if d is None:
        return {"available": False, "reason": "the findings have not been built on this installation "
                                              "(python scripts/addons/build_findings.py)"}
    return {"available": True, "what": d["what"], "built_utc": d["built_utc"], "findings": findings(d)}
