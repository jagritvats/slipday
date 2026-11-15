"""Clicked points on the close-up of the pole: the slope the page gets for them.

A participant saw "too steep" at all 13 touchdown points for every point clicked on the close-up.  These tests pin
what the server really returns for clicked points:
  - the page's click maths (app.js renderPolar().where(), copied here) gives the lat/lon the server measures;
  - the server's slope agrees with an independent slope worked out here from the same LOLA files (own reader, own
    projection, central differences of a bilinear surface instead of the add-on's plane fit);
  - the close-up uses the 5 m and 20 m grids only, never 80 m;
  - some clicked points really are flat enough at all 13 points, and some really are too steep at all 13.
"""
import json
import math
import os

import numpy as np
import pytest

from slipday.addons import safety

ROOT = safety.ROOT
NAMES = [n for n, _l, _g in safety.grids()]
pytestmark = pytest.mark.skipif("ldem_pole_20m" not in NAMES, reason="the LOLA 20 m crop is not installed")

R_KM = 1737.4
HALF_KM, STEP_M, N = 30.0, 500.0, 120          # the close-up and its slip-margin grid (field meta)


def page_click(xk: float, yk: float, snap: bool = True):
    """app.js where(): a click in km on the close-up -> lat, lon (snapped to the 500 m cell when a slip layer is on)."""
    if snap and abs(xk) < HALF_KM and abs(yk) < HALF_KM:
        st = STEP_M / 1000
        col = math.floor((xk + HALF_KM) / st)
        row = math.floor((HALF_KM - yk) / st)
        xk, yk = -HALF_KM + (col + 0.5) * st, HALF_KM - (row + 0.5) * st
    rr = math.hypot(xk, yk)
    lat = round(-(90 - 2 * math.atan(rr / (2 * R_KM)) * 180 / math.pi) * 10000) / 10000
    lon = round(math.atan2(xk, yk) * 180 / math.pi * 1000) / 1000
    return lat, lon


def _grids():
    out = []
    for folder, fn in ((("data", "dem5", "site01"), "ldem_site01_5m_f32.npy"),
                       (("data", "dem5", "site07"), "ldem_site07_5m_f32.npy"),
                       (("data", "dem20"), "ldem_pole_20m_f32.npy"),
                       (("data", "dem"), "ldem_80s_80m_f32.npy")):
        base = os.path.join(ROOT, *folder)
        try:
            with open(os.path.join(base, "dems.json"), encoding="utf-8") as fh:
                e = [d for d in json.load(fh)["dems"] if d["path"].endswith(fn)][0]
            out.append((e["pixel_m"], e["x0_m"], e["y0_m"], np.load(os.path.join(base, fn), mmap_mode="r")))
        except (OSError, IndexError, KeyError):
            continue
    return out


GRIDS = _grids()


def independent_slope(lat: float, lon: float):
    """Slope in degrees on the finest grid that covers the point: central differences of a bilinear surface,
    half-baseline 5 m on 5 m grids and half a cell on coarser ones.  Returns (slope, grid metres)."""
    r = 2 * 1737400.0 * math.tan(math.pi / 4 - abs(math.radians(lat)) / 2)
    x, y = r * math.sin(math.radians(lon)), r * math.cos(math.radians(lon))
    kf = 2 / (1 + math.sin(abs(math.radians(lat))))
    for px, x0, y0, z in GRIDS:
        h = 5.0 if px <= 5 else px / 2

        def at(xx, yy):
            c, rw = (xx - x0) / px, (y0 - yy) / px
            c0, r0 = int(math.floor(c)), int(math.floor(rw))
            if r0 < 0 or c0 < 0 or r0 + 1 >= z.shape[0] or c0 + 1 >= z.shape[1]:
                return None
            fc, fr = c - c0, rw - r0
            q = np.asarray(z[r0:r0 + 2, c0:c0 + 2], dtype=float)
            return (q[0, 0] * (1 - fc) * (1 - fr) + q[0, 1] * fc * (1 - fr) + q[1, 0] * (1 - fc) * fr
                    + q[1, 1] * fc * fr)
        v = [at(x + h, y), at(x - h, y), at(x, y + h), at(x, y - h)]
        if any(t is None for t in v):
            continue
        gx, gy = (v[0] - v[1]) / (2 * h) * kf, (v[2] - v[3]) / (2 * h) * kf
        return math.degrees(math.atan(math.hypot(gx, gy))), px
    return None, None


# clicks in km on the close-up (x right = 90 E, y up = 0 E), measured on 15 Nov 2026
CLICKS = [(-20, 15), (5, -8), (12, 12), (-3, -22), (25, -5), (-10, -10), (2, 2), (-27, 27), (18, -24), (0.4, -6.5)]


def test_clicked_points_match_an_independent_slope():
    app, mine = [], []
    for xk, yk in CLICKS:
        lat, lon = page_click(xk, yk)
        r = safety.site_slopes(lat, lon, 100.0)
        assert r["available"] and r["points_known"] == 13
        for p in r["points"]:
            s, g = independent_slope(p["lat"], p["lon"])
            assert g == p["grid_m"]                           # the same grid is chosen
            app.append(p["slope_deg"])
            mine.append(s)
    app, mine = np.array(app), np.array(mine)
    d = np.abs(app - mine)
    # measured: median 0.36 deg, 90 % within 1.1 deg, correlation 0.995 (two different slope estimators)
    assert np.median(d) < 0.6
    assert np.percentile(d, 90) < 1.6
    assert np.corrcoef(app, mine)[0, 1] > 0.98


def test_close_up_uses_5_and_20_m_only():
    for xk, yk in CLICKS + [(29.75, 29.75), (-29.75, -29.75)]:
        r = safety.site_slopes(*page_click(xk, yk), 100.0)
        assert {p["grid_m"] for p in r["points"]} <= {5.0, 20.0}


def test_not_every_clicked_point_is_too_steep():
    """The participant's "too steep at all 13, everywhere" is not what the server returns."""
    passing = [safety.site_slopes(*page_click(xk, yk), 100.0)["points_passing"] for xk, yk in CLICKS]
    assert 13 in passing                     # flat enough at all 13 (e.g. 3 km W-ish, 22 km towards 180)
    assert 0 in passing                      # and some really are too steep at all 13 (rugged ground near the pole)
    assert len(set(passing)) >= 5
