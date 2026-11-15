"""Add-on: "days of slip the planned landing survives" for the whole map (South pole to 80 deg S), on a coarse grid.

The 500 m slip-margin layer (``/api/slipmap``) covers only the 60 km square round the pole. This add-on serves the
same layer for the whole 80 m LOLA mosaic (608 km across), one point every 2 km, worked out off line:

    python scripts/addons/build_fullmap.py --step-m 2000 --procs 6   # terrain skylines, in resumable chunks
    python scripts/addons/finish_fullmap.py --step-m 2000            # slip margin for the page's opening plan

Same skyline code, same terrain stack (LOLA 80 m, then 240 m and coarser beyond its edge), same evaluation code
(``slipday.field.per_date`` and ``field.statistics``) as the close-up; only the spacing differs. Each point is checked
at its own position only, not at the 13 touchdown points the close-up's scatter check and the site card use.

Stored for one plan only: the page's opening plan (landing 18 Nov 2026 00:00 UTC, 60 landing dates a day apart,
240 sunlit hours and 100 hours of Earth contact in the first 14 days, Sun and Earth up at touchdown, half the Sun's
disc), with either Earth rule. Any other plan gets ``available: false`` with the reason; nothing is worked out at
request time.

The server only reads ``data/addons/fullmap/fullmap_<step>m.npz`` and ``.json``; it never writes.
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import re
import threading
from typing import Optional

import numpy as np
from fastapi import APIRouter, Query, Request, Response

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.environ.get("SLIPDAY_FULLMAP_DIR", os.path.join(ROOT, "data", "addons", "fullmap"))
NOT_DONE = -9                       # a grid point the off-line run has not reached (or without terrain)

VERDICTS = {
    "1": "the planned landing date meets the need at this point",
    "0": "the planned landing date does not meet the need at this point",
    "null": "not worked out (outside the part of the map done so far)",
}
EARTH_RULES = {True: "stations", False: "no_stations"}

_lock = threading.Lock()
_mem: dict = {}


def _stored_file() -> Optional[str]:
    """The finest stored layer (smallest spacing) in the data folder, or None."""
    best = None
    for p in glob.glob(os.path.join(DATA_DIR, "fullmap_*m.json")):
        m = re.search(r"fullmap_(\d+)m\.json$", p)
        if m and os.path.exists(p[:-5] + ".npz"):
            if best is None or int(m.group(1)) < best[0]:
                best = (int(m.group(1)), p)
    return best[1] if best else None


def load() -> Optional[dict]:
    """The stored layer (metadata plus arrays laid out on the full grid), cached in memory; None if not built."""
    path = _stored_file()
    if path is None:
        return None
    stamp = (path, os.path.getmtime(path), os.path.getmtime(path[:-5] + ".npz"))
    with _lock:
        if _mem.get("stamp") == stamp:
            return _mem["data"]
        with open(path, encoding="utf-8") as fh:
            meta = json.load(fh)
        z = np.load(path[:-5] + ".npz")
        n = int(meta["n"])
        idx = np.asarray(z["idx"], dtype=np.int64)
        grids = {}
        for rule in EARTH_RULES.values():
            for k in ("margin", "good"):
                a = np.full(n * n, NOT_DONE, dtype=np.int16)
                a[idx] = z[f"{rule}__{k}"]
                grids[f"{rule}__{k}"] = a
        terrain = np.full(n * n, np.nan, dtype=np.float32)
        terrain[idx] = z["terrain_m"]
        data = {"meta": meta, "n": n, "idx": idx, "lat": np.asarray(z["lat"]), "lon": np.asarray(z["lon"]),
                "terrain": terrain, "grids": grids, "responses": {}}
        _mem.update({"stamp": stamp, "data": data})
        return data


def _plan_mismatch(meta: dict, start: Optional[str], n_dates: Optional[int], need_sun_h: Optional[float],
                   need_earth_h: Optional[float], window_days: Optional[float]) -> Optional[str]:
    plan = meta["plan"]
    asked = []
    if start is not None and start[:10] != plan["start"][:10] or (start and len(start) > 10 and start[11:13] not in ("", "00")):
        asked.append(f"landing {start}")
    if n_dates is not None and int(n_dates) != plan["n_dates"]:
        asked.append(f"{n_dates} landing dates")
    if need_sun_h is not None and float(need_sun_h) != plan["need_sun_h"]:
        asked.append(f"{need_sun_h:g} sunlit hours")
    if need_earth_h is not None and float(need_earth_h) != plan["need_earth_h"]:
        asked.append(f"{need_earth_h:g} hours of Earth contact")
    if window_days is not None and float(window_days) != plan["window_days"]:
        asked.append(f"{window_days:g} days on the surface")
    if not asked:
        return None
    return ("The whole-map layer is worked out for the page's opening plan only (landing 18 Nov 2026, 60 landing "
            "dates, 240 sunlit hours and 100 hours of Earth contact in the first 14 days). You asked for "
            + ", ".join(asked) + ". The close-up of the pole (60 km across) is worked out for any plan.")


def _ints(a) -> list:
    return [None if v == NOT_DONE else int(v) for v in np.asarray(a).tolist()]


def _common(d: dict, rule: str) -> dict:
    meta = d["meta"]
    step = float(meta["step_m"])
    cov = meta["coverage"]
    ag = meta.get("agreement_with_close_up", {})
    return {
        "available": True, "stored": True,
        "label": "Days of slip the planned landing survives: whole map, one point every %g km" % (step / 1000.0),
        "grid_spacing_m": step, "step_m": step, "n": d["n"],
        "first_centre_km": {"x": meta["axis_first_m"] / 1000.0, "y": meta["axis_last_m"] / 1000.0},
        "order": "row by row, row 0 at the top (longitude 0 up), column 0 at the left; x = first_centre_km.x + col * step, "
                 "y = first_centre_km.y - row * step (south polar stereographic, km from the pole)",
        "terrain": meta["dem_label"].split(";")[0],
        "terrain_under_points_m": meta.get("terrain_under_points_m", {}),
        "plan": meta["plan"], "earth_rule": rule, "earth_rule_words": meta["earth_rules"][rule],
        "dates": meta["dates"],
        "coverage": cov,
        "coverage_words": _coverage_words(cov, step),
        "counts": meta["counts"][rule],
        "agreement_with_close_up": ({k: v for k, v in ag.items() if not isinstance(v, dict) or k == rule}
                                    if ag else {}),
        "close_up": {"half_km": 30.0, "step_m": 500.0, "endpoint": "POST /api/slipmap",
                     "words": "Inside the 60 km square round the pole, the close-up layer (one point every 500 m, "
                              "with a check at 13 touchdown points) is the detailed one; draw it on top of this layer."},
        "verdicts": VERDICTS,
        "how": ("Each point is checked at its own position only: one touchdown point, not the 13 touchdown points that "
                "the close-up's scatter check and the site card use, so a margin here can be shorter at a real landing. "
                "Skylines from LOLA 80 m terrain (240 m and coarser beyond its edge), for an observer 2 m above the "
                "ground, the same method as the close-up."),
        "limits": ["one point every %g km: anything smaller than that, such as a crater rim or a small ridge, can be "
                   "missed between points" % (step / 1000.0),
                   "80 m terrain: no boulders or small craters",
                   "each point is checked at its own position only (no landing scatter)",
                   "worked out for the page's opening plan only"],
        "made_utc": meta["made_utc"],
    }


def _coverage_words(cov: dict, step: float) -> str:
    if cov.get("complete"):
        return "Every point of the map is worked out (%d points, one every %g km)." % (cov["grid_points"], step / 1000.0)
    words = "%d of %d points worked out (%.1f %%)." % (cov["done"], cov["grid_points"], 100.0 * cov["share_done"])
    if cov.get("complete_at_m"):
        words += " The whole map is covered at one point every %g km; the in-between points are done for part of it." \
                 % (cov["complete_at_m"] / 1000.0)
    return words


def answer(earth_stations: bool = True) -> dict:
    d = load()
    if d is None:
        return {"available": False, "reason": "the whole-map layer has not been built on this installation "
                                              "(scripts/addons/build_fullmap.py, then scripts/addons/finish_fullmap.py)"}
    rule = EARTH_RULES[bool(earth_stations)]
    key = ("grid", rule)
    with _lock:
        hit = d["responses"].get(key)
    if hit is not None:
        return hit
    m = d["grids"][f"{rule}__margin"]
    verdict = np.where(m == NOT_DONE, NOT_DONE, (m >= 0).astype(np.int16))
    t = d["terrain"]
    out = _common(d, rule)
    out["layers"] = {
        "slip_margin_days": _ints(m),
        "verdict": _ints(verdict),
        "good_dates": _ints(d["grids"][f"{rule}__good"]),
        "terrain_m": [None if not np.isfinite(v) else int(v) for v in t.tolist()],
    }
    out["layer_words"] = {
        "slip_margin_days": "days of slip the planned landing survives at this point; -1: the planned date itself "
                            "fails; null: not worked out",
        "verdict": "1: the planned date meets the need here; 0: it does not; null: not worked out",
        "good_dates": "how many of the landing dates meet the need here",
        "terrain_m": "spacing of the terrain grid under the point, in metres",
    }
    with _lock:
        d["responses"][key] = out
    return out


def points(earth_stations: bool = True, x_min_km: float = -1e9, x_max_km: float = 1e9, y_min_km: float = -1e9,
           y_max_km: float = 1e9, limit: int = 5000) -> dict:
    d = load()
    if d is None:
        return answer(earth_stations)
    rule = EARTH_RULES[bool(earth_stations)]
    meta = d["meta"]
    n, step = d["n"], float(meta["step_m"])
    idx = d["idx"]
    r, c = np.divmod(idx, n)
    x = (meta["axis_first_m"] + c * step) / 1000.0
    y = (meta["axis_last_m"] - r * step) / 1000.0
    sel = np.nonzero((x >= x_min_km) & (x <= x_max_km) & (y >= y_min_km) & (y <= y_max_km))[0]
    total = len(sel)
    sel = sel[:limit]
    m = d["grids"][f"{rule}__margin"][idx[sel]]
    g = d["grids"][f"{rule}__good"][idx[sel]]
    t = d["terrain"][idx[sel]]
    rows = [{"lat": round(float(d["lat"][k]), 5), "lon": round(float(d["lon"][k]), 5), "x_km": round(float(x[k]), 3),
             "y_km": round(float(y[k]), 3), "slip_margin_days": int(mm),
             "verdict": "yes" if mm >= 0 else "no", "good_dates": int(gg),
             "grid_spacing_m": step, "terrain_m": float(tt)}
            for k, mm, gg, tt in zip(sel.tolist(), m.tolist(), g.tolist(), t.tolist()) if mm != NOT_DONE]
    out = {k: v for k, v in _common(d, rule).items() if k not in ("dates",)}
    out.update({"points": rows, "matched": int(total), "returned": len(rows), "truncated": bool(total > limit)})
    return out


router = APIRouter(tags=["add-on: slip margin for the whole map"])


def _encoded(earth_stations: bool, gz: bool) -> Optional[bytes]:
    """The grid answer as JSON bytes (gzipped if asked), made once per Earth rule and kept with the stored data."""
    d = load()
    if d is None:
        return None
    key = ("bytes", EARTH_RULES[bool(earth_stations)], gz)
    with _lock:
        hit = d["responses"].get(key)
    if hit is None:
        raw = json.dumps(answer(earth_stations), separators=(",", ":")).encode("utf-8")
        hit = gzip.compress(raw, 6) if gz else raw
        with _lock:
            d["responses"][key] = hit
    return hit


@router.get("/api/addons/fullmap")
def api_fullmap(request: Request, earth_stations: bool = True, start: Optional[str] = None,
                n_dates: Optional[int] = None, need_sun_h: Optional[float] = None,
                need_earth_h: Optional[float] = None, window_days: Optional[float] = None):
    """Days of slip the planned landing survives, for every point of the whole map (coarse grid), as layers."""
    d = load()
    if d is None:
        return answer(earth_stations)
    why = _plan_mismatch(d["meta"], start, n_dates, need_sun_h, need_earth_h, window_days)
    if why:
        return {"available": False, "reason": why, "plan": d["meta"]["plan"]}
    gz = "gzip" in request.headers.get("accept-encoding", "").lower()
    body = _encoded(earth_stations, gz)
    headers = {"Vary": "Accept-Encoding", "Cache-Control": "no-cache"}
    if gz:
        headers["Content-Encoding"] = "gzip"
    return Response(content=body, media_type="application/json", headers=headers)


@router.get("/api/addons/fullmap/points")
def api_fullmap_points(earth_stations: bool = True, x_min_km: float = -1e9, x_max_km: float = 1e9,
                       y_min_km: float = -1e9, y_max_km: float = 1e9, limit: int = Query(5000, ge=1, le=100000)):
    """The worked-out points as rows (lat, lon, slip margin, verdict, grid spacing, terrain), optionally in a box."""
    return points(earth_stations, x_min_km, x_max_km, y_min_km, y_max_km, limit)


@router.get("/api/addons/fullmap/about")
def api_fullmap_about():
    """What the layer is, its coverage and its agreement with the close-up, without the arrays."""
    d = load()
    if d is None:
        return answer()
    out = _common(d, "stations")
    out.pop("earth_rule"), out.pop("earth_rule_words"), out.pop("counts")
    out["counts"] = d["meta"]["counts"]
    out["agreement_with_close_up"] = d["meta"].get("agreement_with_close_up", {})
    out["earth_rules"] = d["meta"]["earth_rules"]
    out["evaluation_seconds"] = d["meta"].get("evaluation_seconds")
    return out
