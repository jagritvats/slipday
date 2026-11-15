"""Why it flips: the Sun's and the Earth's tracks against the terrain skyline for one landing window,
the time left to sunset and Earthset, and the piece of terrain that ends the slip margin.

The official challenge text asks to "display the positions of the Sun and Earth relative to the horizon at
a selected landing site on a chosen date"; this module puts that view next to the verdict it explains.

For the landing date of one cell of the verdict strip (``day`` days of slip) it returns
  - the 360-degree skyline of the target (azimuth, elevation, distance of the ground that sets it),
  - the hourly positions of the Sun and the Earth through the landing window, with the flags the card counts,
  - when the Sun and the Earth next go behind the skyline,
  - each stretch of the window in which the Sun (or the Earth) is hidden, with the terrain that hides it,
and, for the first day of slip that is no longer a clear yes, which member of the "how sure" check fails,
why, and the direction, distance, position and height of the terrain responsible.

Everything is read off the same skylines and the same rules as the mission card: nothing here is a new
model.  The blocking terrain is the ground that sets the skyline at the azimuth where the body is deepest
behind it during the stretch in question; its distance comes from the ray-march that built the skyline.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Optional

import numpy as np

from . import demstore, gazetteer
from .dem import MOON_RADIUS_M
from .ephem import available_steps, cached_table, grid_start, iso, parse_utc
from .geometry import Site, track
from .metrics import STEP_S, Criteria, earth_up, site_summary, sun_up
from .robust import _flat, _passes, _reasons, banded_slip_grid, ensemble, mission_card
from .sites import smooth_twin, terrain_profile
from .terrain import destination

COMPASS = ["north", "north-north-east", "north-east", "east-north-east", "east", "east-south-east", "south-east",
           "south-south-east", "south", "south-south-west", "south-west", "west-south-west", "west", "west-north-west",
           "north-west", "north-north-west"]
_cache: "OrderedDict[tuple, dict]" = OrderedDict()
_cache_lock = threading.Lock()


def compass(az_deg: float) -> str:
    return COMPASS[int(round((az_deg % 360.0) / 22.5)) % 16]


def _offset(a: Site, b: Site) -> tuple[float, float]:
    """Distance (m) and bearing (deg, clockwise from north) from a to b."""
    la1, lo1, la2, lo2 = map(np.deg2rad, (a.lat, a.lon, b.lat, b.lon))
    dlon = lo2 - lo1
    c = np.sin(la1) * np.sin(la2) + np.cos(la1) * np.cos(la2) * np.cos(dlon)
    dist = float(np.arccos(np.clip(c, -1.0, 1.0)) * MOON_RADIUS_M)
    brg = float(np.rad2deg(np.arctan2(np.sin(dlon) * np.cos(la2),
                                      np.cos(la1) * np.sin(la2) - np.sin(la1) * np.cos(la2) * np.cos(dlon))) % 360.0)
    return dist, brg


def _runs(flags: np.ndarray) -> list[tuple[int, int]]:
    """(start, end) index pairs, end exclusive, of each run of True."""
    f = np.asarray(flags, dtype=bool)
    edges = np.diff(np.concatenate([[0], f.astype(np.int8), [0]]))
    return list(zip(np.nonzero(edges == 1)[0].tolist(), np.nonzero(edges == -1)[0].tolist()))


def _window(site: Site, landing_iso: str, w: int, crit: Criteria):
    """Hourly track of one site through one landing window (w + 1 samples) and the two flags the card counts."""
    s = grid_start(parse_utc(landing_iso), STEP_S)
    n = min(w + 1, available_steps(s, STEP_S))
    if n < 2:
        raise ValueError("time outside the supported ephemeris span (1900-01-01 to 2050-01-01)")
    tr = track(site, cached_table(s, n, STEP_S), crit.min_sun_fraction)
    lit = sun_up(tr)
    ev = earth_up(tr, crit) & (tr.earth_el >= crit.min_earth_el)
    return s, tr, lit, ev


def _terrain_at(site: Site, prof, az_deg: float) -> dict:
    """The ground that sets the skyline of ``site`` at one azimuth."""
    out = {"az_deg": round(float(az_deg) % 360.0, 1), "compass": compass(az_deg)}
    if prof is None:
        out.update({"kind": "smooth sphere", "dist_km": None})
        return out
    k = int(round((az_deg % 360.0) / 360.0 * len(prof.az_deg))) % len(prof.az_deg)
    out["skyline_el_deg"] = round(float(prof.el_deg[k]), 2)
    d = float(prof.dist_km[k])
    if not np.isfinite(d):
        out.update({"kind": "limb of the Moon (no terrain found on that ray)", "dist_km": None})
        return out
    la, lo = destination(site.lat, site.lon, np.deg2rad(az_deg), np.array(d * 1000.0 / MOON_RADIUS_M))
    la, lo = float(la), ((float(lo) + 180.0) % 360.0) - 180.0
    out.update({"kind": "terrain", "dist_km": round(d, 2), "lat": round(la, 4), "lon": round(lo, 4)})
    named = gazetteer.containing(la, lo)
    if named is not None:
        out["named"] = named
    res =float((prof.dem or {}).get("resolution_m") or 0.0)
    if res > 0 and d * 1000.0 <= 2.05 * res:               # the skyline is set by the first or second ray sample
        out["near_field"] = 1 if d * 1000.0 <= 1.05 * res else 2
        out["grid_cell_m"] = round(res)
    dem = demstore.get_dem()
    if dem is not None:
        h = float(dem.height_m(np.array([la]), np.array([lo]))[0])
        if np.isfinite(h):
            out["height_above_site_m"] = round(h - float(prof.site_height_m))
    return out


def _stretch(site: Site, prof, tr, hidden: np.ndarray, body: str, i0: int, i1: int, s: int, w: int) -> dict:
    """One stretch [i0, i1) of the window in which ``body`` is hidden, and the terrain that hides it."""
    az = tr.sun_az if body == "sun" else tr.earth_az
    clear = tr.sun_clear if body == "sun" else tr.earth_clear
    deep = i0 + int(np.argmin(clear[i0:i1]))              # the hour the body's centre is deepest behind the skyline
    # The terrain to name is the ground the body goes behind: the skyline under it in the first hidden hour.
    # A stretch that is already under way at touchdown has no such hour in the window; then it is the ground
    # the body comes out from behind (last hidden hour), or, if it never comes out, the ground at touchdown.
    if i0 > 0:
        k, event = i0, "goes behind"
    elif i1 < len(az):
        k, event = i1 - 1, "comes out from behind"
    else:
        k, event = i0, "is behind"
    out = {"body": body, "from_hour": int(i0), "to_hour": int(i1), "hours": int(min(i1, w) - i0),
           "from_utc": iso(s + i0 * STEP_S), "to_utc": iso(s + i1 * STEP_S), "runs_to_end_of_window": bool(i1 >= w),
           "az_from_deg": round(float(az[i0]), 1), "az_to_deg": round(float(az[i1 - 1]), 1),
           "deepest_below_skyline_deg": round(float(-clear[deep]), 2), "deepest_utc": iso(s + deep * STEP_S),
           "event": event, "event_utc": iso(s + k * STEP_S), "terrain": _terrain_at(site, prof, float(az[k]))}
    return out


def _stretches(site: Site, prof, tr, hidden: np.ndarray, body: str, s: int, w: int, top: int = 3) -> list[dict]:
    runs = [(a, b) for a, b in _runs(hidden[:w])]
    runs.sort(key=lambda r: -(r[1] - r[0]))
    return [_stretch(site, prof, tr, hidden, body, a, b, s, w) for a, b in sorted(runs[:top])]


def _terrain_text(t: dict) -> str:
    if t.get("kind") != "terrain":
        return f"the {t.get('kind', 'smooth sphere')} towards azimuth {t['az_deg']:.0f} deg ({t['compass']})"
    near = t.get("near_field")
    if near:
        return (f"the crest it stands on: ground {t['dist_km'] * 1000:.0f} m away ({'one cell' if near == 1 else 'two cells'} "
                f"of the elevation grid) towards azimuth {t['az_deg']:.0f} deg ({t['compass']})")
    txt = (f"ground {t['dist_km']:g} km away towards azimuth {t['az_deg']:.0f} deg ({t['compass']}), at "
           f"{abs(t['lat']):.3f} {'S' if t['lat'] < 0 else 'N'}, {abs(t['lon']):.3f} {'W' if t['lon'] < 0 else 'E'}")
    if "height_above_site_m" in t:
        h = t["height_above_site_m"]
        txt += f" ({abs(h)} m {'above' if h >= 0 else 'below'} the site)"
    nm = t.get("named")
    if nm:
        main = nm["phrase"].split(", on the rim of")[0]
        txt += f", {main} ({nm['diameter_km']:g} km across; IAU name)"
        if nm.get("rim_also"):
            txt += f" and on the rim of {nm['rim_also']['label']} ({nm['rim_also']['diameter_km']:g} km)"
    return txt


def _day_text(iso_utc: str) -> str:
    mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{int(iso_utc[8:10])} {mon[int(iso_utc[5:7]) - 1]}" + ("" if iso_utc[11:16] == "00:00" else f" {iso_utc[11:16]} UTC")


def why(site: Site, landing, need_sun_h: float, need_earth_h: float, window_days: float, crit: Criteria,
        mask_deg: float, mast_m: float, scatter_m: float = 100.0, slip_days: int = 60,
        sun_at_touchdown: bool = True, earth_at_touchdown: bool = True, day: int = 0) -> dict:
    """The skyline view for the landing date ``day`` days after the planned one, and what ends the margin."""
    key = (site.name, site.lat, site.lon, site.horizon.is_terrain, str(landing), need_sun_h, need_earth_h, window_days,
           crit, mask_deg, mast_m, scatter_m, slip_days, sun_at_touchdown, earth_at_touchdown, int(day),
           getattr(demstore.get_dem(), "fingerprint", None))
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
            return hit
    args = (need_sun_h, need_earth_h, sun_at_touchdown, earth_at_touchdown)
    card = mission_card(site, landing, need_sun_h, need_earth_h, window_days, crit, mask_deg, mast_m, scatter_m,
                        slip_days, sun_at_touchdown, earth_at_touchdown)
    days = card["days"]
    if not 0 <= day < len(days):
        raise ValueError(f"day must be between 0 and {len(days) - 1}")
    d = days[day]
    if d["sunlit_h"] is None:
        raise ValueError("that landing date runs past the end of the ephemeris (2050)")
    w = int(round(window_days * 24))
    prof = terrain_profile(site.lat, site.lon, mast_m) if site.horizon.is_terrain else None

    # ---- the chosen landing window at the target
    s, tr, lit, ev = _window(site, d["landing_utc"], w, crit)
    n = len(lit)
    summ = site_summary(site, d["landing_utc"], window_days, crit)
    s2, tr2, lit2, ev2 = _window(smooth_twin(site, mask_deg), d["landing_utc"], w, crit)
    r = lambda a, k=2: [round(float(x), k) for x in a]  # noqa: E731
    out = {
        "site": {"name": site.name, "lat": site.lat, "lon": site.lon}, "horizon": site.horizon.describe(),
        "day": int(day), "landing_utc": d["landing_utc"], "window_hours": w, "window_days": window_days,
        "verdict": d["verdict"], "points_passing": d["points_passing"], "points": d["points"],
        "slip_margin_days": card["slip_margin_days"], "criteria": card["criteria"],
        "need": {"sunlit_h": need_sun_h, "earth_h": need_earth_h},
        "hours": {"sunlit": int(lit[:w].sum()), "earth": int(ev[:w].sum()),
                  "smooth_sunlit": int(lit2[:w].sum()), "smooth_earth": int(ev2[:w].sum())},
        "track": {"start_utc": iso(s), "step_minutes": 60, "count": n,
                  "sun_az": r(tr.sun_az), "sun_el": r(tr.sun_el, 3), "sun_lit": [int(x) for x in lit],
                  "earth_az": r(tr.earth_az), "earth_el": r(tr.earth_el, 3), "earth_up": [int(x) for x in ev],
                  "sun_radius_deg": round(float(tr.sun_radius_deg.mean()), 3),
                  "earth_radius_deg": round(float(tr.earth_radius_deg.mean()), 3)},
        "touchdown": {"sun_el": summ["now"]["sun_el"], "sun_az": summ["now"]["sun_az"],
                      "sun_skyline_el": summ["now"]["sun_horizon_el"], "sun_up": bool(lit[0]),
                      "sun_disc_fraction": summ["now"]["sun_disc_fraction"],
                      "earth_el": summ["now"]["earth_el"], "earth_az": summ["now"]["earth_az"],
                      "earth_skyline_el": summ["now"]["earth_horizon_el"], "earth_up": bool(ev[0]),
                      "next_sunset": summ["next_sunset"], "next_sunrise": summ["next_sunrise"],
                      "next_earthset": summ["next_earthset"], "next_earthrise": summ["next_earthrise"],
                      "searched_days": summ["search_days"]},
        "sun_hidden": _stretches(site, prof, tr, ~lit, "sun", s, w),
        "earth_hidden": _stretches(site, prof, tr, ~ev, "earth", s, w, top=2),
        "labels": {
            "real": "skyline ray-cast from " + str(site.horizon.describe().get("dem_label", "no terrain data: smooth sphere")).split(";")[0]
                    + " elevation data" if site.horizon.is_terrain else "no terrain data covers this site: smooth-sphere horizon",
            "derived": "Sun and Earth positions computed from JPL DE421 (hourly); rise and set times refined to the second; "
                       "blocking terrain read from the ray-march that built the skyline",
            "rules": card["criteria"]["sun_rule"] + "; " + card["criteria"]["earth_rule"],
        },
    }
    if prof is not None:
        out["skyline"] = {"az_deg": r(prof.az_deg, 1), "el_deg": r(prof.el_deg, 3),
                          "dist_km": [None if not np.isfinite(x) else round(float(x), 2) for x in prof.dist_km],
                          "site_height_m": round(float(prof.site_height_m), 1), "mast_m": prof.mast_m}
    else:
        out["skyline"] = None

    # ---- what ends the margin: the first day of slip that is not a clear yes
    margin = card["slip_margin_days"]
    f = margin + 1
    flip: Optional[dict] = None
    if f < len(days) and days[f]["sunlit_h"] is not None:
        grid, raw = banded_slip_grid([site], landing, slip_days, 24, window_days, crit, mask_deg, mast_m, scatter_m)
        rows, index = raw[0]["rows"], raw[0]["index"]
        members, _ = _flat(ensemble(site, mask_deg, mast_m, scatter_m))
        ok = np.array([_passes(rw, *args)[f] for rw in rows])
        a, b = index["scatter"]
        kind_of = {0: "target"}
        for j in range(a + 1, b):
            kind_of[j] = "touchdown point"
        for name in ("coarse", "near"):
            if name in index:
                kind_of[index[name]] = name
        failing = [j for j in range(len(rows)) if not ok[j]]
        # the member to explain: the target if it fails, else the touchdown point with the fewest sunlit hours
        pts_fail = [j for j in failing if j < b]
        pick = None
        if 0 in failing:
            pick = 0
        elif pts_fail:
            pick = min(pts_fail, key=lambda j: (rows[j]["sunlit"][f], rows[j]["earth"][f]))
        fd = days[f]
        flip = {"day": f, "landing_utc": fd["landing_utc"], "verdict": fd["verdict"],
                "points_passing": fd["points_passing"], "points": fd["points"],
                "coarse_passes": fd.get("coarse_passes"), "near_passes": fd.get("near_passes")}
        if pick is None:
            only = [kind_of[j] for j in failing]
            names = {"coarse": "the coarser elevation grid", "near": "the finer sampling of the nearest ground"}
            flip.update({"member": None, "ended_by": {"kind": "grid", "what": "the terrain grids disagree"}, "text": (
                (f"The planned date (landing {_day_text(fd['landing_utc'])}) is not a clear yes: " if f == 0 else
                 f"A slip of {f} day{'s' if f != 1 else ''} (landing {_day_text(fd['landing_utc'])}) is no longer a clear yes: ") +
                f"all {fd['points']} touchdown points still pass, but " + " and ".join(names.get(x, x) for x in only)
                + " gives the opposite answer. That is a limit of the elevation data, not one ridge that can be named.")})
        else:
            m = members[pick]
            mprof = terrain_profile(m.lat, m.lon, mast_m, "drop1" if kind_of[pick] == "coarse" else
                                    ("near" if kind_of[pick] == "near" else "")) if m.horizon.is_terrain else None
            ms, mtr, mlit, mev = _window(m, fd["landing_utc"], w, crit)
            reasons = _reasons(rows[pick], f, *args)
            sun_td_fail = sun_at_touchdown and not rows[pick]["sun_up_at_landing"][f]
            sun_short = rows[pick]["sunlit"][f] < need_sun_h
            earth_td_fail = earth_at_touchdown and not rows[pick]["earth_up_at_landing"][f]
            body = "sun" if (sun_td_fail or sun_short) else "earth"
            hidden = ~mlit if body == "sun" else ~mev
            runs = _runs(hidden[:w])
            at_td = (sun_td_fail if body == "sun" else earth_td_fail)
            run = None
            if runs:
                run = runs[0] if (at_td and runs[0][0] == 0) else max(runs, key=lambda q: q[1] - q[0])
            st = _stretch(m, mprof, mtr, hidden, body, run[0], run[1], ms, w) if run else None
            dist, brg = _offset(site, m) if pick else (0.0, 0.0)
            where = ("at the target itself" if pick == 0 else f"{dist:.0f} m {compass(brg)} of the target")
            name = "Sun" if body == "sun" else "Earth"
            got = rows[pick]["sunlit"][f] if body == "sun" else rows[pick]["earth"][f]
            need = need_sun_h if body == "sun" else need_earth_h
            unit = "sunlit hours" if body == "sun" else "hours of Earth contact"
            lead = (f"The planned date (landing {_day_text(fd['landing_utc'])}) " if f == 0 else
                    f"A slip of {f} day{'s' if f != 1 else ''} (landing {_day_text(fd['landing_utc'])}) ")
            txt = lead + (("fails" if fd["verdict"] == "no" else "is not a clear yes") if f == 0 else
                          ("fails" if fd["verdict"] == "no" else "is no longer a clear yes")) + f": {where} "
            if at_td and st is not None and st["from_hour"] == 0:
                txt += (f"the {name} is behind the skyline at touchdown and stays hidden for {st['hours']} h. ")
            elif st is not None:
                txt += (f"the {name} is hidden for {int(hidden[:w].sum())} of the {w} hours"
                        + (f" ({st['hours']} in one stretch from {_day_text(st['from_utc'])})" if st["hours"] != int(hidden[:w].sum())
                           else f" (from {_day_text(st['from_utc'])})")
                        + f", leaving {got} {unit} of the {need:g} needed. ")
            else:
                txt += "; ".join(reasons) + ". "
            if st is not None:
                txt += f"The {name} {st['event']} " + _terrain_text(st["terrain"]) + "."
            if body == "sun":
                ended = ({"kind": "sun at touchdown", "what": "landing in sunlight"} if (at_td and not sun_short) else
                         {"kind": "sunlit hours", "what": "the sunlit-hours need", "need_h": need_sun_h, "got_h": rows[pick]["sunlit"][f]})
            else:
                ended = ({"kind": "earth at touchdown", "what": "the Earth in view at touchdown"}
                         if (at_td and rows[pick]["earth"][f] >= need_earth_h) else
                         {"kind": "earth contact hours", "what": "the Earth-contact need", "need_h": need_earth_h, "got_h": rows[pick]["earth"][f]})
            flip["ended_by"] = ended
            flip.update({"member": {"kind": kind_of[pick], "lat": m.lat, "lon": m.lon, "offset_m": round(dist),
                                    "bearing_deg": round(brg, 1), "compass": compass(brg) if pick else None},
                         "body": body, "reasons": reasons, "stretch": st, "text": txt,
                         "failing_points": len(pts_fail), "sunlit_h": rows[pick]["sunlit"][f],
                         "earth_h": rows[pick]["earth"][f]})
    elif f >= len(days):
        flip = {"day": None, "text": f"The plan holds for every one of the {len(days)} landing dates checked, so nothing ends the margin in this span."}
    out["flip"] = flip
    with _cache_lock:
        _cache[key] = out
        while len(_cache) > 96:
            _cache.popitem(last=False)
    return out
