"""A patch of the real elevation grid around a site, for the 3-D view: heights, the directions to the
Sun and the Earth at one instant, and which cells of the patch are in shadow at that instant.

What is real, derived and assumed here:

  real      the heights: bilinear samples of the same LOLA grids every other answer uses
            (``demstore.get_dem()``), laid out on a square east/north frame centred on the site
  derived   the directions to the Sun and the Earth (JPL DE421, as everywhere else), whether each
            clears the site's terrain skyline (the app's own skyline profile for the site), and the
            shadow: for every cell a ray is marched from ``mast_m`` above that cell towards the Sun
            over the same grids, beyond the edge of the patch, on the curved Moon (the elevation
            angle of every terrain sample is ``atan2(rt cos(theta) - r0, rt sin(theta))``, exactly as
            in ``terrain.horizon_profile``).  The Sun's azimuth and elevation are worked out for
            each cell, because near the pole "towards the Sun" is a different compass direction a
            few kilometres away.
  assumed   one thing only: across the half-degree width of the solar disc the skyline is taken as
            level, so the share of the disc a cell sees is the circular-segment share for the
            clearance of the disc's centre.  A cell counts as lit when the centre of the disc clears
            the terrain (which, for a level skyline, is the same as half the disc showing).

The far part of each shadow ray is sampled more coarsely than a site skyline (``STEP_FRAC`` here
against 0.002 there) so that a frame takes about a second; ``tests/test_view3d.py`` measures how often
the centre cell then agrees with the site's own skyline.  The numbers on the mission card never come
from this module.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from . import demstore, load
from .dem import MOON_RADIUS_M
from .ephem import MOON_RADIUS_KM, SUN_RADIUS_KM, compute_table, iso, parse_utc, supported_unix_span
from .geometry import segment_fraction, track_at
from .sites import custom_site, get_site, terrain_profile
from .terrain import destination, elevation_angle_deg, ray_distances_m, sphere_dip_deg

router = APIRouter()

STEP_FRAC = 0.01          # growth of the ray step with distance for the shadow (a site skyline uses 0.002)
MAX_KM = 300.0            # how far a shadow ray is followed, as for a site skyline
CHUNK_SAMPLES = 400_000   # ray samples worked on at once (keeps temporary arrays to a few megabytes)
N_MAX = 101               # grid points per side: 10,000 quads is about what a phone redraws smoothly (about 1.5 s a frame)
FRAME_CACHE = 96          # shadow frames kept (about 15 kB each at the default size)
PATCH_CACHE = 8           # height patches kept

SHADOW_RULE = ("a cell is lit when the centre of the Sun's disc clears all terrain along the ray from that cell "
               "(for a level skyline that is half the disc showing); the digit is the tenth of the disc above the "
               "terrain, taking the skyline as level across the disc")
FRAME_TEXT = ("local east/north frame centred on the site (azimuthal equidistant): row 0 is the northern edge, "
              "column 0 the western edge; heights are metres relative to the site")

_lock = threading.Lock()
_frames: "OrderedDict[tuple, dict]" = OrderedDict()
_patches: "OrderedDict[tuple, dict]" = OrderedDict()


def _get(cache: OrderedDict, key):
    with _lock:
        hit = cache.get(key)
        if hit is not None:
            cache.move_to_end(key)
        return hit


def _put(cache: OrderedDict, key, value, limit: int) -> None:
    with _lock:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > limit:
            cache.popitem(last=False)


def clear_cache() -> None:
    with _lock:
        _frames.clear()
        _patches.clear()


def patch_latlon(lat: float, lon: float, half_km: float, n: int):
    """Latitude and longitude of the n x n cells: east/north offsets laid out along great circles from the site."""
    c = (np.arange(n) - (n - 1) / 2.0) * (2.0 * half_km * 1000.0 / (n - 1))
    east, north = np.meshgrid(c, c[::-1])                    # row 0 is the northern edge
    la, lo = destination(lat, lon, np.arctan2(east, north), np.hypot(east, north) / MOON_RADIUS_M)
    lo = np.mod(lo + 180.0, 360.0) - 180.0
    return la, lo, east, north


def sun_from_cells(la: np.ndarray, lo: np.ndarray, sun_km: np.ndarray):
    """Azimuth, elevation and angular radius (degrees) of the Sun from each cell, as ``geometry.track`` does it."""
    lar, lor = np.deg2rad(la), np.deg2rad(lo)
    up = np.stack([np.cos(lar) * np.cos(lor), np.cos(lar) * np.sin(lor), np.sin(lar)], axis=-1)
    east = np.stack([-np.sin(lor), np.cos(lor), np.zeros_like(lor)], axis=-1)
    north = np.stack([-np.sin(lar) * np.cos(lor), -np.sin(lar) * np.sin(lor), np.cos(lar)], axis=-1)
    topo = sun_km[None, :] - MOON_RADIUS_KM * up
    dist = np.linalg.norm(topo, axis=-1)
    e, n, u = (topo * east).sum(-1), (topo * north).sum(-1), (topo * up).sum(-1)
    el = np.rad2deg(np.arcsin(np.clip(u / dist, -1.0, 1.0)))
    az = np.mod(np.rad2deg(np.arctan2(e, n)), 360.0)
    return az, el, np.rad2deg(np.arcsin(SUN_RADIUS_KM / dist))


def cell_horizon(dem, la: np.ndarray, lo: np.ndarray, h: np.ndarray, az_deg: np.ndarray, mast_m: float,
                 step0_m: float, step_frac: float = STEP_FRAC, max_km: float = MAX_KM) -> np.ndarray:
    """Elevation angle (degrees) of the terrain skyline seen from ``mast_m`` above each cell, in that cell's
    own direction ``az_deg``.  One ray per cell; same geometry as ``terrain.horizon_profile``."""
    d = ray_distances_m(step0_m, max_km * 1000.0, step_frac)
    theta = d / MOON_RADIUS_M
    r0 = MOON_RADIUS_M + h + float(mast_m)
    out = np.full(la.shape, np.nan)
    per = max(1, CHUNK_SAMPLES // len(d))
    azr = np.deg2rad(az_deg)
    for i0 in range(0, la.size, per):
        sl = slice(i0, i0 + per)
        la2, lo2 = destination(la[sl][:, None], lo[sl][:, None], azr[sl][:, None], theta[None, :])
        ang = elevation_angle_deg(theta[None, :], MOON_RADIUS_M + dem.height_m(la2, lo2), r0[sl][:, None])
        out[sl] = np.where(np.isfinite(ang), ang, -np.inf).max(axis=1)
    # a ray with no terrain sample at all: the dip of the reference sphere, as a site skyline does
    none = ~np.isfinite(out) & np.isfinite(h)
    if none.any():
        out[none] = [sphere_dip_deg(float(r)) if r > MOON_RADIUS_M else -90.0 for r in r0[none]]
    return out


def shadow_frame(dem, lat: float, lon: float, half_km: float, n: int, mast_m: float, t_unix: float,
                 step_frac: float = STEP_FRAC) -> dict:
    """Which cells of the patch are lit at ``t_unix``: one digit per cell, row-major, north edge first."""
    t0 = time.time()
    la, lo, _, _ = patch_latlon(lat, lon, half_km, n)
    la, lo = la.ravel(), lo.ravel()
    h = dem.height_m(la, lo)
    here = dem.member_at(lat, lon) if hasattr(dem, "member_at") else dem
    step0 = float((here or dem).resolution_m)            # first sample one grid spacing out, as for a site skyline
    az, el, rad = sun_from_cells(la, lo, compute_table([t_unix]).sun[0])
    ok = np.isfinite(h)
    hz = np.full(la.shape, np.nan)
    if ok.any():
        hz[ok] = cell_horizon(dem, la[ok], lo[ok], h[ok], az[ok], mast_m, step0, step_frac)
    clear = el - hz
    frac = np.where(ok, segment_fraction(np.where(ok, clear, 0.0), rad), 0.0)
    digit = np.minimum(9, np.floor(frac * 10.0 + 1e-9)).astype(int)
    digit = np.where(ok & (clear > 0) & (digit < 5), 5, digit)     # rounding guard: centre above means 5 or more
    digit = np.where(ok & (clear <= 0) & (digit > 4), 4, digit)
    lit = int((digit >= 5).sum())
    return {"shade": "".join(map(str, digit.tolist())), "rule": SHADOW_RULE, "observer_m": float(mast_m),
            "cells": int(la.size), "lit_cells": lit, "lit_share_pct": round(100.0 * lit / la.size, 1),
            "first_sample_m": step0, "step_frac": step_frac, "max_km": MAX_KM,
            "centre_clear_deg": round(float(clear[(n * n) // 2]), 3) if ok[(n * n) // 2] else None,
            "seconds": round(time.time() - t0, 2)}


def height_patch(dem, lat: float, lon: float, half_km: float, n: int) -> dict:
    la, lo, _, _ = patch_latlon(lat, lon, half_km, n)
    h = dem.height_m(la.ravel(), lo.ravel())
    z0 = float(h[(n * n) // 2])
    rel = h - z0
    ok = np.isfinite(rel)
    return {"site_height_m": round(z0, 1),
            "heights_m": [round(float(v), 1) if g else None for v, g in zip(rel, ok)],
            "height_range_m": [round(float(rel[ok].min()), 1), round(float(rel[ok].max()), 1)],
            "cells_without_data": int((~ok).sum())}


def _body(tr, prof, name: str) -> dict:
    az = float(getattr(tr, name + "_az")[0])
    out = {"az_deg": round(az, 2), "el_deg": round(float(getattr(tr, name + "_el")[0]), 3),
           "radius_deg": round(float(getattr(tr, name + "_radius_deg")[0]), 3),
           "clear_deg": round(float(getattr(tr, name + "_clear")[0]), 3)}
    if prof is not None:                                   # the terrain that sets the skyline in that direction
        k = int(round(az / 360.0 * len(prof.az_deg))) % len(prof.az_deg)
        d = float(prof.dist_km[k])
        out["skyline_el_deg"] = round(out["el_deg"] - out["clear_deg"], 3)      # the skyline the clearance was taken from
        out["skyline_km"] = round(d, 2) if np.isfinite(d) else None            # at the nearest of the 720 skyline azimuths
    return out


def terrain3d(site_id: Optional[str], lat: Optional[float], lon: Optional[float], name: str, at: str,
              half_km: float, n: int, mast_m: float, min_sun_fraction: float, earth_margin_deg: float,
              heights: bool) -> dict:
    t_unix = float(parse_utc(at).timestamp())
    lo_t, hi_t = supported_unix_span()
    if not (lo_t <= t_unix <= hi_t):
        raise ValueError("time outside the supported ephemeris span (1900-01-01 to 2050-01-01)")
    dem = demstore.get_dem()
    if dem is None:
        return {"available": False, "reason": "no terrain data installed"}
    try:
        site = (get_site(site_id, 0.0, mast_m, True) if site_id
                else custom_site(name, lat, lon, 0.0, mast_m, True))
    except KeyError:
        raise HTTPException(404, f"unknown site id {site_id!r}")
    z = float(dem.height_m(np.array([site.lat]), np.array([site.lon]))[0])
    if not np.isfinite(z) or not site.horizon.is_terrain:
        return {"available": False, "reason": "no terrain data covers this site",
                "site": {"name": site.name, "lat": site.lat, "lon": site.lon}}
    info = dem.describe_for(site.lat, site.lon) if hasattr(dem, "describe_for") else dem.describe()
    fp = getattr(dem, "fingerprint", dem.name)
    la5, lo5 = round(site.lat, 5), round(site.lon, 5)
    spacing = 2.0 * half_km * 1000.0 / (n - 1)

    tr = track_at(site, [t_unix], min_sun_fraction)
    prof = terrain_profile(site.lat, site.lon, mast_m)
    sun = _body(tr, prof, "sun")
    sun.update({"disc_fraction": round(float(tr.sun_frac[0]), 3), "up": bool(tr.sun_lit[0] > 0),
                "rule": ("any part of the solar disc above the site's terrain skyline" if min_sun_fraction <= 0 else
                         "the whole solar disc above the site's terrain skyline" if min_sun_fraction >= 1 else
                         f"at least {min_sun_fraction * 100:g}% of the solar disc above the site's terrain skyline")})
    earth = _body(tr, prof, "earth")
    earth.update({"up": bool(tr.earth_clear[0] > earth_margin_deg),
                  "rule": f"Earth's centre at least {earth_margin_deg:g} deg above the site's terrain skyline"})

    fkey = (fp, la5, lo5, round(half_km, 3), n, round(mast_m, 2), int(round(t_unix)))
    frame = _get(_frames, fkey)
    cached = frame is not None
    if frame is None:
        load.require_cold()                                # a new frame is about a second of ray-marching
        frame = shadow_frame(dem, site.lat, site.lon, half_km, n, mast_m, t_unix)
        _put(_frames, fkey, frame, FRAME_CACHE)
    out = {"available": True, "site": {"name": site.name, "lat": site.lat, "lon": site.lon, "height_m": round(z, 1)},
           "at_utc": iso(t_unix), "n": n, "half_km": half_km, "spacing_m": round(spacing, 2), "frame": FRAME_TEXT,
           "dem": {"label": info["label"], "resolution_m": info["resolution_m"], "synthetic": bool(info["synthetic"]),
                   "provenance": info.get("provenance", ""),
                   "interpolated": bool(spacing < float(info["resolution_m"]) - 1e-6)},
           "skyline": site.horizon.describe(), "sun": sun, "earth": earth,
           "shadow": dict(frame, cached=cached),
           "directions": "Sun and Earth from JPL DE421 with lunar librations, light-time and aberration applied",
           "vertical": "heights are true metres; any vertical exaggeration is applied, and labelled, by the viewer"}
    if heights:
        pkey = (fp, la5, lo5, round(half_km, 3), n)
        patch = _get(_patches, pkey)
        if patch is None:
            patch = height_patch(dem, site.lat, site.lon, half_km, n)
            _put(_patches, pkey, patch, PATCH_CACHE)
        out.update(patch)
    return out


@router.get("/api/terrain3d")
def api_terrain3d(at: str, site: Optional[str] = None, lat: Optional[float] = Query(None, ge=-90, le=90),
                  lon: Optional[float] = Query(None, ge=-360, le=360), name: Optional[str] = None,
                  half_km: float = Query(4.0, ge=1, le=20), n: int = Query(81, ge=17, le=N_MAX),
                  mast_m: float = Query(2.0, ge=0, le=500), min_sun_fraction: float = Query(0.5, ge=0, le=1),
                  earth_margin_deg: float = Query(0.0, ge=0, le=20), heights: bool = True):
    """Heights of the real elevation grid around a site, the Sun and the Earth at ``at``, and the shadow then.

    ``n`` is forced odd so that the centre cell is the site itself.  ``heights=false`` leaves the height
    patch out (the time slider only needs a new shadow)."""
    try:
        parse_utc(at)
    except (ValueError, TypeError):
        raise HTTPException(422, "at is not a date or time I can read (use e.g. 2026-11-18 or 2026-11-18T06:00:00Z)")
    if not site and (lat is None or lon is None):
        raise HTTPException(422, "a site needs either an id or both lat and lon")
    if n % 2 == 0:
        n += 1
    try:
        return load.run(terrain3d, site, lat, lon, name or "", at, float(half_km), int(n), float(mast_m),
                        float(min_sun_fraction), float(earth_margin_deg), bool(heights))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    # load.Busy (the cold lane's queue is full) is left to the app's own handler: HTTP 503 with Retry-After
