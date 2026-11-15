"""Slip-tolerant atlas, 2027 to 2035 (add-on router).

Serves the stored atlas (data/addons/atlas/atlas.json, built by ``python -m slipday.addons.atlas_build``).  Nothing
else in the app depends on it, and it computes nothing at request time.

    GET /api/addons/atlas                    summary: rule, per-year table, drift, check against the 2027-2030 calendar
    GET /api/addons/atlas/heat?variant=...   monthly shares for the heat strip (variant: main | sun_only)
    GET /api/addons/atlas/year/{year}        one year in full, both variants
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JSON_PATH = os.path.join(ROOT, "data", "addons", "atlas", "atlas.json")
VARIANTS = ("main", "sun_only")

router = APIRouter(prefix="/api/addons/atlas", tags=["atlas"])


@lru_cache(maxsize=1)
def _load_cached(mtime: float) -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def load() -> dict | None:
    if not os.path.exists(JSON_PATH):
        return None
    return _load_cached(os.path.getmtime(JSON_PATH))


def _missing() -> dict:
    return {"available": False, "reason": "the atlas has not been built on this installation "
                                          "(python -m slipday.addons.atlas_build)"}


@router.get("")
def atlas_summary():
    d = load()
    if d is None:
        return _missing()
    out = {"available": True}
    for k in ("what", "rule", "citation", "n_sites", "years", "overlap", "subsolar_drift"):
        out[k] = d[k]
    out["variants"] = {}
    for v in VARIANTS:
        x = d["variants"][v]
        out["variants"][v] = {"best_year": x["best_year"], "worst_year": x["worst_year"],
                              "all_nine_whole_span": x["all_nine_whole_span"], "whole_span_best": x["whole_span_best"],
                              "season_drift": x["season_drift"], "season_drift_by_region": x["season_drift_by_region"],
                              "first_try_drift": x["first_try_drift"],
                              "per_year": [{k: r[k] for k in ("year", "n_times", "all_nine", "best", "regions_to_match_all_nine")}
                                           for r in x["per_year"]]}
    return out


@router.get("/heat")
def atlas_heat(variant: str = Query("main", pattern="^(main|sun_only)$")):
    d = load()
    if d is None:
        return _missing()
    return {"available": True, "variant": variant, "years": d["years"], "step_hours": d["rule"]["step_hours"],
            **d["variants"][variant]["heat"]}


@router.get("/year/{year}")
def atlas_year(year: int):
    d = load()
    if d is None:
        return _missing()
    if year not in d["years"]:
        raise HTTPException(404, f"the atlas covers {d['years'][0]} to {d['years'][-1]}")
    i = d["years"].index(year)
    return {"available": True, "year": year, "step_hours": d["rule"]["step_hours"],
            **{v: d["variants"][v]["per_year"][i] for v in VARIANTS}}
