"""Add-on: one-page landing-site brief for a review board (`brief-1`).

GET /api/addons/brief?site=..&date=..&slip=..  assembles, from the entry's own endpoints (called in-process through
the ASGI app, so every number is exactly what the page's endpoints answer), one JSON document:
question, inputs, verdict (power and contact / ground), slip margin, next launch windows, hours against the need,
longest night, slope and safe-touchdown chance per lander class, descent lighting, relay contact, alternatives,
terrain grid, validation checks, labelled assumptions and data sources.  No new computation is done here.
"""
from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

METHOD_VERSION = "brief-1"
OPENING = {"site": "robust_pick", "date": "2026-11-18", "slip": 3}
FOLLOW_DAYS_MIN = 15          # slip days the mission card follows (at least; more when the asked slip is longer)

router = APIRouter(tags=["add-on: review-board brief"])

_CLIENT = None
_LOCK = threading.Lock()
_CACHE: dict = {}


def _client():
    """An in-process client on the entry's own app: the brief reads the same answers a browser would."""
    global _CLIENT
    with _LOCK:
        if _CLIENT is None:
            from fastapi.testclient import TestClient
            from ..api import app
            _CLIENT = TestClient(app, raise_server_exceptions=False)
        return _CLIENT


def _call(method: str, path: str, *, params: Optional[dict] = None, body: Optional[dict] = None) -> dict:
    """One endpoint answer as a dict; a failure is reported in the dict instead of failing the whole brief."""
    try:
        r = _client().request(method, path, params=params, json=body)
    except Exception as exc:                       # pragma: no cover - transport failure
        return {"available": False, "reason": f"{path} could not be called: {exc}", "endpoint": path}
    try:
        data = r.json()
    except ValueError:
        data = {"detail": r.text[:300]}
    if r.status_code != 200:
        return {"available": False, "status": r.status_code, "endpoint": path,
                "reason": str(data.get("detail") if isinstance(data, dict) else data)}
    return data if isinstance(data, dict) else {"value": data}


def _iso(date: str) -> str:
    from ..ephem import parse_utc
    try:
        t = parse_utc(date)
    except (ValueError, TypeError):
        raise HTTPException(422, "date is not a date or time I can read (use e.g. 2026-11-18 or 2026-11-18T00:00:00Z)")
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _site_ref(site: Optional[str], lat: Optional[float], lon: Optional[float], name: str) -> dict:
    if site:
        return {"id": site}
    if lat is None or lon is None:
        raise HTTPException(422, "give a site id (site=...) or both lat and lon")
    return {"lat": lat, "lon": lon, "name": name or ""}


def _site_q(ref: dict, key: str = "id") -> dict:
    """The site as query parameters; the add-ons call the id parameter `id`, the relay calls it `site`."""
    if "id" in ref:
        return {key: ref["id"]}
    return {"lat": ref["lat"], "lon": ref["lon"], "name": ref.get("name", "")}


def _at(seq, i, default=None):
    try:
        return seq[i]
    except (IndexError, TypeError, KeyError):
        return default


# ---------------------------------------------------------------- sources and assumptions, gathered from the answers
URL_RE = re.compile(r"https?://[^\s\)\]\"'<>,;]+")


def _sources(parts: dict) -> list:
    """Every link found in the endpoint answers, with the words around it, de-duplicated by URL."""
    seen: dict = {}

    def label_of(d: dict, key: str, text: str) -> str:
        if key.endswith("_url") and isinstance(d.get(key[:-4]), str):
            return d[key[:-4]]
        for k in ("source", "figure", "product", "label", "name", "title"):
            v = d.get(k)
            if isinstance(v, str) and v and not URL_RE.fullmatch(v.strip()):
                return v
        stripped = URL_RE.sub("", text).strip(" :()-,.")
        return stripped or key

    def walk(o: Any, where: str):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str):
                    for u in URL_RE.findall(v):
                        u = u.rstrip(".")
                        if u not in seen:
                            seen[u] = {"label": label_of(o, k, v)[:240], "url": u, "found_in": where}
                else:
                    walk(v, where)
        elif isinstance(o, list):
            for v in o:
                walk(v, where)
    for where, data in parts.items():
        walk(data, where)
    fixed = [
        {"label": "JPL DE421 planetary and lunar ephemeris (Sun and Earth directions, lunar librations)",
         "url": "https://ssd.jpl.nasa.gov/planets/eph_export.html", "found_in": "health"},
        {"label": "JPL Horizons (reference tables used for the direction check)",
         "url": "https://ssd.jpl.nasa.gov/horizons/", "found_in": "validation"},
        {"label": "NASA GSFC Planetary Geodesy Data Archive: LOLA polar terrain grids",
         "url": "https://pgda.gsfc.nasa.gov/products/90", "found_in": "terrain/validation"},
    ]
    for f in fixed:
        if not any(u.startswith(f["url"]) for u in seen):
            seen[f["url"]] = f
    return list(seen.values())


def _assumptions(parts: dict) -> list:
    """Labelled assumptions: explicit lists from the add-ons, plus every sentence an endpoint marks ASSUMED or
    ILLUSTRATIVE.  Labels: assumed, illustrative, limit, rule."""
    out, seen = [], set()

    def add(label: str, text: str, where: str):
        t = " ".join(str(text).split())
        if not t or t in seen or any(t in o["text"] for o in out):
            return
        seen.add(t)
        out.append({"label": label, "text": t, "from": where})

    def kind(t: str) -> str:
        u = t.upper()
        return "illustrative" if "ILLUSTRATIVE" in u else "assumed" if "ASSUMED" in u or "ASSUME" in u else "limit"

    m = parts.get("mission") or {}
    crit = m.get("criteria") or {}
    for k in ("sun_rule", "earth_rule"):
        if crit.get(k):
            add("rule", f"{'Sunlit' if k == 'sun_rule' else 'Earth contact'} means {crit[k]}.", "mission")
    if (m.get("need") or {}).get("text"):
        add("assumed", "Mission need (default, change it on the main page): " + m["need"]["text"], "mission")
    if (m.get("sure") or {}).get("assumes"):
        add("assumed", m["sure"]["assumes"], "mission")
    for c in (parts.get("lander_classes") or {}).get("classes", []):
        if c.get("basis"):
            add("assumed", f"{c.get('label', c.get('id'))}: {c['basis']}", "lander-classes")
    if (parts.get("lander_classes") or {}).get("assumption"):
        add("assumed", parts["lander_classes"]["assumption"], "lander-classes")
    for t in (parts.get("lighting") or {}).get("assumptions", []):
        add(kind(t), t, "planner/lighting")
    rl = parts.get("relay") or {}
    if rl.get("label"):
        add("assumed", "Relay: " + rl["label"] + (f"; {rl['config_text']}" if rl.get("config_text") else ""), "relay")
    for src in ("safety", "safetouch"):
        for t in (parts.get(src) or {}).get("limits", []):
            add("limit", t, src)
    if (parts.get("windows") or {}).get("rule"):
        add("rule", parts["windows"]["rule"], "windows")
    if (parts.get("survival") or {}).get("rule"):
        add("rule", parts["survival"]["rule"], "survival")

    def walk(o: Any, where: str):
        if isinstance(o, dict):
            for v in o.values():
                walk(v, where)
        elif isinstance(o, list):
            for v in o:
                walk(v, where)
        elif isinstance(o, str) and ("ASSUMED" in o or "ILLUSTRATIVE" in o) and len(o) < 600:
            add(kind(o), o, where)
    for where, data in parts.items():
        if where not in ("terrain_validation",):
            walk(data, where)
    return out


# ---------------------------------------------------------------- the brief
def _word(v: Optional[str]) -> str:
    return {"yes": "Yes", "not sure": "Not sure", "no": "No", "flat": "Yes", "steep": "No"}.get(v or "", v or "unknown")


def build(ref: dict, landing: str, slip: int, alternatives: bool = True) -> dict:
    follow = max(FOLLOW_DAYS_MIN, slip)
    body = {"site": ref, "landing": landing, "slip_days": follow}
    parts: dict = {}
    parts["mission"] = mission = _call("POST", "/api/mission", body=body)
    if mission.get("available") is False and "verdict" not in mission:
        raise HTTPException(mission.get("status") or 422, mission.get("reason") or "the mission check failed")
    parts["windows"] = _call("POST", "/api/windows", body=body)
    parts["survival"] = _call("POST", "/api/survival", body=body)
    parts["lander_classes"] = _call("POST", "/api/lander-classes", body=body)
    parts["safety"] = _call("GET", "/api/addons/safety/site", params=_site_q(ref))
    parts["safetouch"] = _call("GET", "/api/addons/safetouch/site", params=_site_q(ref))
    parts["lighting"] = _call("GET", "/api/addons/planner/lighting",
                              params={**_site_q(ref), "landing": landing, "slip_days": slip})
    parts["joint"] = _call("GET", "/api/addons/planner/joint", params={**_site_q(ref), "landing": landing, "slip_days": slip})
    parts["relay"] = _call("GET", "/api/addons/relay/window", params={**_site_q(ref, "site"), "landing": landing})
    if alternatives:
        parts["alternatives"] = _call("GET", "/api/addons/planner/alternatives",
                                      params={**_site_q(ref), "landing": landing, "slip_days": slip})
    else:
        parts["alternatives"] = {"available": False, "reason": "left out of this request (alternatives=false)"}
    parts["validation"] = _call("GET", "/api/validation")
    parts["terrain_validation"] = _call("GET", "/api/terrain/validation")
    parts["health"] = _call("GET", "/api/health")

    site = mission.get("site") or {}
    days = mission.get("days") or []
    d0, ds = _at(days, 0, {}), _at(days, slip, {})
    need = mission.get("need") or {}
    margin = mission.get("slip_margin_days")
    verdict = mission.get("verdict")
    holds = verdict == "yes" and isinstance(margin, (int, float)) and margin >= slip
    sf, st = parts["safety"], parts["safetouch"]
    ground = sf.get("verdict") if sf.get("available") else None
    name = site.get("friendly_name") or site.get("name") or "the site"

    # power and contact
    power = {
        "verdict": verdict, "word": _word(verdict), "headline": mission.get("headline"),
        "sentences": mission.get("sentences", []),
        "holds_through_slip": holds,
        "at_slip": {"slip_days": slip, "landing_utc": ds.get("landing_utc"), "verdict": ds.get("verdict"),
                    "word": _word(ds.get("verdict")), "reasons": ds.get("reasons", [])},
        "how_sure": (mission.get("sure") or {}).get("text"),
        "finer_grid": (mission.get("finer_grid_check") or {}).get("short"),
    }
    groundv = {
        "verdict": ground, "word": _word(ground) if ground else "not checked",
        "headline": sf.get("headline") or sf.get("reason"),
        "limit_deg": sf.get("limit_deg"), "goal_deg": sf.get("goal_deg"),
    }
    overall = ("yes" if holds and ground == "flat" else
               "no" if verdict == "no" or ground == "steep" or (ds.get("verdict") == "no") else "not sure")

    # hours against the need
    hours = {
        "need_sunlit_h": need.get("sunlit_h"), "need_earth_h": need.get("earth_h"),
        "window_days": mission.get("window_days"),
        "planned": {"landing_utc": d0.get("landing_utc"), "sunlit_h": d0.get("sunlit_h"), "earth_h": d0.get("earth_h"),
                    "sunlit_range_h": d0.get("sunlit_range_h"), "earth_range_h": d0.get("earth_range_h"),
                    "usable_h": d0.get("usable_h")},
        "at_slip": {"landing_utc": ds.get("landing_utc"), "sunlit_h": ds.get("sunlit_h"), "earth_h": ds.get("earth_h"),
                    "sunlit_range_h": ds.get("sunlit_range_h"), "earth_range_h": ds.get("earth_range_h"),
                    "usable_h": ds.get("usable_h")},
        "by_day": [{"slip_days": d.get("slip_days"), "verdict": d.get("verdict"), "sunlit_h": d.get("sunlit_h"),
                    "earth_h": d.get("earth_h")} for d in days],
    }

    sv = parts["survival"]
    sd = sv.get("days") or []
    night = {
        "available": bool(sv.get("available")), "reason": sv.get("reason"),
        "planned_h": (_at(sd, 0) or {}).get("night_h"), "at_slip_h": (_at(sd, slip) or {}).get("night_h"),
        "planned_outage_h": (_at(sd, 0) or {}).get("outage_h"), "at_slip_outage_h": (_at(sd, slip) or {}).get("outage_h"),
        "worst_over_passing_days": sv.get("worst_over_passing_days"),
        "sentence": sv.get("night_sentence"), "outage_sentence": sv.get("outage_sentence"),
    }

    wrows = [{"k": r.get("k"), "landing_utc": r.get("landing_utc"), "verdict": r.get("verdict"), "word": _word(r.get("verdict")),
              "slip_margin_days": r.get("slip_margin_days"), "sunlit_h": r.get("sunlit_h"), "earth_h": r.get("earth_h"),
              "night_in_window_h": r.get("night_in_window_h"), "fails_on": r.get("fails_on", []),
              "reasons": r.get("reasons")} for r in (parts["windows"].get("rows") or [])]

    lc = parts["lander_classes"]
    jt = parts["joint"]
    st_by = {c.get("id"): c for c in (st.get("classes") or [])}
    jt_by = {c.get("id"): c for c in (jt.get("classes") or [])}
    classes = []
    for c in lc.get("classes") or []:
        s2, j2 = st_by.get(c.get("id"), {}), jt_by.get(c.get("id"), {})
        classes.append({
            "id": c.get("id"), "label": c.get("label"), "within_99_pct_m": c.get("within_99_pct_m"),
            "assumed": c.get("assumed"),
            "plan_holds_planned_pct": c.get("planned_pct"), "plan_holds_at_slip_pct": _at(c.get("chance_pct"), slip),
            "margin_90_days": c.get("margin_90_days"),
            "flat_8deg_pct": s2.get("p8"), "flat_8deg_range": s2.get("p8_range"), "flat_5deg_pct": s2.get("p5"),
            "both_at_slip_pct": j2.get("joint_pct"), "both_range": j2.get("joint_range"),
        })
    slope = {
        "available": bool(sf.get("available")), "reason": sf.get("reason"),
        "steepest": sf.get("steepest"), "points_passing": sf.get("points_passing"), "points_total": sf.get("points_total"),
        "grid_words": sf.get("grid_words"), "limit_deg": sf.get("limit_deg"),
        "safetouch_available": bool(st.get("available")), "safetouch_reason": st.get("reason"),
        "safetouch_grid": (st.get("grid") or {}).get("label"),
        "joint_available": bool(jt.get("available")), "joint_reason": jt.get("reason"),
        "classes": classes, "threshold_pct": lc.get("threshold_pct"),
    }

    lt = parts["lighting"]
    lighting = {
        "available": bool(lt.get("available")), "reason": lt.get("reason"),
        "touchdown_utc": lt.get("touchdown_utc"), "sun": lt.get("sun"), "approach": lt.get("approach"),
        "camera": lt.get("camera"), "text": lt.get("text"),
        "shadow": [{"label": c.get("label"), "in_shadow_pct": c.get("in_shadow_pct"), "grid_m": c.get("grid_m")}
                   for c in ((lt.get("shadow") or {}).get("classes") or [])],
    }

    rl = parts["relay"]
    relay = {
        "available": bool(rl.get("available")), "reason": rl.get("reason"),
        "label": rl.get("label"), "config_text": rl.get("config_text"), "window_hours": rl.get("window_hours"),
        "hours": rl.get("hours"), "margin_earth_days": (rl.get("slip") or {}).get("margin_earth_days"),
        "margin_either_days": (rl.get("slip") or {}).get("margin_either_days"),
        "either_ends_because": (rl.get("slip") or {}).get("either_ends_because"),
        "one_relay_hours": (rl.get("one_relay") or {}).get("hours"),
    }

    al = parts["alternatives"]
    alts = {
        "available": "rows" in al, "reason": al.get("reason"), "touchdown_utc": al.get("touchdown_utc"),
        "sites_checked": al.get("sites_checked"), "sites_yes": al.get("sites_yes"), "rank_rule": al.get("rank_rule"),
        "rows": [{k: r.get(k) for k in ("rank", "name", "kind", "lat", "lon", "verdict", "slip_margin_days",
                                        "points_passing", "points", "sunlit_h", "earth_h", "why")}
                 for r in (al.get("rows") or [])[:5]],
    }

    hz = mission.get("horizon") or {}
    tg = mission.get("terrain_grid") or {}
    terrain = {
        "grid": tg, "label": tg.get("label"), "product": tg.get("product"), "resolution_m": tg.get("resolution_m"),
        "horizon_label": hz.get("dem_label"), "provenance": hz.get("provenance"),
        "provenance_first": (hz.get("provenance") or "").split(";")[0], "validated": hz.get("validated"),
        "slope_grids": [g.get("product") or g.get("label") for g in (sf.get("grids_used") or [])],
    }

    va, tv = parts["validation"], parts["terrain_validation"]
    checks = []
    if va.get("rows"):
        checks.append({"name": "Sun and Earth directions against JPL Horizons tables",
                       "result": f"{va['rows']} rows, largest difference {va.get('max_abs_el_deg'):.6f} deg in elevation and "
                                 f"{va.get('max_abs_az_deg'):.6f} deg in azimuth",
                       "note": va.get("what_it_checks")})
    for h in (tv.get("headline") or [])[:5]:
        checks.append({"name": h.get("k"), "result": h.get("v"), "note": h.get("s"), "grid": h.get("tag")})
    if tv.get("available") is not None:
        checks.append({"name": "Terrain checks were run on the installed grid",
                       "result": "yes" if tv.get("same_grid") else "no", "note": f"ran on {tv.get('ran_on')}; installed {tv.get('installed')}"})
    if power["how_sure"]:
        checks.append({"name": "How sure (13 touchdown points, coarser grid, finer near-field)", "result": _word(verdict),
                       "note": power["how_sure"]})
    if power["finer_grid"]:
        checks.append({"name": "Stored finer-grid check of this example", "result": "", "note": power["finer_grid"]})

    q_site = f"{name} ({site.get('subtitle') or ''})".replace(" ()", "")
    return {
        "method_version": METHOD_VERSION,
        "made_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "question": (f"Can we land at {name} on {landing[:10]} and still meet the mission's need if the launch slips by "
                     f"up to {slip} day{'s' if slip != 1 else ''}, on ground flat enough to land on?"),
        "answer": {"overall": overall, "word": _word(overall)},
        "inputs": {"site": {k: site.get(k) for k in ("name", "friendly_name", "subtitle", "lat", "lon", "name_source")},
                   "site_ref": ref, "q_site": q_site, "landing_utc": landing, "slip_days": slip,
                   "need": need, "window_days": mission.get("window_days"),
                   "scatter_m": (mission.get("sure") or {}).get("scatter_m"),
                   "rules": mission.get("criteria")},
        "verdict": {"power_and_contact": power, "ground": groundv},
        "slip_margin": {"days": margin, "asked_days": slip, "holds": holds,
                        "target_only_days": mission.get("target_only_margin_days"),
                        "next_good_dates": mission.get("next_good_dates", [])},
        "windows": {"rows": wrows, "rule": parts["windows"].get("rule"), "available": parts["windows"].get("available"),
                    "reason": parts["windows"].get("reason")},
        "hours": hours, "longest_night": night, "slope": slope, "lighting": lighting, "relay": relay,
        "alternatives": alts, "terrain": terrain, "checks": checks,
        "assumptions": _assumptions(parts), "sources": _sources(parts),
        "endpoints": ["POST /api/mission", "POST /api/windows", "POST /api/survival", "POST /api/lander-classes",
                      "GET /api/addons/safety/site", "GET /api/addons/safetouch/site", "GET /api/addons/planner/lighting",
                      "GET /api/addons/planner/joint", "GET /api/addons/relay/window", "GET /api/addons/planner/alternatives",
                      "GET /api/validation", "GET /api/terrain/validation", "GET /api/health"],
    }


@router.get("/api/addons/brief")
def api_brief(site: Optional[str] = Query(None, description="a site id from /api/sites"),
              date: str = Query(OPENING["date"], description="planned landing, e.g. 2026-11-18 or 2026-11-18T00:00:00Z"),
              slip: int = Query(OPENING["slip"], ge=0, le=120, description="launch slip to defend, days"),
              lat: Optional[float] = Query(None, ge=-90, le=90), lon: Optional[float] = Query(None, ge=-360, le=360),
              name: str = Query("", max_length=200), alternatives: bool = True):
    """The review-board brief for one site, landing date and slip, assembled from the entry's own endpoints."""
    if not site and lat is None and lon is None:
        site = OPENING["site"]
    ref = _site_ref(site, lat, lon, name)
    landing = _iso(date)
    key = (tuple(sorted(ref.items())), landing, slip, alternatives)
    if key in _CACHE:
        return _CACHE[key]
    out = build(ref, landing, slip, alternatives)
    _CACHE[key] = out
    while len(_CACHE) > 16:
        _CACHE.pop(next(iter(_CACHE)))
    return out
