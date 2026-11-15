"""Turn the full-map skylines into the served slip-margin layer, and check it against the 500 m close-up.

Reads the chunks written by ``scripts/addons/build_fullmap.py`` (whatever share is done), and evaluates them with
the close-up's own code (``slipday.field.per_date`` and ``field.statistics``, unchanged) for the page's opening plan:
landing 18 Nov 2026 00:00 UTC, 60 landing dates one day apart, 240 sunlit hours and 100 hours of Earth contact in
the first 14 days, Sun and Earth up at touchdown, half the Sun's disc, no extra mask. Both Earth rules are stored
(Deep Space Network station needed or not; the page's default is "needed").

Writes ``data/addons/fullmap/fullmap_<step>m.npz`` and ``fullmap_<step>m.json``.

    python scripts/addons/finish_fullmap.py --step-m 2000
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
os.environ.setdefault("SLIPDAY_DEM_DIR", os.path.join(ROOT, "data", "dem"))

from build_fullmap import OUT, grid, order  # noqa: E402
from slipday import field, scatterfield  # noqa: E402
from slipday.metrics import Criteria  # noqa: E402

PLAN = {"start": "2026-11-18T00:00:00Z", "n_dates": 60, "window_days": 14.0, "need_sun_h": 240.0, "need_earth_h": 100.0,
        "sun_at_touchdown": True, "earth_at_touchdown": True, "min_sun_fraction": 0.5, "mask_deg": 0.0}
RULES = {"stations": True, "no_stations": False}
LAYERS = ("margin", "good", "worst_sun", "median_sun", "worst_total", "median_total")
CLOSE_DIR = os.path.join(ROOT, "data", "field")


def crit(stations: bool) -> Criteria:
    return Criteria(PLAN["min_sun_fraction"], -90.0, -90.0, 0.0, stations)


def stats_for(field_dir: str, stations: bool):
    field.FIELD_DIR = field_dir
    field.reload()
    pd = field.per_date(PLAN["start"], PLAN["n_dates"], 24, PLAN["window_days"], crit(stations), PLAN["mask_deg"])
    st = field.statistics(pd, PLAN["need_sun_h"], PLAN["need_earth_h"], PLAN["sun_at_touchdown"], PLAN["earth_at_touchdown"])
    return pd, st


def assemble(sub: str):
    files = sorted(glob.glob(os.path.join(sub, "chunk_*.npz")))
    parts = [np.load(f) for f in files]
    if not parts:
        sys.exit("no chunks yet")
    cat = {k: np.concatenate([p[k] for p in parts]) for k in ("idx", "lat", "lon", "el", "height_m", "grid_m")}
    secs = float(sum(float(p["seconds"]) for p in parts))
    srt = np.argsort(cat["idx"])
    return {k: v[srt] for k, v in cat.items()}, len(files), secs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step-m", type=float, default=2000.0)
    a = ap.parse_args()
    step = int(a.step_m)
    sub = os.path.join(OUT, "chunks_%dm" % step)
    with open(os.path.join(sub, "grid.json")) as fh:
        gmeta = json.load(fh)
    c, X, Y = grid(a.step_m)
    n = len(c)
    pts, nchunks, cpu_s = assemble(sub)
    idx = pts["idx"].astype(np.int64)
    have_terrain = np.isfinite(pts["height_m"])
    print(f"{len(idx)} of {n * n} points done ({nchunks} chunks); without terrain: {int((~have_terrain).sum())}", flush=True)

    # coverage, in plain counts
    r, col = np.divmod(idx, n)
    lattice = (r % 2 == 0) & (col % 2 == 0)
    n_lattice = int(((np.arange(n) % 2 == 0).sum()) ** 2)
    rr = np.hypot(X.ravel()[idx], Y.ravel()[idx])
    inside80 = pts["lat"] <= -80.0
    full_lat = -(90.0 - np.rad2deg(2.0 * np.arctan(np.hypot(X.ravel(), Y.ravel()) / (2.0 * 1737400.0))))
    coverage = {"grid_points": n * n, "done": int(len(idx)), "share_done": round(len(idx) / (n * n), 4),
                "half_spacing_lattice_points": n_lattice, "half_spacing_lattice_done": int(lattice.sum()),
                "points_south_of_80S": int((full_lat <= -80.0).sum()), "points_south_of_80S_done": int(inside80.sum()),
                "complete": bool(len(idx) == n * n),
                "complete_at_m": (step if len(idx) == n * n else (2 * step if lattice.sum() == n_lattice else None)),
                "chunks": nchunks, "worker_cpu_seconds": round(cpu_s, 1),
                "seconds_per_point_per_process": round(cpu_s / max(len(idx), 1), 3)}

    # the close-up's own numbers for the same plan (what /api/slipmap and /api/robust-map return)
    close = {}
    for name, stations in RULES.items():
        _, st = stats_for(CLOSE_DIR, stations)
        rb = scatterfield.robust_margin(PLAN["start"], PLAN["n_dates"], PLAN["window_days"], crit(stations), PLAN["mask_deg"],
                                        PLAN["need_sun_h"], PLAN["need_earth_h"], True, True)
        close[name] = {"margin": np.asarray(st["margin"]).copy(), "good": np.asarray(st["good"]).copy(),
                       "robust": np.asarray(rb["robust"]).copy() if rb and rb.get("available") else None}
    cpts = np.load(os.path.join(CLOSE_DIR, "pole_points.npz"))
    cel = np.load(os.path.join(CLOSE_DIR, "pole_el_i16.npy"), mmap_mode="r")
    with open(os.path.join(CLOSE_DIR, "pole_field.json")) as fh:
        cmeta = json.load(fh)
    scatterfield.reload()

    # evaluate the full-map skylines with the same code, through a field directory of the same layout
    tmp = tempfile.mkdtemp(prefix="fullmap_field_")
    try:
        ok = np.nonzero(have_terrain)[0]
        np.save(os.path.join(tmp, "pole_el_i16.npy"), pts["el"][ok])
        np.savez(os.path.join(tmp, "pole_points.npz"), lat=pts["lat"][ok], lon=pts["lon"][ok], height_m=pts["height_m"][ok])
        with open(os.path.join(tmp, "pole_field.json"), "w") as fh:
            json.dump({"n": n, "step_m": a.step_m, "mast_m": gmeta["mast_m"], "dem_fingerprint": gmeta["dem_fingerprint"]}, fh)
        res = {}
        t0 = time.time()
        for name, stations in RULES.items():
            pd, st = stats_for(tmp, stations)
            res[name] = {}
            for k in LAYERS:
                v = np.full(len(idx), -9, dtype=np.int16)
                v[ok] = np.asarray(st[k]).astype(np.int16)
                res[name][k] = v
            dates = pd["dates"]
        eval_s = time.time() - t0
        field.FIELD_DIR = CLOSE_DIR
        field.reload()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # agreement at the points the two grids share (exactly the same positions)
    X0, Y0 = X.ravel()[idx], Y.ravel()[idx]
    half_c = cmeta["half_km"] * 1000.0
    cstep = cmeta["step_m"]
    inside = (np.abs(X0) < half_c) & (np.abs(Y0) < half_c)
    ccol = np.round((X0 + half_c - cstep / 2) / cstep).astype(int)
    crow = np.round((half_c - cstep / 2 - Y0) / cstep).astype(int)
    k_full = np.nonzero(inside)[0]
    k_close = crow[inside] * cmeta["n"] + ccol[inside]
    agree = {"shared_points": int(len(k_full))}
    if len(k_full):
        dpos = np.hypot(pts["lat"][k_full] - cpts["lat"][k_close], (pts["lon"][k_full] - cpts["lon"][k_close]) *
                        np.cos(np.deg2rad(pts["lat"][k_full])))
        sky = np.abs(pts["el"][k_full].astype(np.int32) - np.asarray(cel[k_close]).astype(np.int32))
        agree["largest_position_difference_deg"] = float(dpos.max())
        agree["skylines_identical"] = int((sky.max(axis=1) == 0).sum())
        agree["largest_skyline_difference_deg"] = round(float(sky.max()) * 0.002, 4)
        for name in RULES:
            mf = res[name]["margin"][k_full].astype(int)
            mc = close[name]["margin"][k_close].astype(int)
            gf = res[name]["good"][k_full].astype(int)
            gc = close[name]["good"][k_close].astype(int)
            row = {"same_margin": int((mf == mc).sum()), "same_good_dates": int((gf == gc).sum()),
                   "same_verdict_on_planned_date": int(((mf >= 0) == (mc >= 0)).sum()),
                   "planned_date_meets_need_here": int((mc >= 0).sum())}
            rb = close[name]["robust"]
            if rb is not None:
                rk = rb[k_close].astype(int)
                col_ = mc >= 0
                row["close_up_13_point_check"] = {
                    "coloured_at_the_point": int(col_.sum()),
                    "same_margin_at_all_13_points": int((col_ & (rk == mc)).sum()),
                    "shorter_margin_at_all_13_points": int((col_ & (rk >= 0) & (rk < mc)).sum()),
                    "margin_lost_at_13_points": int((rk == scatterfield.LOST).sum()),
                    "not_re_checked": int((rk == scatterfield.NOT_CHECKED).sum())}
            agree[name] = row

    out_npz = os.path.join(OUT, "fullmap_%dm.npz" % step)
    arrays = {"idx": idx.astype(np.int32), "lat": pts["lat"], "lon": pts["lon"], "height_m": pts["height_m"],
              "terrain_m": pts["grid_m"]}
    for name in RULES:
        for k in LAYERS:
            arrays[f"{name}__{k}"] = res[name][k]
    tmpf = out_npz + ".tmp.npz"
    np.savez_compressed(tmpf, **arrays)
    os.replace(tmpf, out_npz)
    counts = {}
    for name in RULES:
        m = res[name]["margin"][have_terrain]
        counts[name] = {"planned_date_fails": int((m == -1).sum()), "survives_0_days": int((m == 0).sum()),
                        "survives_1_to_4_days": int(((m >= 1) & (m <= 4)).sum()),
                        "survives_5_days_or_more": int((m >= 5).sum()), "largest_margin": int(m.max()) if len(m) else None}
    tg = {f"{float(g):g}": int((pts["grid_m"] == g).sum()) for g in np.unique(pts["grid_m"][have_terrain])}
    meta = {"step_m": a.step_m, "n": n, "axis_first_m": float(c[0]), "axis_last_m": float(c[-1]),
            "made_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "plan": PLAN,
            "earth_rules": {"stations": "Earth contact only while a Deep Space Network station sees the Moon (page default)",
                            "no_stations": "Earth above the skyline is enough"},
            "dates": dates, "evaluation_seconds": round(eval_s, 1), "coverage": coverage,
            "points_without_terrain": int((~have_terrain).sum()), "terrain_under_points_m": tg,
            "dem_name": gmeta["dem_name"], "dem_fingerprint": gmeta["dem_fingerprint"], "dem_label": gmeta["dem_label"],
            "close_up_dem_fingerprint": cmeta.get("dem_fingerprint"), "mast_m": gmeta["mast_m"],
            "counts": counts, "agreement_with_close_up": agree, "npz": os.path.basename(out_npz)}
    with open(os.path.join(OUT, "fullmap_%dm.json" % step), "w") as fh:
        json.dump(meta, fh, indent=1)
    print(json.dumps({k: meta[k] for k in ("coverage", "counts", "agreement_with_close_up", "terrain_under_points_m",
                                           "evaluation_seconds")}, indent=1))


if __name__ == "__main__":
    main()
