"""How sure is the answer?  Landing scatter, a coarser grid and a finer near-field sampling.

A single point on an 80 m grid is a fragile thing near the lunar south pole: on a crest a shift
of 20 to 40 m moves the sunlit share by 1 to 4 points and the longest darkness by tens of hours
(measured; see REALDATA.md).  Instead of hiding that, every slip-grid cell and every mission
verdict here is computed for a small ensemble of the same site:

  target    the stated point on the finest grid that covers it
  scatter   12 more points around it: 8 on a circle of ``scatter_m`` (default 100 m) and 4 at half
            that distance, standing in for where a lander actually comes down
  coarse    the stated point with the finest grid left out (240 m instead of 80 m)
  near      the stated point with the first ray sample at half a grid spacing instead of one

The spread across ``scatter`` is the landing-dispersion band; ``coarse`` and ``near`` say whether
the answer depends on the elevation grid or on the sampling convention.  A verdict is only
"yes" when every member agrees.
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

from .dem import MOON_RADIUS_M
from .geometry import Site
from .ephem import available_steps, cached_table, grid_start, iso, parse_utc
from .geometry import track
from .metrics import STEP_S, Criteria, slip_grid, station_ok, sun_up
from .sites import horizon_for, smooth_twin
from .terrain import destination

# (fraction of the scatter radius, bearing in degrees)
SCATTER_LAYOUT = [(1.0, b) for b in range(0, 360, 45)] + [(0.5, b) for b in (22.5, 112.5, 202.5, 292.5)]
METRICS = ("total", "continuous", "sunlit", "earth")


def scatter_points(lat: float, lon: float, radius_m: float) -> list[tuple[float, float]]:
    """The 12 points of the landing-scatter pattern around (lat, lon)."""
    out = []
    for frac, bearing in SCATTER_LAYOUT:
        la, lo = destination(lat, lon, np.deg2rad(bearing), np.array(frac * radius_m / MOON_RADIUS_M))
        lo = ((float(lo) + 180.0) % 360.0) - 180.0
        out.append((round(float(la), 5), round(lo, 5)))
    return out


def effective_scatter_m(site: Site, scatter_m: float) -> float:
    """The scatter radius actually used: never less than one cell of the grid under the site.

    Points closer together than a grid cell sit on the same bilinear patch and see almost the same
    skyline, so a 100 m scatter on a 240 m grid cannot disagree with itself and the "how sure" check
    turns overconfident (measured: two ridge sites read "yes" on the 240 m grid where the 80 m grid
    says "not sure").  The pattern is therefore spread to at least one cell, and the card says so.
    """
    if scatter_m <= 0 or not site.horizon.is_terrain:
        return float(scatter_m)
    cell = float(np.ceil(float(site.horizon.meta.get("resolution_m") or 0.0)))      # whole metres: 80, 240, 474, 1896
    return float(max(scatter_m, cell))


def ensemble(site: Site, mask_deg: float, mast_m: float, scatter_m: float) -> dict:
    """Member sites for one target.  ``site`` must already carry its terrain horizon.

    ``scatter_m`` is the radius asked for; ``members["scatter_m"]`` is the one used (see
    ``effective_scatter_m``)."""
    used = effective_scatter_m(site, scatter_m)
    members = {"target": site, "scatter": [], "coarse": None, "near": None,
               "scatter_m": used, "scatter_requested_m": float(scatter_m)}
    if not site.horizon.is_terrain:
        return members
    if used > 0:
        for la, lo in scatter_points(site.lat, site.lon, used):
            hz = horizon_for(la, lo, mask_deg, mast_m, True)
            if hz.is_terrain:
                members["scatter"].append(Site(site.name, la, lo, horizon=hz))
    hz = horizon_for(site.lat, site.lon, mask_deg, mast_m, True, variant="drop1")
    if hz.is_terrain:
        members["coarse"] = Site(site.name, site.lat, site.lon, horizon=hz)
    hz = horizon_for(site.lat, site.lon, mask_deg, mast_m, True, variant="near")
    if hz.is_terrain:
        members["near"] = Site(site.name, site.lat, site.lon, horizon=hz)
    return members


def _flat(members: dict) -> tuple[list[Site], dict]:
    sites = [members["target"]] + list(members["scatter"])
    index = {"scatter": (0, len(sites))}           # target counts as one of the scatter points
    for k in ("coarse", "near"):
        if members[k] is not None:
            index[k] = len(sites)
            sites.append(members[k])
    return sites, index


def _stack(rows: Sequence[dict], key: str) -> np.ndarray:
    """(members, dates) float array with NaN where a cell was not computed."""
    return np.array([[np.nan if v is None else float(v) for v in r[key]] for r in rows], dtype=float)


def _lst(a: np.ndarray, cast=int) -> list:
    return [None if not np.isfinite(v) else cast(v) for v in a]


def banded_slip_grid(targets: Sequence[Site], start, n_dates: int, date_step_hours: int, window_days: float,
                     crit: Criteria, mask_deg: float, mast_m: float, scatter_m: float) -> tuple[dict, list]:
    """The slip grid with, per row, the spread over the landing scatter and the coarse/near variants.

    Returns the grid (rows as in ``metrics.slip_grid`` plus ``band``) and, per row, the raw member
    rows for callers that need more than the band (the mission card).
    """
    all_sites: list[Site] = []
    spans = []
    for s in targets:
        ens = ensemble(s, mask_deg, mast_m, scatter_m)
        sites, index = _flat(ens)
        index["scatter_m"] = ens["scatter_m"]
        spans.append((len(all_sites), len(sites), index))
        all_sites.extend(sites)
    grid = slip_grid(all_sites, start, n_dates, date_step_hours, window_days, crit)
    rows, raw = [], []
    for (i0, n, index), s in zip(spans, targets):
        mine = grid["rows"][i0:i0 + n]
        row = mine[0]
        a, b = index["scatter"]
        if s.horizon.is_terrain and (b - a > 1 or "coarse" in index or "near" in index):
            band = {"points": b - a, "scatter_m": index["scatter_m"] if b - a > 1 else 0.0,
                    "scatter_requested_m": float(scatter_m)}
            for key in METRICS:
                m = _stack(mine[a:b], key)
                band[key] = {"min": _lst(m.min(axis=0)), "max": _lst(m.max(axis=0)),
                             "median": _lst(np.median(m, axis=0), lambda v: round(float(v), 1))}
                for k in ("coarse", "near"):
                    if k in index:
                        band[key][k] = mine[index[k]][key]
            for k in ("coarse", "near"):
                if k in index:
                    band[k + "_horizon"] = mine[index[k]]["horizon"]
            row["band"] = band
        rows.append(row)
        raw.append({"rows": mine, "index": index})
    grid["rows"] = rows
    return grid, raw


# --------------------------------------------------------------------------- mission card

def _passes(row: dict, need_sun: float, need_earth: float, sun_at_td: bool, earth_at_td: bool) -> np.ndarray:
    sun = np.array([np.nan if v is None else v for v in row["sunlit"]], dtype=float)
    earth = np.array([np.nan if v is None else v for v in row["earth"]], dtype=float)
    ok = (sun >= need_sun) & (earth >= need_earth)
    if sun_at_td:
        ok &= np.array([bool(v) for v in row["sun_up_at_landing"]])
    if earth_at_td:
        ok &= np.array([bool(v) for v in row["earth_up_at_landing"]])
    return ok


def _reasons(row: dict, i: int, need_sun: float, need_earth: float, sun_at_td: bool, earth_at_td: bool) -> list[str]:
    out = []
    if row["sunlit"][i] is None:
        return ["past the end of the ephemeris (2050)"]
    if sun_at_td and not row["sun_up_at_landing"][i]:
        out.append(f"the Sun is behind the skyline at touchdown ({abs(row['sun_clear_at_landing'][i]):.1f} deg under it)")
    if earth_at_td and not row["earth_up_at_landing"][i]:
        out.append(f"the Earth is behind the skyline at touchdown ({abs(row['earth_clear_at_landing'][i]):.1f} deg under it)")
    if row["sunlit"][i] < need_sun:
        out.append(f"only {row['sunlit'][i]} sunlit hours of the {need_sun:g} needed")
    if row["earth"][i] < need_earth:
        out.append(f"only {row['earth'][i]} hours of Earth contact of the {need_earth:g} needed")
    return out


_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _day(iso_utc: str) -> str:
    """'18 Nov 2026', with the hour when the landing is not at 00:00 UTC."""
    d = f"{int(iso_utc[8:10])} {_MON[int(iso_utc[5:7]) - 1]} {iso_utc[:4]}"
    return d if iso_utc.endswith("T00:00:00Z") else d + f" {iso_utc[11:16]} UTC"


def mission_card(site: Site, landing, need_sun_h: float, need_earth_h: float, window_days: float, crit: Criteria,
                 mask_deg: float, mast_m: float, scatter_m: float = 100.0, slip_days: int = 60,
                 sun_at_touchdown: bool = True, earth_at_touchdown: bool = True) -> dict:
    """A plain yes / not sure / no for one site, landing date and requirement, for every day of slip.

    "yes" needs every ensemble member to pass, "no" needs every member to fail, anything else is
    "not sure".  ``slip_margin_days`` is the longest slip that keeps a "yes" on every day up to it.
    """
    grid, raw = banded_slip_grid([site], landing, slip_days, 24, window_days, crit, mask_deg, mast_m, scatter_m)
    row, mine, index = grid["rows"][0], raw[0]["rows"], raw[0]["index"]
    asked_m = float(scatter_m)
    scatter_m = float(index.get("scatter_m", scatter_m))     # the radius used: at least one grid cell
    args = (need_sun_h, need_earth_h, sun_at_touchdown, earth_at_touchdown)
    ok = np.array([_passes(r, *args) for r in mine])                    # (members, dates)
    computed = np.array([v is not None for v in row["sunlit"]])
    a, b = index["scatter"]
    n_pts = b - a
    pts_ok = ok[a:b].sum(axis=0)
    all_ok, none_ok = ok.all(axis=0), ~ok.any(axis=0)
    verdict = np.where(~computed, "n/a", np.where(all_ok, "yes", np.where(none_ok, "no", "not sure")))
    smooth = slip_grid([smooth_twin(site, mask_deg)], landing, slip_days, 24, window_days, crit)["rows"][0]
    smooth_ok = _passes(smooth, *args)

    days = []
    for i, d in enumerate(grid["dates"]):
        entry = {"slip_days": i, "landing_utc": d, "verdict": str(verdict[i]),
                 "sunlit_h": row["sunlit"][i], "earth_h": row["earth"][i], "usable_h": row["total"][i],
                 "target_passes": bool(ok[0, i]), "points_passing": int(pts_ok[i]), "points": n_pts,
                 "smooth_sphere_passes": bool(smooth_ok[i]),
                 "reasons": [] if ok[0, i] else _reasons(row, i, *args)}
        if "band" in row:
            bd = row["band"]
            entry["sunlit_range_h"] = [bd["sunlit"]["min"][i], bd["sunlit"]["max"][i]]
            entry["earth_range_h"] = [bd["earth"]["min"][i], bd["earth"]["max"][i]]
            for k in ("coarse", "near"):
                if k in index:
                    entry[k + "_passes"] = bool(ok[index[k], i])
                    entry[k + "_sunlit_h"] = mine[index[k]]["sunlit"][i]
                    entry[k + "_earth_h"] = mine[index[k]]["earth"][i]
        if verdict[i] == "not sure":
            why = []
            if pts_ok[i] < n_pts and n_pts > 1:
                why.append(f"{int(pts_ok[i])} of {n_pts} points within {scatter_m:g} m pass")
            for k, label in (("coarse", "the coarser grid"), ("near", "the finer near-field sampling")):
                if k in index and bool(ok[index[k], i]) != bool(ok[0, i]):
                    why.append(f"{label} gives the opposite answer")
            entry["unsure_because"] = why
        days.append(entry)

    margin = -1
    for i in range(len(days)):
        if verdict[i] != "yes":
            break
        margin = i
    # the next good dates after the first day that is not a clear yes
    first_bad = margin + 1
    next_good = [days[i]["landing_utc"] for i in range(first_bad, len(days)) if verdict[i] == "yes"][:3]
    target_margin = -1
    for i in range(len(days)):
        if not ok[0, i] or not computed[i]:
            break
        target_margin = i

    d0 = days[0]
    v0 = d0["verdict"]
    head = {"yes": "Yes", "no": "No", "not sure": "Not sure", "n/a": "Not computed"}[v0]
    where = f"{site.name} on {_day(d0['landing_utc'])}"
    need = (f"{need_sun_h:g} sunlit hours and {need_earth_h:g} hours of Earth contact in the first "
            f"{window_days:g} days" + (", landing in sunlight" if sun_at_touchdown else "")
            + (", with the Earth in view at touchdown" if earth_at_touchdown else ""))
    sentences = []
    if v0 == "n/a":
        sentences.append("That landing date runs past the end of the ephemeris (2050).")
    else:
        got = f"{d0['sunlit_h']} sunlit hours and {d0['earth_h']} hours of Earth contact"
        if v0 == "yes":
            sentences.append(f"A landing at {where} gives {got}; the mission needs {need}.")
        elif v0 == "no":
            sentences.append(f"A landing at {where} does not meet the need ({need}): " + "; ".join(d0["reasons"] or
                             ["the stated point passes, but no other member of the check does"]) + ".")
        else:
            sentences.append(f"A landing at {where} gives {got} at the stated point, but the answer is not robust: "
                             + "; ".join(d0.get("unsure_because") or ["members of the check disagree"]) + ".")
    if margin >= 0:
        if margin + 1 < len(days):
            nxt = days[margin + 1]
            why = "; ".join(nxt["reasons"] or nxt.get("unsure_because") or ["the check no longer agrees"])
            verb = "fails" if nxt["verdict"] == "no" else "is no longer a clear yes"
            if margin == 0:
                sentences.append(f"The plan has no slip margin: a slip of 1 day {verb}: {why}.")
            else:
                sentences.append(f"The plan survives a slip of up to {margin} day{'s' if margin != 1 else ''}. "
                                 f"A slip of {margin + 1} days {verb}: {why}.")
            lost = d0["sunlit_h"] - days[margin]["sunlit_h"] if margin else 0
            if margin and lost:
                sentences.append(f"Using the whole margin costs {lost} sunlit hours "
                                 f"({d0['sunlit_h']} down to {days[margin]['sunlit_h']}).")
        else:
            sentences.append(f"The plan holds for every one of the {len(days)} landing dates checked.")
    if next_good:
        lead = "After that the next good landing dates are " if margin >= 0 else "The next good landing dates are "
        sentences.append(lead + ", ".join(_day(x) for x in next_good) + ".")
    elif margin + 1 < len(days):
        sentences.append(f"No {'other ' if margin >= 0 else ''}landing date in the {len(days)} days checked is a clear yes.")

    widened = bool(n_pts > 1 and scatter_m > asked_m + 1e-9)
    res_m = float(site.horizon.meta.get("resolution_m") or 0.0) if site.horizon.is_terrain else 0.0
    sure = {"points": n_pts, "scatter_m": scatter_m if n_pts > 1 else 0.0,
            "scatter_requested_m": asked_m, "scatter_widened": widened, "grid_resolution_m": res_m,
            "points_passing": int(pts_ok[0]), "coarse_passes": bool(ok[index["coarse"], 0]) if "coarse" in index else None,
            "near_passes": bool(ok[index["near"], 0]) if "near" in index else None,
            "coarse_label": (row.get("band", {}).get("coarse_horizon") or {}).get("dem_label"),
            "terrain": site.horizon.is_terrain, "validated": bool(site.horizon.meta.get("validated", False)),
            "smooth_sphere_passes": bool(smooth_ok[0])}
    if not site.horizon.is_terrain:
        sure["text"] = "No terrain data covers this site: the answer is for a smooth sphere and has no spread."
    else:
        bits = [f"{int(pts_ok[0])} of {n_pts} points within {scatter_m:g} m of the target pass"] if n_pts > 1 else []
        if "coarse" in index:
            bits.append(f"the coarser grid ({str(sure['coarse_label']).split(';')[0]}) says "
                        f"{'yes' if sure['coarse_passes'] else 'no'}")
        if "near" in index:
            bits.append(f"finer near-field sampling says {'yes' if sure['near_passes'] else 'no'}")
        sure["text"] = "How sure: " + "; ".join(bits) + "."
        if n_pts > 1:
            # the verdict is conditional on this radius; say so next to it, not in a footnote
            sure["assumes"] = (f"This answer assumes the lander comes down within {scatter_m:g} m of the target. "
                               "A wider miss can change it: see the landing-circle rows below.")
        if widened:
            sure["text"] += (f" The scatter was widened from {asked_m:g} m to {scatter_m:g} m, one cell of this "
                             f"{np.ceil(res_m):.0f} m grid: points closer together than a cell cannot disagree, "
                             "which would make the check look surer than it is.")
        if not sure["validated"]:
            sure["text"] += " This grid is outside the area checked against the LOLA team's maps."
    return {
        "site": {"name": site.name, "lat": site.lat, "lon": site.lon}, "horizon": site.horizon.describe(),
        "landing_utc": d0["landing_utc"], "window_days": window_days,
        "need": {"sunlit_h": need_sun_h, "earth_h": need_earth_h, "sun_at_touchdown": sun_at_touchdown,
                 "earth_at_touchdown": earth_at_touchdown, "text": need},
        "criteria": crit.describe(), "verdict": v0, "headline": head, "sentences": sentences, "sure": sure,
        "slip_margin_days": margin, "target_only_margin_days": target_margin, "next_good_dates": next_good,
        "days": days, "truncated_at_ephemeris_end": grid["truncated_at_ephemeris_end"],
        "smooth_sphere": {"verdict_planned": "yes" if smooth_ok[0] else "no",
                          "good_dates": int(smooth_ok.sum()), "label": "smooth sphere (no terrain)"},
        "good_dates": int((verdict == "yes").sum()), "unsure_dates": int((verdict == "not sure").sum()),
    }


# --------------------------------------------------------------------------- landing circle

# (radius in m, number of points, first bearing in degrees).  The 100 m ring and four of the 50 m
# points are the mission card's own scatter points, so their skylines are already cached.
RING_LAYOUT = [(50.0, 8, 22.5), (100.0, 8, 0.0), (150.0, 8, 22.5), (250.0, 12, 0.0), (375.0, 12, 15.0),
               (500.0, 12, 0.0), (750.0, 16, 11.25), (1000.0, 16, 0.0)]
LANDING_CIRCLES = [
    {"id": "100m", "radius_m": 100.0, "label": "within 100 m", "note": "precision landing"},
    {"id": "250m", "radius_m": 250.0, "label": "within 250 m", "note": "IM-2 came down about 250 m from its target"},
    {"id": "500m", "radius_m": 500.0, "label": "within 500 m", "note": ""},
    {"id": "1km", "radius_m": 1000.0, "label": "within 1 km", "note": "no precision landing"},
]
CIRCLE_ASSUMPTION = ("Each figure is the share of a landing circle, with touchdown equally likely anywhere inside it, "
                     "where the plan meets the need. It is a count over sampled touchdown points on this elevation "
                     "grid, not a dispersion model of any lander, and the elevation data are not perturbed.")
# Sampling range: the share is a count over a few dozen touchdown points, so it moves by several points with
# the choice of points (the local review counted 55 % on 68 points where 37 points gave 62 %).  The range
# printed beside each share is the 5th to 95th percentile of the same count over BOOT_N resamplings of the
# touchdown points, drawn with replacement ring by ring from a fixed seed, so the figure is reproducible.
BOOT_N = 400
BOOT_SEED = 20261114
RANGE_NOTE = ("Range: 5th to 95th percentile of the same count over %d resamplings of the touchdown points (with "
              "replacement, ring by ring). It says how far the figure moves with the choice of sampled points, "
              "not how uncertain the terrain is." % BOOT_N)


def _boot_ring_means(ok: np.ndarray, rings: list, rng: np.random.Generator) -> list[np.ndarray]:
    """Per ring: (BOOT_N, dates) pass shares of resampled ring points."""
    out = []
    for _, a, b in rings:
        n = b - a
        pick = rng.integers(0, n, size=(BOOT_N, n))
        out.append(ok[a:b].astype(float)[pick].mean(axis=1))
    return out


def landing_circles(site: Site, landing, need_sun_h: float, need_earth_h: float, window_days: float, crit: Criteria,
                    mask_deg: float, mast_m: float, slip_days: int = 60, sun_at_touchdown: bool = True,
                    earth_at_touchdown: bool = True) -> dict:
    """Share of a landing circle in which the plan still works, for every day of slip and four circle sizes.

    Touchdown points sit on rings around the target (``RING_LAYOUT``); each ring stands for the annulus
    between the mid-radii to its neighbours, weighted by area, so the figure is an area share of the
    circle.  Rings closer to the target than half a grid cell are left out (they sit on the target's own
    interpolated patch), and a circle smaller than one cell is reported as not resolvable on that grid.
    """
    if not site.horizon.is_terrain:
        return {"available": False, "reason": "no terrain data covers this site, so there is nothing to scatter over"}
    res = float(site.horizon.meta.get("resolution_m") or 0.0)
    pts: list[Site] = [site]
    rings = []                                             # (radius, first index, end index)
    for radius, n, b0 in RING_LAYOUT:
        if radius < res / 2.0:
            continue
        i0 = len(pts)
        for k in range(n):
            la, lo = destination(site.lat, site.lon, np.deg2rad(b0 + k * 360.0 / n), np.array(radius / MOON_RADIUS_M))
            lo = ((float(lo) + 180.0) % 360.0) - 180.0
            la, lo = round(float(la), 5), round(lo, 5)
            hz = horizon_for(la, lo, mask_deg, mast_m, True)
            if hz.is_terrain:
                pts.append(Site(site.name, la, lo, horizon=hz))
        if len(pts) > i0:
            rings.append((radius, i0, len(pts)))
    grid = slip_grid(pts, landing, slip_days, 24, window_days, crit)
    ok = np.array([_passes(r, need_sun_h, need_earth_h, sun_at_touchdown, earth_at_touchdown) for r in grid["rows"]])
    computed = np.array([v is not None for v in grid["rows"][0]["sunlit"]])
    boot = _boot_ring_means(ok, rings, np.random.default_rng(BOOT_SEED))
    classes = []
    for c in LANDING_CIRCLES:
        big = c["radius_m"]
        entry = {"id": c["id"], "radius_m": big, "label": c["label"], "note": c["note"]}
        use = [r for r in rings if r[0] <= big + 1e-9]
        if big < res or not use:
            entry.update({"resolvable": False, "points": 1,
                          "why": f"smaller than one {np.ceil(res):.0f} m cell of the elevation grid under this site"})
            classes.append(entry)
            continue
        radii = [0.0] + [r[0] for r in use]
        edge = [0.0] + [(radii[i] + radii[i + 1]) / 2.0 for i in range(len(radii) - 1)] + [big]
        w = np.array([edge[i + 1] ** 2 - edge[i] ** 2 for i in range(len(radii))])
        w = w / w.sum()
        share = w[0] * ok[0].astype(float)
        for wi, (_, a, b) in zip(w[1:], use):
            share = share + wi * ok[a:b].mean(axis=0)
        pct = np.round(share * 100.0, 1)
        bs = w[0] * ok[0].astype(float)[None, :]
        for wi, ring in zip(w[1:], use):
            bs = bs + wi * boot[rings.index(ring)]
        lo_pct, hi_pct = np.round(np.percentile(bs * 100.0, [5, 95], axis=0), 1)
        margin = -1
        for i in range(len(pct)):
            if not computed[i] or pct[i] < 90.0:
                break
            margin = i
        entry.update({"resolvable": True, "points": 1 + sum(b - a for _, a, b in use),
                      "share_pct": [None if not computed[i] else float(pct[i]) for i in range(len(pct))],
                      "planned_pct": float(pct[0]) if computed[0] else None,
                      "range_lo_pct": [None if not computed[i] else float(lo_pct[i]) for i in range(len(pct))],
                      "range_hi_pct": [None if not computed[i] else float(hi_pct[i]) for i in range(len(pct))],
                      "planned_range_pct": [float(lo_pct[0]), float(hi_pct[0])] if computed[0] else None,
                      "margin_90_days": margin, "dates_at_90": int(((pct >= 90.0) & computed).sum())})
        classes.append(entry)
    return {"available": True, "site": {"name": site.name, "lat": site.lat, "lon": site.lon},
            "horizon": site.horizon.describe(), "landing_utc": grid["dates"][0], "dates": grid["dates"],
            "grid_resolution_m": res, "points": len(pts), "classes": classes, "assumption": CIRCLE_ASSUMPTION,
            "range_note": RANGE_NOTE, "threshold_pct": 90.0}


# --------------------------------------------------------------------------- chance by lander class

# Rings beyond the landing circles, for dispersions wider than 1 km.
OUTER_RINGS = [(1500.0, 16, 11.25), (2000.0, 16, 0.0), (2500.0, 16, 11.25)]
# ASSUMED dispersions.  None of these is a model of a named lander: each is a two-dimensional Gaussian whose size
# is taken from one public figure, quoted under "basis".  sigma_major / sigma_minor are the standard deviations
# along and across the long axis; about 99 % of touchdowns fall within three of them.
LANDER_CLASSES = [
    {"id": "precision", "label": "precision lander", "sigma_major_m": 33.0, "sigma_minor_m": 33.0,
     "figure": "pinpoint landing within an accuracy of 100 m", "source": "JAXA press release, 25 Jan 2024",
     "source_url": "https://global.jaxa.jp/press/2024/01/20240125-1_e.html",
     "basis": "ASSUMED: 99 % of touchdowns within 100 m. The figure: JAXA calls \"pinpoint landing within an accuracy of "
              "100m\" the main mission of SLIM, and reports touchdown \"approximately 55m east of the original target "
              "landing site\" (JAXA press release, 25 Jan 2024, read 15 Nov 2026). Treating 100 m as the 99 % radius "
              "of a circular Gaussian is this project's choice."},
    {"id": "clps", "label": "CLPS-class lander", "sigma_major_m": 250.0, "sigma_minor_m": 250.0,
     "figure": "one landing about 820 feet (250 m) from its intended site", "source": "NASA news release, 7 Mar 2025",
     "source_url": "https://www.nasa.gov/news-release/nasa-receives-some-data-before-intuitive-machines-ends-lunar-mission/",
     "basis": "ASSUMED: one standard deviation of 250 m. The figure: NASA reports IM-2 \"on its side about 820 feet from "
              "the intended landing site, Mons Mouton\" (NASA news release, 7 Mar 2025, read 15 Nov 2026); 820 feet is "
              "250 m. One landing is not a statistic; taking its miss as one standard deviation of a circular Gaussian "
              "is this project's choice."},
    {"id": "wide", "label": "unguided lander", "sigma_major_m": 670.0, "sigma_minor_m": 400.0,
     "figure": "a prime landing site of 4 km x 2.4 km", "source": "ISRO, Chandrayaan-3 details page",
     "source_url": "https://www.isro.gov.in/Chandrayaan3_Details.html",
     "basis": "ASSUMED: a lander with no terrain-relative navigation, as an ellipse of 670 m by 400 m. The figure: ISRO "
              "lists Chandrayaan-3's \"Landing Site (Prime) 4 km x 2.4 km\" (ISRO Chandrayaan-3 details page, read 15 Nov "
              "2026). Taking a third of that area's half-axes as one standard deviation is this project's choice, and "
              "Chandrayaan-3 itself was guided. The direction of the long axis is not known, so every direction is tried."},
]
CLASS_ASSUMPTION = ("Each figure is the chance that the plan still meets the need when the touchdown point is drawn from "
                    "an ASSUMED two-dimensional Gaussian around the target. The three sizes are illustrations tied to one "
                    "public figure each, not a model of any named lander; the outcome at each touchdown point comes from "
                    "the real elevation grid, which is not perturbed.")
ORIENTATIONS = np.arange(0.0, 180.0, 15.0)


def _cell_weights(radii: list, edges: list, counts: list, first: list, sig_a: float, sig_b: float, theta_deg: float,
                  sub_r: int = 8, sub_t: int = 6) -> tuple[float, list[np.ndarray]]:
    """Probability mass of a Gaussian ellipse (long axis at bearing ``theta_deg``) in the cell each touchdown
    point stands for: the central disc for the target, and for a ring point the part of its ring's annulus
    nearest to its bearing.  Midpoint quadrature in polar coordinates."""
    th = np.deg2rad(theta_deg)

    def mass(r0, r1, b0, b1):
        rr = r0 + (np.arange(sub_r) + 0.5) * (r1 - r0) / sub_r
        bb = b0 + (np.arange(sub_t) + 0.5) * (b1 - b0) / sub_t
        R, B = np.meshgrid(rr, np.deg2rad(bb), indexing="ij")
        # bearing is clockwise from north; along = component on the long axis, across = the other one
        along = R * np.cos(B - th)
        across = R * np.sin(B - th)
        pdf = np.exp(-0.5 * ((along / sig_a) ** 2 + (across / sig_b) ** 2)) / (2.0 * np.pi * sig_a * sig_b)
        return float((pdf * R).sum() * ((r1 - r0) / sub_r) * np.deg2rad((b1 - b0) / sub_t))

    centre = mass(0.0, edges[1], 0.0, 360.0) if edges[1] > 0 else 0.0
    per_ring = []
    for i, (n, b0) in enumerate(zip(counts, first)):
        step = 360.0 / n
        per_ring.append(np.array([mass(edges[i + 1], edges[i + 2], b0 + (k - 0.5) * step, b0 + (k + 0.5) * step)
                                  for k in range(n)]))
    return centre, per_ring


def lander_classes(site: Site, landing, need_sun_h: float, need_earth_h: float, window_days: float, crit: Criteria,
                   mask_deg: float, mast_m: float, slip_days: int = 60, sun_at_touchdown: bool = True,
                   earth_at_touchdown: bool = True) -> dict:
    """Chance that the plan holds, per day of slip, for three ASSUMED landing dispersions.

    The same ring points as the landing circles plus three rings out to 2.5 km.  Each point is weighted by
    the probability mass of the class's Gaussian ellipse in the cell it stands for; the long axis is tried
    in twelve directions (the approach direction is not known) and the touchdown points are resampled as for
    the circles.  Reported per day: the mean over directions, and a range that covers both effects.
    """
    if not site.horizon.is_terrain:
        return {"available": False, "reason": "no terrain data covers this site, so there is nothing to scatter over"}
    res = float(site.horizon.meta.get("resolution_m") or 0.0)
    pts: list[Site] = [site]
    rings = []                                             # (radius, first index, end index, first bearing)
    for radius, n, b0 in RING_LAYOUT + OUTER_RINGS:
        if radius < res / 2.0:
            continue
        i0 = len(pts)
        for k in range(n):
            la, lo = destination(site.lat, site.lon, np.deg2rad(b0 + k * 360.0 / n), np.array(radius / MOON_RADIUS_M))
            lo = ((float(lo) + 180.0) % 360.0) - 180.0
            la, lo = round(float(la), 5), round(lo, 5)
            hz = horizon_for(la, lo, mask_deg, mast_m, True)
            if hz.is_terrain:
                pts.append(Site(site.name, la, lo, horizon=hz))
        if len(pts) - i0 == n:                             # a ring that loses points at the edge of the grid is left out
            rings.append((radius, i0, len(pts), b0))
        else:
            del pts[i0:]
    if not rings:
        return {"available": False, "reason": "no touchdown points can be placed around this site on this grid"}
    grid = slip_grid(pts, landing, slip_days, 24, window_days, crit)
    ok = np.array([_passes(r, need_sun_h, need_earth_h, sun_at_touchdown, earth_at_touchdown) for r in grid["rows"]])
    computed = np.array([v is not None for v in grid["rows"][0]["sunlit"]])
    radii = [0.0] + [r[0] for r in rings]
    outer = radii[-1] + (radii[-1] - radii[-2]) / 2.0
    edges = [0.0] + [(radii[i] + radii[i + 1]) / 2.0 for i in range(len(radii) - 1)] + [outer]
    counts = [r[2] - r[1] for r in rings]
    first = [r[3] for r in rings]
    rng = np.random.default_rng(BOOT_SEED)
    picks = [rng.integers(0, n, size=(BOOT_N, n)) for n in counts]
    okf = ok.astype(float)
    classes = []
    for c in LANDER_CLASSES:
        sa, sb = c["sigma_major_m"], c["sigma_minor_m"]
        entry = {"id": c["id"], "label": c["label"], "sigma_major_m": sa, "sigma_minor_m": sb, "basis": c["basis"],
                 "figure": c["figure"], "source": c["source"], "source_url": c["source_url"],
                 "within_99_pct_m": round(3.035 * sa), "assumed": True}
        if 3.035 * sa < res:
            entry.update({"resolvable": False,
                          "why": f"99 % of its touchdowns fall inside one {np.ceil(res):.0f} m cell of the elevation grid under this site"})
            classes.append(entry)
            continue
        dirs = ORIENTATIONS if sa != sb else np.array([0.0])
        per_dir, boots, inside = [], [], []
        for th in dirs:
            wc, wr = _cell_weights(radii, edges, counts, first, sa, sb, float(th))
            total = wc + sum(float(x.sum()) for x in wr)
            inside.append(total)
            share = wc * okf[0]
            bs = np.repeat((wc * okf[0])[None, :], BOOT_N, axis=0)
            for (_, a, b, _), wk, pk in zip(rings, wr, picks):
                share = share + wk @ okf[a:b]
                bs = bs + np.einsum("k,bkd->bd", wk, okf[a:b][pk])
            per_dir.append(share / total)
            boots.append(bs / total)
        per_dir = np.array(per_dir) * 100.0                          # (directions, dates)
        boots = np.concatenate(boots, axis=0) * 100.0                # (directions * BOOT_N, dates)
        mean = np.round(per_dir.mean(axis=0), 1)
        s_lo, s_hi = np.percentile(boots, [5, 95], axis=0)
        lo = np.round(np.minimum(per_dir.min(axis=0), s_lo), 1)
        hi = np.round(np.maximum(per_dir.max(axis=0), s_hi), 1)
        margin = -1
        for i in range(len(mean)):
            if not computed[i] or mean[i] < 90.0:
                break
            margin = i
        val = lambda a: [None if not computed[i] else float(a[i]) for i in range(len(a))]  # noqa: E731
        entry.update({
            "resolvable": True, "points": len(pts), "directions": int(len(dirs)),
            "chance_pct": val(mean), "range_lo_pct": val(lo), "range_hi_pct": val(hi),
            "planned_pct": float(mean[0]) if computed[0] else None,
            "planned_range_pct": [float(lo[0]), float(hi[0])] if computed[0] else None,
            "planned_direction_range_pct": [round(float(per_dir[:, 0].min()), 1), round(float(per_dir[:, 0].max()), 1)],
            "planned_sampling_range_pct": [round(float(s_lo[0]), 1), round(float(s_hi[0]), 1)],
            "margin_90_days": margin, "dates_at_90": int(((mean >= 90.0) & computed).sum()),
            "mass_inside_sampled_area_pct": round(float(np.mean(inside)) * 100.0, 2)})
        classes.append(entry)
    return {"available": True, "site": {"name": site.name, "lat": site.lat, "lon": site.lon},
            "horizon": site.horizon.describe(), "landing_utc": grid["dates"][0], "dates": grid["dates"],
            "grid_resolution_m": res, "points": len(pts), "outer_radius_m": outer, "classes": classes,
            "assumption": CLASS_ASSUMPTION, "threshold_pct": 90.0,
            "range_note": ("Range: the lowest and highest of (a) the chance for each of the twelve directions of the long axis "
                           f"and (b) the 5th to 95th percentile over {BOOT_N} resamplings of the touchdown points. "
                           "The chance is taken over the sampled area; the share of the Gaussian that falls outside it is "
                           "left out and reported per class.")}


# --------------------------------------------------------------------------- slip-robust sites from the map

def robust_sites(field_points: dict, margin: np.ndarray, good: np.ndarray, landing, need_sun_h: float,
                 need_earth_h: float, window_days: float, crit: Criteria, mask_deg: float, mast_m: float,
                 scatter_m: float = 100.0, slip_days: int = 60, sun_at_touchdown: bool = True,
                 earth_at_touchdown: bool = True, candidates: int = 12, min_separation_m: float = 1000.0) -> dict:
    """Re-check the best points of the slip-margin map with the full "how sure" ensemble.

    The map is one point per cell with no scatter, so its margins are upper-side figures.  This takes
    the ``candidates`` map points with the largest single-point margin (at least ``min_separation_m``
    apart, so they are different places), runs the mission card at each, and reports which stay "yes".
    """
    lat, lon = np.asarray(field_points["lat"]), np.asarray(field_points["lon"])
    order = np.lexsort((-np.asarray(good), -np.asarray(margin)))        # largest margin first, then most good dates
    chosen: list[int] = []
    rad = np.deg2rad
    for i in order:
        if margin[i] < 0 or len(chosen) >= candidates:
            break
        far = True
        for j in chosen:
            c = (np.sin(rad(lat[i])) * np.sin(rad(lat[j]))
                 + np.cos(rad(lat[i])) * np.cos(rad(lat[j])) * np.cos(rad(lon[i] - lon[j])))
            if np.arccos(np.clip(c, -1.0, 1.0)) * MOON_RADIUS_M < min_separation_m:
                far = False
                break
        if far:
            chosen.append(int(i))
    rows = []
    for i in chosen:
        la, lo = round(float(lat[i]), 5), round(float(lon[i]), 5)
        hz = horizon_for(la, lo, mask_deg, mast_m, True)
        s = Site(f"{abs(la):.3f} S, {abs(lo):.3f} {'W' if lo < 0 else 'E'}", la, lo, horizon=hz)
        m = mission_card(s, landing, need_sun_h, need_earth_h, window_days, crit, mask_deg, mast_m, scatter_m,
                         slip_days, sun_at_touchdown, earth_at_touchdown)
        rows.append({"lat": la, "lon": lo, "name": s.name, "map_margin_days": int(margin[i]), "map_good_dates": int(good[i]),
                     "verdict": m["verdict"], "slip_margin_days": m["slip_margin_days"], "good_dates": m["good_dates"],
                     "unsure_dates": m["unsure_dates"], "points_passing": m["sure"]["points_passing"],
                     "points": m["sure"]["points"], "scatter_m": m["sure"]["scatter_m"],
                     "coarse_passes": m["sure"]["coarse_passes"], "near_passes": m["sure"]["near_passes"],
                     "sunlit_h": m["days"][0]["sunlit_h"], "earth_h": m["days"][0]["earth_h"],
                     "grid": str(m["horizon"].get("dem_label", "")).split(";")[0]})
    rows.sort(key=lambda r: (r["verdict"] != "yes", -r["slip_margin_days"], -r["good_dates"]))
    return {"candidates": len(rows), "stay_yes": sum(r["verdict"] == "yes" for r in rows),
            "min_separation_m": min_separation_m, "rows": rows,
            "what": "The map points with the largest single-point slip margin, re-checked with the landing scatter, "
                    "the coarser grid and the finer near-field sampling. A site stays on the list only if every "
                    "member of that check says yes on the planned date."}


# --------------------------------------------------------------------------- how much Earth clearance the answer has

SWEEP_MASKS = np.round(np.arange(0.0, 10.0001, 0.05), 2)


def earth_mask_sweep(site: Site, landing, need_sun_h: float, need_earth_h: float, window_days: float, crit: Criteria,
                     mask_deg: float, mast_m: float, scatter_m: float = 100.0, slip_days: int = 60,
                     sun_at_touchdown: bool = True, earth_at_touchdown: bool = True, masks=None) -> dict:
    """The mission card's verdict and slip margin as the Earth rule is tightened.

    The card counts the Earth as in view when its centre is above the terrain skyline by ``crit.earth_margin_deg``
    (0 by default: no link margin).  This repeats the card for every mask from 0 to 10 degrees in steps of 0.05,
    with everything else unchanged (same 13 touchdown points, coarser grid and near-field member, same Sun rule,
    same station rule), and reports where the planned date stops being a clear "yes".  One pass over the stored
    skylines; the masks only change which hours count.
    """
    masks = SWEEP_MASKS if masks is None else np.asarray(masks, dtype=float)
    ens = ensemble(site, mask_deg, mast_m, scatter_m)
    members, index = _flat(ens)
    s = grid_start(parse_utc(landing), STEP_S)
    w = int(round(window_days * 24))
    n = min((slip_days - 1) * 24 + w + 1, available_steps(s, STEP_S))
    if n < w + 2:
        raise ValueError("time outside the supported ephemeris span (1900-01-01 to 2050-01-01)")
    table = cached_table(s, n, STEP_S)
    starts = np.arange(slip_days) * 24
    sv = starts[starts + w <= n - 1]
    st_ok = station_ok(table.unix, crit)
    ok = np.zeros((len(masks), len(members), len(sv)), dtype=bool)
    clear0 = np.zeros((len(members), len(sv)))
    for k, m in enumerate(members):
        tr = track(m, table, crit.min_sun_fraction)
        lit = sun_up(tr)
        cs = np.concatenate([[0], np.cumsum(lit)])
        sun_ok = (cs[sv + w] - cs[sv]) >= need_sun_h
        if sun_at_touchdown:
            sun_ok &= lit[sv]
        base = (tr.earth_el >= crit.min_earth_el) & st_ok
        ev = (tr.earth_clear[None, :] > masks[:, None]) & base[None, :]                 # (masks, hours)
        ce = np.concatenate([np.zeros((len(masks), 1), dtype=np.int32), np.cumsum(ev, axis=1, dtype=np.int32)], axis=1)
        e_ok = (ce[:, sv + w] - ce[:, sv]) >= need_earth_h
        if earth_at_touchdown:
            e_ok &= ev[:, sv]
        ok[:, k, :] = e_ok & sun_ok[None, :]
        clear0[k] = tr.earth_clear[sv]
    a, b = index["scatter"]
    all_ok, none_ok = ok.all(axis=1), ~ok.any(axis=1)                                   # (masks, dates)
    verdict = np.where(all_ok, "yes", np.where(none_ok, "no", "not sure"))
    margin = np.array([(-1 if not all_ok[i, 0] else (int(np.argmin(all_ok[i])) - 1 if not all_ok[i].all() else len(sv) - 1))
                       for i in range(len(masks))])
    pts = ok[:, a:b, 0].sum(axis=1)
    v0 = verdict[:, 0]
    not_yes = np.nonzero(v0 != "yes")[0]
    is_no = np.nonzero(v0 == "no")[0]
    first_bad = int(not_yes[0]) if len(not_yes) else None
    cur = float(crit.earth_margin_deg)
    i_cur = int(np.argmin(np.abs(masks - cur)))
    m0 = int(margin[0])
    yes_days = list(range(0, m0 + 1)) if m0 >= 0 else []
    least = [float(clear0[a:b, d].min()) for d in yes_days]                             # least clearance of the 13 points, per day
    out = {
        "site": {"name": site.name, "lat": site.lat, "lon": site.lon}, "landing_utc": iso(s + int(sv[0]) * 0) if len(sv) else None,
        "step_deg": 0.05, "max_deg": float(masks[-1]), "rule": "Earth's centre above the terrain skyline by at least the mask",
        "current_mask_deg": cur, "stations": bool(crit.stations),
        "verdict_at_zero": str(v0[0]), "margin_days_at_zero": m0,
        "yes_up_to_deg": (None if v0[0] != "yes" else (float(masks[first_bad - 1]) if first_bad is not None else float(masks[-1]))),
        "not_sure_from_deg": next((float(masks[i]) for i in range(len(masks)) if v0[i] == "not sure"), None),
        "no_from_deg": float(masks[is_no[0]]) if len(is_no) else None,
        "clearance_at_touchdown_deg": round(float(clear0[0, 0]), 2),
        "least_clearance_of_points_deg": round(float(clear0[a:b, 0].min()), 2), "points": int(b - a),
        "masks": [float(x) for x in masks[::2]], "verdict_planned": [str(x) for x in v0[::2]],
        "margin_days": [int(x) for x in margin[::2]], "points_passing_planned": [int(x) for x in pts[::2]],
        "at": [{"mask_deg": float(m), "verdict": str(v0[i]), "margin_days": int(margin[i]), "points_passing": int(pts[i])}
               for m in (0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0) for i in [int(np.argmin(np.abs(masks - m)))]],
        "current": {"mask_deg": float(masks[i_cur]), "verdict": str(v0[i_cur]), "margin_days": int(margin[i_cur])},
        "clear_yes_days_at_zero": yes_days,
        "least_clearance_by_day_deg": [round(x, 2) for x in least],
        "thinnest_day": (int(yes_days[int(np.argmin(least))]) if least else None),
    }
    return out
