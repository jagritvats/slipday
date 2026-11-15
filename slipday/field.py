"""Slip-robustness map: what a slip costs at every point of a grid around the south pole.

``scripts/build_field.py`` stores one terrain skyline per grid point (same ray-march as a single
site).  At run time this module evaluates all of them at once for a set of candidate landing
dates and turns the result into per-point statistics: the slip margin from the planned date,
the number of dates that meet a mission's need, and the worst and the median landing date.

The evaluation is vectorised over points.  It follows ``geometry.track`` exactly (same disc
fraction in 15 strips, same Earth rule).  The strips are only evaluated where the solar disc can
straddle the skyline: where the whole disc is above the highest, or below the lowest, of the four
skyline samples its strips can touch, the fraction is 1 or 0 without them.  That shortcut is exact.
``tests/test_round3_real.py`` checks the result against the single-site code, sample by sample.
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import OrderedDict
from typing import Optional

import numpy as np

from . import load as lanes
from .ephem import EARTH_RADIUS_KM, MOON_RADIUS_KM, SUN_RADIUS_KM, available_steps, cached_table, grid_start, iso, parse_utc
from .metrics import STEP_S, Criteria

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELD_DIR = os.environ.get("SLIPDAY_FIELD_DIR", os.path.join(ROOT, "data", "field"))
EL_SCALE = 0.002            # degrees per stored int16 unit
N_STRIPS = 15
CHUNK = 96
THREADS = max(1, min(4, int(os.environ.get("SLIPDAY_FIELD_THREADS", "1"))))
STRIDE = max(1, int(os.environ.get("SLIPDAY_FIELD_STRIDE", "1")))

_lock = threading.Lock()
_state: dict = {"loaded": False, "field": None}
_results: "OrderedDict[tuple, dict]" = OrderedDict()
_compute_lock = threading.Lock()


def load() -> Optional[dict]:
    """The stored skyline field, or None when it has not been built on this installation."""
    with _lock:
        if _state["loaded"]:
            return _state["field"]
        _state["loaded"] = True
        meta_path = os.path.join(FIELD_DIR, "pole_field.json")
        try:
            with open(meta_path) as fh:
                meta = json.load(fh)
            pts = np.load(os.path.join(FIELD_DIR, "pole_points.npz"))
            el = np.load(os.path.join(FIELD_DIR, "pole_el_i16.npy"), mmap_mode="r")
            lat, lon, h = pts["lat"], pts["lon"], pts["height_m"]
            if STRIDE > 1:                       # a slow host can evaluate every 2nd (3rd, ...) point each way
                n = meta["n"]
                idx = np.arange(n)[STRIDE // 2::STRIDE]
                keep = (idx[:, None] * n + idx[None, :]).ravel()
                lat, lon, h, el = lat[keep], lon[keep], h[keep], np.ascontiguousarray(el[keep])
                meta = dict(meta, n=len(idx), step_m=meta["step_m"] * STRIDE, points=len(keep), thinned_by=STRIDE)
            _state["field"] = {"meta": meta, "lat": lat, "lon": lon, "height_m": h, "el": el}
        except (OSError, ValueError, KeyError):
            _state["field"] = None
        return _state["field"]


def reload() -> None:
    with _lock:
        _state["loaded"] = False
        _results.clear()


def _interp(el: np.ndarray, rows: np.ndarray, az: np.ndarray) -> np.ndarray:
    """Skyline elevation (deg) at azimuth ``az`` for each row index; ``el`` is (points, n_az)."""
    n_az = el.shape[1]
    x = np.mod(az, 360.0) * (n_az / 360.0)
    i0 = np.floor(x).astype(np.int64)
    f = x - i0
    i0 %= n_az
    i1 = (i0 + 1) % n_az
    return el[rows, i0] * (1.0 - f) + el[rows, i1] * f


def _azel(vec: np.ndarray, east: np.ndarray, north: np.ndarray, up: np.ndarray):
    """Azimuth, elevation (deg) and distance (km) of a body for every (point, time).

    ``vec`` is (times, 3) in the Moon-fixed frame; the observer sits at R * up, which is
    perpendicular to east and north, so the topocentric components are plain dot products.
    """
    e = east @ vec.T
    n = north @ vec.T
    u = up @ vec.T - MOON_RADIUS_KM
    dist = np.sqrt(e * e + n * n + u * u)
    el = np.rad2deg(np.arcsin(np.clip(u / dist, -1.0, 1.0)))
    az = np.mod(np.rad2deg(np.arctan2(e, n)), 360.0)
    return az, el, dist


def evaluate_points(lat: np.ndarray, lon: np.ndarray, el_deg: np.ndarray, table, crit: Criteria,
                    mask_deg: float = 0.0):
    """Sun-up and Earth-up flags, (points, times), for points with terrain skylines ``el_deg``."""
    la, lo = np.deg2rad(lat), np.deg2rad(lon)
    up = np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=1)
    east = np.stack([-np.sin(lo), np.cos(lo), np.zeros_like(lo)], axis=1)
    north = np.stack([-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)], axis=1)
    el = np.maximum(el_deg, mask_deg) if mask_deg else el_deg
    rows = np.arange(len(lat))[:, None]

    s_az, s_el, s_d = _azel(table.sun, east, north, up)
    s_rad = np.rad2deg(np.arcsin(SUN_RADIUS_KM / s_d))
    f0 = crit.min_sun_fraction
    # Highest and lowest skyline sample among the four a disc centred between samples i and i+1 can
    # touch (its strips reach at most half a sample either side of the centre).
    hi = np.maximum(np.maximum(np.roll(el, 1, axis=1), el), np.maximum(np.roll(el, -1, axis=1), np.roll(el, -2, axis=1)))
    lo = np.minimum(np.minimum(np.roll(el, 1, axis=1), el), np.minimum(np.roll(el, -1, axis=1), np.roll(el, -2, axis=1)))
    n_az = el.shape[1]
    i0 = np.floor(s_az * (n_az / 360.0)).astype(np.int64) % n_az
    lit = (s_el - s_rad) > hi[rows, i0]                     # whole disc above everything it can touch
    amb = ~lit & ((s_el + s_rad) >= lo[rows, i0])           # not wholly below either: needs the strips
    if amb.any():
        r_idx, t_idx = np.nonzero(amb)
        az, e, rad = s_az[r_idx, t_idx], s_el[r_idx, t_idx], s_rad[r_idx, t_idx]
        u = -1.0 + (2.0 * np.arange(N_STRIPS) + 1.0) / N_STRIPS
        half = np.sqrt(1.0 - u * u)
        cos_el = np.maximum(np.cos(np.deg2rad(e)), 0.2)
        strip_az = az[:, None] + (u[None, :] * rad[:, None]) / cos_el[:, None]
        h = _interp(el, r_idx[:, None], strip_az)
        top = e[:, None] + half[None, :] * rad[:, None]
        full = 2.0 * half[None, :] * rad[:, None]
        frac = np.clip(top - h, 0.0, full).sum(axis=1) / full.sum(axis=1)
        lit[r_idx, t_idx] = (frac > 0.0) if f0 <= 0.0 else (frac - min(f0, 0.999) > 0.0)
    if crit.min_sun_el > -90:
        lit &= s_el >= crit.min_sun_el

    e_az, e_el, _ = _azel(table.earth, east, north, up)
    earth = (e_el - _interp(el, rows, e_az)) > crit.earth_margin_deg
    if crit.min_earth_el > -90:
        earth &= e_el >= crit.min_earth_el
    if crit.stations:                                   # the same for every point: a ground station sees the Moon or not
        from .metrics import station_ok
        earth &= station_ok(table.unix, crit)[None, :]
    return lit, earth


# The map the page opens on (landing 18 Nov 2026, 60 dates, 14 days, stated rules) is kept in memory when other
# maps are asked for, so that a first visit never waits behind its recomputation (pass 3, review: one first visit
# under load took 62 s to network idle because the opening map had dropped out of memory).
OPENING_START_UNIX = 1794960000          # 2026-11-18T00:00:00Z


def pinned(key) -> bool:
    """True for the cache keys of the opening map (either Earth rule, no extra mask or margin)."""
    return (key[0] == OPENING_START_UNIX and key[1] == 60 and key[2] == 24 and key[3] == 336 and key[4] == 0.5
            and key[5] <= -90 and key[6] <= -90 and key[7] == 0 and key[8] == 0)


def evict(cache: "OrderedDict", keep: int) -> None:
    """Drop the oldest entries beyond ``keep``, never the opening map's."""
    while len(cache) > keep:
        old = next((k for k in cache if not pinned(k)), None)
        if old is None:
            break
        cache.pop(old)


def _key(start_unix, n_dates, stride, window_h, crit: Criteria, mask_deg):
    return (int(start_unix), int(n_dates), int(stride), int(window_h), crit.min_sun_fraction, crit.min_sun_el,
            crit.min_earth_el, crit.earth_margin_deg, float(mask_deg), bool(crit.stations))


def per_date(start, n_dates: int = 60, date_step_hours: int = 24, window_days: float = 14.0,
             crit: Criteria = Criteria(), mask_deg: float = 0.0) -> Optional[dict]:
    """Sunlit, Earth-contact and usable hours after each candidate landing date, for every field point.

    Returns arrays of shape (points, dates) or None when no field is installed.  Results for the
    last few parameter sets are kept in memory (about 7 MB each).
    """
    fld = load()
    if fld is None:
        return None
    s = grid_start(parse_utc(start), STEP_S)
    w = int(round(window_days * 24))
    stride = int(date_step_hours)
    key = _key(s, n_dates, stride, w, crit, mask_deg)
    if _results.get(key) is None:
        lanes.require_cold()                    # checked before the lock, so a light request never waits on it
    with _compute_lock:                        # one evaluation at a time; later callers reuse the result
        hit = _results.get(key)
        if hit is not None:
            _results.move_to_end(key)
            return hit
        lanes.require_cold()                    # a new evaluation of every map point takes seconds: cold lane
        t0 = time.time()
        wanted = (n_dates - 1) * stride + w + 1
        n = min(wanted, available_steps(s, STEP_S))
        if n < w + 2:
            raise ValueError("time outside the supported ephemeris span (1900-01-01 to 2050-01-01)")
        table = cached_table(s, n, STEP_S)
        starts = np.arange(n_dates) * stride
        valid = starts + w <= n - 1
        sv = starts[valid]
        npts = len(fld["lat"])
        out = {k: np.zeros((npts, n_dates), dtype=np.int16) for k in ("sunlit", "earth", "total")}
        out["sun0"] = np.zeros((npts, n_dates), dtype=bool)
        out["earth0"] = np.zeros((npts, n_dates), dtype=bool)
        el_all = fld["el"]

        def block(i0: int) -> None:
            sl = slice(i0, min(i0 + CHUNK, npts))
            el = np.asarray(el_all[sl], dtype=np.float32) * np.float32(EL_SCALE)
            lit, earth = evaluate_points(fld["lat"][sl], fld["lon"][sl], el, table, crit, mask_deg)
            for name, flags in (("sunlit", lit), ("earth", earth), ("total", lit & earth)):
                cs = np.concatenate([np.zeros((flags.shape[0], 1), dtype=np.int32),
                                     np.cumsum(flags, axis=1, dtype=np.int32)], axis=1)
                out[name][sl][:, valid] = cs[:, sv + w] - cs[:, sv]
            out["sun0"][sl][:, valid] = lit[:, sv]
            out["earth0"][sl][:, valid] = earth[:, sv]

        if THREADS > 1:                         # NumPy releases the GIL inside its loops
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(THREADS) as ex:
                list(ex.map(block, range(0, npts, CHUNK)))
        else:
            for i0 in range(0, npts, CHUNK):
                block(i0)
        out.update({"valid": valid, "dates": [iso(s + int(k) * 3600) for k in starts], "window_hours": w,
                    "seconds": round(time.time() - t0, 2), "start_utc": iso(s)})
        _results[key] = out
        evict(_results, 3)
        return out


def statistics(pd: dict, need_sun_h: float, need_earth_h: float, sun_at_touchdown: bool = True,
               earth_at_touchdown: bool = True) -> dict:
    """Per-point numbers for the map, from ``per_date`` output and a mission need."""
    valid = pd["valid"]
    sun, earth, total = pd["sunlit"][:, valid], pd["earth"][:, valid], pd["total"][:, valid]
    ok = (sun >= need_sun_h) & (earth >= need_earth_h)
    if sun_at_touchdown:
        ok &= pd["sun0"][:, valid]
    if earth_at_touchdown:
        ok &= pd["earth0"][:, valid]
    nd = ok.shape[1]
    bad = ~ok
    first_bad = np.where(bad.any(axis=1), np.argmax(bad, axis=1), nd)
    return {
        "margin": (first_bad - 1).astype(np.int16),            # -1: the planned date itself fails
        "good": ok.sum(axis=1).astype(np.int16),
        "worst_sun": sun.min(axis=1), "median_sun": np.median(sun, axis=1).astype(np.int16),
        "worst_total": total.min(axis=1), "median_total": np.median(total, axis=1).astype(np.int16),
        "dates": int(nd),
    }
