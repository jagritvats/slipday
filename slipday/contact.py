"""Earth contact as real station visibility, for one site.

An hour counts as Earth contact under the station rule when the Earth's centre is above the terrain skyline
at the site by the card's Earth mask (the rule used everywhere else) AND the Moon's centre is at or above the
Deep Space Network's elevation limit at one or more of its three complexes (``stations``; coordinates and the
10-degree low-power transmit limit read from the DSN Telecommunications Link Design Handbook 810-005,
module 301 Rev. P).  The hour is credited to the complex at which the Moon stands highest (rule R3 of
LOCAL_PASS_2_RESULTS.md, pass 3).

Two views:
  window_contact   the landing window, hour by hour: which complex carries each hour, and the hours the Earth
                   is above the skyline but no complex has the Moon above its limit
  cycle_shares     the same split, year by year, over one 18.6-year cycle of the Moon's orbit (2-hour steps)
"""
from __future__ import annotations

import numpy as np

from . import stations
from .ephem import available_steps, cached_table, grid_start, iso, parse_utc
from .geometry import Site, track
from .metrics import STEP_S, Criteria

NAMES = [c["id"] for c in stations.COMPLEXES]
LABELS = {"goldstone": "Goldstone", "madrid": "Madrid", "canberra": "Canberra"}
CYCLE_START_YEAR = 2026
CYCLE_YEARS = 19                  # 2026 to 2044 inclusive covers one 18.6-year nodal cycle
CYCLE_STEP_S = 7200


def _earth_above(site: Site, table, crit: Criteria) -> np.ndarray:
    tr = track(site, table, crit.min_sun_fraction)
    return (tr.earth_clear > crit.earth_margin_deg) & (tr.earth_el >= crit.min_earth_el)


def _split(up: np.ndarray, unix: np.ndarray) -> dict:
    car = stations.carrier(unix)
    out = {"earth_above_skyline": int(up.sum())}
    for i, n in enumerate(NAMES):
        out[n] = int((up & (car == i)).sum())
    out["none_in_view"] = int((up & (car < 0)).sum())
    out["station_contact"] = int((up & (car >= 0)).sum())
    return out


def window_contact(site: Site, landing, window_days: float, crit: Criteria) -> dict:
    """Hour-by-hour Earth contact over the landing window, split by the complex that carries it."""
    s = grid_start(parse_utc(landing), STEP_S)
    n = min(int(round(window_days * 24)), available_steps(s, STEP_S))
    table = cached_table(s, n, STEP_S)
    up = _earth_above(site, table, crit)
    car = stations.carrier(table.unix)
    el = stations.moon_elevation_deg(table.unix)
    hours = _split(up, table.unix)
    code = np.where(up, np.where(car >= 0, car, 3), -1).astype(int)    # -1 Earth hidden, 0..2 complex, 3 none in view
    runs = []                                                           # the gaps: Earth up, no complex
    i = 0
    while i < n:
        if code[i] == 3:
            j = i
            while j + 1 < n and code[j + 1] == 3:
                j += 1
            runs.append({"from_utc": iso(int(table.unix[i])), "hours": j - i + 1})
            i = j + 1
        else:
            i += 1
    return {"start_utc": iso(s), "hours": int(n), "window_days": window_days, "split": hours,
            "code": [int(v) for v in code], "codes": {"-1": "Earth below the skyline", "0": "Goldstone",
                                                      "1": "Madrid", "2": "Canberra", "3": "no complex in view"},
            "gaps": runs, "longest_gap_h": max([r["hours"] for r in runs], default=0),
            "moon_el_at_start": {n_: round(float(el[k, 0]), 2) for k, n_ in enumerate(NAMES)}}


def cycle_shares(site: Site, crit: Criteria, start_year: int = CYCLE_START_YEAR, years: int = CYCLE_YEARS) -> dict:
    """Per year: of the hours with the Earth above the skyline, the share each complex carries and the share with none."""
    rows = []
    for y in range(start_year, start_year + years):
        s = int(parse_utc(f"{y}-01-01T00:00:00Z").timestamp())
        e = int(parse_utc(f"{y + 1}-01-01T00:00:00Z").timestamp())
        n = min((e - s) // CYCLE_STEP_S, available_steps(s, CYCLE_STEP_S))
        if n < 10:
            break
        table = cached_table(s, n, CYCLE_STEP_S)
        up = _earth_above(site, table, crit)
        sp = _split(up, table.unix)
        tot = max(sp["earth_above_skyline"], 1)
        row = {"year": y, "earth_above_skyline_share": round(sp["earth_above_skyline"] / n, 4),
               "none_in_view_share": round(sp["none_in_view"] / tot, 4)}
        for k in NAMES:
            row[k + "_share"] = round(sp[k] / tot, 4)
        rows.append(row)
    return {"step_hours": CYCLE_STEP_S / 3600, "rows": rows,
            "what": ("of the hours with the Earth's centre above the skyline at this site, the share carried by each "
                     "complex (Moon highest there and at or above its limit) and the share with no complex in view")}


def report(site: Site, landing, window_days: float, crit: Criteria) -> dict:
    d = stations.describe()
    return {"available": True, "site": {"name": site.name, "lat": site.lat, "lon": site.lon},
            "window": window_contact(site, landing, window_days, crit),
            "cycle": cycle_shares(site, crit),
            "rule": d["rule"], "mask_deg": d["mask_deg"], "mask_cited": d["mask_cited"], "mask_quote": d["mask_quote"],
            "mask_url": d["mask_url"], "complexes": [{"id": c["id"], "name": c["name"], "antenna": c["antenna"],
                                                      "lat_deg": c["lat_deg"], "lon_deg": c["lon_deg"]}
                                                     for c in d["complexes"]],
            "horizons_check": {"rows": 294, "largest_diff_deg": 0.0006,
                               "what": "Moon elevation at the three complexes against JPL Horizons, 20 to 22 Nov 2026 "
                                       "and 10 to 12 Jun 2034 (scripts/check_stations_horizons.py)"},
            "model": d["model"]}
