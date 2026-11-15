"""How many of NASA's nine south-pole landing regions (now for Artemis IV) must stay open: availability on published landing sites.

An addition beside the rest of the page; nothing else in the app depends on it.  The sites are the 130 candidate
landing sites of Wueller et al. 2026 (JGR Planets 131(3) e2025JE009434, CC BY 4.0; data: Zenodo record
17084058), 78 of them in NASA's nine current regions.  ``data/regions/wueller2026_sites.json`` is written from
the published shapefile by ``scripts/build_wueller_sites.py``.

The rule (DEEP_PASS_3.md, F2):
  * landing times every 6 hours, 2027 to 2030; a 6.25-day stay (150 hours; NASA LPSC 2026 abstract, NTRS
    20250011660: "approximately 5.75 to 6.25 days");
  * a site is a clear Yes when every member of the card's check (13 touchdown points within 100 m, the coarser
    grid, the near-field sampling) has the Sun up every hour of the stay, at least 100 hours of Earth contact,
    and the Sun and the Earth in view at touchdown;
  * fragile: at some touchdown point the Sun's centre comes within 0.27 degrees of the skyline during the stay,
    or the Earth's centre is within 0.27 degrees of it at touchdown;
  * a region is open when at least one of its sites is a clear Yes that is not fragile.

``site_flags`` is the vectorised form of ``robust.mission_card`` for one landing day; ``tests/test_regions.py``
checks it against ``mission_card`` itself.
"""
from __future__ import annotations

import json
import os
from itertools import combinations

import numpy as np

from .geometry import Site, track
from .metrics import Criteria, earth_up, sun_up
from .robust import _flat, ensemble
from .windows import SUN_RADIUS_DEG

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITES_PATH = os.path.join(ROOT, "data", "regions", "wueller2026_sites.json")
OUT_PATH = os.path.join(ROOT, "data", "validation", "region_availability.json")

# NASA's nine regions in NASA's order (NASA, 28 Oct 2024), with the codes Wueller et al. use
REGIONS = [("PCB", "Peak near Cabeus B"), ("HW", "Haworth"), ("MMA", "Malapert Massif"), ("MMP", "Mons Mouton Plateau"),
           ("MMO", "Mons Mouton"), ("NR1", "Nobile Rim 1"), ("NR2", "Nobile Rim 2"), ("dGR2", "de Gerlache Rim 2"),
           ("SP", "Slater Plain")]
NAME = dict(REGIONS)

STAY_DAYS = 6.25
STAY_H = 150
STEP_H = 6
NEED_EARTH_H = 100
START = "2027-01-01T00:00:00Z"
END = "2030-12-31T18:00:00Z"
CRIT = Criteria(stations=True)
MASK_DEG, MAST_M, SCATTER_M = 0.0, 2.0, 100.0

# Wueller et al. 2026, Table 2: midsummer periods (subsolar latitude at or below -1.5 degrees), first and last day
MIDSUMMER = {2025: ("2025-11-20", "2025-12-21"), 2026: ("2026-11-06", "2026-11-27"), 2027: ("2027-10-15", "2027-11-14"),
             2028: ("2028-09-27", "2028-10-14"), 2029: ("2029-09-15", "2029-10-02"), 2030: ("2030-08-19", "2030-09-19"),
             2031: ("2031-08-05", "2031-08-26"), 2032: ("2032-07-13", "2032-08-12")}

CITATION = ("Wueller, L., Berger, L. M., Christopher, H., Sugimoto, K., Thaker, A. D., Carton, L., Jo, W., Lee, S., "
            "Pedrelli, R., Sanchez, P., & Kring, D. A. (2026). Assessing Potential Landing Sites With Favorable "
            "Illumination and Accessible, Potentially Volatile-Rich Permanently Shadowed Regions Within Artemis "
            "Candidate Landing Regions. Journal of Geophysical Research: Planets, 131(3), e2025JE009434. "
            "https://doi.org/10.1029/2025JE009434 (CC BY 4.0). Data: https://doi.org/10.5281/zenodo.17084058")


def load_sites(nine_only: bool = True) -> list:
    """The published sites (all 130, or the 78 in NASA's nine current regions), [] when the file is missing."""
    if not os.path.exists(SITES_PATH):
        return []
    sites = json.load(open(SITES_PATH, encoding="utf-8"))["sites"]
    return [s for s in sites if s["region"] in NAME] if nine_only else sites


def window_sum(flags: np.ndarray, w: int) -> np.ndarray:
    """Sum over [i, i + w) for every i with a full window, along the last axis."""
    c = np.concatenate([np.zeros(flags.shape[:-1] + (1,)), np.cumsum(flags, axis=-1)], axis=-1)
    return c[..., w:] - c[..., :-w]


def window_min(x: np.ndarray, w: int) -> np.ndarray:
    """Minimum over [i, i + w) for every i with a full window (1-D)."""
    return np.lib.stride_tricks.sliding_window_view(x, w).min(axis=1)


def members_of(lat: float, lon: float, name: str = "") -> tuple:
    """The card's check members for a point: (sites, number of touchdown points)."""
    from .sites import custom_site
    s = custom_site(name, lat, lon, MASK_DEG, MAST_M)
    if not s.horizon.is_terrain:
        return [s], 1
    members, index = _flat(ensemble(s, MASK_DEG, MAST_M, SCATTER_M))
    return members, index["scatter"][1] - index["scatter"][0]


def site_flags(members: list, n_points: int, table, starts: np.ndarray, stay_h: int = STAY_H,
               need_earth_h: float = NEED_EARTH_H, crit: Criteria = CRIT) -> dict:
    """For landings at hour indices ``starts`` of ``table``: clear Yes, fragile, and the Sun-only variant."""
    ok_all = np.ones(starts.size, dtype=bool)
    ok_sun = np.ones(starts.size, dtype=bool)
    low = np.full(starts.size, 99.0)
    low_sun = np.full(starts.size, 99.0)
    for k, p in enumerate(members):
        tr = track(p, table, crit.min_sun_fraction)
        lit = sun_up(tr)
        ev = earth_up(tr, crit) & (tr.earth_el >= crit.min_earth_el)
        sun_all = window_sum(lit, stay_h)[starts] >= stay_h
        earth_n = window_sum(ev, stay_h)[starts]
        s_ok = sun_all & lit[starts]
        ok_sun &= s_ok
        ok_all &= s_ok & ev[starts] & (earth_n >= need_earth_h)
        if k < n_points:
            low_sun = np.minimum(low_sun, window_min(tr.sun_clear, stay_h)[starts])
            low = np.minimum(low, tr.earth_clear[starts] - crit.earth_margin_deg)
    low = np.minimum(low, low_sun)
    return {"yes": ok_all, "fragile": ok_all & (low < SUN_RADIUS_DEG), "yes_sun_only": ok_sun,
            "fragile_sun_only": ok_sun & (low_sun < SUN_RADIUS_DEG), "min_clearance": low}


def longest_lit_run_days(member: Site, table, hour0_unix: int, first_day: str, last_day: str) -> float:
    """Longest run of 12-hourly samples (00 and 12 UTC, first_day to last_day) with any part of the Sun's disc above
    the skyline, in days (samples / 2), as Wueller et al. count it.  ``table`` is hourly from ``hour0_unix``."""
    from .ephem import parse_utc
    a = int((parse_utc(first_day + "T00:00:00Z").timestamp() - hour0_unix) // 3600)
    b = int((parse_utc(last_day + "T12:00:00Z").timestamp() - hour0_unix) // 3600)
    tr = track(member, table, 0.0)
    lit = (tr.sun_lit > 0)[a:b + 1:12]
    best = run = 0
    for v in lit:
        run = run + 1 if v else 0
        best = max(best, run)
    return best / 2.0


# ------------------------------------------------------------------ coverage

def coverage(open_: np.ndarray, chosen) -> float:
    """Share of times with at least one of the chosen regions open (open_: regions x times, bool)."""
    if not len(chosen):
        return 0.0
    return float(open_[list(chosen)].any(axis=0).mean())


def greedy(open_: np.ndarray) -> list:
    """Regions in greedy order: first the one open most often, then each time the one adding most uncovered times."""
    left = list(range(open_.shape[0]))
    covered = np.zeros(open_.shape[1], dtype=bool)
    order = []
    while left:
        gains = [int((open_[r] & ~covered).sum()) for r in left]
        r = left[int(np.argmax(gains))]          # ties: the earlier region in NASA's order
        order.append(r)
        left.remove(r)
        covered |= open_[r]
    return order


def best_sets(open_: np.ndarray) -> list:
    """For k = 1..n, the set with the largest coverage, trying every set (ties: first in NASA's order)."""
    n = open_.shape[0]
    out = []
    for k in range(1, n + 1):
        best, cov = None, -1.0
        for c in combinations(range(n), k):
            v = coverage(open_, c)
            if v > cov + 1e-12:
                best, cov = c, v
        out.append((list(best), cov))
    return out


def load() -> dict | None:
    if not os.path.exists(OUT_PATH):
        return None
    return json.load(open(OUT_PATH, encoding="utf-8"))


def decode(s: str) -> np.ndarray:
    """A per-time string of base-36 digits back to integers."""
    return np.array([int(c, 36) for c in s], dtype=int)


def encode(a: np.ndarray) -> str:
    return "".join(np.base_repr(int(v), 36) for v in a)
