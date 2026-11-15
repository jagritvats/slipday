"""HTTP API and static front end.  Run with: uvicorn slipday.api:app"""
from __future__ import annotations

import csv
import glob
import importlib
import importlib.util
import io
import json
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import contact, demstore, field, horizons, load, moonmap, replay, scatterfield, shadowsites, survival, windows, finer20
from .ephem import cache_samples, parse_utc
from .geometry import Site
from .hindcast import hindcast
from .load import Busy, run, run_big
from .metrics import SYNODIC_DAYS, Criteria, any_light_flags, longest_run, series, site_summary, slip_grid, span_stats
from .robust import (banded_slip_grid, earth_mask_sweep, ensemble, lander_classes, landing_circles, mission_card,
                     robust_sites)
from .why import why as why_flips
from .sites import SITES, custom_site, get_site, horizon_for, smooth_twin, terrain_profile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "static")
FIXTURES = os.path.join(ROOT, "fixtures")
VALIDATION = os.path.join(ROOT, "data", "validation", "terrain_validation.json")

app = FastAPI(title="Slipday", version="0.3.0",
              description="What a launch slip costs at a lunar landing site: Sun and Earth above the terrain "
                          "skyline, by site and landing date, with a spread on every answer.")
app.add_middleware(GZipMiddleware, minimum_size=2000)


@app.exception_handler(Busy)
def _busy(_request, exc: Busy):
    """The cold lane's queue is full: say so at once instead of holding the connection for minutes."""
    return JSONResponse({"detail": str(exc), "busy": True, "retry_after_s": exc.retry_after_s}, status_code=503,
                        headers={"Retry-After": str(exc.retry_after_s)})


class SiteRef(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-360, le=360)


class Options(BaseModel):
    mask_deg: float = Field(default=0.0, ge=0, le=30)
    min_sun_el: float = Field(default=-90.0, ge=-90, le=90)      # -90 = no extra minimum
    min_earth_el: float = Field(default=-90.0, ge=-90, le=90)
    terrain: bool = True
    mast_m: float = Field(default=2.0, ge=0, le=500)
    min_sun_fraction: float = Field(default=0.5, ge=0, le=1)
    earth_margin_deg: float = Field(default=0.0, ge=0, le=20)
    earth_stations: bool = False        # Earth contact also needs a DSN complex with the Moon above its mask

    def criteria(self) -> Criteria:
        return Criteria(self.min_sun_fraction, self.min_sun_el, self.min_earth_el, self.earth_margin_deg,
                        self.earth_stations)


class CompareRequest(Options):
    sites: List[SiteRef] = Field(min_length=1, max_length=4)
    start: str
    hours: int = Field(default=24 * 60, ge=24, le=24 * 400)
    step_minutes: int = Field(default=60, ge=10, le=720)
    at: Optional[str] = None


class SlipRequest(Options):
    sites: List[SiteRef] = Field(min_length=1, max_length=12)
    start: str
    n_dates: int = Field(default=60, ge=1, le=400)
    date_step_hours: int = Field(default=24, ge=1, le=24 * 30)
    window_days: float = Field(default=14.0, gt=0, le=120)
    scatter_m: float = Field(default=0.0, ge=0, le=500)       # > 0 adds the landing-scatter band to each row
    band: bool = False                                        # coarse-grid and near-field variants without scatter


class Need(Options):
    need_sun_h: float = Field(default=240.0, ge=0, le=24 * 120)
    need_earth_h: float = Field(default=100.0, ge=0, le=24 * 120)
    window_days: float = Field(default=14.0, gt=0, le=120)
    sun_at_touchdown: bool = True
    earth_at_touchdown: bool = True


class MissionRequest(Need):
    site: SiteRef
    landing: str
    scatter_m: float = Field(default=100.0, ge=0, le=500)
    slip_days: int = Field(default=60, ge=1, le=120)


class SlipMapRequest(Need):
    start: str
    n_dates: int = Field(default=60, ge=2, le=90)


class PairsRequest(Options):
    sites: List[SiteRef] = Field(min_length=2, max_length=4)
    start: str
    days: float = Field(default=365.0, gt=1, le=800)


def _resolve(ref: SiteRef, opt: Options) -> tuple[Site, Optional[Site]]:
    """The site with the best horizon available, and its smooth-sphere twin
    when the first one uses terrain (None otherwise)."""
    try:
        if ref.id:
            site = get_site(ref.id, opt.mask_deg, opt.mast_m, opt.terrain)
        else:
            if ref.lat is None or ref.lon is None:
                raise HTTPException(422, "a site needs either an id or both lat and lon")
            site = custom_site(ref.name or "", ref.lat, ref.lon, opt.mask_deg, opt.mast_m, opt.terrain)
    except KeyError:
        raise HTTPException(404, f"unknown site id {ref.id!r}")
    return site, (smooth_twin(site, opt.mask_deg) if site.horizon.is_terrain else None)


def _options(mask_deg=0.0, min_sun_el=-90.0, min_earth_el=-90.0, terrain=True, mast_m=2.0,
             min_sun_fraction=0.5, earth_margin_deg=0.0) -> Options:
    return Options(mask_deg=mask_deg, min_sun_el=min_sun_el, min_earth_el=min_earth_el, terrain=terrain,
                   mast_m=mast_m, min_sun_fraction=min_sun_fraction, earth_margin_deg=earth_margin_deg)


def _guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


def _parse_or_422(text: str, what: str) -> datetime:
    try:
        return parse_utc(text)
    except (ValueError, TypeError):
        raise HTTPException(422, f"{what} is not a date or time I can read (use e.g. 2026-11-14 or 2026-11-14T06:00:00Z)")


@app.get("/api/health")
def health():
    t = demstore.status()
    return {"status": "ok", "version": app.version, "ephemeris": "JPL DE421 (de421 PyPI package)",
            "orientation": "DE421 lunar librations, Mean Earth/polar axis frame",
            "horizon_default": ("terrain (" + t["label"] + ") where the DEM covers the site, smooth sphere elsewhere"
                                if t["available"] else "smooth sphere, 0 deg (no terrain data installed)"),
            "terrain": t, "ephemeris_cache_samples": cache_samples(),
            "horizons_crosscheck_enabled": horizons.enabled(),
            "malloc_arena_limit": load.ARENA_LIMIT or "none (not glibc, so not needed)",
            "lanes": load.lanes()}


@app.get("/api/sites")
def sites():
    dem = demstore.get_dem()
    out = []
    for s in SITES:
        d = dict(s)
        d["terrain"] = bool(dem is not None and np.isfinite(dem.height_m(np.array([s["lat"]]), np.array([s["lon"]]))[0]))
        out.append(d)
    return {"sites": out, "terrain": demstore.status()}


Q_LAT = Query(None, ge=-90, le=90)
Q_LON = Query(None, ge=-360, le=360)


@app.get("/api/series")
def api_series(start: str, site: Optional[str] = None, lat: Optional[float] = Q_LAT, lon: Optional[float] = Q_LON,
               name: Optional[str] = None, hours: int = Query(24 * 30, ge=1, le=24 * 400),
               step_minutes: int = Query(60, ge=10, le=720), mask_deg: float = Query(0.0, ge=0, le=30),
               terrain: bool = True, mast_m: float = Query(2.0, ge=0, le=500),
               min_sun_fraction: float = Query(0.5, ge=0, le=1), earth_margin_deg: float = Query(0.0, ge=0, le=20)):
    opt = _options(mask_deg, terrain=terrain, mast_m=mast_m, min_sun_fraction=min_sun_fraction,
                   earth_margin_deg=earth_margin_deg)
    _parse_or_422(start, "start")

    def work():
        s, _ = _resolve(SiteRef(id=site, name=name, lat=lat, lon=lon), opt)
        return _guard(series, s, start, hours, step_minutes, opt.criteria())
    return run(work)


@app.get("/api/metrics")
def api_metrics(at: str, site: Optional[str] = None, lat: Optional[float] = Q_LAT, lon: Optional[float] = Q_LON,
                name: Optional[str] = None, window_days: float = Query(SYNODIC_DAYS, gt=0, le=60),
                mask_deg: float = Query(0.0, ge=0, le=30), min_sun_el: float = Query(-90.0, ge=-90, le=90),
                min_earth_el: float = Query(-90.0, ge=-90, le=90), terrain: bool = True,
                mast_m: float = Query(2.0, ge=0, le=500), min_sun_fraction: float = Query(0.5, ge=0, le=1),
                earth_margin_deg: float = Query(0.0, ge=0, le=20)):
    opt = _options(mask_deg, min_sun_el, min_earth_el, terrain, mast_m, min_sun_fraction, earth_margin_deg)
    _parse_or_422(at, "at")

    def work():
        s, twin = _resolve(SiteRef(id=site, name=name, lat=lat, lon=lon), opt)
        out = _guard(site_summary, s, at, window_days, opt.criteria())
        if twin is not None:
            out["smooth"] = _guard(site_summary, twin, at, window_days, opt.criteria())
        return out
    return run(work)


def _compare(req: CompareRequest) -> dict:
    at = req.at or req.start
    crit = req.criteria()
    out = []
    for ref in req.sites:
        s, twin = _resolve(ref, req)
        entry = {
            "terrain": s.horizon.is_terrain,
            "series": _guard(series, s, req.start, req.hours, req.step_minutes, crit),
            "metrics": _guard(site_summary, s, at, SYNODIC_DAYS, crit),
        }
        if twin is not None:
            ss = _guard(series, twin, req.start, req.hours, req.step_minutes, crit)
            entry["smooth"] = {"horizon": ss["horizon"], "lit": ss["lit"], "earth_vis": ss["earth_vis"],
                               "usable": ss["usable"], "events": ss["events"],
                               "metrics": _guard(site_summary, twin, at, SYNODIC_DAYS, crit)}
            entry["profile"] = terrain_profile(s.lat, s.lon, req.mast_m).to_json()
        out.append(entry)
    return {"start": req.start, "at": at, "criteria": crit.describe(), "terrain": demstore.status(), "sites": out}


@app.post("/api/compare")
def api_compare(req: CompareRequest):
    _parse_or_422(req.start, "start")
    return run(_compare, req)


def _slipgrid(req: SlipRequest) -> dict:
    _parse_or_422(req.start, "start")
    pairs = [_resolve(r, req) for r in req.sites]
    crit = req.criteria()
    if req.scatter_m > 0 or req.band:
        if len(pairs) * req.n_dates > 12 * 120:
            raise HTTPException(422, "the scatter band is limited to 1,440 site-date cells per request")
        grid, _ = _guard(banded_slip_grid, [p[0] for p in pairs], req.start, req.n_dates, req.date_step_hours,
                         req.window_days, crit, req.mask_deg, req.mast_m, req.scatter_m)
    else:
        grid = _guard(slip_grid, [p[0] for p in pairs], req.start, req.n_dates, req.date_step_hours,
                      req.window_days, crit)
    twins = [(i, p[1]) for i, p in enumerate(pairs) if p[1] is not None]
    if twins:
        g2 = _guard(slip_grid, [t[1] for t in twins], req.start, req.n_dates, req.date_step_hours,
                    req.window_days, crit)
        for (i, _), row in zip(twins, g2["rows"]):
            grid["rows"][i]["smooth"] = {k: row[k] for k in ("horizon", "total", "continuous", "sunlit", "earth")}
    grid["terrain"] = demstore.status()
    return grid


@app.post("/api/slipgrid")
def api_slipgrid(req: SlipRequest):
    return run(_slipgrid, req)


@app.post("/api/mission")
def api_mission(req: MissionRequest):
    """Yes / not sure / no for one site, landing date and need, for every day of slip."""
    _parse_or_422(req.landing, "landing")

    def work():
        site, _ = _resolve(req.site, req)
        return _guard(mission_card, site, req.landing, req.need_sun_h, req.need_earth_h, req.window_days,
                      req.criteria(), req.mask_deg, req.mast_m, req.scatter_m, req.slip_days,
                      req.sun_at_touchdown, req.earth_at_touchdown)
    out = run(work)
    out["terrain"] = demstore.status()
    fine = _finer_check(out["site"]["lat"], out["site"]["lon"], out["landing_utc"], req)
    if fine is not None:
        out["finer_grid_check"] = fine
    return out


FINER = os.path.join(ROOT, "data", "validation", "finer_grid_check.json")


@lru_cache(maxsize=1)
def _finer_store():
    try:
        with open(FINER) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _finer_entries(store: dict) -> list:
    """Every stored example in one shape: the two ridge sites of scripts/ridge_20m.py and the candidates tried by
    scripts/pick_opening_example.py."""
    out = list(store.get("entries", []))
    op = store.get("opening_example") or {}
    for c in op.get("tried", []):
        if "card_20m" in c:
            out.append({"site_id": None, "lat": c["lat"], "lon": c["lon"], "landing_utc": op["landing_utc"],
                        "need_sun_h": op["need_sun_h"], "need_earth_h": op["need_earth_h"], "window_days": op["window_days"],
                        "scatter_m": op["scatter_m"], "fine": c["card_20m"], "used": c["card_80m"], "candidate_rank": c["rank"],
                        "chosen": bool(op.get("chosen") and op["chosen"]["rank"] == c["rank"])})
    return out


@lru_cache(maxsize=1)
def _grid5_store() -> Optional[dict]:
    try:
        with open(os.path.join(field.FIELD_DIR, "..", "validation", "grids_5m.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _grid5(lat: float, lon: float, landing_utc: str) -> Optional[dict]:
    """The stored 5 m site-model result for this example (scripts/compare_grids.py), if there is one."""
    st = _grid5_store()
    if not st or st.get("landing") != landing_utc:
        return None
    ids = {"robust_pick": (-89.0098, 122.76389), "shackleton": (-89.4398, -137.17)}
    for r in st["rows"]:
        if "5 m" in str(r.get("grid")) and r["site"] in ids and abs(ids[r["site"]][0] - lat) < 1e-3 and abs(ids[r["site"]][1] - lon) < 1e-3:
            names = {"data/dem5/site07": "Site07, peak near Shackleton", "data/dem5/site01": "Site01, connecting ridge"}
            return {**{k: r[k] for k in ("verdict", "slip_margin_days", "points_passing_by_day", "sunlit_h", "earth_h")},
                    "grid_name": names.get(r["stack"], r["stack"])}
    return None


def _finer_check(lat: float, lon: float, landing_utc: str, req) -> Optional[dict]:
    """The stored off-line check of this very example on a finer grid, if there is one.

    It is shown beside the verdict, so that the first screen says whether the finer grid supports the answer.
    Only an exact match counts: same place, landing, need, window, scatter and default rules, and only while
    the page itself computes on the grid the comparison was made against."""
    store = _finer_store()
    if not store or demstore.status().get("label") != store.get("used_grid"):
        return None
    default_rules = (req.mask_deg == 0 and req.min_sun_fraction == 0.5 and req.earth_margin_deg == 0 and req.mast_m == 2.0
                     and req.min_sun_el <= -90 and req.min_earth_el <= -90 and req.terrain and req.sun_at_touchdown
                     and req.earth_at_touchdown)
    word = {"yes": "Yes", "not sure": "Not sure", "no": "No"}
    for e in _finer_entries(store):
        if (default_rules and abs(e["lat"] - lat) < 1e-5 and abs(e["lon"] - lon) < 1e-5 and e["landing_utc"] == landing_utc
                and e["need_sun_h"] == req.need_sun_h and e["need_earth_h"] == req.need_earth_h
                and e["window_days"] == req.window_days and e["scatter_m"] == req.scatter_m):
            fine, used = e["fine"], e["used"]
            p, n = fine["points_passing_by_day"], fine["points"]
            end = 0
            while end + 1 < len(p) and p[end + 1] == n:
                end += 1
            agrees = fine["verdict"] == used["verdict"]
            short = (("Both grids agree. " if agrees else "")
                     + f"On the 20 m grid: {word.get(fine['verdict'], 'not computed')} as planned ({p[0]} of {n} touchdown points)"
                     + (f", {fine['slip_margin_days']} days of margin" if fine["verdict"] == "yes" else
                        (f"; slips of 1 to {end} days pass" if end >= 1 else "")) + ".")
            text = e.get("text") or (
                f"On NASA's 20 m LOLA grid this example reads {word.get(fine['verdict'])} on the planned date: {p[0]} of {n} "
                f"touchdown points pass" + (f", with {fine['slip_margin_days']} days of slip margin" if fine["verdict"] == "yes" else "")
                + f". On the 80 m grid used here: {word.get(used['verdict'])}, {used['points_passing_by_day'][0]} of {used['points']}"
                + (f", {used['slip_margin_days']} days of margin" if used["verdict"] == "yes" else "") + ".")
            g5 = _grid5(lat, lon, landing_utc)
            if g5 is not None:                      # the LOLA team's 5 m site model, where one covers the site
                vw = word.get(g5["verdict"], g5["verdict"])
                same = g5["verdict"] == fine["verdict"] and g5["slip_margin_days"] == fine["slip_margin_days"] and g5["verdict"] == "yes"
                short += " 5 m: the same." if same else f" 5 m: {vw} ({g5['points_passing_by_day'][0]} of 13)."

                text += (f" On the LOLA team's 5 m site model ({g5['grid_name']}): {vw} on the planned date, {g5['points_passing_by_day'][0]} of 13 "
                         "touchdown points" + (f", {g5['slip_margin_days']} days of slip margin" if g5["verdict"] == "yes" else "") + ".")
            return {"text": text, "short": short, "agrees": agrees, "fine_grid": store["fine_grid"].split(";")[0], "grid5": g5,
                    "verdict": fine["verdict"], "slip_margin_days": fine["slip_margin_days"], "points_passing": p[0],
                    "points": n, "made_utc": store["made_utc"], "opening_example": bool(e.get("chosen"))}
    return None


@app.get("/api/finer-grid")
def api_finer_grid():
    """The stored comparison of the default example on a finer terrain grid (scripts/ridge_20m.py --save)."""
    store = _finer_store()
    if not store:
        return {"available": False, "reason": "scripts/ridge_20m.py --save has not been run on this installation"}
    return {"available": True, **store}


@app.post("/api/landing-circles")
def api_landing_circles(req: MissionRequest):
    """Share of a landing circle (100 m to 1 km) in which the plan still works, for every day of slip."""
    _parse_or_422(req.landing, "landing")

    def work():
        site, _ = _resolve(req.site, req)
        return _guard(landing_circles, site, req.landing, req.need_sun_h, req.need_earth_h, req.window_days,
                      req.criteria(), req.mask_deg, req.mast_m, req.slip_days, req.sun_at_touchdown,
                      req.earth_at_touchdown)
    out = run_big(work)
    out["need"] = {"sunlit_h": req.need_sun_h, "earth_h": req.need_earth_h}
    return out


class WhyRequest(MissionRequest):
    day: int = Field(default=0, ge=0, le=119)               # which cell of the verdict strip: days of slip


@app.post("/api/why")
def api_why(req: WhyRequest):
    """Sun and Earth against the terrain skyline for one landing window, and the terrain that ends the margin."""
    _parse_or_422(req.landing, "landing")

    def work():
        site, _ = _resolve(req.site, req)
        return _guard(why_flips, site, req.landing, req.need_sun_h, req.need_earth_h, req.window_days, req.criteria(),
                      req.mask_deg, req.mast_m, req.scatter_m, req.slip_days, req.sun_at_touchdown,
                      req.earth_at_touchdown, req.day)
    out = dict(run(work))
    psr = moonmap.nearest_permanent_shadow(out["site"]["lat"], out["site"]["lon"])
    if psr is not None:
        out["permanent_shadow"] = psr
    return out


@app.post("/api/earth-mask")
def api_earth_mask(req: MissionRequest):
    """How much Earth clearance the card's answer has: verdict and slip margin for every mask from 0 to 10 degrees."""
    _parse_or_422(req.landing, "landing")

    def work():
        site, _ = _resolve(req.site, req)
        if not site.horizon.is_terrain:
            return {"available": False, "reason": "no terrain data covers this site, so there is no skyline to clear"}
        out = _guard(earth_mask_sweep, site, req.landing, req.need_sun_h, req.need_earth_h, req.window_days, req.criteria(),
                     req.mask_deg, req.mast_m, req.scatter_m, req.slip_days, req.sun_at_touchdown, req.earth_at_touchdown)
        out["available"] = True
        return out
    out = run(work)
    out["published_mask"] = PUBLISHED_MASK
    return out


@app.post("/api/stations")
def api_stations(req: MissionRequest):
    """Earth contact as station visibility: which Deep Space Network complex carries each hour of the landing window,
    the hours with none in view, and the split year by year over one 18.6-year cycle."""
    _parse_or_422(req.landing, "landing")

    def work():
        site, _ = _resolve(req.site, req)
        if not site.horizon.is_terrain:
            return {"available": False, "reason": "no terrain data covers this site, so there is no skyline to clear"}
        return _guard(contact.report, site, req.landing, req.window_days, req.criteria())
    return run(work)


@app.post("/api/survival")
def api_survival(req: MissionRequest):
    """Hours to ride through on stored energy, for every day of slip: the longest night and the longest Earth outage
    in the mission window, at the worst of the 13 touchdown points (rule R5, pass 4)."""
    _parse_or_422(req.landing, "landing")

    def work():
        site, _ = _resolve(req.site, req)
        if not site.horizon.is_terrain:
            return {"available": False, "reason": "no terrain data covers this site"}
        crit = req.criteria()
        m = _guard(mission_card, site, req.landing, req.need_sun_h, req.need_earth_h, req.window_days, crit,
                   req.mask_deg, req.mast_m, req.scatter_m, req.slip_days, req.sun_at_touchdown, req.earth_at_touchdown)
        ens = ensemble(site, req.mask_deg, req.mast_m, req.scatter_m)
        from .robust import _flat
        members, index = _flat(ens)
        out = _guard(survival.site_survival, members, index, req.landing, req.window_days, crit, req.slip_days,
                     [d["verdict"] for d in m["days"]], int(m["slip_margin_days"]) if m["verdict"] == "yes" else -1)
        out["verdict"] = m["verdict"]
        out["site"] = {"name": site.name, "lat": site.lat, "lon": site.lon}
        return out
    return run(work)


@app.post("/api/survival-map")
def api_survival_map(req: SlipMapRequest):
    """The scatter-checked map coloured by the worst longest night over the slip days that still pass (rule R5)."""
    _parse_or_422(req.start, "start")
    if field.load() is None:
        return {"available": False, "reason": "the skyline field has not been built on this installation"}
    refusal = _stored_mast_refusal(req)
    if refusal:
        return refusal

    def work():
        r = _guard(survival.survival_map, req.start, req.n_dates, req.window_days, req.criteria(), req.mask_deg,
                   req.need_sun_h, req.need_earth_h, req.sun_at_touchdown, req.earth_at_touchdown)
        return r or {"available": False, "reason": "the scatter skylines are not installed"}
    out = run(work)
    if out.get("available"):
        meta = field.load()["meta"]
        out = dict(out)
        out.update({"n": meta["n"], "half_km": meta["half_km"], "step_m": meta["step_m"]})
    return out


@app.post("/api/windows")
def api_windows(req: MissionRequest):
    """The planned landing and the next three monthly launch windows (one synodic month apart, the same solar phase),
    each judged with the card's rules and need, with the whole night and Earth outage it meets (rules R9, R10)."""
    _parse_or_422(req.landing, "landing")

    def work():
        site, _ = _resolve(req.site, req)
        if not site.horizon.is_terrain:
            return {"available": False, "reason": "no terrain data covers this site"}
        return _guard(windows.next_windows, site, req.landing, [0, 1, 2, 3], req.need_sun_h, req.need_earth_h,
                      req.window_days, req.criteria(), req.mask_deg, req.mast_m, req.scatter_m, req.sun_at_touchdown,
                      req.earth_at_touchdown)
    return run(work)


class WindowOptionsRequest(MissionRequest):
    alternatives: List[SiteRef] = Field(default_factory=list, max_length=8)


@app.post("/api/window-options")
def api_window_options(req: WindowOptionsRequest):
    """Rule R13: for each of the next three monthly windows, the best landing hour for this site (every 6 h within
    72 h of the window's landing) and which other site is a clear yes at the window's landing (the page's sites,
    then the 18 scatter-robust map candidates of section H.1, in that order)."""
    _parse_or_422(req.landing, "landing")
    key = req.model_dump_json()
    if key in _OPTIONS_CACHE:
        return _OPTIONS_CACHE[key]

    def work():
        site, _ = _resolve(req.site, req)
        if not site.horizon.is_terrain:
            return {"available": False, "reason": "no terrain data covers this site"}
        crit = req.criteria()
        args = (req.need_sun_h, req.need_earth_h, req.window_days, crit, req.mask_deg, req.mast_m, req.scatter_m,
                req.sun_at_touchdown, req.earth_at_touchdown)
        cands = []
        for ref in req.alternatives:
            try:
                s2, _ = _resolve(ref, req)
            except HTTPException:
                continue
            if abs(s2.lat - site.lat) > 1e-6 or abs(s2.lon - site.lon) > 1e-6:
                cands.append(("page", s2))
        for c in windows.map_candidates():
            if abs(c["lat"] - site.lat) < 0.003 and abs(c["lon"] - site.lon) < 0.15:      # the plan's own site is not an alternative
                continue
            cands.append(("map", custom_site(f"map point {abs(c['lat']):.3f} S, {abs(c['lon']):.3f} {'W' if c['lon'] < 0 else 'E'}",
                                             c["lat"], c["lon"], req.mask_deg, req.mast_m)))
        t0 = parse_utc(req.landing)
        rows = []
        for k in (1, 2, 3):
            L = windows._hour(t0 + timedelta(days=windows.SYNODIC_DAYS * k)).strftime("%Y-%m-%dT%H:%M:%SZ")
            best = windows.best_hour(site, L, *args)
            yes_at_hour, yes_any = [], []
            for kind, s2 in cands:
                m = mission_card(s2, L, req.need_sun_h, req.need_earth_h, req.window_days, crit, req.mask_deg, req.mast_m,
                                 req.scatter_m, 15, req.sun_at_touchdown, req.earth_at_touchdown)
                if m["verdict"] == "yes":
                    yes_at_hour.append(s2.name)
                bh = windows.best_hour(s2, L, *args)          # the same +/- 72 h search as the plan's own site
                if bh["found"]:
                    yes_any.append({"name": s2.name, "lat": s2.lat, "lon": s2.lon, "kind": kind, "landing_utc": bh["landing_utc"],
                                    "slip_margin_days": bh["slip_margin_days"], "fragile": bh["fragile"],
                                    "min_clearance_deg": bh["min_clearance_deg"]})
            rows.append({"k": k, "landing_utc": L, "best_hour": best, "sites_checked": len(cands),
                         "sites_yes_at_window_hour": len(yes_at_hour), "sites_yes": yes_any,
                         "first_yes": yes_any[0] if yes_any else None})
        return {"available": True, "rows": rows, "rule": "R13 in DEEP_PASS.md"}
    out = run(work)
    if out.get("available"):
        _OPTIONS_CACHE[key] = out
        while len(_OPTIONS_CACHE) > 16:
            _OPTIONS_CACHE.pop(next(iter(_OPTIONS_CACHE)))
    return out


_OPTIONS_CACHE: dict = {}


@app.get("/api/artemis-regions")
def api_artemis_regions():
    """NASA's nine Artemis III candidate regions, on the published candidate landing sites of Wueller et al. 2026,
    judged in each missed window of the opening plan and of IM-1 (scripts/artemis_regions.py)."""
    path = os.path.join(field.FIELD_DIR, "..", "validation", "artemis_regions.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return {"available": True, **json.load(fh)}
    except (OSError, ValueError):
        return {"available": False, "reason": "not computed on this installation (scripts/artemis_regions.py)"}


@app.get("/api/region-availability")
def api_region_availability():
    """How many of NASA's nine Artemis III regions must stay open, 2027 to 2030, on the published candidate landing
    sites of Wueller et al. 2026 (scripts/region_availability.py).  An addition: no other answer depends on it."""
    from . import regions
    d = regions.load()
    if d is None:
        return {"available": False, "reason": "not computed on this installation (scripts/region_availability.py)"}
    return {"available": True, **d}


@app.get("/api/real-windows")
def api_real_windows():
    """Two real south-pole missions and their launch windows (scripts/real_windows.py, rule R10), with sources."""
    path = os.path.join(field.FIELD_DIR, "..", "validation", "real_windows.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return {"available": True, **json.load(fh)}
    except (OSError, ValueError):
        return {"available": False, "reason": "not computed on this installation (scripts/real_windows.py)"}


# A published elevation mask for a direct-to-Earth link from the lunar surface, if one could be read first-hand
# (pass 3, rule R1).  None means none was found: every non-zero mask on the page is then labelled illustrative.
PUBLISHED_MASK = None


@app.post("/api/lander-classes")
def api_lander_classes(req: MissionRequest):
    """Chance that the plan holds, per day of slip, for three ASSUMED landing dispersions (Gaussian ellipses)."""
    _parse_or_422(req.landing, "landing")

    def work():
        site, _ = _resolve(req.site, req)
        return _guard(lander_classes, site, req.landing, req.need_sun_h, req.need_earth_h, req.window_days,
                      req.criteria(), req.mask_deg, req.mast_m, req.slip_days, req.sun_at_touchdown,
                      req.earth_at_touchdown)
    out = run_big(work)
    out["need"] = {"sunlit_h": req.need_sun_h, "earth_h": req.need_earth_h}
    return out


class YearRequest(MissionRequest):
    days: int = Field(default=365, ge=30, le=400)


@lru_cache(maxsize=24)
def _year(req_json: str) -> dict:
    req = YearRequest(**json.loads(req_json))
    site, _ = _resolve(req.site, req)
    m = mission_card(site, req.landing, req.need_sun_h, req.need_earth_h, req.window_days, req.criteria(),
                     req.mask_deg, req.mast_m, req.scatter_m, req.days, req.sun_at_touchdown, req.earth_at_touchdown)
    code = {"yes": "y", "not sure": "u", "no": "n", "n/a": "-"}
    verdicts = "".join(code[d["verdict"]] for d in m["days"])
    months: dict = {}
    for d in m["days"]:
        k = d["landing_utc"][:7]
        e = months.setdefault(k, {"month": k, "dates": 0, "yes": 0, "not_sure": 0, "no": 0})
        e["dates"] += 1
        e[{"yes": "yes", "not sure": "not_sure", "no": "no"}.get(d["verdict"], "no")] += 1 if d["verdict"] != "n/a" else 0
    runs, cur = [], 0
    for ch in verdicts:
        if ch == "y":
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return {"site": m["site"], "horizon": m["horizon"], "start_utc": m["days"][0]["landing_utc"], "days": len(m["days"]),
            "verdicts": verdicts, "yes": verdicts.count("y"), "not_sure": verdicts.count("u"), "no": verdicts.count("n"),
            "smooth_sphere_yes": int(sum(1 for d in m["days"] if d["smooth_sphere_passes"])),
            "smooth_sphere": "".join("y" if d["smooth_sphere_passes"] else "n" for d in m["days"]),
            "months": list(months.values()), "longest_yes_run_days": max(runs) if runs else 0, "yes_runs": len(runs),
            "months_without_a_yes": [e["month"] for e in months.values() if e["yes"] == 0],
            "need": m["need"], "scatter_m": m["sure"]["scatter_m"], "points": m["sure"]["points"],
            "what": "One cell per landing date for a year from the planned date, with the same three-state check as the "
                    "card: yes only when every touchdown point, the coarser grid and the finer near-field sampling agree."}


@app.post("/api/year-ribbon")
def api_year(req: YearRequest):
    """The card's verdict for every landing date of a year from the planned date."""
    _parse_or_422(req.landing, "landing")
    return run(_guard, _year, req.model_dump_json())


def _stored_mast_refusal(req) -> Optional[dict]:
    """The scatter check and the shadow-site list read skylines stored for one observer height; another height is
    not answered with them (pass 3, review bug 8)."""
    meta = (scatterfield.load() or {}).get("meta") or (field.load() or {}).get("meta") or {}
    stored = meta.get("mast_m")
    if stored is not None and abs(req.mast_m - float(stored)) > 1e-6:
        return {"available": False, "stored_mast_m": float(stored), "asked_mast_m": req.mast_m,
                "reason": f"the scatter check is stored for an observer {float(stored):g} m above ground only, so it is not "
                          f"available for {req.mast_m:g} m (choose {float(stored):g} m to see it)"}
    return None


def _finer_map_dates(req) -> Optional[dict]:
    """The 20 m re-check for 14 map dates (scripts/finer_map_dates.py, rule R6), under the page's default need and
    rules with the station rule on; None for anything else."""
    path = os.path.join(field.FIELD_DIR, "..", "validation", "finer_map_dates.json")
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return None
    sc = d.get("scenario", {})
    same = (req.n_dates == sc.get("n_dates") and req.need_sun_h == sc.get("need_sun_h") and req.need_earth_h == sc.get("need_earth_h")
            and req.window_days == sc.get("window_days") and req.sun_at_touchdown and req.earth_at_touchdown and req.earth_stations
            and req.mask_deg == 0 and req.earth_margin_deg == 0 and req.min_sun_fraction == 0.5 and req.mast_m == 2.0
            and req.min_sun_el <= -90 and req.min_earth_el <= -90 and req.terrain)
    if not same or demstore.status().get("label") != d.get("used_grid"):
        return None
    row = next((x for x in d.get("dates", []) if req.start[:10] == x["start"][:10] and req.start[11:13] in ("", "00")), None)
    if row is None:
        return None
    return {"points_done": row["points"], "points_total": row["points"], "share_done": 1.0, "agree": row["agree"],
            "disagree": row["points"] - row["agree"], "agree_share": row["agree_share"], "equal_margins": row["equal_margins"],
            "complete": True, "made_utc": d["made_utc"], "fine_grid": d["fine_grid"], "earth_rule": sc.get("earth_rule"),
            "dates_checked": [x["start"][:10] for x in d["dates"]],
            "cells": {k: [v[1], bool(v[2])] for k, v in row["cells"].items()}}


def _finer_map(req) -> Optional[dict]:
    """The off-line re-check of the coloured map points on the 20 m grid, for the scenarios it was made for
    (scripts/finer_map_dates.py for 14 dates; scripts/finer_map_check.py for the default date); None for any other
    request, so that no other map is marked."""
    fd = _finer_map_dates(req)
    if fd is not None:
        return fd
    path = os.path.join(field.FIELD_DIR, "..", "validation", "finer_map_check.json")
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return None
    sc = d.get("scenario", {})
    same = (req.start.startswith(sc.get("start", "")[:10]) and req.start[11:13] in ("", "00") and req.n_dates == sc.get("n_dates")
            and req.need_sun_h == sc.get("need_sun_h") and req.need_earth_h == sc.get("need_earth_h")
            and req.window_days == sc.get("window_days") and req.sun_at_touchdown and req.earth_at_touchdown
            and req.mask_deg == 0 and req.earth_margin_deg == 0 and req.min_sun_fraction == 0.5 and req.mast_m == 2.0
            and req.min_sun_el <= -90 and req.min_earth_el <= -90 and req.terrain)
    if not same or demstore.status().get("label") != d.get("used_grid"):
        return None
    rows = d.get("rows", [])
    return {"points_done": d["points_done"], "points_total": d["points_total"], "share_done": d["share_done"],
            "agree": d["agree"], "disagree": d["disagree"], "agree_share": d["agree_share"],
            "equal_margins": d["equal_margins"], "complete": d["complete"], "made_utc": d["made_utc"],
            "fine_grid": d["fine_grid"], "earth_rule": sc.get("earth_rule"),
            "cells": {str(r[0]): [r[2], bool(r[3])] for r in rows}}


@app.post("/api/finer-map")
def api_finer_map(req: SlipMapRequest):
    """The 20 m mark for any map date and rule, worked out on request from the stored 20 m skylines (deep pass)."""
    _parse_or_422(req.start, "start")
    if field.load() is None:
        return {"available": False, "reason": "the skyline field has not been built on this installation"}
    refusal = _stored_mast_refusal(req)
    if refusal:
        return refusal
    if not finer20.available():
        return {"available": False, "reason": "the 20 m skylines are not installed (scripts/fetch_ldem20_tiles.py, scripts/finer_map_store.py)"}
    r = run(_guard, finer20.cells, req.start, req.n_dates, req.window_days, req.criteria(), req.mask_deg, req.need_sun_h,
            req.need_earth_h, req.sun_at_touchdown, req.earth_at_touchdown)
    if not r:
        return {"available": False, "reason": "the scatter-checked map is not available for this request"}
    return {"available": True, **r}


@app.post("/api/robust-map")
def api_robust_map(req: SlipMapRequest):
    """The slip-margin map re-checked at 13 touchdown points per coloured map point."""
    _parse_or_422(req.start, "start")
    if field.load() is None:
        return {"available": False, "reason": "the skyline field has not been built on this installation "
                                              "(run scripts/build_field.py)"}
    refusal = _stored_mast_refusal(req)
    if refusal:
        return refusal
    r = run(_guard, scatterfield.robust_margin, req.start, req.n_dates, req.window_days, req.criteria(), req.mask_deg,
            req.need_sun_h, req.need_earth_h, req.sun_at_touchdown, req.earth_at_touchdown)
    if not r.get("available"):
        return r
    meta = field.load()["meta"]
    out = {k: r[k] for k in ("available", "members", "scatter_m", "dates", "start_utc", "window_hours", "counts", "stored", "what")}
    out.update({"n": meta["n"], "half_km": meta["half_km"], "step_m": meta["step_m"], "mast_m": meta["mast_m"],
                "dem_label": meta["dem_label"],
                "need": {"sunlit_h": req.need_sun_h, "earth_h": req.need_earth_h, "window_days": req.window_days},
                "codes": {"-1": "the planned date does not meet the need at the map point",
                          "-2": "passes at the map point, scatter skylines not stored: not re-checked",
                          "-3": "passes at the map point, but not at all 13 touchdown points: the margin is lost"},
                "layers": {"robust": _ints(r["robust"]), "single": _ints(r["single"]), "points_passing": _ints(r["points_passing"])}})
    fm = _finer_map(req)
    if fm is not None:
        out["finer"] = fm
    return out


@app.post("/api/shadow-sites")
def api_shadow_sites(req: SlipMapRequest):
    """Map points that survive a slip at all 13 touchdown points and have permanent shadow within reach."""
    _parse_or_422(req.start, "start")
    if field.load() is None or shadowsites.load() is None:
        return {"available": False, "reason": "the skyline field or the permanent-shadow mask has not been built on this "
                                              "installation (scripts/build_field.py, scripts/prepare_psr.py)"}
    refusal = _stored_mast_refusal(req)
    if refusal:
        return refusal

    def work():
        r = _guard(scatterfield.robust_margin, req.start, req.n_dates, req.window_days, req.criteria(), req.mask_deg,
                   req.need_sun_h, req.need_earth_h, req.sun_at_touchdown, req.earth_at_touchdown)
        if not r or not r.get("available"):
            return {"available": False, "reason": (r or {}).get("reason", "the scatter-checked map is not available")}
        out = shadowsites.shadow_sites(r["robust"], r["single"])
        out.update({"start_utc": r["start_utc"], "dates": r["dates"], "members": r["members"], "scatter_m": r["scatter_m"]})
        return out
    out = run(work)
    if out.get("available"):
        meta = field.load()["meta"]
        out.update({"n": meta["n"], "half_km": meta["half_km"], "step_m": meta["step_m"],
                    "need": {"sunlit_h": req.need_sun_h, "earth_h": req.need_earth_h, "window_days": req.window_days}})
        fm = _finer_map(req)                 # the off-line 20 m re-check, for its own scenario only
        if fm is not None:
            for row in out["rows"] + out["on_shadow_itself"]:
                cell = fm["cells"].get(str(row["map_index"]))
                row["margin_20m"] = None if cell is None else cell[0]
            out["finer"] = {k: fm[k] for k in ("agree_share", "points_done", "complete", "fine_grid")}
    return out


class RobustSitesRequest(SlipMapRequest):
    scatter_m: float = Field(default=100.0, ge=0, le=500)
    candidates: int = Field(default=12, ge=1, le=20)


@app.post("/api/robust-sites")
def api_robust_sites(req: RobustSitesRequest):
    """The best points of the slip-margin map, re-checked with the landing scatter and the other grid."""
    _parse_or_422(req.start, "start")
    fld = field.load()
    if fld is None:
        return {"available": False, "reason": "the skyline field has not been built on this installation "
                                              "(run scripts/build_field.py)"}
    meta = fld["meta"]
    dem = demstore.get_dem()
    def work():
        pd = _guard(field.per_date, req.start, req.n_dates, 24, req.window_days, req.criteria(), req.mask_deg)
        st = field.statistics(pd, req.need_sun_h, req.need_earth_h, req.sun_at_touchdown, req.earth_at_touchdown)
        return pd, st, _guard(robust_sites, fld, st["margin"], st["good"], req.start, req.need_sun_h,
                              req.need_earth_h, req.window_days, req.criteria(), req.mask_deg, meta["mast_m"],
                              req.scatter_m, req.n_dates, req.sun_at_touchdown, req.earth_at_touchdown, req.candidates)
    pd, st, out = run_big(work)
    out.update({"available": True, "start_utc": pd["start_utc"], "dates": st["dates"], "mast_m": meta["mast_m"],
                "map_step_m": meta["step_m"], "map_half_km": meta["half_km"],
                "need": {"sunlit_h": req.need_sun_h, "earth_h": req.need_earth_h, "window_days": req.window_days},
                "notes": ([] if dem is not None and meta.get("dem_fingerprint") == getattr(dem, "fingerprint", None) else
                          ["the map skylines were built from " + meta["dem_label"].split(";")[0]
                           + ", which is not the terrain stack this installation re-checks the sites with"])})
    return out


@app.get("/api/replays")
def api_replays():
    """Real landings offered as worked examples for the mission card."""
    return {"note": replay.NOTE, "missions": replay.MISSIONS}


def _ints(a) -> list:
    return [int(v) for v in np.asarray(a).ravel()]


@app.post("/api/slipmap")
def api_slipmap(req: SlipMapRequest):
    """Per-point slip statistics for the grid of pre-computed skylines around the south pole."""
    _parse_or_422(req.start, "start")
    fld = field.load()
    if fld is None:
        return {"available": False, "reason": "the skyline field has not been built on this installation "
                                              "(run scripts/build_field.py)"}
    dem = demstore.get_dem()
    meta = fld["meta"]
    def work():
        pd = _guard(field.per_date, req.start, req.n_dates, 24, req.window_days, req.criteria(), req.mask_deg)
        return pd, field.statistics(pd, req.need_sun_h, req.need_earth_h, req.sun_at_touchdown, req.earth_at_touchdown)
    pd, st = run(work)
    notes = []
    if abs(req.mast_m - meta["mast_m"]) > 1e-6:
        notes.append(f"the map is for an observer {meta['mast_m']:g} m above ground, whatever height is chosen elsewhere")
    if dem is None or meta.get("dem_fingerprint") != getattr(dem, "fingerprint", None):
        notes.append("the map skylines were built from " + meta["dem_label"].split(";")[0]
                     + ", which is not the terrain stack this installation computes sites with")
    return {
        "available": True, "n": meta["n"], "half_km": meta["half_km"], "step_m": meta["step_m"],
        "mast_m": meta["mast_m"], "dem_label": meta["dem_label"], "start_utc": pd["start_utc"],
        "dates": st["dates"], "window_hours": pd["window_hours"], "seconds": pd["seconds"],
        "need": {"sunlit_h": req.need_sun_h, "earth_h": req.need_earth_h, "sun_at_touchdown": req.sun_at_touchdown,
                 "earth_at_touchdown": req.earth_at_touchdown},
        "criteria": req.criteria().describe(), "notes": notes,
        "what": "each value is one point, sampled every %g m; row 0 is the top of the map (longitude 0)" % meta["step_m"],
        "layers": {k: _ints(st[k]) for k in ("margin", "good", "worst_sun", "median_sun", "worst_total", "median_total")},
    }


@app.post("/api/pairs")
def api_pairs(req: PairsRequest):
    """Two sites as one power system: share of time at least one is sunlit, and the longest time both are dark."""
    _parse_or_422(req.start, "start")
    def work():
        ss = [_resolve(r, req)[0] for r in req.sites]
        return ss, [_guard(any_light_flags, s, req.start, req.days, 60) for s in ss]
    sites, flags = run(work)
    single = [{"name": s.name, "any_light_pct": round(float(f.mean()) * 100, 2), "longest_dark_h": float(longest_run(~f)),
               "horizon": s.horizon.describe()} for s, f in zip(sites, flags)]
    pairs = []
    for i in range(len(sites)):
        for j in range(i + 1, len(sites)):
            either = flags[i] | flags[j]
            pairs.append({"a": i, "b": j, "either_lit_pct": round(float(either.mean()) * 100, 2),
                          "both_lit_pct": round(float((flags[i] & flags[j]).mean()) * 100, 2),
                          "longest_joint_dark_h": float(longest_run(~either)),
                          "distance_km": round(_distance_km(sites[i], sites[j]), 2)})
    return {"start": req.start, "days": float(len(flags[0])) / 24.0, "rule": "any part of the solar disc above the skyline, hourly samples",
            "sites": single, "pairs": pairs,
            "caveat": "Model output with no published figure to check it against. Longest darkness on ridge crests "
                      "moves by tens of hours for a 20 to 40 m shift at 80 m/px; treat it as indicative."}


def _distance_km(a: Site, b: Site) -> float:
    la1, lo1, la2, lo2 = map(np.deg2rad, (a.lat, a.lon, b.lat, b.lon))
    c = np.sin(la1) * np.sin(la2) + np.cos(la1) * np.cos(la2) * np.cos(lo1 - lo2)
    return float(np.arccos(np.clip(c, -1.0, 1.0)) * 1737.4)


@app.get("/api/horizon")
def api_horizon(site: Optional[str] = None, lat: Optional[float] = Q_LAT, lon: Optional[float] = Q_LON,
                mast_m: float = Query(2.0, ge=0, le=500)):
    """The 360-degree terrain horizon profile of a site."""
    def work():
        st, _ = _resolve(SiteRef(id=site, lat=lat, lon=lon), _options(mast_m=mast_m))
        return st, terrain_profile(st.lat, st.lon, mast_m)
    s, prof = run(work)
    if prof is None:
        t = demstore.status()
        raise HTTPException(404, "no terrain data covers this site" if t["available"] else "no terrain data installed")
    out = prof.to_json()
    out["site"] = {"name": s.name, "lat": s.lat, "lon": s.lon}
    out["label"] = s.horizon.describe()["label"]
    return out


BAND_KEYS = ("any_light_pct", "lit_pct", "mean_disc_fraction_pct", "longest_dark_h", "longest_light_h",
             "earth_visible_pct", "longest_earth_outage_h")
LADDER_KEYS = BAND_KEYS + ("usable_pct",)


@lru_cache(maxsize=48)
def _stats(site_key: str, start: str, days: float, step_minutes: int, opt_json: str,
           scatter_m: float = 0.0, ladder: bool = False) -> dict:
    opt = Options(**json.loads(opt_json))
    ref = SiteRef(**json.loads(site_key))
    s, twin = _resolve(ref, opt)
    crit = opt.criteria()
    primary = span_stats(s, start, days, step_minutes, crit)
    out = {"site": primary["site"], "start_utc": primary["start_utc"], "days": primary["days"],
           "step_minutes": step_minutes, "criteria": crit.describe(),
           "terrain": primary if s.horizon.is_terrain else None,
           "smooth": span_stats(twin, start, days, step_minutes, crit) if twin is not None else primary}
    short = primary["samples"] <= 20_000        # the extras are for year-scale spans only
    if s.horizon.is_terrain and scatter_m > 0 and short:
        ens = ensemble(s, opt.mask_deg, opt.mast_m, scatter_m)
        pts = [primary] + [span_stats(m, start, days, step_minutes, crit) for m in ens["scatter"]]
        band = {"points": len(pts), "scatter_m": ens["scatter_m"], "scatter_requested_m": scatter_m}
        for k in BAND_KEYS:
            vals = [p[k] for p in pts]
            band[k] = [min(vals), max(vals)]
        for name in ("coarse", "near"):
            if ens[name] is not None:
                st = span_stats(ens[name], start, days, step_minutes, crit)
                band[name] = {k: st[k] for k in BAND_KEYS}
                band[name]["label"] = st["horizon"].get("dem_label", "")
        out["band"] = band
    if s.horizon.is_terrain and ladder and short:
        steps = [{"label": primary["horizon"]["dem_label"].split(";")[0], "resolution_m": primary["horizon"]["resolution_m"],
                  "model": "terrain", **{k: primary[k] for k in LADDER_KEYS}}]
        for k in range(1, 5):
            hz = horizon_for(s.lat, s.lon, opt.mask_deg, opt.mast_m, True, variant=f"drop{k}")
            if not hz.is_terrain:
                break
            st = span_stats(Site(s.name, s.lat, s.lon, horizon=hz), start, days, step_minutes, crit)
            steps.append({"label": hz.meta["dem_label"].split(";")[0], "resolution_m": hz.meta["resolution_m"],
                          "model": "terrain", **{key: st[key] for key in LADDER_KEYS}})
        steps.append({"label": "smooth sphere", "resolution_m": None, "model": "smooth sphere",
                      **{k: out["smooth"][k] for k in LADDER_KEYS}})
        out["ladder"] = steps
    return out


@app.get("/api/stats")
def api_stats(start: str, site: Optional[str] = None, lat: Optional[float] = Q_LAT, lon: Optional[float] = Q_LON,
              name: Optional[str] = None, days: float = Query(365.0, gt=1, le=7310),
              step_minutes: int = Query(60, ge=10, le=720), mask_deg: float = Query(0.0, ge=0, le=30),
              min_sun_el: float = Query(-90.0, ge=-90, le=90), min_earth_el: float = Query(-90.0, ge=-90, le=90),
              terrain: bool = True, mast_m: float = Query(2.0, ge=0, le=500),
              min_sun_fraction: float = Query(0.5, ge=0, le=1), earth_margin_deg: float = Query(0.0, ge=0, le=20),
              scatter_m: float = Query(0.0, ge=0, le=500), ladder: bool = False):
    """Illumination and Earth-visibility statistics over a long span, terrain and smooth sphere side by side.

    ``scatter_m`` adds the range over the landing scatter and the coarse-grid and near-field variants;
    ``ladder`` adds the same site on every coarser grid installed (both for spans up to 20,000 samples).
    """
    opt = _options(mask_deg, min_sun_el, min_earth_el, terrain, mast_m, min_sun_fraction, earth_margin_deg)
    _parse_or_422(start, "start")
    ref = SiteRef(id=site, name=name, lat=lat, lon=lon)
    out = run(_guard, _stats, ref.model_dump_json(), start, float(days), int(step_minutes), opt.model_dump_json(),
              float(scatter_m), bool(ladder))
    if mast_m < 1.0 and out.get("terrain"):
        out = dict(out)
        out["warning"] = ("Observer below 1 m: on crests the result depends on how the nearest ground is sampled "
                          "(first ray sample one grid spacing out). Ground-level crest values are not converged; "
                          "see LIMITATIONS.md.")
    return out


# ------------------------------------------------------------------ exports

def _csv_response(name: str, header_lines: list[str], columns: list[str], rows: list[list]) -> Response:
    buf = io.StringIO()
    for line in header_lines:
        buf.write("# " + line + "\n")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(columns)
    w.writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _provenance_lines(crit: dict) -> list[str]:
    t = demstore.status()
    lines = [
        "Slipday export, generated " + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Sun/Earth directions: computed from JPL DE421 (positions and lunar librations), Mean Earth frame, "
        "light-time and aberration applied",
        "Rule for Sun up: " + crit["sun_rule"],
        "Rule for Earth up: " + crit["earth_rule"],
    ]
    if t["available"]:
        for d in t["dems"]:
            lines.append(("SYNTHETIC TEST DEM (not lunar data): " if d["synthetic"] else "Terrain data: ")
                         + f"{d['label']} [{d['product']}] {d['provenance']}".strip())
    else:
        lines.append("Terrain data: none installed; every row is the smooth-sphere model")
    lines.append("Each row says which horizon model it used in the horizon_model and horizon_label columns")
    return lines


@app.post("/api/export/slipgrid.csv")
def export_slipgrid(req: SlipRequest):
    g = run(_slipgrid, req)
    cols = ["site", "lat", "lon", "horizon_model", "horizon_label", "landing_utc", "window_hours",
            "unbroken_usable_hours_from_touchdown", "total_usable_hours", "sunlit_hours", "earth_contact_hours",
            "sun_elevation_at_landing_deg", "earth_elevation_at_landing_deg",
            "scatter_points", "scatter_radius_m", "usable_hours_min_in_scatter", "usable_hours_max_in_scatter",
            "sunlit_hours_min_in_scatter", "sunlit_hours_max_in_scatter", "usable_hours_on_coarser_grid"]
    rows = []
    for row in g["rows"]:
        variants = [(row["horizon"], row, row.get("band"))]
        if "smooth" in row:
            variants.append((row["smooth"]["horizon"], row["smooth"], None))
        for hz, data, bd in variants:
            for i, d in enumerate(g["dates"]):
                extra = ["", "", "", "", "", "", ""]
                if bd:
                    extra = [bd["points"], bd["scatter_m"], bd["total"]["min"][i], bd["total"]["max"][i],
                             bd["sunlit"]["min"][i], bd["sunlit"]["max"][i], (bd["total"].get("coarse") or [""] * len(g["dates"]))[i]]
                rows.append([row["site"]["name"], row["site"]["lat"], row["site"]["lon"], hz["model"], hz["label"],
                             d, g["window_hours"], data["continuous"][i], data["total"][i], data["sunlit"][i],
                             data["earth"][i], row["sun_el_at_landing"][i], row["earth_el_at_landing"][i]] + extra)
    head = _provenance_lines(g["criteria"]) + [
        f"Slip grid: {len(g['dates'])} landing dates from {g['start_utc']}, hours counted over the "
        f"{g['window_days']:g} days after each landing (hourly samples)"]
    return _csv_response("slipday_slip_grid.csv", head, cols, rows)


@app.post("/api/export/compare.csv")
def export_compare(req: CompareRequest):
    c = run(_compare, req)
    cols = ["site", "lat", "lon", "horizon_model", "horizon_label", "at_utc", "sun_elevation_deg", "sun_azimuth_deg",
            "horizon_at_sun_azimuth_deg", "sun_disc_fraction_visible", "sun_up", "earth_elevation_deg",
            "earth_azimuth_deg", "horizon_at_earth_azimuth_deg", "earth_up", "next_sunset_utc", "next_sunrise_utc",
            "next_earthset_utc", "next_earthrise_utc", "window_days", "sunlit_hours", "sunlit_share",
            "mean_sun_disc_fraction", "earth_visible_share", "usable_hours", "longest_dark_hours",
            "longest_light_hours", "longest_earth_outage_hours"]
    rows = []
    for entry in c["sites"]:
        variants = [entry["metrics"]]
        if "smooth" in entry:
            variants.append(entry["smooth"]["metrics"])
        for m in variants:
            n, w = m["now"], m["window"]
            ev = lambda k: (m[k] or {}).get("utc", "")  # noqa: E731
            rows.append([m["site"]["name"], m["site"]["lat"], m["site"]["lon"], m["horizon"]["model"],
                         m["horizon"]["label"], m["utc"], n["sun_el"], n["sun_az"], n["sun_horizon_el"],
                         n["sun_disc_fraction"], int(n["sun_up"]), n["earth_el"], n["earth_az"],
                         n["earth_horizon_el"], int(n["earth_up"]), ev("next_sunset"), ev("next_sunrise"),
                         ev("next_earthset"), ev("next_earthrise"), w["days"], w["sunlit_hours"], w["sunlit_share"],
                         w["mean_sun_disc_fraction"], w["earth_visible_share"], w["usable_hours"],
                         w["longest_dark_hours"], w["longest_light_hours"], w["longest_earth_outage_hours"]])
    head = _provenance_lines(c["criteria"]) + [
        "Comparison at " + c["at"] + "; window figures cover the following 29.5 days (hourly samples); "
        "next events are searched 200 days ahead"]
    return _csv_response("slipday_comparison.csv", head, cols, rows)


@app.post("/api/export/series.csv")
def export_series(req: CompareRequest):
    c = run(_compare, req)
    cols = ["site", "utc", "sun_elevation_deg", "sun_azimuth_deg", "earth_elevation_deg", "earth_azimuth_deg",
            "horizon_model", "horizon_at_sun_azimuth_deg", "horizon_at_earth_azimuth_deg",
            "sun_disc_fraction_visible", "sun_up", "earth_up", "sun_up_smooth_sphere", "earth_up_smooth_sphere"]
    rows = []
    for entry in c["sites"]:
        s = entry["series"]
        sm = entry.get("smooth")
        for i in range(s["count"]):
            t = datetime.fromtimestamp(s["start_unix"] + i * s["step_minutes"] * 60, tz=timezone.utc)
            rows.append([s["site"]["name"], t.strftime("%Y-%m-%dT%H:%M:%SZ"), s["sun_el"][i], s["sun_az"][i],
                         s["earth_el"][i], s["earth_az"][i], s["horizon"]["model"], s["sun_horizon"][i],
                         s["earth_horizon"][i], s["sun_frac"][i], s["lit"][i], s["earth_vis"][i],
                         sm["lit"][i] if sm else s["lit"][i], sm["earth_vis"][i] if sm else s["earth_vis"][i]])
    return _csv_response("slipday_series.csv", _provenance_lines(c["criteria"]), cols, rows)


# --------------------------------------------------------------- map, checks

@app.get("/api/map")
def api_map(half_km: Optional[float] = Query(None, gt=1, le=1000)):
    got = _guard(moonmap.get, None, 760, half_km)
    if got is None:
        return {"available": False, "reason": "no terrain data installed"}
    meta = dict(got[1])
    q = f"&half_km={half_km:g}" if half_km else ""
    meta["image"] = "/api/map/image" + ("?" + q[1:] if q else "")
    layers = []
    for name in ((demstore.config() or {}).get("layers", {})):
        lay = moonmap.get_layer(name, None, 760, half_km)
        if lay is not None:
            layers.append({"id": name, "image": f"/api/map/image?layer={name}{q}", **lay[1]})
    meta["layers"] = layers
    fld = field.load()
    meta["slip_field"] = ({"available": True, **{k: fld["meta"][k] for k in ("n", "half_km", "step_m", "mast_m", "dem_label")}}
                          if fld is not None else {"available": False})
    meta["scatter_field"] = {"available": bool(fld is not None and scatterfield.load() is not None)}
    psr = moonmap.permanent_shadow_overlay(None, 760, half_km)
    meta["permanent_shadow"] = ({"available": True, "image": "/api/map/shadow" + ("?" + q[1:] if q else ""), **psr[1]}
                                if psr is not None else {"available": False})
    return meta


@app.get("/api/map/shadow")
def api_map_shadow(half_km: Optional[float] = Query(None, gt=1, le=1000)):
    """Transparent overlay: map cells where the LOLA team's average-illumination map is zero (permanent shadow)."""
    got = _guard(moonmap.permanent_shadow_overlay, None, 760, half_km)
    if got is None:
        raise HTTPException(404, "the average-illumination layer is not installed")
    return Response(got[0], media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@app.get("/api/map/image")
def api_map_image(layer: Optional[str] = None, half_km: Optional[float] = Query(None, gt=1, le=1000)):
    got = _guard(moonmap.get_layer, layer, None, 760, half_km) if layer else _guard(moonmap.get, None, 760, half_km)
    if got is None:
        raise HTTPException(404, "no such map layer" if layer else "no terrain data installed")
    return Response(got[0], media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})


@app.get("/api/hindcast")
def api_hindcast():
    return hindcast()


@app.get("/api/terrain/validation")
def api_terrain_validation():
    """Terrain results against published references, as written by scripts/validate_terrain.py."""
    if not os.path.exists(VALIDATION):
        return {"available": False,
                "reason": "scripts/validate_terrain.py has not been run on this installation"}
    with open(VALIDATION) as fh:
        out = json.load(fh)
    out["available"] = True
    # the stored figures belong to the grids they were run on; say so when this installation differs
    ran_on = (out.get("dems") or [{}])[0].get("label")
    now = demstore.status()
    here = now["dems"][0]["label"] if now["available"] and now["dems"] else None
    out["ran_on"] = ran_on
    out["installed"] = here
    out["same_grid"] = bool(ran_on and here and ran_on == here)
    return out


@lru_cache(maxsize=1)
def _fixture_validation() -> dict:
    import re
    results = []
    for path in sorted(glob.glob(os.path.join(FIXTURES, "horizons_*.csv"))):
        with open(path) as fh:
            text = fh.read()
        meta = {}
        for line in text.splitlines():
            if line.startswith("# Target:"):
                m = re.search(r"Target: (\w+).*E-lon ([-\d.]+) deg, lat ([-\d.]+) deg", line)
                meta = {"target": m.group(1).lower(), "lon": float(m.group(2)), "lat": float(m.group(3))}
        rows = horizons.parse_table(text)
        site = Site(os.path.basename(path), meta["lat"], meta["lon"])
        for orientation in ("de421", "iau2009"):
            res = horizons.compare_rows(site, meta["target"], rows, orientation)
            res.update({"fixture": os.path.basename(path), "lat": meta["lat"], "lon": meta["lon"]})
            results.append(res)
    best = [r for r in results if r["orientation"] == "de421"]
    return {
        "reference": "JPL Horizons observer tables saved under fixtures/ (airless apparent azimuth/elevation)",
        "what_it_checks": "direction of the Sun and Earth over a smooth sphere; it says nothing about terrain",
        "rows": sum(r["rows"] for r in best),
        "max_abs_el_deg": max((r["max_abs_el_deg"] for r in best), default=None),
        "max_abs_az_deg": max((r["max_abs_az_deg"] for r in best), default=None),
        "results": results,
    }


@app.get("/api/validation")
def api_validation():
    """Accuracy of the Sun/Earth directions against the Horizons tables shipped with the repository."""
    return _fixture_validation()


@app.get("/api/horizons/check")
def api_horizons_check(start: str, stop: str, site: Optional[str] = None,
                       lat: Optional[float] = Q_LAT, lon: Optional[float] = Q_LON, step: str = "6h"):
    """Live cross-check against the JPL Horizons API (needs SLIPDAY_HORIZONS=1 and internet)."""
    if not horizons.enabled():
        raise HTTPException(503, "Horizons cross-check is disabled; start the server with SLIPDAY_HORIZONS=1")
    t0, t1 = _parse_or_422(start, "start"), _parse_or_422(stop, "stop")
    if t1 <= t0:
        raise HTTPException(422, "stop must be later than start")
    if (t1 - t0).days > 90:
        raise HTTPException(422, "keep the cross-check span to 90 days or less")
    s, _ = _resolve(SiteRef(id=site, lat=lat, lon=lon), _options(terrain=False))
    try:
        return horizons.crosscheck(s, start, stop, step)
    except Exception as exc:  # network errors, proxy refusals, unexpected payloads
        raise HTTPException(502, f"Horizons request failed: {exc}")


for _extra in ("why", "scatterfield", "view3d", "contrast", "addons.atlas", "addons.safety", "addons.relay", "addons.safetouch"):
    if importlib.util.find_spec("slipday." + _extra) is not None:
        _mod = importlib.import_module("slipday." + _extra)
        if hasattr(_mod, "router"):
            app.include_router(_mod.router)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(os.path.join(STATIC, "favicon.svg"), media_type="image/svg+xml")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC), name="static")
