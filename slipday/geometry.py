"""Site geometry: azimuth/elevation of Sun and Earth from a point on the Moon,
plus the horizon model that decides what "above the horizon" means.

Conventions: selenographic latitude north-positive, longitude east-positive
(Mean-Earth style, as approximated by the IAU rotation model).  Azimuth is
clockwise from local north through east.  Elevation is geometric, measured
from the plane perpendicular to the local radial direction.  There is no
refraction on the Moon.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np

from .ephem import (EARTH_RADIUS_KM, MOON_RADIUS_KM, SUN_RADIUS_KM, EphemTable,
                    compute_table)


class Horizon:
    """Elevation (degrees) a body must exceed, as a function of azimuth.

    ``kind`` tells the user interface how to label results:
      smooth-sphere  0 degrees everywhere (no terrain)
      flat-mask      one user-set angle at every azimuth
      profile        a 360-degree terrain profile ray-cast from a DEM
    ``meta`` carries the provenance of a profile (DEM label, resolution, mast
    height, site height) so every number derived from it can be labelled.
    """

    def __init__(self, mask_deg: float = 0.0,
                 profile_az_deg: Optional[Sequence[float]] = None,
                 profile_el_deg: Optional[Sequence[float]] = None,
                 source: str = "", meta: Optional[dict] = None):
        self.mask_deg = float(mask_deg)
        self.source = source
        self.meta = dict(meta or {})
        if profile_az_deg is not None and profile_el_deg is not None:
            az = np.mod(np.asarray(profile_az_deg, dtype=float), 360.0)
            el = np.asarray(profile_el_deg, dtype=float)
            if az.shape != el.shape or az.size < 2:
                raise ValueError("horizon profile needs matching azimuth and elevation arrays")
            order = np.argsort(az)
            self._az, self._el = az[order], el[order]
            self.kind = "profile"
        else:
            self._az = self._el = None
            self.kind = "flat-mask" if self.mask_deg != 0.0 else "smooth-sphere"

    @property
    def is_terrain(self) -> bool:
        return self.kind == "profile"

    def elevation_at(self, az_deg) -> np.ndarray:
        az = np.mod(np.asarray(az_deg, dtype=float), 360.0)
        if self._az is None:
            return np.full(az.shape, self.mask_deg)
        terrain = np.interp(az, self._az, self._el, period=360.0)
        return np.maximum(terrain, self.mask_deg) if self.mask_deg else terrain

    def describe(self) -> dict:
        if self.kind == "profile":
            mast = self.meta.get("mast_m")
            label = "terrain (" + (self.source or "DEM") + ")"
            if mast is not None:
                label += f", {mast:g} m above ground"
            if self.mask_deg:
                label += f", plus {self.mask_deg:g} deg mask"
        elif self.kind == "flat-mask":
            label = f"smooth sphere + flat {self.mask_deg:g} deg mask (no terrain)"
        else:
            label = "smooth sphere (0 deg, no terrain)"
        out = {"kind": self.kind, "mask_deg": self.mask_deg, "label": label,
               "model": "terrain" if self.kind == "profile" else "smooth sphere",
               "synthetic": bool(self.meta.get("synthetic", False))}
        if self.kind == "profile":
            out.update({k: self.meta[k] for k in ("dem_label", "resolution_m", "mast_m", "site_height_m",
                                                  "min_el_deg", "max_el_deg", "min_coverage_km", "provenance",
                                                  "first_sample_m", "validated")
                        if k in self.meta})
        return out


def disc_fraction(horizon: "Horizon", az_deg, el_deg, radius_deg, n_strips: int = 15) -> np.ndarray:
    """Fraction (0..1) of a circular disc of angular radius ``radius_deg`` centred
    at (az, el) that lies above the horizon.

    The disc is cut into ``n_strips`` vertical strips of equal width; each strip
    is compared with the horizon elevation at its own azimuth, so a notch or a
    peak narrower than the disc is handled.  For a level horizon the result
    converges to the circular-segment formula.
    """
    az = np.atleast_1d(np.asarray(az_deg, dtype=float))
    el = np.atleast_1d(np.asarray(el_deg, dtype=float))
    rad = np.broadcast_to(np.asarray(radius_deg, dtype=float), el.shape)
    u = -1.0 + (2.0 * np.arange(n_strips) + 1.0) / n_strips          # strip centres in units of the radius
    half = np.sqrt(1.0 - u * u)                                       # half-height of each strip, same units
    cos_el = np.maximum(np.cos(np.deg2rad(el)), 0.2)
    strip_az = az[:, None] + (u[None, :] * rad[:, None]) / cos_el[:, None]
    h = horizon.elevation_at(strip_az)
    top = el[:, None] + half[None, :] * rad[:, None]
    full = 2.0 * half[None, :] * rad[:, None]
    visible = np.clip(top - h, 0.0, full)
    return visible.sum(axis=1) / full.sum(axis=1)


def segment_fraction(clearance_deg, radius_deg) -> np.ndarray:
    """Visible fraction of a disc whose centre is ``clearance`` above a level horizon."""
    x = np.clip(np.asarray(clearance_deg, dtype=float) / np.asarray(radius_deg, dtype=float), -1.0, 1.0)
    return 1.0 - (np.arccos(x) - x * np.sqrt(1.0 - x * x)) / np.pi


@dataclass(frozen=True)
class Site:
    name: str
    lat: float
    lon: float
    alt_km: float = 0.0
    horizon: Horizon = field(default_factory=Horizon, compare=False)

    def __post_init__(self):
        if not (-90.0 <= self.lat <= 90.0):
            raise ValueError("latitude must be between -90 and 90 degrees")
        if not (-360.0 <= self.lon <= 360.0):
            raise ValueError("longitude must be between -360 and 360 degrees")


@dataclass(frozen=True)
class Track:
    """Sun and Earth as seen from one site on a time grid (degrees)."""

    unix: np.ndarray
    sun_az: np.ndarray
    sun_el: np.ndarray
    earth_az: np.ndarray
    earth_el: np.ndarray
    sun_radius_deg: np.ndarray
    earth_radius_deg: np.ndarray
    sun_clear: np.ndarray     # disc-centre elevation minus horizon at that azimuth
    earth_clear: np.ndarray
    sun_frac: np.ndarray      # fraction of the solar disc above the horizon (0..1)
    sun_lit: np.ndarray       # signed: > 0 when the Sun counts as up (see ``track``)


def _enu(lat_deg: float, lon_deg: float):
    la, lo = np.deg2rad(lat_deg), np.deg2rad(lon_deg)
    up = np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    east = np.array([-np.sin(lo), np.cos(lo), 0.0])
    north = np.array([-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)])
    return east, north, up


def _azel(vec_bf: np.ndarray, site_pos: np.ndarray, east, north, up):
    topo = vec_bf - site_pos
    dist = np.linalg.norm(topo, axis=1)
    e, n, u = topo @ east, topo @ north, topo @ up
    el = np.rad2deg(np.arcsin(np.clip(u / dist, -1.0, 1.0)))
    az = np.mod(np.rad2deg(np.arctan2(e, n)), 360.0)
    return az, el, dist


def track(site: Site, table: EphemTable, min_sun_fraction: float = 0.5) -> Track:
    """Sun and Earth from ``site`` at every instant of ``table``.

    The Sun is an extended disc.  ``sun_frac`` is the fraction of it above the
    horizon.  The Sun counts as up (``sun_lit`` > 0) when more than
    ``min_sun_fraction`` of the disc is visible.  With the default of one half
    and a level horizon that is the same instant as the disc centre crossing
    the horizon, so smooth-sphere results are unchanged from the centre rule;
    for those horizons ``sun_lit`` is the centre clearance in degrees, shifted
    by the equivalent amount when another fraction is asked for.
    The Earth is judged at its disc centre.
    """
    east, north, up = _enu(site.lat, site.lon)
    pos = (MOON_RADIUS_KM + site.alt_km) * up
    s_az, s_el, s_d = _azel(table.sun, pos, east, north, up)
    e_az, e_el, e_d = _azel(table.earth, pos, east, north, up)
    s_rad = np.rad2deg(np.arcsin(SUN_RADIUS_KM / s_d))
    s_clear = s_el - site.horizon.elevation_at(s_az)
    if site.horizon.is_terrain:
        frac = disc_fraction(site.horizon, s_az, s_el, s_rad)
        if min_sun_fraction <= 0.0:          # "any part of the disc": strictly positive fraction
            lit = np.where(frac > 0.0, np.maximum(frac, 1e-9), -1.0)
        else:                                # "whole disc" is asked as 1.0; allow for rounding
            lit = frac - min(min_sun_fraction, 0.999)
    else:
        frac = segment_fraction(s_clear, s_rad)
        lit = s_clear - _segment_offset(min_sun_fraction) * s_rad
    return Track(
        unix=table.unix,
        sun_az=s_az, sun_el=s_el, earth_az=e_az, earth_el=e_el,
        sun_radius_deg=s_rad,
        earth_radius_deg=np.rad2deg(np.arcsin(EARTH_RADIUS_KM / e_d)),
        sun_clear=s_clear,
        earth_clear=e_el - site.horizon.elevation_at(e_az),
        sun_frac=frac, sun_lit=lit,
    )


def _segment_offset(fraction: float) -> float:
    """Centre clearance, in disc radii, at which ``fraction`` of the disc shows
    above a level horizon (0 for one half, -1 for none, +1 for all)."""
    f = float(fraction)
    if f <= 0.0:
        return -1.0
    if f >= 1.0:
        return 1.0
    if abs(f - 0.5) < 1e-12:
        return 0.0
    lo, hi = -1.0, 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if float(segment_fraction(mid, 1.0)) < f:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def track_at(site: Site, unix_seconds, min_sun_fraction: float = 0.5) -> Track:
    """Uncached evaluation at arbitrary instants (used to refine events)."""
    return track(site, compute_table(unix_seconds), min_sun_fraction)


def sub_point(vec_bf: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Selenographic lat/lon (degrees) directly beneath a body, e.g. the sub-Earth point."""
    v = np.atleast_2d(vec_bf)
    r = np.linalg.norm(v, axis=1)
    lat = np.rad2deg(np.arcsin(v[:, 2] / r))
    lon = np.rad2deg(np.arctan2(v[:, 1], v[:, 0]))
    return lat, lon
