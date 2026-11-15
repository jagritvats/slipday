"""Add-on: three planner checks for one site and one touchdown time.

1. Descent lighting.  The Sun's elevation and azimuth at touchdown (JPL DE421, the entry's own geometry.track_at),
   the Sun's direction relative to an approach heading the visitor enters, and the share of the landing-scatter
   ellipse that is in shadow at touchdown (the 3-D view's own shadow ray-cast, view3d.cell_horizon, on the finest
   terrain installed under each touchdown point).
2. Joint chance per lander class.  From the same Gaussian touchdown draws the safe-touchdown add-on uses
   (safetouch.draws(), fixed seed): the share of draws where BOTH the plan holds (the entry's own pass rule,
   robust._passes, at the nearest touchdown point of the lander-class rings) AND the ground is within 8 degrees
   (safetouch's 5 m slope).  Only where a LOLA 5 m site model covers the spread, as for safetouch.
3. Alternatives at the slipped date.  The curated south-pole sites and the 18 map candidates judged with the entry's
   own mission card (robust.mission_card) at the slipped landing date itself, ranked by slip margin.

Nothing here changes another computation.  Assumptions that are not published are labelled ILLUSTRATIVE.
"""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

METHOD_VERSION = "planner-1"

# ILLUSTRATIVE descent-camera lighting limits (no published figure was found and read for this entry)
CAMERA_MAX_REL_DEG = 90.0      # Sun behind (0) or beside (90) the lander, seen along the approach; beyond 90 it is ahead
CAMERA_BEHIND_DEG = 60.0       # within 60 degrees of straight behind counts as "behind"
CAMERA_MIN_EL_DEG = 5.0        # Sun at least 5 degrees up; ILLUSTRATIVE; sites near the pole stay below it
SHADOW_DRAWS = 1500            # touchdown points per class for the shadow share
SHADOW_SEED = 20261115         # the safe-touchdown add-on's seed
DEFAULT_NEED = {"need_sun_h": 240.0, "need_earth_h": 100.0, "window_days": 14.0, "scatter_m": 100.0,
                "mask_deg": 0.0, "mast_m": 2.0, "sun_at_touchdown": True, "earth_at_touchdown": True}
ALT_SLIP_DAYS = 15             # days of slip each alternative is followed for (as the window-options check)
ALT_GROUP = "South pole"

ASSUMPTIONS = [
    "Approach heading: ILLUSTRATIVE, entered by you (default: coming in from the north). No real approach track is used.",
    f"Camera lighting limits: ILLUSTRATIVE. 'Good' here means the Sun is behind or beside the lander "
    f"(within {CAMERA_MAX_REL_DEG:g} degrees of straight behind) and above the local skyline. A low-Sun limit of "
    f"{CAMERA_MIN_EL_DEG:g} degrees is shown for reference only; no published figure was read for this entry.",
    "Lander classes: the entry's three ASSUMED landing spreads (each tied to one public figure), not models of real landers.",
    "Shadow share: the long axis of a non-round spread is laid along the approach heading (ILLUSTRATIVE).",
]


def _wrap(a: float) -> float:
    return float(a) % 360.0


def _rel(sun_az: float, from_az: float) -> float:
    """Angle between the Sun's azimuth and the direction the lander comes FROM: 0 = Sun straight behind."""
    d = abs(_wrap(sun_az - from_az))
    return 360.0 - d if d > 180.0 else d


def _site(lat: float, lon: float, name: str, mast_m: float):
    from ..sites import custom_site
    return custom_site(name or f"{lat:.4f}, {lon:.4f}", lat, lon, 0.0, mast_m, True)


def _iso(t) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _touchdown(landing: str, slip_days: int) -> str:
    from ..ephem import parse_utc
    return _iso(parse_utc(landing) + timedelta(days=int(slip_days)))


# ---------------- 1. descent lighting ----------------

def _shadow_points(lat: float, lon: float, sa: float, sb: float, heading_from_deg: float, n: int, seed: int):
    """n Gaussian touchdown points (lat, lon) around the site; long axis along the approach line."""
    from ..dem import MOON_RADIUS_M
    from ..terrain import destination
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n, 2))
    along, across = z[:, 0] * sa, z[:, 1] * sb
    t = math.radians(heading_from_deg)
    east = along * math.sin(t) + across * math.cos(t)
    north = along * math.cos(t) - across * math.sin(t)
    la, lo = destination(lat, lon, np.arctan2(east, north), np.hypot(east, north) / MOON_RADIUS_M)
    return np.asarray(la, float), np.mod(np.asarray(lo, float) + 180.0, 360.0) - 180.0


def shadow_share(lat: float, lon: float, t_unix: float, heading_from_deg: float, observer_m: float) -> dict:
    """Share of each class's touchdown points whose Sun-disc centre is below the terrain skyline at t_unix."""
    from .. import demstore
    from ..ephem import compute_table
    from ..robust import LANDER_CLASSES
    from ..view3d import STEP_FRAC, cell_horizon, sun_from_cells
    dem = demstore.get_dem()
    if dem is None:
        return {"available": False, "reason": "no terrain data installed"}
    sun = compute_table([t_unix]).sun[0]
    out = []
    for k, c in enumerate(LANDER_CLASSES):
        sa, sb = float(c["sigma_major_m"]), float(c["sigma_minor_m"])
        la, lo = _shadow_points(lat, lon, sa, sb, heading_from_deg, SHADOW_DRAWS, SHADOW_SEED + k)
        h = dem.height_m(la, lo)
        ok = np.isfinite(h)
        entry = {"id": c["id"], "label": c["label"], "sigma_major_m": sa, "sigma_minor_m": sb, "assumed": True,
                 "points": int(SHADOW_DRAWS), "points_on_terrain": int(ok.sum())}
        if ok.sum() < 0.99 * SHADOW_DRAWS:
            entry.update({"available": False, "why": "more than 1 % of the touchdown points fall off the terrain"})
            out.append(entry)
            continue
        az, el, _rad = sun_from_cells(la[ok], lo[ok], sun)
        # finest grid under each point sets the first ray sample, as the 3-D view does for its centre
        res = []
        for a, b in zip(la[ok][:50], lo[ok][:50]):
            m = dem.member_at(float(a), float(b)) if hasattr(dem, "member_at") else dem
            res.append(float((m or dem).resolution_m))
        step0 = float(min(res))
        hz = cell_horizon(dem, la[ok], lo[ok], h[ok], az, observer_m, step0, STEP_FRAC)
        dark = (el - hz) <= 0.0
        nd = int(dark.sum())
        entry.update({"available": True, "in_shadow_pct": round(100.0 * nd / int(ok.sum()), 1),
                      "in_shadow_count": nd, "grid_m": step0})
        out.append(entry)
    info = dem.describe_for(lat, lon) if hasattr(dem, "describe_for") else dem.describe()
    return {"available": True, "classes": out, "observer_m": observer_m, "terrain": info.get("label"),
            "terrain_resolution_m": info.get("resolution_m"),
            "rule": ("a touchdown point is in shadow when the centre of the Sun's disc is at or below the terrain skyline "
                     "seen from the observer height above that point, along the Sun's direction (the 3-D view's own "
                     "ray-cast, curved Moon, rays followed to 300 km)")}


def lighting(lat: float, lon: float, landing: str, slip_days: int = 0, heading_from_deg: float = 0.0,
             name: str = "", observer_m: float = 2.0, with_shadow: bool = True) -> dict:
    from ..ephem import parse_utc
    from ..geometry import track_at
    from ..sites import terrain_profile
    at = _touchdown(landing, slip_days)
    t_unix = float(parse_utc(at).timestamp())
    site = _site(lat, lon, name, observer_m)
    tr = track_at(site, [t_unix], 0.5)
    az = round(float(tr.sun_az[0]), 2)
    el = round(float(tr.sun_el[0]), 3)
    clear = round(float(tr.sun_clear[0]), 3)
    rel = round(_rel(az, heading_from_deg), 1)
    side = "behind" if rel <= CAMERA_BEHIND_DEG else ("beside" if rel <= CAMERA_MAX_REL_DEG else "ahead")
    up = clear > 0.0
    good = bool(up and rel <= CAMERA_MAX_REL_DEG)
    words = {"behind": "behind the lander", "beside": "to the side of the lander", "ahead": "ahead of the lander, toward the camera"}
    text = (f"At touchdown ({at.replace('T', ' ').replace(':00Z', ' UTC')}) the Sun is {el:.2f}° above the level horizon "
            f"at azimuth {az:.1f}° and {'clears' if up else 'is hidden by'} the local skyline "
            f"({abs(clear):.2f}° {'above' if up else 'below'} it). Coming in from {heading_from_deg:g}°, the Sun is "
            f"{rel:.0f}° from straight behind: {words[side]}.")
    if el < CAMERA_MIN_EL_DEG:
        text += (f" It is lower than the illustrative {CAMERA_MIN_EL_DEG:g}° limit. Near the south pole the Sun always "
                 "stays within a few degrees of the horizon, so long shadows at touchdown cannot be avoided there.")
    out = {"available": True, "method_version": METHOD_VERSION,
           "site": {"name": site.name, "lat": site.lat, "lon": site.lon}, "touchdown_utc": at,
           "landing_utc": _touchdown(landing, 0), "slip_days": int(slip_days),
           "terrain": site.horizon.describe() if site.horizon.is_terrain else None,
           "sun": {"az_deg": az, "el_deg": el, "clear_of_skyline_deg": clear, "above_skyline": bool(up),
                   "disc_fraction": round(float(tr.sun_frac[0]), 3)},
           "approach": {"from_deg": float(heading_from_deg) % 360.0, "illustrative": True,
                        "sun_from_behind_deg": rel, "sun_side": side},
           "camera": {"good": good, "illustrative": True, "max_from_behind_deg": CAMERA_MAX_REL_DEG,
                      "behind_within_deg": CAMERA_BEHIND_DEG, "min_el_deg": CAMERA_MIN_EL_DEG,
                      "meets_min_el": bool(el >= CAMERA_MIN_EL_DEG)},
           "text": text, "assumptions": ASSUMPTIONS}
    if with_shadow:
        out["shadow"] = shadow_share(site.lat, site.lon, t_unix, heading_from_deg, observer_m)
    return out


# ---------------- 2. joint chance ----------------

def joint(lat: float, lon: float, landing: str, slip_days: int = 0, name: str = "", need: Optional[dict] = None) -> dict:
    """Share of the safe-touchdown draws where the plan holds AND the ground is within 8 degrees."""
    from ..dem import MOON_RADIUS_M
    from ..geometry import Site
    from ..metrics import Criteria, slip_grid
    from ..robust import OUTER_RINGS, RING_LAYOUT, _passes
    from ..sites import horizon_for
    from ..terrain import destination
    from . import safetouch as st
    p = dict(DEFAULT_NEED, **(need or {}))
    lon = ((float(lon) + 180.0) % 360.0) - 180.0
    at = _touchdown(landing, slip_days)
    loc = st.locate(lat, lon)
    if loc is None:
        return {"available": False, "reason": st.TOO_COARSE, "site": {"name": name, "lat": lat, "lon": lon},
                "touchdown_utc": at}
    g = loc["g"]
    px = g.pixel_m
    half = int(round(st.PATCH_HALF_M / px))
    rc, cc = int(round(loc["row"])), int(round(loc["col"]))
    S, r0, c0 = st.slope_patch(g, rc, cc, half)
    # the plan-holds points: the target and the lander-class rings (robust.lander_classes' own layout)
    hz0 = horizon_for(lat, lon, p["mask_deg"], p["mast_m"], True)
    pts = [Site(name or "site", lat, lon, horizon=hz0)]
    res = float(hz0.meta.get("resolution_m") or 0.0) if hz0.is_terrain else 0.0
    for radius, n, b0 in RING_LAYOUT + OUTER_RINGS:
        if radius < res / 2.0:
            continue
        for k in range(n):
            la, lo = destination(lat, lon, np.deg2rad(b0 + k * 360.0 / n), np.array(radius / MOON_RADIUS_M))
            la, lo = round(float(la), 5), round(((float(lo) + 180.0) % 360.0) - 180.0, 5)
            hz = horizon_for(la, lo, p["mask_deg"], p["mast_m"], True)
            if hz.is_terrain:
                pts.append(Site(name or "site", la, lo, horizon=hz))
    crit = Criteria(0.5, -90.0, -90.0, 0.0, False)
    grid = slip_grid(pts, at, 1, 24, p["window_days"], crit)
    ok = np.array([bool(_passes(r, p["need_sun_h"], p["need_earth_h"], p["sun_at_touchdown"], p["earth_at_touchdown"])[0])
                   for r in grid["rows"]])
    # map positions of the plan points on the 5 m grid; each draw takes the outcome of the nearest one
    px_pts = np.array([[float(v) for v in g.project(s.lat, s.lon)] for s in pts])
    classes = []
    for c in st.lander_classes():
        d = st.draws()[c["id"]]
        row, col = st._class_cells(loc, c["id"], r0, c0)
        cnt = st._count(S, row, col)
        entry = {"id": c["id"], "label": c["label"], "sigma_major_m": c["sigma_major_m"],
                 "sigma_minor_m": c["sigma_minor_m"], "assumed": True, "draws": cnt["n"]}
        outside = 1.0 - cnt["valid"] / cnt["n"]
        if outside > st.MAX_OUTSIDE:
            entry.update({"available": False, "why": f"{100 * outside:.1f} % of this lander's touchdown points fall off "
                                                     "the 5 m terrain, so no chance is given for it here"})
            classes.append(entry)
            continue
        x = loc["x"] + d["dx"]
        y = loc["y"] + d["dy"]
        # nearest plan point, in chunks to keep memory small
        near = np.empty(len(x), dtype=np.int64)
        for i0 in range(0, len(x), 4000):
            dx = x[i0:i0 + 4000, None] - px_pts[None, :, 0]
            dy = y[i0:i0 + 4000, None] - px_pts[None, :, 1]
            near[i0:i0 + 4000] = np.argmin(dx * dx + dy * dy, axis=1)
        dist = np.hypot(x - px_pts[near, 0], y - px_pts[near, 1])
        v = cnt["ok"]
        plan = ok[near][v]
        flat = cnt["s"][v] <= st.LIMIT_DEG
        n = int(v.sum())
        kj, kp, kf = int((plan & flat).sum()), int(plan.sum()), int(flat.sum())
        entry.update({"available": True, "draws_used": n,
                      "plan_holds_pct": st._pct(kp, n), "flat_pct": st._pct(kf, n),
                      "joint_pct": st._pct(kj, n), "joint_count": kj, "joint_range": list(st.wilson(kj, n)),
                      "if_independent_pct": round(100.0 * (kp / n) * (kf / n), 1),
                      "median_distance_to_plan_point_m": round(float(np.median(dist)), 1),
                      "max_distance_to_plan_point_m": round(float(dist.max()), 1)})
        classes.append(entry)
    return {"available": True, "method_version": METHOD_VERSION,
            "site": {"name": name or f"{lat:.4f}, {lon:.4f}", "lat": float(lat), "lon": float(lon)},
            "touchdown_utc": at, "slip_days": int(slip_days), "limit_deg": st.LIMIT_DEG,
            "grid": {"name": loc["name"], "label": loc["label"], "cell_m": px},
            "plan_points": len(pts), "plan_points_passing": int(ok.sum()), "plan_grid_m": res, "need": p,
            "classes": classes,
            "how": ("Touchdown points are the safe-touchdown add-on's own random draws. At each one the slope comes "
                    "from the 5 m terrain (8° or less counts as flat enough) and 'the plan holds' is the sunlight and "
                    "Earth-contact verdict of the nearest of the lander-class ring points (out to 2.5 km). The joint "
                    "chance is the share of draws where both are true."),
            "assumptions": ASSUMPTIONS[2:3]}


# ---------------- 3. alternatives at the slipped date ----------------

def alternatives(landing: str, slip_days: int, exclude_lat: Optional[float] = None, exclude_lon: Optional[float] = None,
                 need: Optional[dict] = None, follow_days: int = ALT_SLIP_DAYS) -> dict:
    from ..metrics import Criteria
    from ..robust import mission_card
    from ..sites import SITES, custom_site, get_site
    from .. import windows
    p = dict(DEFAULT_NEED, **(need or {}))
    at = _touchdown(landing, slip_days)
    crit = Criteria(0.5, -90.0, -90.0, 0.0, False)
    cands = []
    for s in SITES:
        if s["group"] != ALT_GROUP:
            continue
        cands.append(("curated", s["id"], get_site(s["id"], p["mask_deg"], p["mast_m"], True)))
    try:
        mc = windows.map_candidates()
    except Exception:          # the map field is not built on this installation
        mc = []
    for c in mc:
        nm = f"map point {abs(c['lat']):.3f} S, {abs(c['lon']):.3f} {'W' if c['lon'] < 0 else 'E'}"
        cands.append(("map", None, custom_site(nm, c["lat"], c["lon"], p["mask_deg"], p["mast_m"])))
    rows = []
    for kind, sid, s in cands:
        if exclude_lat is not None and exclude_lon is not None and abs(s.lat - exclude_lat) < 0.003 \
                and abs(((s.lon - exclude_lon + 180) % 360) - 180) < 0.15:
            continue
        if not s.horizon.is_terrain:
            rows.append({"name": s.name, "id": sid, "kind": kind, "lat": s.lat, "lon": s.lon, "verdict": "n/a",
                         "slip_margin_days": None, "why": "no terrain data covers this site"})
            continue
        m = mission_card(s, at, p["need_sun_h"], p["need_earth_h"], p["window_days"], crit, p["mask_deg"], p["mast_m"],
                         p["scatter_m"], follow_days, p["sun_at_touchdown"], p["earth_at_touchdown"])
        d0 = m["days"][0]
        rows.append({"name": s.name, "id": sid, "kind": kind, "lat": s.lat, "lon": s.lon, "verdict": m["verdict"],
                     "slip_margin_days": int(m["slip_margin_days"]), "sunlit_h": d0["sunlit_h"], "earth_h": d0["earth_h"],
                     "points_passing": m["sure"]["points_passing"], "points": m["sure"]["points"],
                     "grid_m": m["sure"]["grid_resolution_m"], "headline": m["headline"],
                     "why": "; ".join(d0.get("reasons") or d0.get("unsure_because") or [])})
    order = {"yes": 0, "not sure": 1, "no": 2, "n/a": 3}
    rows.sort(key=lambda r: (order.get(r["verdict"], 3), -(r["slip_margin_days"] if r["slip_margin_days"] is not None else -9),
                             -(r.get("points_passing") or 0), -(r.get("sunlit_h") or 0)))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return {"available": True, "method_version": METHOD_VERSION, "landing_utc": _touchdown(landing, 0),
            "slip_days": int(slip_days), "touchdown_utc": at, "followed_for_days": follow_days,
            "sites_checked": len(rows), "sites_yes": sum(r["verdict"] == "yes" for r in rows), "rows": rows,
            "need": p, "rank_rule": ("clear yes first, then not sure, then no; within each, the longest slip margin "
                                     f"(followed for {follow_days} days from the slipped date), then the most touchdown "
                                     "points passing, then the most sunlit hours"),
            "sources": f"curated sites of the '{ALT_GROUP}' group and the {len(mc)} scatter-checked map candidates"}


# ---------------- the router ----------------

router = APIRouter(tags=["add-on: planner checks"])


def _need(need_sun_h, need_earth_h, window_days, scatter_m) -> dict:
    return {"need_sun_h": need_sun_h, "need_earth_h": need_earth_h, "window_days": window_days, "scatter_m": scatter_m}


def _where(id, lat, lon, name):
    if id:
        from ..sites import _BY_ID
        s = _BY_ID.get(id)
        if s is None:
            raise HTTPException(404, f"no site with id {id!r}")
        return s["lat"], s["lon"], name or s["name"]
    if lat is None or lon is None:
        raise HTTPException(422, "give a site id, or lat and lon")
    return float(lat), ((float(lon) + 180.0) % 360.0) - 180.0, name


def _check_date(landing: str):
    from ..ephem import parse_utc
    try:
        parse_utc(landing)
    except (ValueError, TypeError):
        raise HTTPException(422, "landing is not a date I can read (use e.g. 2026-11-18)")


def _run(fn, *a, **k):
    from .. import load
    try:
        return load.run_big(lambda: fn(*a, **k))
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/api/addons/planner/lighting")
def api_lighting(id: Optional[str] = None, lat: Optional[float] = Query(None, ge=-90, le=90),
                 lon: Optional[float] = Query(None, ge=-360, le=360), name: str = Query("", max_length=200),
                 landing: str = "2026-11-18T00:00:00Z", slip_days: int = Query(0, ge=0, le=120),
                 heading_from_deg: float = Query(0.0, ge=0, le=360), observer_m: float = Query(2.0, ge=0, le=50),
                 shadow: bool = True):
    """Sun at touchdown, its direction relative to the approach, and the shadowed share of the landing spread."""
    _check_date(landing)
    la, lo, nm = _where(id, lat, lon, name)
    return _run(lighting, la, lo, landing, slip_days, heading_from_deg, nm, observer_m, shadow)


@router.get("/api/addons/planner/joint")
def api_joint(id: Optional[str] = None, lat: Optional[float] = Query(None, ge=-90, le=90),
              lon: Optional[float] = Query(None, ge=-360, le=360), name: str = Query("", max_length=200),
              landing: str = "2026-11-18T00:00:00Z", slip_days: int = Query(0, ge=0, le=120),
              need_sun_h: float = Query(240.0, ge=0, le=2880), need_earth_h: float = Query(100.0, ge=0, le=2880),
              window_days: float = Query(14.0, gt=0, le=120)):
    """Chance per lander class that the plan holds AND the ground is within 8 degrees (5 m terrain only)."""
    _check_date(landing)
    la, lo, nm = _where(id, lat, lon, name)
    return _run(joint, la, lo, landing, slip_days, nm, _need(need_sun_h, need_earth_h, window_days, 100.0))


@router.get("/api/addons/planner/alternatives")
def api_alternatives(landing: str = "2026-11-18T00:00:00Z", slip_days: int = Query(0, ge=0, le=120),
                     id: Optional[str] = None, lat: Optional[float] = Query(None, ge=-90, le=90),
                     lon: Optional[float] = Query(None, ge=-360, le=360),
                     need_sun_h: float = Query(240.0, ge=0, le=2880), need_earth_h: float = Query(100.0, ge=0, le=2880),
                     window_days: float = Query(14.0, gt=0, le=120), scatter_m: float = Query(100.0, ge=0, le=500)):
    """Curated south-pole sites and map candidates judged at the slipped landing date itself, ranked by margin."""
    _check_date(landing)
    la = lo = None
    if id or (lat is not None and lon is not None):
        la, lo, _ = _where(id, lat, lon, "")
    key = (landing, slip_days, la, lo, need_sun_h, need_earth_h, window_days, scatter_m)
    hit = _ALT_CACHE.get(key)
    if hit is not None:
        return hit
    out = _run(alternatives, landing, slip_days, la, lo, _need(need_sun_h, need_earth_h, window_days, scatter_m))
    _ALT_CACHE[key] = out
    while len(_ALT_CACHE) > 16:
        _ALT_CACHE.pop(next(iter(_ALT_CACHE)))
    return out


_ALT_CACHE: dict = {}


@router.get("/api/addons/planner/about")
def api_about():
    return {"method_version": METHOD_VERSION, "assumptions": ASSUMPTIONS,
            "camera": {"max_from_behind_deg": CAMERA_MAX_REL_DEG, "behind_within_deg": CAMERA_BEHIND_DEG,
                       "min_el_deg": CAMERA_MIN_EL_DEG, "illustrative": True},
            "shadow_draws_per_class": SHADOW_DRAWS, "alternatives_followed_days": ALT_SLIP_DAYS}
