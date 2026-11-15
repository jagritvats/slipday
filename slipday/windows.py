"""Next launch windows: how a real slip moves the landing, and what the site says there (rules R9 and R10,
DEEP_PASS.md).

Real landing opportunities come in steps.  A south-pole lander's launch window is a few days each month, built
so that the landing falls when the Sun and the Earth suit the site (Intuitive Machines on IM-1, Spaceflight Now,
27 Oct 2023: "each month has a window around three to six days"; Space.com, Feb 2024: a "three-day window ... to
land on the moon on Feb. 22").  A day's slip inside the window leaves the landing where it is; missing the window
moves it to the next month's window at the same solar phase, about one synodic month later.  The Earth's own
cycle in the site's sky is shorter than the synodic month, so the next window finds the Earth elsewhere.

``next_windows`` judges the planned landing and the landings k synodic months away with the card's own rules and
need, and adds the whole night and Earth outage the lander would meet (rule R8).  ``sunrise_windows`` finds, for a
mission with no published landing date, the landings 24 hours after the Sun first counts as up in each lunar day
(an assumption, labelled wherever it is used).
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from . import survival
from .ephem import available_steps, cached_table, grid_start, iso, parse_utc
from .geometry import Site, track
from .metrics import STEP_S, Criteria, earth_up, sun_up
from .robust import _flat, ensemble, mission_card
from .terrain import destination

SYNODIC_DAYS = 29.530589


def _hour(dt):
    return (dt + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)


def judge(site: Site, landing: str, need_sun_h: float, need_earth_h: float, window_days: float, crit: Criteria,
          mask_deg: float, mast_m: float, scatter_m: float, sun_at_td: bool = True, earth_at_td: bool = True,
          long_days: float = 0.0) -> dict:
    """The card's verdict for one landing, the whole night and outage it meets, and (if asked) totals over a longer
    published mission duration."""
    m = mission_card(site, landing, need_sun_h, need_earth_h, window_days, crit, mask_deg, mast_m, scatter_m, 15,
                     sun_at_td, earth_at_td)
    members, index = _flat(ensemble(site, mask_deg, mast_m, scatter_m))
    sv = survival.site_survival(members, index, landing, window_days, crit, 1, [m["days"][0]["verdict"]], -1)
    d0, day0 = sv["days"][0], m["days"][0]
    out = {"landing_utc": m["landing_utc"], "verdict": m["verdict"], "slip_margin_days": m["slip_margin_days"],
           "points_passing": day0.get("points_passing"), "points": m["sure"]["points"],
           "sunlit_h": day0.get("sunlit_h"), "earth_h": day0.get("earth_h"),
           "night_met_h": d0["night_full_h"], "outage_met_h": d0["outage_full_h"],
           "night_in_window_h": d0["night_h"], "outage_in_window_h": d0["outage_h"],
           "next_good_utc": (m["next_good_dates"][0] if m["next_good_dates"] else None),
           "fails_on": fails_on(day0.get("reasons")) if m["verdict"] != "yes" else [],
           "reasons": m["sentences"][0] if m.get("sentences") else ""}
    if long_days > 0:
        out["long"] = long_totals(members[index["scatter"][0]:index["scatter"][1]], landing, long_days, crit)
    return out


def long_totals(points: list, landing: str, days: float, crit: Criteria) -> dict:
    """Over a longer mission (e.g. VIPER's 100 days): hours with the Sun up, hours of Earth contact and the longest
    whole night met, worst of the touchdown points."""
    s = grid_start(parse_utc(landing), STEP_S)
    w = int(round(days * 24))
    n = min(w + survival.EXTRA_DAYS * 24, available_steps(s, STEP_S))
    table = cached_table(s, n, STEP_S)
    sun = np.zeros((len(points), n), dtype=bool)
    earth = np.zeros((len(points), n), dtype=bool)
    for k, p in enumerate(points):
        tr = track(p, table, crit.min_sun_fraction)
        sun[k] = sun_up(tr)
        earth[k] = earth_up(tr, crit) & (tr.earth_el >= crit.min_earth_el)
    night, _ = survival.full_runs(~sun, [0], w)
    outage, _ = survival.full_runs(~earth, [0], w)
    sun_h = sun[:, :w].sum(axis=1)
    earth_h = earth[:, :w].sum(axis=1)
    both = (sun & earth)[:, :w].sum(axis=1)
    return {"days": days, "hours": w, "sunlit_h_min": int(sun_h.min()), "earth_h_min": int(earth_h.min()),
            "sun_and_earth_h_min": int(both.min()), "night_met_h_max": int(night.max()), "outage_met_h_max": int(outage.max())}


def next_windows(site: Site, landing: str, ks, need_sun_h: float, need_earth_h: float, window_days: float,
                 crit: Criteria, mask_deg: float, mast_m: float, scatter_m: float, sun_at_td: bool = True,
                 earth_at_td: bool = True, long_days: float = 0.0) -> dict:
    t0 = parse_utc(landing)
    rows = []
    for k in ks:
        L = _hour(t0 + timedelta(days=SYNODIC_DAYS * k)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = judge(site, L, need_sun_h, need_earth_h, window_days, crit, mask_deg, mast_m, scatter_m, sun_at_td,
                  earth_at_td, long_days)
        r["k"] = int(k)
        rows.append(r)
    return {"available": True, "site": {"name": site.name, "lat": site.lat, "lon": site.lon}, "step_days": SYNODIC_DAYS,
            "rows": rows, "rule": ("Window k lands k synodic months (29.53 days) after the planned landing, at the same solar "
                                   "phase, as real monthly launch windows do; each is judged with the card's rules and need.")}


def sunrise_windows(site: Site, start: str, end: str, crit: Criteria, after_h: int = 24, min_dark_h: int = 24) -> list:
    """Landings ``after_h`` hours after the Sun first counts as up in each lunar day at the target (a lunar day
    begins where a run of at least ``min_dark_h`` hours without the Sun ends).  An assumption for missions with
    no published landing date."""
    s = grid_start(parse_utc(start), STEP_S)
    e = grid_start(parse_utc(end), STEP_S)
    n = min((e - s) // STEP_S + 1, available_steps(s, STEP_S))
    table = cached_table(s, n, STEP_S)
    lit = sun_up(track(site, table, crit.min_sun_fraction))
    out = []
    dark = 0
    for i in range(n):
        if not lit[i]:
            dark += 1
            continue
        if dark >= min_dark_h:
            out.append(iso(s + (i + after_h) * STEP_S))
        dark = 0
    return out


def rim_point(lat: float, lon: float, diameter_km: float, bearing_deg: float = 270.0) -> tuple:
    """The point at a crater's rim radius from its centre along a local bearing (270: due local west)."""
    la, lo = destination(lat, lon, np.deg2rad(bearing_deg), np.array(diameter_km * 500.0 / 1737400.0))
    return round(float(la), 4), round(((float(lo) + 180.0) % 360.0) - 180.0, 4)


# ------------------------------------------------------------------ follow-up: which need fails, best hour, other sites

_SHORT = (("Sun is behind the skyline at touchdown", "Sun at touchdown"), ("Earth is behind the skyline at touchdown", "Earth at touchdown"),
          ("sunlit hours", "sunlight"), ("hours of Earth contact", "Earth contact"))


def fails_on(reasons: list) -> list:
    """Rule R11: the needs or conditions that fail at the target, in short words."""
    out = []
    for r in reasons or []:
        for key, word in _SHORT:
            if key in r and word not in out:
                out.append(word)
    return out


def best_hour(site: Site, landing: str, need_sun_h: float, need_earth_h: float, window_days: float, crit: Criteria,
              mask_deg: float, mast_m: float, scatter_m: float, sun_at_td: bool = True, earth_at_td: bool = True,
              span_h: int = 72, step_h: int = 6) -> dict:
    """Rule R13 (b): the clear-yes landing with the largest slip margin within +/- span_h of the window's landing,
    every step_h hours; ties to the earliest.  None found: {"found": False}."""
    t0 = parse_utc(landing)
    best = None
    tried = 0
    for dh in range(-span_h, span_h + 1, step_h):
        L = (t0 + timedelta(hours=dh)).strftime("%Y-%m-%dT%H:%M:%SZ")
        m = mission_card(site, L, need_sun_h, need_earth_h, window_days, crit, mask_deg, mast_m, scatter_m, 15, sun_at_td, earth_at_td)
        tried += 1
        if m["verdict"] == "yes" and (best is None or m["slip_margin_days"] > best["slip_margin_days"]):
            best = {"landing_utc": m["landing_utc"], "slip_margin_days": int(m["slip_margin_days"]), "offset_h": dh}
    planned = mission_card(site, landing, need_sun_h, need_earth_h, window_days, crit, mask_deg, mast_m, scatter_m, 15, sun_at_td, earth_at_td)
    pm = int(planned["slip_margin_days"]) if planned["verdict"] == "yes" else -1
    out = {"found": best is not None, **(best or {}), "tried": tried, "span_h": span_h, "step_h": step_h,
           "planned_margin_days": pm, "tie_with_planned": bool(best is not None and pm == best["slip_margin_days"] and best["offset_h"] != 0)}
    if best is not None:
        out.update(fragility(site, best["landing_utc"], best["slip_margin_days"], crit, mask_deg, mast_m, scatter_m, sun_at_td, earth_at_td))
    return out


def map_candidates() -> list:
    """The 18 scatter-robust map points of section H.1, in that order (default scenario of 18 Nov 2026)."""
    from . import field, scatterfield
    fld = field.load()
    if fld is None or scatterfield.load() is None:
        return []
    crit = Criteria()
    rm = scatterfield.robust_margin("2026-11-18T00:00:00Z", 60, 14.0, crit, 0.0, 240.0, 100.0, True, True)
    pd = field.per_date("2026-11-18T00:00:00Z", 60, 24, 14.0, crit, 0.0)
    st = field.statistics(pd, 240.0, 100.0, True, True)
    rob, good = rm["robust"], st["good"]
    idx = np.nonzero(rob >= 5)[0]
    order = sorted(idx.tolist(), key=lambda i: (-int(rob[i]), -int(good[i]), int(i)))
    return [{"rank": r, "lat": round(float(fld["lat"][i]), 5), "lon": round(float(fld["lon"][i]), 5)} for r, i in enumerate(order, 1)]


SUN_RADIUS_DEG = 0.27     # the Sun's apparent radius: under the half-disc rule a touchdown point within this of the
                          # skyline can change its answer with a small shift in terrain or ephemeris (final fixes)


def fragility(site: Site, landing: str, margin: int, crit: Criteria, mask_deg: float, mast_m: float, scatter_m: float,
              sun_at_td: bool = True, earth_at_td: bool = True) -> dict:
    """The smallest Sun (and Earth) clearance at touchdown over the 13 touchdown points and the passing slip days
    0..margin; a margin is "fragile" when it is under the Sun's apparent radius (0.27 degrees)."""
    members, index = _flat(ensemble(site, mask_deg, mast_m, scatter_m))
    pts = members[index["scatter"][0]:index["scatter"][1]]
    s = grid_start(parse_utc(landing), STEP_S)
    days = max(int(margin), 0) + 1
    table = cached_table(s, (days - 1) * 24 + 1, STEP_S)
    hrs = np.arange(days) * 24
    low = []
    for p in pts:
        tr = track(p, table, crit.min_sun_fraction)
        if sun_at_td:
            low.append(float(tr.sun_clear[hrs].min()))
        if earth_at_td:
            low.append(float((tr.earth_clear[hrs] - crit.earth_margin_deg).min()))
    m = min(low) if low else 99.0
    return {"min_clearance_deg": round(m, 2), "fragile": bool(m < SUN_RADIUS_DEG)}
