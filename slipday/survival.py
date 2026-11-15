"""Survival across slip days: the hours a lander must ride through on stored energy, for each day of slip.

Rule R5 (LOCAL_PASS_2_RESULTS.md, pass 4).  For a landing on slip
day d the mission window is hours [24 d, 24 d + window) of the card's window.  Within it:
  longest night         the longest run of hours in which the Sun does not count as up under the card's Sun
                        rule (half the disc above the terrain skyline by default)
  longest Earth outage  the longest run of hours without Earth contact under the card's Earth rule (the Earth's
                        centre above the skyline by the card's mask, and a Deep Space Network complex with the
                        Moon at least 10 degrees up when the station rule is on)
A run still going at the end of the window is cut there and flagged; one going on at touchdown counts from
touchdown.  No battery model is used: these are hours, not watt-hours.

The card takes, for each slip day, the worst of the 13 touchdown points.  The map takes, for each point that
keeps a margin at all 13 touchdown points, the worst over those points and over the slip days that still pass.
"""
from __future__ import annotations

import time
from typing import Optional

import numpy as np

from . import field, scatterfield
from .ephem import available_steps, cached_table, grid_start, iso, parse_utc
from .geometry import Site, track
from .metrics import STEP_S, Criteria, earth_up, sun_up

CLASSES = [(0, 24, "under 1 day"), (24, 72, "1 to 3 days"), (72, 168, "3 to 7 days"), (168, 288, "7 to 12 days"),
           (288, 10 ** 6, "12 days or more")]          # rule R14 (follow-up): lunar-day units, chosen after seeing pass 4's spread


def run_end_lengths(flags: np.ndarray) -> np.ndarray:
    """For a (rows, hours) boolean array: at each hour, the length of the run of True that ends there (0 if False)."""
    f = np.asarray(flags, dtype=bool)
    out = np.zeros(f.shape, dtype=np.int32)
    run = np.zeros(f.shape[:-1], dtype=np.int32)
    for t in range(f.shape[-1]):
        run = np.where(f[..., t], run + 1, 0)
        out[..., t] = run
    return out


def longest_in_windows(flags: np.ndarray, starts, w: int, L: Optional[np.ndarray] = None):
    """Longest run of True inside each window [s, s + w) of each row, and whether that run is still going at the
    window's end.  ``flags`` is (rows, hours); returns two (rows, windows) arrays.  ``L`` may carry
    ``run_end_lengths(flags)`` when it has been worked out already."""
    f = np.asarray(flags, dtype=bool)
    if f.ndim == 1:
        f = f[None, :]
    L = run_end_lengths(f) if L is None else L
    starts = np.asarray(starts, dtype=int)
    best = np.zeros((f.shape[0], len(starts)), dtype=np.int32)
    past = np.zeros((f.shape[0], len(starts)), dtype=bool)
    t_idx = np.arange(w)
    for k, s in enumerate(starts):
        seg = L[:, s:s + w]
        lim = np.minimum(seg, t_idx[None, :] + 1)          # a run is counted from the window's start at most
        best[:, k] = lim.max(axis=1)
        last = lim[:, -1]
        cont = f[:, s + w] if s + w < f.shape[1] else np.zeros(f.shape[0], dtype=bool)
        past[:, k] = (last == best[:, k]) & (last > 0) & cont
    return best, past


EXTRA_DAYS = 45      # the table runs this far past the last window, so that a run starting inside it can end (rule R8)


def runs_of(flags: np.ndarray):
    """Start and end (inclusive) of every run of True in a 1-D series."""
    f = np.asarray(flags, dtype=bool).astype(np.int8)
    d = np.diff(np.concatenate([[0], f, [0]]))
    return np.nonzero(d == 1)[0], np.nonzero(d == -1)[0] - 1


def full_runs(flags: np.ndarray, starts, w: int):
    """Rule R8.  For each window [s, s + w) of each row: the longest run of True that is under way at s or begins
    inside the window, measured from s (if under way then) or from its start, to its end however far past the
    window; and whether that run is still going at the end of the series (so its length is a lower bound)."""
    f = np.asarray(flags, dtype=bool)
    if f.ndim == 1:
        f = f[None, :]
    starts = np.asarray(starts, dtype=int)
    best = np.zeros((f.shape[0], len(starts)), dtype=np.int32)
    open_ = np.zeros((f.shape[0], len(starts)), dtype=bool)
    last = f.shape[1] - 1
    for r in range(f.shape[0]):
        a, b = runs_of(f[r])
        if not len(a):
            continue
        S = starts[:, None]
        hit = (a[None, :] < S + w) & (b[None, :] >= S)
        length = np.where(hit, b[None, :] - np.maximum(a[None, :], S) + 1, 0)
        k = length.argmax(axis=1)
        best[r] = length[np.arange(len(starts)), k]
        open_[r] = (b[k] == last) & (best[r] > 0)
    return best, open_


def longest_run_hours(flags: np.ndarray) -> int:
    """Longest run of True in a 1-D hourly series (the same count as metrics._longest_run_hours at one hour)."""
    b, _ = longest_in_windows(np.asarray(flags, dtype=bool)[None, :], [0], len(flags))
    return int(b[0, 0])


def _flags(site: Site, table, crit: Criteria):
    tr = track(site, table, crit.min_sun_fraction)
    lit = sun_up(tr)
    earth = earth_up(tr, crit) & (tr.earth_el >= crit.min_earth_el)
    return lit, earth


def _sentence(word: str, unit_days: list, margin: int, past: list = None) -> str:
    if margin < 1 or margin >= len(unit_days):
        return ""
    a, b = unit_days[0], unit_days[margin]
    tail = " (still going when the window ends)" if past and past[margin] else ""
    if b > a:
        return f"slip {margin} day{'s' if margin != 1 else ''} and the longest {word} grows from {a} to {b} hours{tail}"
    if b < a:
        return f"slip {margin} day{'s' if margin != 1 else ''} and the longest {word} shrinks from {a} to {b} hours{tail}"
    return f"slip {margin} day{'s' if margin != 1 else ''} and the longest {word} stays at {a} hours{tail}"


def site_survival(members: list, index: dict, landing, window_days: float, crit: Criteria, slip_days: int,
                  verdicts: Optional[list] = None, margin: int = -1) -> dict:
    """Per slip day: longest night and longest Earth outage, at the target and at the worst touchdown point."""
    s = grid_start(parse_utc(landing), STEP_S)
    w = int(round(window_days * 24))
    n_win = min((slip_days - 1) * 24 + w + 1, available_steps(s, STEP_S))
    n = min(n_win + EXTRA_DAYS * 24, available_steps(s, STEP_S))
    table = cached_table(s, n, STEP_S)
    starts = np.arange(slip_days) * 24
    sv = starts[starts + w <= n_win - 1]
    a, b = index["scatter"]
    pts = members[a:b]
    lit = np.zeros((len(pts), n), dtype=bool)
    earth = np.zeros((len(pts), n), dtype=bool)
    for k, m in enumerate(pts):
        lit[k], earth[k] = _flags(m, table, crit)
    night, night_past = longest_in_windows(~lit, sv, w)
    out_h, out_past = longest_in_windows(~earth, sv, w)
    fn, fn_open = full_runs(~lit, sv, w)
    fo, fo_open = full_runs(~earth, sv, w)
    worst_n, worst_o = night.max(axis=0), out_h.max(axis=0)
    days = []
    for d in range(len(sv)):
        kn, ko = int(np.argmax(night[:, d])), int(np.argmax(out_h[:, d]))
        kfn, kfo = int(np.argmax(fn[:, d])), int(np.argmax(fo[:, d]))
        days.append({"day": int(d), "landing_utc": iso(s + int(sv[d]) * 3600),
                     "verdict": (verdicts[d] if verdicts and d < len(verdicts) else None),
                     "night_full_h": int(fn[kfn, d]), "night_full_open": bool(fn_open[kfn, d]),
                     "outage_full_h": int(fo[kfo, d]), "outage_full_open": bool(fo_open[kfo, d]),
                     "night_h": int(worst_n[d]), "night_target_h": int(night[0, d]), "night_past_window": bool(night_past[kn, d]),
                     "outage_h": int(worst_o[d]), "outage_target_h": int(out_h[0, d]), "outage_past_window": bool(out_past[ko, d])})
    nights = [x["night_full_h"] for x in days]
    outs = [x["outage_full_h"] for x in days]
    return {"available": True, "window_days": window_days, "window_hours": w, "points": len(pts), "margin_days": margin,
            "days": days, "rule": ("The longest night (the Sun not up under the card's Sun rule) and the longest Earth outage "
                                   "(no contact under the card's Earth rule) that a lander meets: runs under way at touchdown "
                                   "or beginning inside the mission window, measured to their end even past the window; worst "
                                   "of the touchdown points. Hours, not a battery model."),
            "night_sentence": _sentence("night", nights, margin) if margin >= 1 else "",
            "outage_sentence": _sentence("Earth outage", outs, margin) if margin >= 1 else "",
            "worst_over_passing_days": ({"night_h": int(max(nights[:margin + 1])), "outage_h": int(max(outs[:margin + 1]))}
                                        if margin >= 0 else None)}


_cache: dict = {}


def survival_map(start, n_dates: int, window_days: float, crit: Criteria, mask_deg: float, need_sun_h: float,
                 need_earth_h: float, sun_at_touchdown: bool, earth_at_touchdown: bool) -> Optional[dict]:
    """For each map point that keeps a margin at all 13 touchdown points: the worst longest night and the worst
    longest Earth outage over its 13 touchdown points and over the slip days that still pass."""
    fld, store = field.load(), scatterfield.load()
    if fld is None or store is None:
        return None
    r = scatterfield.robust_margin(start, n_dates, window_days, crit, mask_deg, need_sun_h, need_earth_h,
                                   sun_at_touchdown, earth_at_touchdown)
    if not r or not r.get("available"):
        return r
    key = (str(start), n_dates, window_days, field._key(0, 0, 0, 0, crit, mask_deg), need_sun_h, need_earth_h,
           sun_at_touchdown, earth_at_touchdown)
    if key in _cache:
        return _cache[key]
    t0 = time.time()
    robust = np.asarray(r["robust"])
    s = grid_start(parse_utc(start), STEP_S)
    w = int(round(window_days * 24))
    n_win = min((n_dates - 1) * 24 + w + 1, available_steps(s, STEP_S))
    n = min(n_win + EXTRA_DAYS * 24, available_steps(s, STEP_S))
    table = cached_table(s, n, STEP_S)
    pos = {int(i): k for k, i in enumerate(store["idx"])}
    keep = [int(i) for i in np.nonzero(robust >= 0)[0] if int(i) in pos]
    night = np.full(len(robust), -1, dtype=np.int32)
    outage = np.full(len(robust), -1, dtype=np.int32)
    night0 = np.full(len(robust), -1, dtype=np.int32)
    past = np.zeros(len(robust), dtype=bool)
    chunk = 40
    for c0 in range(0, len(keep), chunk):
        part = keep[c0:c0 + chunk]
        lat, lon, el = [], [], []
        for i in part:
            k = pos[i]
            lat += [fld["lat"][i]] + list(store["lat"][k])
            lon += [fld["lon"][i]] + list(store["lon"][k])
            el.append(np.asarray(fld["el"][i], dtype=np.float32)[None, :])
            el.append(np.asarray(store["el"][k], dtype=np.float32))
        el = np.concatenate(el, axis=0) * np.float32(field.EL_SCALE)
        lit, earth = field.evaluate_points(np.array(lat), np.array(lon), el, table, crit, mask_deg)
        dark, off = ~lit, ~earth
        for j, i in enumerate(part):
            rows = slice(13 * j, 13 * j + 13)
            m = int(robust[i])
            days = np.arange(m + 1) * 24
            bn, pn = full_runs(dark[rows], days, w)
            bo, _ = full_runs(off[rows], days, w)
            night[i], outage[i], night0[i] = int(bn.max()), int(bo.max()), int(bn[:, 0].max())
            past[i] = bool(pn[np.unravel_index(np.argmax(bn), bn.shape)])
    vals = night[night >= 0]
    hist = [{"label": lab, "lo": lo, "hi": hi, "points": int(((vals >= lo) & (vals < hi)).sum())} for lo, hi, lab in CLASSES]
    grows = int(((night > night0) & (night >= 0)).sum())
    out = {"available": True, "start_utc": r["start_utc"], "dates": r["dates"], "members": r["members"],
           "scatter_m": r["scatter_m"], "points": len(keep), "classes": hist,
           "night_grows_with_slip": grows, "night_largest_h": int(vals.max()) if len(vals) else None,
           "night_smallest_h": int(vals.min()) if len(vals) else None,
           "layers": {"night": [int(v) for v in night], "outage": [int(v) for v in outage], "night_day0": [int(v) for v in night0],
                      "night_past_window": [bool(v) for v in past]},
           "seconds": round(time.time() - t0, 2),
           "rule": ("Worst full night (and Earth outage) that a lander meets, measured to its end even past the window, over the 13 touchdown points and over the slip days that still "
                    "pass, inside the card's window; points that lose their margin are not coloured. Hours, not a battery model.")}
    _cache[key] = out
    if len(_cache) > 6:
        _cache.pop(next(iter(_cache)))
    return out
