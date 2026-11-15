"""Add-on: "Chance of a safe touchdown".  How likely is the ground under the lander to be flat enough?

The "flat enough to land?" add-on (safety.py) checks the slope at 13 fixed touchdown points.  A real lander
comes down somewhere in a spread around its aim point.  This module draws touchdown points at random from the
entry's own three lander classes (robust.LANDER_CLASSES) and counts the share that land on ground within 8
degrees of level (NASA HLS-R-0071, threshold) and within 5 degrees (its goal).

The method was written down in ADDON_safetouch.md (Part 1) before any chance was computed.  In short:

  where      only where a LOLA 5 m site model covers the spread (Site01, Site07).  Elsewhere: no number.
  slope      safety.py's own: a plane fitted to the 3 x 3 cells around the point, a 10 m square.  Worked out once
             for every 5 m cell of a patch around the site; a touchdown point takes the slope of its cell.
  draws      20,000 per round class, 2,000 for each of 12 long-axis directions of the unguided class, fixed seed.
  range      95 % Wilson range of a share; for the unguided class also the lowest and highest direction.
  +/- 2 deg  NASA's 5 m slope maps are uncertain by about 2 degrees per point: the shares are recomputed with
             every slope 2 degrees higher and 2 degrees lower.
  aim point  every point of a 10 m grid within 200 m; the best is offered only if it beats the planned site
             clearly and keeps the slip-margin verdict of the entry's own mission card.

All grids are read in place, read-only, memory-mapped.
"""
from __future__ import annotations

import base64
import json
import math
import os
from functools import lru_cache
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from . import safety

ROOT = safety.ROOT
STORE_DIR = os.path.join(ROOT, "data", "addons", "safetouch")
STORE = os.path.join(STORE_DIR, "sites.json")

LIMIT_DEG = safety.LIMIT_DEG          # 8, HLS-R-0071 threshold
GOAL_DEG = safety.GOAL_DEG            # 5, HLS-R-0071 goal
UNCERTAINTY_DEG = 2.0                 # NASA 5 m slope maps: about 2 degrees per point
FIVE_M = ("ldem_site01_5m", "ldem_site07_5m")
SEED = 20261115
N_ROUND = 20000
N_PER_DIRECTION = 2000
DIRECTIONS = np.arange(0.0, 180.0, 15.0)   # long-axis directions tried for a non-round class (as robust.py)
MAX_OUTSIDE = 0.01                    # a class is left out if more than 1 % of its draws fall off the 5 m grid
AIM_RADIUS_M = 200.0
AIM_STEP_M = 10.0
AIM_MIN_GAIN_PP = 1.0                 # percentage points
AIM_TRIES = 5
AIM_SEPARATION_M = 20.0
PATCH_HALF_M = 3400.0                 # slope is worked out for this square around the aim point
NEAR = (300.0, 5.0)                   # picture: half-width, metres per picture cell
WIDE = (2400.0, 20.0)
WITHIN_99 = 3.035                     # 99 % of a round 2-D Gaussian lies within 3.035 standard deviations

# the page's default need (static/app.js: OPENING, needSun, needEarth; api.py MissionRequest defaults)
SLIP_DEFAULTS = {"landing": "2026-11-18T00:00:00Z", "need_sun_h": 240.0, "need_earth_h": 100.0, "window_days": 14.0,
                 "scatter_m": 100.0, "slip_days": 60, "mask_deg": 0.0, "mast_m": 2.0}

NAMED = {"robust_pick": (-89.0098, 122.76389, "Opening example (89.010 S, 122.764 E)"),
         "shackleton": (-89.4398, -137.17, "Shackleton connecting ridge (C1)")}

METHOD_VERSION = "safetouch-1"

PLAIN_LIMITS = [
    "Boulders and small craters are invisible here: 5 m terrain shows nothing smaller than about 10 m. A lander can "
    "still come down on a rock or in a small crater that this terrain does not show.",
    "The three lander sizes are this entry's assumptions, each tied to one public figure, not a model of any real lander.",
    "NASA's 8° is how far the lander may lean. Ground slope is not the same thing: a footpad on a rock can tilt it more.",
    "Only two 16 km squares near Shackleton have 5 m terrain here. Everywhere else 80 m terrain is far too coarse "
    "for the ground under a lander, so no chance is given.",
    "The ±2° figures shift every slope the same way at once. Real errors vary from place to place, so the truth is "
    "most likely between the two.",
]

TOO_COARSE = ("No chance is given here: only 80 m (or 20 m) terrain covers this place, and one 80 m cell is wider than "
              "eight landers side by side, far too coarse for the ground under a lander. The chance of a safe "
              "touchdown is shown only where NASA's 5 m terrain exists: the opening example, C1 (the Shackleton "
              "connecting ridge) and the rest of the two 16 km squares of the LOLA 5 m site models near Shackleton.")


# ---------------- the 5 m grid and the slope patch ----------------

def five_m_grids() -> list:
    return [(n, label, g) for n, label, g in safety.grids() if n in FIVE_M]


def locate(lat: float, lon: float) -> Optional[dict]:
    """The 5 m grid whose cells cover (lat, lon), with the point's map position, or None."""
    for name, label, g in five_m_grids():
        x, y = g.project(lat, lon)
        x, y = float(x), float(y)
        col, row = (x - g.x0_m) / g.pixel_m, (g.y0_m - y) / g.pixel_m
        ny, nx = g.z.shape
        if 1 <= row <= ny - 2 and 1 <= col <= nx - 2 and lat * g.pole > 0:
            return {"name": name, "label": label, "g": g, "x": x, "y": y, "row": row, "col": col}
    return None


def slope_patch(g, rc: int, cc: int, half_cells: int):
    """Slope (degrees) of every 5 m cell in rows rc-half..rc+half, columns cc-half..cc+half, exactly as
    safety.slope_on works it out (plane through the 3 x 3 cells around the cell).  NaN off the grid."""
    px = g.pixel_m
    ny, nx = g.z.shape
    n = 2 * half_cells + 1
    r0, c0 = rc - half_cells, cc - half_cells
    out = np.full((n, n), np.nan)
    # rows / columns of the patch that have all 3 x 3 neighbours on the grid
    a0, a1 = max(r0, 1), min(r0 + n - 1, ny - 2)
    b0, b1 = max(c0, 1), min(c0 + n - 1, nx - 2)
    if a0 > a1 or b0 > b1:
        return out, r0, c0
    z = np.asarray(g.z[a0 - 1:a1 + 2, b0 - 1:b1 + 2], dtype=float) * g.scale + g.offset
    if g.nodata is not None:
        z[np.asarray(g.z[a0 - 1:a1 + 2, b0 - 1:b1 + 2]) == g.nodata] = np.nan
    # map distance -> ground distance (polar stereographic, true scale at the pole), at each cell's latitude
    rows = np.arange(a0, a1 + 1)
    cols = np.arange(b0, b1 + 1)
    X, Y = np.meshgrid(g.x0_m + cols * px, g.y0_m - rows * px)
    lat, _ = g.unproject(X, Y)
    kf = 2.0 / (1.0 + np.sin(np.abs(np.deg2rad(lat))))
    dx = (z[:, 2:] - z[:, :-2])                       # column offset +1 minus -1, every row of the 3
    dx = dx[:-2] + dx[1:-1] + dx[2:]
    dy = (z[2:, :] - z[:-2, :])                       # row offset +1 minus -1, every column of the 3
    dy = dy[:, :-2] + dy[:, 1:-1] + dy[:, 2:]
    gx = dx / 6.0 / px * kf
    gy = dy / 6.0 / px * kf
    out[a0 - r0:a1 - r0 + 1, b0 - c0:b1 - c0 + 1] = np.degrees(np.arctan(np.hypot(gx, gy)))
    return out, r0, c0


# ---------------- the lander classes and the draws ----------------

def lander_classes() -> list:
    from ..robust import LANDER_CLASSES
    return LANDER_CLASSES


@lru_cache(maxsize=1)
def draws() -> dict:
    """Touchdown offsets in metres (east-ish x, north-ish y on the map grid) per class, from the fixed seed.
    The same offsets serve every site and every candidate aim point."""
    rng = np.random.default_rng(SEED)
    out = {}
    for c in lander_classes():
        sa, sb = float(c["sigma_major_m"]), float(c["sigma_minor_m"])
        if sa == sb:
            n = rng.standard_normal((N_ROUND, 2))
            out[c["id"]] = {"dx": n[:, 0] * sa, "dy": n[:, 1] * sa, "direction": None}
        else:
            dx, dy, di = [], [], []
            for k, th in enumerate(DIRECTIONS):
                n = rng.standard_normal((N_PER_DIRECTION, 2))
                along, across = n[:, 0] * sa, n[:, 1] * sb
                t = math.radians(th)
                dx.append(along * math.sin(t) + across * math.cos(t))
                dy.append(along * math.cos(t) - across * math.sin(t))
                di.append(np.full(N_PER_DIRECTION, k))
            out[c["id"]] = {"dx": np.concatenate(dx), "dy": np.concatenate(dy), "direction": np.concatenate(di)}
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple:
    """95 % range of a share k / n, in per cent."""
    if n <= 0:
        return (None, None)
    p = k / n
    d = 1.0 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100.0 * max(0.0, mid - half), 1), round(100.0 * min(1.0, mid + half), 1))


def _pct(k, n):
    return None if n <= 0 else round(100.0 * k / n, 1)


# ---------------- one site ----------------

def _class_cells(loc: dict, cid: str, r0: int, c0: int):
    """Patch row and column of each draw of one class around the planned aim point."""
    d = draws()[cid]
    g = loc["g"]
    col = np.rint((loc["x"] + d["dx"] - g.x0_m) / g.pixel_m).astype(np.int64) - c0
    row = np.rint((g.y0_m - (loc["y"] + d["dy"])) / g.pixel_m).astype(np.int64) - r0
    return row, col


def _count(S: np.ndarray, row: np.ndarray, col: np.ndarray, di: int = 0, dj: int = 0) -> dict:
    """Counts for one aim point (shifted by di rows, dj columns from the planned one)."""
    n = S.shape[0]
    r, c = row + di, col + dj
    inside = (r >= 0) & (c >= 0) & (r < n) & (c < n)
    s = np.full(row.shape, np.nan)
    s[inside] = S[r[inside], c[inside]]
    ok = np.isfinite(s)
    return {"n": int(len(s)), "valid": int(ok.sum()), "s": s, "ok": ok}


def _shares(s: np.ndarray, ok: np.ndarray) -> dict:
    v = s[ok]
    n = len(v)
    out = {"draws_used": n}
    for key, lim in (("p8", LIMIT_DEG), ("p5", GOAL_DEG)):
        k = int((v <= lim).sum())
        out[key] = _pct(k, n)
        out[key + "_count"] = k                   # so the page can tell "every draw" from "rounds to 100.0"
        out[key + "_range"] = list(wilson(k, n))
        # slopes 2 degrees higher (worse) and 2 degrees lower (better); a slope below 0 counts as 0, so lower
        # never hurts
        ks = int((v + UNCERTAINTY_DEG <= lim).sum())
        kf = int((np.maximum(v - UNCERTAINTY_DEG, 0.0) <= lim).sum())
        out[key + "_if_steeper"], out[key + "_if_steeper_count"] = _pct(ks, n), ks
        out[key + "_if_flatter"], out[key + "_if_flatter_count"] = _pct(kf, n), kf
    return out


def _slip(lat: float, lon: float) -> dict:
    """The entry's own mission card at (lat, lon) for the page's default need: verdict and slip margin."""
    from ..geometry import Site
    from ..metrics import Criteria
    from ..robust import mission_card
    from ..sites import horizon_for
    p = SLIP_DEFAULTS
    hz = horizon_for(lat, lon, p["mask_deg"], p["mast_m"], True)
    site = Site(f"{lat:.5f}, {lon:.5f}", lat, lon, horizon=hz)
    m = mission_card(site, p["landing"], p["need_sun_h"], p["need_earth_h"], p["window_days"], Criteria(0.5, -90.0, -90.0, 0.0, False),
                     p["mask_deg"], p["mast_m"], p["scatter_m"], p["slip_days"])
    return {"verdict": m["verdict"], "slip_margin_days": int(m["slip_margin_days"]),
            "grid_m": float(hz.meta.get("resolution_m") or 0.0) if hz.is_terrain else None,
            "points_passing": m["sure"].get("points_passing"), "points": m["sure"].get("points")}


def _picture(S: np.ndarray, half_cells: int, half_m: float, step_m: float, px: float) -> dict:
    """Slope of the patch around the aim point for the page, one byte per picture cell: tenths of a degree,
    capped at 254 (25.4 degrees or more); 255 means no 5 m terrain."""
    k = int(round(step_m / px))
    h = int(round(half_m / px))
    sub = S[half_cells - h:half_cells + h + 1:k, half_cells - h:half_cells + h + 1:k]
    q = np.where(np.isfinite(sub), np.clip(np.rint(sub * 10.0), 0, 254), 255).astype(np.uint8)
    return {"half_m": half_m, "step_m": step_m, "n": int(q.shape[0]), "every_nth_cell": k,
            "data": base64.b64encode(q.tobytes()).decode("ascii"),
            "encoding": "row by row from the top of the map grid; tenths of a degree; 255 = no 5 m terrain"}


def compute(lat: float, lon: float, name: str = "", with_slip: bool = True) -> dict:
    """The chance of a safe touchdown at (lat, lon) for the three lander classes."""
    lon = ((float(lon) + 180.0) % 360.0) - 180.0
    loc = locate(lat, lon)
    if loc is None:
        return {"available": False, "reason": TOO_COARSE, "site": {"name": name, "lat": lat, "lon": lon},
                "limits": PLAIN_LIMITS}
    g = loc["g"]
    px = g.pixel_m
    half = int(round(PATCH_HALF_M / px))
    rc, cc = int(round(loc["row"])), int(round(loc["col"]))
    S, r0, c0 = slope_patch(g, rc, cc, half)
    # the planned aim point is (loc x, y); patch indices are relative to the cell (rc, cc) at the centre
    step = int(round(AIM_STEP_M / px))
    rad = int(round(AIM_RADIUS_M / px))
    cand = [(i, j) for i in range(-rad, rad + 1, step) for j in range(-rad, rad + 1, step) if (i * i + j * j) * px * px <= AIM_RADIUS_M ** 2 + 1e-6]
    classes, best_by_class = [], {}
    for c in lander_classes():
        cid = c["id"]
        row, col = _class_cells(loc, cid, r0, c0)
        base = _count(S, row, col)
        outside = 1.0 - base["valid"] / base["n"]
        entry = {"id": cid, "label": c["label"], "sigma_major_m": c["sigma_major_m"], "sigma_minor_m": c["sigma_minor_m"],
                 "within_99_pct_m": round(WITHIN_99 * c["sigma_major_m"]),
                 "within_99_pct_minor_m": round(WITHIN_99 * c["sigma_minor_m"]),
                 "figure": c["figure"], "source": c["source"], "source_url": c["source_url"], "basis": c["basis"],
                 "assumed": True, "draws": base["n"], "outside_5m_pct": round(100.0 * outside, 2),
                 "round": c["sigma_major_m"] == c["sigma_minor_m"]}
        if outside > MAX_OUTSIDE:
            entry.update({"available": False,
                          "why": f"{100 * outside:.1f} % of this lander's touchdown points fall off the 5 m terrain "
                                 f"(the rule is at most {100 * MAX_OUTSIDE:g} %), so no chance is given for it here."})
            classes.append(entry)
            continue
        entry["available"] = True
        entry.update(_shares(base["s"], base["ok"]))
        d = draws()[cid]
        if d["direction"] is not None:
            per = []
            for k in range(len(DIRECTIONS)):
                m = (d["direction"] == k) & base["ok"]
                v = base["s"][m]
                per.append((_pct(int((v <= LIMIT_DEG).sum()), len(v)), _pct(int((v <= GOAL_DEG).sum()), len(v))))
            entry["directions"] = len(DIRECTIONS)
            entry["p8_by_direction"] = [p[0] for p in per]
            entry["p5_by_direction"] = [p[1] for p in per]
            entry["p8_direction_span"] = [min(p[0] for p in per), max(p[0] for p in per)]
            entry["p5_direction_span"] = [min(p[1] for p in per), max(p[1] for p in per)]
            entry["p8_range"] = [min(entry["p8_range"][0], entry["p8_direction_span"][0]), max(entry["p8_range"][1], entry["p8_direction_span"][1])]
            entry["p5_range"] = [min(entry["p5_range"][0], entry["p5_direction_span"][0]), max(entry["p5_range"][1], entry["p5_direction_span"][1])]
        # candidate aim points: same draws, aim moved by whole cells
        scored = []
        for i, j in cand:
            r = _count(S, row, col, -i, j)        # i cells toward +y (up the map) is -i rows
            if r["valid"] < (1.0 - MAX_OUTSIDE) * r["n"]:
                continue
            v = r["s"][r["ok"]]
            k8, k5 = int((v <= LIMIT_DEG).sum()), int((v <= GOAL_DEG).sum())
            scored.append((k8 / len(v), k5 / len(v), -math.hypot(i, j), i, j, k8, k5, len(v)))
        scored.sort(reverse=True)
        best_by_class[cid] = scored
        classes.append(entry)

    out = {"available": True, "method_version": METHOD_VERSION,
           "site": {"name": name or f"{lat:.4f}, {lon:.4f}", "lat": float(lat), "lon": float(lon)},
           "grid": {"name": loc["name"], "label": loc["label"], "cell_m": px, "baseline_m": (safety._block(px) - 1) * px},
           "limit_deg": LIMIT_DEG, "goal_deg": GOAL_DEG, "uncertainty_deg": UNCERTAINTY_DEG, "classes": classes,
           "aim_radius_m": AIM_RADIUS_M, "aim_step_m": AIM_STEP_M, "aim_candidates": len(cand)}
    # pictures and the direction of the pole on them (up = +y of the map grid)
    rr = math.hypot(loc["x"], loc["y"]) or 1.0
    out["picture"] = {"near": _picture(S, half, NEAR[0], NEAR[1], px), "wide": _picture(S, half, WIDE[0], WIDE[1], px),
                      "pole_dir": [round(-loc["x"] / rr, 4), round(loc["y"] / rr, 4)],
                      "pole_note": "screen x to the right, screen y down; the arrow points toward the south pole",
                      "aim_cell_offset_m": [round((loc["col"] - cc) * px, 2), round(-(loc["row"] - rc) * px, 2)]}
    # suggestions, with the slip-margin check of the entry's own mission card
    slip_cache: dict = {}

    def slip_at(a, b):
        key = (round(a, 5), round(b, 5))
        if key not in slip_cache:
            slip_cache[key] = _slip(*key)
        return slip_cache[key]

    planned_slip = slip_at(lat, lon) if with_slip else None
    out["slip_planned"] = planned_slip
    out["slip_rules"] = dict(SLIP_DEFAULTS)
    for entry in classes:
        if not entry.get("available"):
            continue
        entry["suggestion"] = _suggest(entry, best_by_class[entry["id"]], loc, px, planned_slip, slip_at, with_slip)
    out["limits"] = PLAIN_LIMITS
    out["source"] = safety.SOURCE
    out["how"] = ("Touchdown points are drawn at random around the aim point, as far out as each lander's accuracy says. "
                  "At each one the slope is measured as in the flat-enough check: a flat plane fitted to the 5 m terrain "
                  "of a 10 m square, about a lander's width. The chance is the share of touchdown points where that "
                  "slope is 8° or less (5° or less for NASA's goal).")
    return out


def _suggest(entry: dict, scored: list, loc: dict, px: float, planned_slip, slip_at, with_slip: bool) -> dict:
    p_lo_planned = entry["p8_range"]
    planned = next((s for s in scored if s[3] == 0 and s[4] == 0), None)
    if planned is None or not scored:
        return {"offered": False, "why": "the planned site could not be scored"}
    base_k8 = planned[0]
    tried, rejected = [], []
    g = loc["g"]
    for s in scored:
        if len(tried) >= AIM_TRIES:
            break
        p8, p5, _nd, i, j, k8, k5, n = s
        if i == 0 and j == 0:
            break                                  # nothing better than the planned site is left
        rng8 = wilson(k8, n)
        gain = 100.0 * (p8 - base_k8)
        # the candidate must beat the planned site clearly: 95 % ranges apart and at least 1 percentage point
        if gain < AIM_MIN_GAIN_PP or rng8[0] <= p_lo_planned[1]:
            break                                  # sorted: no later candidate does better
        if any(math.hypot((i - a) * px, (j - b) * px) < AIM_SEPARATION_M for a, b in rejected):
            continue
        x = loc["x"] + j * px                      # the draws are offsets from the exact aim point
        y = loc["y"] + i * px
        la, lo = g.unproject(x, y)
        la, lo = round(float(la), 5), round(float(lo), 5)
        cand = {"lat": la, "lon": lo, "dx_m": round(j * px, 1), "dy_m": round(i * px, 1),
                "distance_m": round(math.hypot(i, j) * px, 1), "p8": round(100.0 * p8, 1), "p8_range": list(rng8),
                "p5": round(100.0 * p5, 1), "p5_range": list(wilson(k5, n)), "gain_pp": round(gain, 1)}
        if not with_slip:
            cand["slip"] = None
            tried.append(cand)
            return {"offered": True, "slip_checked": False, **cand, "tried": tried,
                    "note": "The slip-margin check was not run for this answer."}
        sl = slip_at(la, lo)
        cand["slip"] = sl
        keep = (sl["verdict"] == planned_slip["verdict"]) and (sl["slip_margin_days"] >= planned_slip["slip_margin_days"])
        cand["keeps_slip_verdict"] = bool(keep)
        tried.append(cand)
        if keep:
            return {"offered": True, "slip_checked": True, **cand, "tried": tried,
                    "note": "A suggestion, not a site study: it looks only at slope over 10 m and the slip margin."}
        rejected.append((i, j))
    if not tried:
        return {"offered": False, "tried": [],
                "why": f"No aim point within {AIM_RADIUS_M:g} m does clearly better (by at least {AIM_MIN_GAIN_PP:g} "
                       "percentage point, beyond the sampling range)."}
    return {"offered": False, "tried": tried,
            "why": f"Aim points within {AIM_RADIUS_M:g} m that do better for slope lose the slip margin "
                   f"({len(tried)} tried), so none is suggested."}


# ---------------- the store ----------------

@lru_cache(maxsize=1)
def store() -> Optional[dict]:
    try:
        with open(STORE, encoding="utf-8") as fh:
            st = json.load(fh)
        return st if st.get("method_version") == METHOD_VERSION else None
    except (OSError, ValueError):
        return None


def stored(lat: float, lon: float) -> Optional[dict]:
    st = store()
    if not st:
        return None
    for r in st.get("sites", {}).values():
        if abs(r["site"]["lat"] - lat) < 1e-5 and abs(r["site"]["lon"] - lon) < 1e-5:
            return r
    return None


def build() -> dict:
    """Work out the named sites and write data/addons/safetouch/sites.json."""
    import datetime
    os.makedirs(STORE_DIR, exist_ok=True)
    out = {"method_version": METHOD_VERSION,
           "built_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "note": "made by: python -m slipday.addons.safetouch (see ADDON_safetouch.md)", "sites": {}}
    for sid, (la, lo, nm) in NAMED.items():
        out["sites"][sid] = compute(la, lo, nm, with_slip=True)
    with open(STORE, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    store.cache_clear()
    return out


# ---------------- the router ----------------

router = APIRouter(tags=["add-on: chance of a safe touchdown"])


@router.get("/api/addons/safetouch/site")
def api_site(id: Optional[str] = Query(default=None, description="a site id from /api/sites"),
             lat: Optional[float] = Query(default=None, ge=-90, le=90),
             lon: Optional[float] = Query(default=None, ge=-360, le=360),
             name: str = Query(default="", max_length=200)):
    """The chance that the ground under the lander is within 8 (and 5) degrees, per lander class."""
    if id:
        if id in NAMED:
            lat, lon, name = NAMED[id][0], NAMED[id][1], name or NAMED[id][2]
        else:
            from ..sites import SITES
            hit = next((s for s in SITES if s["id"] == id), None)
            if hit is None:
                raise HTTPException(404, f"no site with id {id!r}")
            lat, lon, name = hit["lat"], hit["lon"], name or hit["name"]
    if lat is None or lon is None:
        raise HTTPException(422, "give a site id, or lat and lon")
    lat = float(lat)
    lon = ((float(lon) + 180.0) % 360.0) - 180.0
    hit = stored(lat, lon)
    if hit is not None:
        res = dict(hit)
        if name:
            res["site"] = {**res["site"], "name": name}
        res["from_store"] = True
        return res
    if locate(lat, lon) is None:
        return {"available": False, "reason": TOO_COARSE, "site": {"name": name, "lat": lat, "lon": lon},
                "limits": PLAIN_LIMITS}
    from .. import load as lanes

    def work():
        return compute(lat, lon, name, with_slip=True)
    res = lanes.run_big(work)
    res["from_store"] = False
    return res


@router.get("/api/addons/safetouch/about")
def api_about():
    """The method, the lander classes, the 5 m grids on this machine and what the chance cannot tell."""
    return {"limit_deg": LIMIT_DEG, "goal_deg": GOAL_DEG, "uncertainty_deg": UNCERTAINTY_DEG,
            "draws_round": N_ROUND, "draws_per_direction": N_PER_DIRECTION, "directions": len(DIRECTIONS), "seed": SEED,
            "aim_radius_m": AIM_RADIUS_M, "aim_step_m": AIM_STEP_M,
            "grids": [{"name": n, "label": label} for n, label, _g in five_m_grids()],
            "classes": [{k: c[k] for k in ("id", "label", "sigma_major_m", "sigma_minor_m", "figure", "source", "source_url", "basis")}
                        for c in lander_classes()],
            "slip_rules": SLIP_DEFAULTS, "limits": PLAIN_LIMITS, "method_version": METHOD_VERSION}


if __name__ == "__main__":
    import time
    t = time.time()
    res = build()
    for sid, r in res["sites"].items():
        print(sid, r["site"]["name"], r.get("grid", {}).get("name"), "slip:", r.get("slip_planned"))
        for c in r.get("classes", []):
            if c.get("available"):
                sg = c.get("suggestion", {})
                print(f"  {c['label']:20s} p8 {c['p8']} {c['p8_range']} (+2: {c['p8_if_steeper']}, -2: {c['p8_if_flatter']})"
                      f"  p5 {c['p5']} {c['p5_range']} (+2: {c['p5_if_steeper']}, -2: {c['p5_if_flatter']})"
                      f"  outside {c['outside_5m_pct']} %  dir {c.get('p8_direction_span')}")
                print("     suggestion:", {k: sg.get(k) for k in ("offered", "lat", "lon", "distance_m", "p8", "p8_range", "p5", "gain_pp", "why")},
                      "tried", [(t_["distance_m"], t_["p8"], (t_.get("slip") or {}).get("verdict"), (t_.get("slip") or {}).get("slip_margin_days")) for t_ in sg.get("tried", [])])
            else:
                print(f"  {c['label']}: not available: {c.get('why')}")
    print(f"{time.time() - t:.1f} s")
