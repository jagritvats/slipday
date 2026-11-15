"""Terrain horizon: the elevation angle of the skyline in every direction, as
seen from a point a few metres above the lunar surface.

Method.  From the site, march outward along great circles in ``n_az`` azimuths.
At each sample the DEM gives the terrain height h; the sample lies at central
angle theta = d / R from the observer.  With the observer at radius
r0 = R + z_site + mast and the terrain point at radius rt = R + h, the elevation
angle above the observer's local horizontal is exactly

    el = atan2(rt cos(theta) - r0, rt sin(theta))

(no flat-plane approximation: at 100 km the surface of the reference sphere
has already dropped 2.9 km below the tangent plane).  The horizon in that
azimuth is the largest ``el`` along the ray.  For a smooth sphere this gives
the dip of the horizon, -acos(R / (R + h0)).

Sample spacing starts at the DEM grid spacing and grows in proportion to the
distance (``step_frac``), so near terrain is sampled at full resolution and a
300 km ray stays cheap.  Everything is vectorised: one site takes well under a
second on a laptop for 720 azimuths.

Profiles are cached on disk (``data/horizon_cache``) keyed by DEM, site, mast
height and sampling settings.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np

from . import load
from .dem import DEM, MOON_RADIUS_M

ROOT =os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.environ.get("SLIPDAY_HORIZON_CACHE", os.path.join(ROOT, "data", "horizon_cache"))
CACHE_VERSION = 3


@dataclass
class HorizonProfile:
    az_deg: np.ndarray           # (n_az,) azimuth, clockwise from north
    el_deg: np.ndarray           # (n_az,) horizon elevation angle
    dist_km: np.ndarray          # (n_az,) distance to the point that sets the horizon (NaN: no terrain found)
    coverage_km: np.ndarray      # (n_az,) how far along the ray the DEM had data
    lat: float
    lon: float
    mast_m: float
    site_height_m: float         # DEM height at the site, relative to the 1737.4 km sphere
    max_km: float
    dem: dict                    # DEM.describe()
    floor_used: np.ndarray       # (n_az,) True where the ray had no DEM sample at all

    def to_json(self, decimate: int = 1) -> dict:
        r = lambda a, k: [None if not np.isfinite(x) else round(float(x), k) for x in a[::decimate]]  # noqa: E731
        return {
            "az_deg": r(self.az_deg, 2), "el_deg": r(self.el_deg, 3), "dist_km": r(self.dist_km, 2),
            "lat": self.lat, "lon": self.lon, "mast_m": self.mast_m,
            "site_height_m": round(self.site_height_m, 1), "max_km": self.max_km, "dem": self.dem,
            "min_el_deg": round(float(self.el_deg.min()), 3), "max_el_deg": round(float(self.el_deg.max()), 3),
            "mean_el_deg": round(float(self.el_deg.mean()), 3),
            "min_coverage_km": round(float(self.coverage_km.min()), 1),
            "azimuths_without_terrain": int(self.floor_used.sum()),
        }


def destination(lat_deg: float, lon_deg: float, az_rad: np.ndarray, delta_rad: np.ndarray):
    """Points reached from (lat, lon) along azimuth ``az`` after central angle ``delta``."""
    la = np.deg2rad(lat_deg)
    sin_la, cos_la = np.sin(la), np.cos(la)
    sin_d, cos_d = np.sin(delta_rad), np.cos(delta_rad)
    sin_lat2 = np.clip(sin_la * cos_d + cos_la * sin_d * np.cos(az_rad), -1.0, 1.0)
    lat2 = np.arcsin(sin_lat2)
    lon2 = np.deg2rad(lon_deg) + np.arctan2(np.sin(az_rad) * sin_d * cos_la, cos_d - sin_la * sin_lat2)
    return np.rad2deg(lat2), np.rad2deg(lon2)


def ray_distances_m(min_step_m: float, max_m: float, step_frac: float) -> np.ndarray:
    """Sample distances: spacing max(min_step, step_frac * d)."""
    d_switch = min_step_m / step_frac
    if d_switch >= max_m:
        return np.arange(min_step_m, max_m + min_step_m, min_step_m)
    near = np.arange(min_step_m, d_switch, min_step_m)
    n_far = int(np.ceil(np.log(max_m / d_switch) / np.log1p(step_frac))) + 1
    far = d_switch * (1.0 + step_frac) ** np.arange(n_far)
    return np.concatenate([near, far[far <= max_m * (1 + step_frac)]])


def elevation_angle_deg(theta_rad, terrain_radius_m, observer_radius_m):
    """Exact elevation angle of a point at central angle theta and radius rt,
    seen from an observer at radius r0 (spherical geometry)."""
    return np.rad2deg(np.arctan2(terrain_radius_m * np.cos(theta_rad) - observer_radius_m,
                                 terrain_radius_m * np.sin(theta_rad)))


def sphere_dip_deg(observer_radius_m: float, radius_m: float = MOON_RADIUS_M) -> float:
    """Dip of the smooth-sphere horizon for an observer above the sphere: -acos(R / r0)."""
    if observer_radius_m <= radius_m:
        return float("nan")
    return -float(np.rad2deg(np.arccos(radius_m / observer_radius_m)))


def horizon_profile(dem: DEM, lat: float, lon: float, mast_m: float = 2.0, n_az: int = 720,
                    max_km: float = 300.0, step_frac: float = 0.002, min_step_m: Optional[float] = None,
                    radius_m: float = MOON_RADIUS_M, chunk: int = 90) -> HorizonProfile:
    """Ray-march the DEM into a 360-degree horizon profile for one site."""
    z_site = float(dem.height_m(np.array([lat]), np.array([lon]))[0])
    if not np.isfinite(z_site):
        raise ValueError(f"site {lat:.4f}, {lon:.4f} is outside the DEM ({dem.name})")
    r0 = radius_m + z_site + float(mast_m)
    here = dem.member_at(lat, lon) if hasattr(dem, "member_at") else dem
    step0 = float(min_step_m or (here or dem).resolution_m)
    info = dict(dem.describe_for(lat, lon) if hasattr(dem, "describe_for") else dem.describe())
    # Near-field convention, recorded with every profile: the first ray sample is ``step0`` from the
    # observer.  By default that is one spacing of the grid under the site (node to node, the convention
    # of the LOLA team's illumination maps): a grid holds no information about ground nearer than that,
    # and sampling the bilinear patch any closer measures the interpolation, not the Moon.
    info["first_sample_m"] = step0
    d = ray_distances_m(step0, max_km * 1000.0, step_frac)
    theta = d / radius_m
    az = np.arange(n_az) * (360.0 / n_az)
    el = np.empty(n_az)
    dist = np.empty(n_az)
    cover = np.empty(n_az)
    for i0 in range(0, n_az, chunk):
        a = np.deg2rad(az[i0:i0 + chunk])[:, None]
        la, lo = destination(lat, lon, a, theta[None, :])
        h = dem.height_m(la, lo)
        ang = elevation_angle_deg(theta[None, :], radius_m + h, r0)
        has = np.isfinite(ang)
        ang = np.where(has, ang, -np.inf)
        k = np.argmax(ang, axis=1)
        rows = np.arange(ang.shape[0])
        el[i0:i0 + chunk] = ang[rows, k]
        dist[i0:i0 + chunk] = d[k] / 1000.0
        # coverage: distance of the last sample before the first gap in DEM data
        first_gap = np.where(has.all(axis=1), has.shape[1], np.argmin(has, axis=1))
        cover[i0:i0 + chunk] = np.where(first_gap > 0, d[np.maximum(first_gap - 1, 0)] / 1000.0, 0.0)
    # Where a ray has no DEM sample at all, fall back to the dip of the reference
    # sphere (or straight down if the observer sits below it).  Rays that leave
    # the DEM part-way keep the horizon set by the terrain that is known; their
    # ``coverage_km`` is shorter than ``max_km`` and says so.
    floor = sphere_dip_deg(r0, radius_m)
    floor_used = ~np.isfinite(el)
    el = np.where(floor_used, floor if np.isfinite(floor) else -90.0, el)
    dist = np.where(floor_used, np.nan, dist)
    return HorizonProfile(az_deg=az, el_deg=el, dist_km=dist, coverage_km=cover, lat=float(lat), lon=float(lon),
                          mast_m=float(mast_m), site_height_m=z_site, max_km=float(max_km), dem=info,
                          floor_used=floor_used)


# --------------------------------------------------------------------------
# Disk cache
# --------------------------------------------------------------------------

def _cache_key(dem: DEM, lat: float, lon: float, mast_m: float, n_az: int, max_km: float, step_frac: float,
               min_step_m: Optional[float] = None) -> str:
    parts = [CACHE_VERSION, dem.name, getattr(dem, "fingerprint", ""), round(lat, 5), round(lon, 5),
             round(mast_m, 2), n_az, round(max_km, 1), step_frac]
    if min_step_m:                       # only non-default near-field settings change the key
        parts.append(round(float(min_step_m), 2))
    return hashlib.sha1(json.dumps(parts).encode()).hexdigest()[:20]


def cached_profile(dem: DEM, lat: float, lon: float, mast_m: float = 2.0, n_az: int = 720,
                   max_km: float = 300.0, step_frac: float = 0.002, use_disk: bool = True,
                   min_step_m: Optional[float] = None) -> HorizonProfile:
    key = _cache_key(dem, lat, lon, mast_m, n_az, max_km, step_frac, min_step_m)
    path = os.path.join(CACHE_DIR, f"{dem.name}_{key}.npz")
    if use_disk and os.path.exists(path):
        try:
            with np.load(path, allow_pickle=False) as f:
                meta = json.loads(str(f["meta"]))
                return HorizonProfile(az_deg=f["az"], el_deg=f["el"], dist_km=f["dist"], coverage_km=f["cover"],
                                      floor_used=f["floor"], **meta)
        except Exception:
            pass  # unreadable cache entry: recompute and overwrite
    load.require_cold()        # a new skyline is slow: a request in the light lane moves to the cold lane here
    prof = horizon_profile(dem, lat, lon, mast_m, n_az, max_km, step_frac, min_step_m)
    if use_disk:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            meta = {"lat": prof.lat, "lon": prof.lon, "mast_m": prof.mast_m, "site_height_m": prof.site_height_m,
                    "max_km": prof.max_km, "dem": prof.dem}
            tmp = path + ".tmp.npz"
            np.savez_compressed(tmp, az=prof.az_deg, el=prof.el_deg, dist=prof.dist_km, cover=prof.coverage_km,
                                floor=prof.floor_used, meta=json.dumps(meta))
            os.replace(tmp, path)
        except OSError:
            pass  # read-only deployment: run without the disk cache
    return prof
