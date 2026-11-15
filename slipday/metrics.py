"""Rise/set events, headline metrics, long-span statistics and the slip grid.

Everything here works on a ``Site`` whatever its horizon model is (smooth
sphere, flat mask or a terrain profile); the callers build a terrain site and
its smooth-sphere twin and show both.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

import numpy as np

from .ephem import available_steps, cached_table, grid_start, iso, parse_utc
from .geometry import Site, Track, track, track_at

STEP_S = 3600
SYNODIC_DAYS = 29.530589
SEARCH_DAYS = 200          # how far ahead "next sunrise/sunset/Earthset" is searched
SPAN_BLOCK = 17_544        # samples worked on at once in long-span statistics (two years of hours)
MAX_SPAN_SAMPLES = 180_000


@dataclass(frozen=True)
class Criteria:
    """What counts as power and as a link.

    min_sun_fraction  share of the solar disc that must be above the horizon
                      (0 = any part, 0.5 = half the disc, 1 = whole disc)
    min_sun_el        optional extra rule: the disc centre must also be at least this
                      high above the level horizon (deg); -90 means no extra rule.
                      Over terrain the Sun can be up at a negative elevation (an
                      observer on high ground sees below the level horizon), so
                      the default must not demand zero.
    min_earth_el      the same for the Earth's centre
    earth_margin_deg  the Earth's centre must clear the local horizon (terrain
                      or sphere) by at least this much (deg); a direct-to-Earth
                      link needs some margin, and the Earth's disc is 0.95 deg
                      in radius
    """

    min_sun_fraction: float = 0.5
    min_sun_el: float = -90.0
    min_earth_el: float = -90.0
    earth_margin_deg: float = 0.0
    stations: bool = False        # Earth contact also needs a Deep Space Network complex with the Moon above its mask

    def describe(self) -> dict:
        f = self.min_sun_fraction
        rule = ("any part of the solar disc above the horizon" if f <= 0 else
                "the whole solar disc above the horizon" if f >= 1 else
                f"at least {f * 100:g}% of the solar disc above the horizon")
        extra = lambda v: None if v <= -90 else v  # noqa: E731
        sun_extra = "" if self.min_sun_el <= -90 else f", and the Sun at least {self.min_sun_el:g} deg high"
        earth_extra = "" if self.min_earth_el <= -90 else f", and at least {self.min_earth_el:g} deg high"
        station_extra = ""
        if self.stations:
            from . import stations as _st
            station_extra = (f", and the Moon at least {_st.MASK_DEG:g} deg up at one or more Deep Space Network "
                             "complexes (Goldstone, Madrid, Canberra)")
        return {"min_sun_fraction": f, "min_sun_el": extra(self.min_sun_el), "min_earth_el": extra(self.min_earth_el),
                "earth_margin_deg": self.earth_margin_deg, "stations": self.stations, "sun_rule": rule + sun_extra,
                "earth_rule": f"Earth's centre at least {self.earth_margin_deg:g} deg above the horizon" + earth_extra
                              + station_extra}


DEFAULT = Criteria()


def _track(site: Site, table, crit: Criteria) -> Track:
    return track(site, table, crit.min_sun_fraction)


def sun_up(tr: Track) -> np.ndarray:
    return tr.sun_lit > 0


def station_ok(unix, crit: Criteria = DEFAULT):
    """True where a ground station can see the Moon, under the criteria's station rule (all True without it)."""
    if not crit.stations:
        return np.ones(np.shape(unix), dtype=bool)
    from . import stations as _st
    return np.asarray(_st.any_in_view(np.asarray(unix, dtype=float)), dtype=bool)


def earth_up(tr: Track, crit: Criteria = DEFAULT) -> np.ndarray:
    up = tr.earth_clear > crit.earth_margin_deg
    return up & station_ok(tr.unix, crit) if crit.stations else up


def _value(tr: Track, body: str, limb: str, crit: Criteria = DEFAULT) -> np.ndarray:
    """Signed quantity whose zero crossing is a rise or a set."""
    if body == "sun":
        if limb == "upper":
            return tr.sun_clear + tr.sun_radius_deg
        return tr.sun_lit
    if body == "earth":
        v = tr.earth_clear - crit.earth_margin_deg
        if limb == "upper":
            v = v + tr.earth_radius_deg
        return v
    raise ValueError("body must be 'sun' or 'earth'")


def find_events(site: Site, tr: Track, body: str, limb: str = "center",
                refine: bool = True, crit: Criteria = DEFAULT) -> list[dict]:
    """Rise and set instants of a body within the span of ``tr``.

    Sign changes are located on the grid, then refined by bisection on the
    exact geometry (to about one second) rather than by interpolation.
    """
    v = _value(tr, body, limb, crit)
    up = v > 0
    idx = np.nonzero(up[1:] != up[:-1])[0]
    if idx.size == 0:
        return []
    lo, hi = tr.unix[idx].copy(), tr.unix[idx + 1].copy()
    rising = ~up[idx]
    if refine:
        n_iter = int(np.ceil(np.log2(max(float((hi - lo).max()), 2.0)))) + 1   # down to under 1 s
        for _ in range(n_iter):
            mid = 0.5 * (lo + hi)
            vm = _value(track_at(site, mid, crit.min_sun_fraction), body, limb, crit)
            above = vm > 0
            go_right = above != rising   # still on the "before" side
            lo = np.where(go_right, mid, lo)
            hi = np.where(go_right, hi, mid)
        t = 0.5 * (lo + hi)
    else:
        t = 0.5 * (lo + hi)
    kind = {"sun": ("sunrise", "sunset"), "earth": ("earthrise", "earthset")}[body]
    return [{"type": kind[0] if r else kind[1], "unix": float(x), "utc": iso(x)}
            for x, r in zip(t, rising)]


def longest_run(flags: np.ndarray) -> int:
    """Length (samples) of the longest run of True."""
    f = np.asarray(flags, dtype=bool)
    if not f.any():
        return 0
    edges = np.diff(np.concatenate([[0], f.astype(np.int8), [0]]))
    starts, ends = np.nonzero(edges == 1)[0], np.nonzero(edges == -1)[0]
    return int((ends - starts).max())


def _longest_run_hours(flags: np.ndarray, step_h: float) -> float:
    return longest_run(flags) * step_h


def usable_mask(tr: Track, crit: Criteria = DEFAULT) -> np.ndarray:
    """Power and direct-to-Earth link both available."""
    return (sun_up(tr) & (tr.sun_el >= crit.min_sun_el)
            & earth_up(tr, crit) & (tr.earth_el >= crit.min_earth_el))


def _next(events: list[dict], kind: str, t0: float) -> Optional[dict]:
    for ev in events:
        if ev["type"] == kind and ev["unix"] > t0:
            return {"utc": ev["utc"], "unix": ev["unix"], "hours_from_now": round((ev["unix"] - t0) / 3600.0, 2)}
    return None


def _clamped_steps(start_unix: int, wanted: int, step_s: int) -> tuple[int, bool]:
    """Number of samples to use: ``wanted`` or as many as the ephemeris allows."""
    avail = available_steps(start_unix, step_s)
    return (wanted, False) if wanted <= avail else (avail, True)


def site_summary(site: Site, when: datetime | str, window_days: float = SYNODIC_DAYS,
                 crit: Criteria = DEFAULT, search_days: int = SEARCH_DAYS) -> dict:
    """Headline numbers for one site at one instant."""
    t0 = parse_utc(when).timestamp()
    start = grid_start(parse_utc(when), STEP_S)
    n, truncated = _clamped_steps(start, int(search_days * 24) + 2, STEP_S)
    if n < 3:
        raise ValueError("time outside the supported ephemeris span (1900-01-01 to 2050-01-01)")
    tr = _track(site, cached_table(start, n, STEP_S), crit)
    now = track_at(site, [t0], crit.min_sun_fraction)

    sun_ev = find_events(site, tr, "sun", crit=crit)
    earth_ev = find_events(site, tr, "earth", crit=crit)
    is_sun_up = bool(sun_up(now)[0])
    is_earth_up = bool(earth_up(now, crit)[0])

    nw = min(int(round(window_days * 24)), n - 1)
    w = slice(0, nw)
    step_h = STEP_S / 3600.0
    sunlit = sun_up(tr)[w]
    earth_vis = earth_up(tr, crit)[w]
    usable = usable_mask(tr, crit)[w]

    searched = round((n - 1) / 24.0, 1)
    next_rise = _next(sun_ev, "sunrise", t0)
    next_set = _next(sun_ev, "sunset", t0)
    if is_sun_up:
        day = {"state": "in progress", "sunrise_utc": None,
               "sunset_utc": next_set["utc"] if next_set else None,
               "sunlight_hours_remaining": next_set["hours_from_now"] if next_set else None}
    else:
        after = _next(sun_ev, "sunset", next_rise["unix"]) if next_rise else None
        day = {"state": "next", "sunrise_utc": next_rise["utc"] if next_rise else None,
               "sunset_utc": after["utc"] if after else None,
               "sunlight_hours": round(after["hours_from_now"], 1) if after else None}

    return {
        "site": {"name": site.name, "lat": site.lat, "lon": site.lon},
        "utc": iso(t0),
        "horizon": site.horizon.describe(),
        "criteria": crit.describe(),
        "now": {
            "sun_el": round(float(now.sun_el[0]), 3), "sun_az": round(float(now.sun_az[0]), 2),
            "earth_el": round(float(now.earth_el[0]), 3), "earth_az": round(float(now.earth_az[0]), 2),
            "sun_horizon_el": round(float(now.sun_el[0] - now.sun_clear[0]), 3),
            "earth_horizon_el": round(float(now.earth_el[0] - now.earth_clear[0]), 3),
            "sun_disc_fraction": round(float(now.sun_frac[0]), 3),
            "sun_up": is_sun_up, "earth_up": is_earth_up,
            "usable": bool(usable_mask(now, crit)[0]),
        },
        "next_sunset": next_set,
        "next_sunrise": next_rise,
        "next_earthset": _next(earth_ev, "earthset", t0),
        "next_earthrise": _next(earth_ev, "earthrise", t0),
        "lunar_day": day,
        "search_days": searched,
        "search_truncated_at_ephemeris_end": truncated,
        "window": {
            "days": round(nw / 24.0, 2),
            "sunlit_hours": float(sunlit.sum() * step_h),
            "sunlit_share": round(float(sunlit.mean()), 4),
            "mean_sun_disc_fraction": round(float(tr.sun_frac[w].mean()), 4),
            "earth_visible_hours": float(earth_vis.sum() * step_h),
            "earth_visible_share": round(float(earth_vis.mean()), 4),
            "usable_hours": float(usable.sum() * step_h),
            "max_sun_el": round(float(tr.sun_el[w].max()), 2),
            "min_earth_el": round(float(tr.earth_el[w].min()), 2),
            "max_earth_el": round(float(tr.earth_el[w].max()), 2),
            "longest_dark_hours": _longest_run_hours(~sunlit, step_h),
            "longest_light_hours": _longest_run_hours(sunlit, step_h),
            "longest_earth_outage_hours": _longest_run_hours(~earth_vis, step_h),
            "longest_usable_run_hours": _longest_run_hours(usable, step_h),
            "min_sun_el": None if crit.min_sun_el <= -90 else crit.min_sun_el,
            "min_earth_el_required": None if crit.min_earth_el <= -90 else crit.min_earth_el,
        },
    }


def series(site: Site, start: datetime | str, hours: int, step_minutes: int = 60,
           crit: Criteria = DEFAULT, lookahead_days: int = SEARCH_DAYS) -> dict:
    """Elevation/azimuth curves for charts, plus rise/set events.

    Events are searched over the charted span and ``lookahead_days`` beyond it
    (hourly grid, refined), so "time to sunset" at the last charted hour is
    answered from the same list as everywhere else.
    """
    step_s = int(step_minutes * 60)
    s = grid_start(parse_utc(start), step_s)
    n, truncated = _clamped_steps(s, int(hours * 3600 // step_s) + 1, step_s)
    if n < 2:
        raise ValueError("time outside the supported ephemeris span (1900-01-01 to 2050-01-01)")
    tr = _track(site, cached_table(s, n, step_s), crit)
    s_h = grid_start(parse_utc(start), STEP_S)
    n_ev, _ = _clamped_steps(s_h, int((n - 1) * step_s // STEP_S) + int(lookahead_days * 24) + 2, STEP_S)
    tr_ev = _track(site, cached_table(s_h, n_ev, STEP_S), crit)
    r = lambda a, k=3: [round(float(x), k) for x in a]  # noqa: E731
    return {
        "site": {"name": site.name, "lat": site.lat, "lon": site.lon},
        "horizon": site.horizon.describe(),
        "criteria": crit.describe(),
        "start_utc": iso(s), "step_minutes": step_minutes, "count": n,
        "start_unix": s, "truncated_at_ephemeris_end": truncated,
        "events_searched_until_utc": iso(tr_ev.unix[-1]),
        "sun_el": r(tr.sun_el), "sun_az": r(tr.sun_az, 2),
        "earth_el": r(tr.earth_el), "earth_az": r(tr.earth_az, 2),
        "sun_horizon": r(tr.sun_el - tr.sun_clear, 3),
        "earth_horizon": r(tr.earth_el - tr.earth_clear, 3),
        "sun_frac": r(tr.sun_frac, 3),
        "sun_radius_deg": round(float(tr.sun_radius_deg.mean()), 4),
        "earth_radius_deg": round(float(tr.earth_radius_deg.mean()), 4),
        "lit": [int(x) for x in sun_up(tr)],
        "earth_vis": [int(x) for x in earth_up(tr, crit)],
        "usable": [int(x) for x in usable_mask(tr, crit)],
        "events": find_events(site, tr_ev, "sun", crit=crit) + find_events(site, tr_ev, "earth", crit=crit),
    }


def span_stats(site: Site, start: datetime | str, days: float = 365.0, step_minutes: int = 60,
               crit: Criteria = DEFAULT) -> dict:
    """Illumination and Earth-visibility statistics over a long span.

    Three illumination figures are reported because published studies differ
    in what they quote:
      mean_disc_fraction_pct  time-average of the visible fraction of the solar
                              disc ("average illumination")
      any_light_pct           share of time with any part of the disc visible
      lit_pct                 share of time meeting ``crit.min_sun_fraction``
    ``longest_dark_h`` is the longest run with no part of the disc visible.
    """
    step_s = int(step_minutes * 60)
    s = grid_start(parse_utc(start), step_s)
    n, truncated = _clamped_steps(s, int(round(days * 86400 / step_s)), step_s)
    if n > MAX_SPAN_SAMPLES:
        raise ValueError(f"request too large: {n} time samples (limit {MAX_SPAN_SAMPLES}); "
                         "use a shorter span or a coarser step")
    step_h = step_s / 3600.0
    # Long spans are worked through in blocks so the temporary arrays stay small (a 20-year hourly
    # span would otherwise hold 175,000 x 15 solar-disc strips several times over).
    flags = {k: np.empty(n, dtype=bool) for k in ("any", "lit", "centre", "earth", "usable", "full")}
    frac_sum = 0.0
    sun_lo = earth_lo = np.inf
    sun_hi = earth_hi = -np.inf
    last_unix = float(s)
    for i0 in range(0, n, SPAN_BLOCK):
        m = min(SPAN_BLOCK, n - i0)
        tr = _track(site, cached_table(s + i0 * step_s, m, step_s), crit)
        sl = slice(i0, i0 + m)
        flags["any"][sl] = tr.sun_frac > 0.0
        flags["lit"][sl] = sun_up(tr)
        flags["centre"][sl] = tr.sun_clear > 0
        flags["earth"][sl] = earth_up(tr, crit)
        flags["usable"][sl] = usable_mask(tr, crit)
        flags["full"][sl] = tr.sun_frac >= 0.999
        frac_sum += float(tr.sun_frac.sum())
        sun_lo, sun_hi = min(sun_lo, float(tr.sun_el.min())), max(sun_hi, float(tr.sun_el.max()))
        earth_lo, earth_hi = min(earth_lo, float(tr.earth_el.min())), max(earth_hi, float(tr.earth_el.max()))
        last_unix = float(tr.unix[-1])
    any_light, lit, ev, usable = flags["any"], flags["lit"], flags["earth"], flags["usable"]
    pct = lambda x: round(float(np.mean(x)) * 100.0, 2)  # noqa: E731
    return {
        "site": {"name": site.name, "lat": site.lat, "lon": site.lon},
        "horizon": site.horizon.describe(), "criteria": crit.describe(),
        "start_utc": iso(s), "end_utc": iso(last_unix), "days": round(n * step_s / 86400.0, 2),
        "step_minutes": step_minutes, "samples": n, "truncated_at_ephemeris_end": truncated,
        "mean_disc_fraction_pct": round(frac_sum / n * 100.0, 2),
        "any_light_pct": pct(any_light),
        "lit_pct": pct(lit),
        "centre_up_pct": pct(flags["centre"]),
        "longest_dark_h": _longest_run_hours(~any_light, step_h),
        "longest_below_rule_h": _longest_run_hours(~lit, step_h),
        "longest_light_h": _longest_run_hours(any_light, step_h),
        "longest_full_disc_h": _longest_run_hours(flags["full"], step_h),
        "earth_visible_pct": pct(ev),
        "longest_earth_outage_h": _longest_run_hours(~ev, step_h),
        "longest_earth_visible_h": _longest_run_hours(ev, step_h),
        "usable_pct": pct(usable),
        "longest_usable_h": _longest_run_hours(usable, step_h),
        "max_sun_el": round(sun_hi, 3), "min_sun_el": round(sun_lo, 3),
        "max_earth_el": round(earth_hi, 3), "min_earth_el": round(earth_lo, 3),
    }


def any_light_flags(site: Site, start: datetime | str, days: float = 365.0, step_minutes: int = 60) -> np.ndarray:
    """True where any part of the solar disc is above the site's horizon (used for site pairs)."""
    step_s = int(step_minutes * 60)
    s = grid_start(parse_utc(start), step_s)
    n, _ = _clamped_steps(s, int(round(days * 86400 / step_s)), step_s)
    if n > MAX_SPAN_SAMPLES:
        raise ValueError(f"request too large: {n} time samples (limit {MAX_SPAN_SAMPLES})")
    out = np.empty(n, dtype=bool)
    for i0 in range(0, n, SPAN_BLOCK):
        m = min(SPAN_BLOCK, n - i0)
        out[i0:i0 + m] = track(site, cached_table(s + i0 * step_s, m, step_s), 0.0).sun_frac > 0.0
    return out


def slip_grid(sites: Sequence[Site], start: datetime | str, n_dates: int = 60,
              date_step_hours: int = 24, window_days: float = 14.0,
              crit: Criteria = DEFAULT) -> dict:
    """Usable hours for every (site, candidate landing date) pair.

    For a landing at each candidate instant:
      total       hours within the following ``window_days`` when the Sun and
                  the Earth are both usable
      continuous  unbroken usable hours starting at touchdown (0 if you land
                  in the dark or without a link), capped at the window
      sunlit      hours with the Sun up in the window (ignores the Earth)
      earth       hours with the Earth in view in the window (ignores the Sun)
    plus whether the Sun and the Earth are up at the moment of touchdown.
    Cells whose window would run past the end of the ephemeris are ``None``.
    """
    if n_dates < 1 or n_dates > 400:
        raise ValueError("n_dates must be between 1 and 400")
    s = grid_start(parse_utc(start), STEP_S)
    w = int(round(window_days * 24))
    stride = int(date_step_hours)
    wanted = (n_dates - 1) * stride + w + 1
    n, truncated = _clamped_steps(s, wanted, STEP_S)
    table = cached_table(s, n, STEP_S)
    starts = np.arange(n_dates) * stride
    valid = starts + w <= n - 1
    sv = starts[valid]

    def fill(values, cast):
        out = [None] * n_dates
        for k, v in zip(np.nonzero(valid)[0], values):
            out[int(k)] = cast(v)
        return out

    rows = []
    for site in sites:
        tr = _track(site, table, crit)
        ok = usable_mask(tr, crit)
        csum = np.concatenate([[0], np.cumsum(ok)])
        total = csum[sv + w] - csum[sv]
        # run[i] = unbroken usable samples starting at i
        idx = np.arange(n)
        next_bad = np.where(~ok, idx, n)
        next_bad = np.minimum.accumulate(next_bad[::-1])[::-1]
        run = next_bad - idx
        cont = np.minimum(run[sv], w)
        lit = sun_up(tr)
        sunlit = np.concatenate([[0], np.cumsum(lit)])
        ev = earth_up(tr, crit) & (tr.earth_el >= crit.min_earth_el)
        earth = np.concatenate([[0], np.cumsum(ev)])
        rows.append({
            "site": {"name": site.name, "lat": site.lat, "lon": site.lon},
            "horizon": site.horizon.describe(),
            "total": fill(total, int),
            "continuous": fill(cont, int),
            "sunlit": fill(sunlit[sv + w] - sunlit[sv], int),
            "earth": fill(earth[sv + w] - earth[sv], int),
            "sun_up_at_landing": fill(lit[sv], bool),
            "earth_up_at_landing": fill(ev[sv], bool),
            "sun_clear_at_landing": fill(tr.sun_clear[sv], lambda x: round(float(x), 2)),
            "earth_clear_at_landing": fill(tr.earth_clear[sv], lambda x: round(float(x), 2)),
            "sun_el_at_landing": fill(tr.sun_el[sv], lambda x: round(float(x), 1)),
            "earth_el_at_landing": fill(tr.earth_el[sv], lambda x: round(float(x), 1)),
        })
    return {
        "start_utc": iso(s), "dates": [iso(s + int(k) * 3600) for k in starts],
        "date_step_hours": stride, "window_days": window_days, "window_hours": w,
        "criteria": crit.describe(), "truncated_at_ephemeris_end": truncated, "rows": rows,
    }
