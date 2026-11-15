"""Train the learned instant estimate (slipday/addons/estimate.py) and measure it honestly.

    python scripts/addons/train_estimate.py

Training answers: the whole-map layer (data/addons/fullmap, 92,416 points every 2 km, page's opening plan, station
Earth rule). Features: cheap terrain numbers from the 80 m LOLA mosaic (estimate.features).

Two tests, neither used for any tuning (all model settings are fixed below, chosen before any test was run):

A. Spatial blocks. The map is cut into 8 x 8 blocks (76 km square). Blocks are dealt into 5 groups; each group is
   predicted by a model trained on the other groups, with a 4 km strip round the held-out blocks also left out of
   training. Compared with nearest neighbour from the training points (i.e. where the grid has no answers nearby).

B. The page's real case: a click between grid points. The 14,400 close-up points (500 m apart, 60 km square round the
   pole, same skyline method) minus the 900 that sit on the 2 km grid = 13,500 off-grid points. The model is
   trained on the whole map minus that square and a 4 km strip; nearest neighbour uses the full 2 km grid,
   exactly as the page's stand-in does.

Writes data/addons/estimate/model.joblib and report.json.
"""
from __future__ import annotations

import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "6")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
os.environ.setdefault("SLIPDAY_DEM_DIR", os.path.join(ROOT, "data", "dem"))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor  # noqa: E402

from slipday.addons import estimate as E  # noqa: E402

OUT = os.path.join(ROOT, "data", "addons", "estimate")
SEED = 26
BLOCKS = 8
FOLDS = 5
BUFFER_M = 4000.0
PLAN_START = "2026-11-18T00:00:00Z"


def make_models():
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=40,
                                         l2_regularization=1.0, random_state=SEED)
    reg = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=40,
                                        l2_regularization=1.0, random_state=SEED)
    return clf, reg


def fit(F, margin):
    clf, reg = make_models()
    clf.fit(F, (margin >= 0).astype(int))
    reg.fit(F, margin.astype(float))
    return {"classifier": clf, "regressor": reg, "threshold": 0.5}


def predict(m, F):
    yes = m["classifier"].predict_proba(F)[:, 1] >= m["threshold"]
    mg = np.where(yes, np.maximum(0, np.rint(m["regressor"].predict(F))), -1).astype(int)
    return mg


def scores(truth, pred) -> dict:
    t_yes, p_yes = truth >= 0, pred >= 0
    no = ~t_yes
    return {
        "points": int(truth.size),
        "truly_yes": int(t_yes.sum()),
        "verdict_accuracy": round(float((t_yes == p_yes).mean()), 4),
        "margin_error_days_mean": round(float(np.abs(truth - pred).mean()), 3),
        "margin_error_days_mean_where_truly_yes": (round(float(np.abs(truth - pred)[t_yes].mean()), 3)
                                                   if t_yes.any() else None),
        "false_yes": int((p_yes & no).sum()),
        "false_yes_share_of_true_no": round(float((p_yes & no).sum() / max(1, no.sum())), 4),
        "missed_yes": int((~p_yes & t_yes).sum()),
        "missed_yes_share_of_true_yes": round(float((~p_yes & t_yes).sum() / max(1, t_yes.sum())), 4),
    }


def features_chunked(x, y):
    out = []
    for i in range(0, x.size, 8000):
        out.append(E.features(x[i:i + 8000], y[i:i + 8000]))
    return np.vstack(out)


def close_up_margins():
    """The close-up's own slip margins for the opening plan (the same code /api/slipmap runs)."""
    from slipday import field
    from slipday.api import SlipMapRequest
    req = SlipMapRequest(start=PLAN_START)
    fld = field.load()
    pd = field.per_date(req.start, req.n_dates, 24, req.window_days, req.criteria(), req.mask_deg)
    st = field.statistics(pd, req.need_sun_h, req.need_earth_h, req.sun_at_touchdown, req.earth_at_touchdown)
    z = np.load(os.path.join(ROOT, "data", "field", "pole_points.npz"))
    return np.asarray(z["lat"]), np.asarray(z["lon"]), np.asarray(st["margin"]).ravel().astype(int), fld["meta"]


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    z = np.load(os.path.join(ROOT, "data", "addons", "fullmap", "fullmap_2000m.npz"))
    x, y = E.project(z["lat"], z["lon"])
    margin = np.asarray(z["stations__margin"]).astype(int)
    print(f"{margin.size} points, {int((margin >= 0).sum())} yes", flush=True)
    t = time.time()
    F = features_chunked(x, y)
    feat_s = time.time() - t
    print(f"features {F.shape} in {feat_s:.1f} s", flush=True)

    # ---------------- A: spatial blocks
    edge = 304000.0
    bsize = 2 * edge / BLOCKS
    bc = np.clip(((x + edge) // bsize).astype(int), 0, BLOCKS - 1)
    br = np.clip(((edge - y) // bsize).astype(int), 0, BLOCKS - 1)
    block = br * BLOCKS + bc
    rng = np.random.default_rng(SEED)
    fold_of_block = rng.permutation(np.arange(BLOCKS * BLOCKS) % FOLDS)
    fold = fold_of_block[block]
    pred_m = np.full(margin.size, -9)
    pred_nn = np.full(margin.size, -9)
    nn_dist = np.zeros(margin.size)
    for k in range(FOLDS):
        test = fold == k
        # distance from each point to the nearest held-out point (strip round the held-out blocks)
        d, _ = cKDTree(np.column_stack([x[test], y[test]])).query(np.column_stack([x, y]), p=np.inf)
        train = (~test) & (d > BUFFER_M)
        m = fit(F[train], margin[train])
        pred_m[test] = predict(m, F[test])
        dd, j = cKDTree(np.column_stack([x[train], y[train]])).query(np.column_stack([x[test], y[test]]))
        pred_nn[test] = margin[train][j]
        nn_dist[test] = dd
        print(f"fold {k}: {int(test.sum())} test, {int(train.sum())} train", flush=True)
    A = {"model": scores(margin, pred_m), "nearest_neighbour_from_training_points": scores(margin, pred_nn),
         "always_no": scores(margin, np.full(margin.size, -1)),
         "nearest_neighbour_distance_km_median": round(float(np.median(nn_dist)) / 1000, 1)}
    print("A", json.dumps(A, indent=1), flush=True)

    # ---------------- B: clicks between grid points, inside the close-up square
    clat, clon, cmargin, cmeta = close_up_margins()
    cx, cy = E.project(clat, clon)
    tree_all = cKDTree(np.column_stack([x, y]))
    dd, j = tree_all.query(np.column_stack([cx, cy]))
    on_grid = dd < 1.0
    agree = int((cmargin[on_grid] == margin[j[on_grid]]).sum())
    print(f"close-up: {cmargin.size} points, {int(on_grid.sum())} on the 2 km grid, {agree} agree", flush=True)
    off = ~on_grid
    half = 30000.0 + BUFFER_M
    trainB = ~((np.abs(x) < half) & (np.abs(y) < half))
    mB = fit(F[trainB], margin[trainB])
    CF = features_chunked(cx[off], cy[off])
    pB = predict(mB, CF)
    nnB = margin[j[off]]
    B = {"close_up_points": int(cmargin.size), "on_2km_grid": int(on_grid.sum()),
         "on_grid_same_margin": agree, "off_grid_test_points": int(off.sum()),
         "nearest_grid_point_distance_km_median": round(float(np.median(dd[off])) / 1000, 2),
         "model": scores(cmargin[off], pB), "nearest_neighbour_from_full_2km_grid": scores(cmargin[off], nnB),
         "always_no": scores(cmargin[off], np.full(int(off.sum()), -1))}
    print("B", json.dumps(B, indent=1), flush=True)

    # ---------------- B2 (second design, added after B's first result): terrain + the nearby grid answers
    # Training points see their grid neighbours within 2.9 km, never themselves; test clicks see the grid points
    # within 2.9 km of them, the same information the page's nearest-neighbour stand-in has.
    G = E.grid_features(x, y, margin, x, y, exclude_self=True)
    CG = E.grid_features(x, y, margin, cx[off], cy[off], exclude_self=False)
    FH, CFH = np.hstack([F, G]), np.hstack([CF, CG])
    mH = fit(FH[trainB], margin[trainB])
    pH = predict(mH, CFH)
    B["terrain_plus_grid_model"] = scores(cmargin[off], pH)
    B["terrain_plus_grid_note"] = ("second design, tried after the terrain-only result was seen; its settings are "
                                   "the same fixed ones, and it was run once")
    print("B2", json.dumps(B["terrain_plus_grid_model"], indent=1), flush=True)

    # ---------------- ship decision: the page's case is B (the grid covers the whole map)
    nb = B["nearest_neighbour_from_full_2km_grid"]

    def beats_nn(s):
        return (s["verdict_accuracy"] > nb["verdict_accuracy"] and s["margin_error_days_mean"] < nb["margin_error_days_mean"]
                and s["false_yes"] <= nb["false_yes"])
    use_grid = beats_nn(B["terrain_plus_grid_model"]) and not beats_nn(B["model"])
    beats = beats_nn(B["model"]) or use_grid
    mb = B["terrain_plus_grid_model"] if use_grid else B["model"]

    # ---------------- final model on every point, and timing
    final = fit(FH if use_grid else F, margin)
    final["uses_grid"] = bool(use_grid)
    joblib.dump(final, os.path.join(OUT, "model.joblib"), compress=3)
    t = time.time()
    for i in range(50):
        px, py = x[i * 997] + 700.0, y[i * 997] + 300.0
        f1 = E.features([px], [py])
        if use_grid:
            g = E.grid()
            f1 = np.hstack([f1, E.grid_features(g["x"], g["y"], g["margin"], [px], [py], False, tree=g["tree"])])
        final["classifier"].predict_proba(f1)
        final["regressor"].predict(f1)
    per_ms = (time.time() - t) / 50 * 1000
    size = os.path.getsize(os.path.join(OUT, "model.joblib"))
    rep = {
        "made_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "plan": "landing 18 Nov 2026, 60 landing dates, 240 sunlit h and 100 h Earth contact (stations) in 14 days",
        "training_points": int(margin.size), "features": E.FEATURE_NAMES,
        "verdict": "yes = the planned landing date meets the need (slip margin 0 or more); margin -1 = fails",
        "margin_error_convention": "a 'no' counts as margin -1, so calling a 0-day point 'no' is 1 day off",
        "model": "two histogram gradient-boosted tree models (scikit-learn): one for yes/no, one for the margin",
        "settings_fixed_before_testing": True,
        "test_A_spatial_blocks": A, "test_B_clicks_between_grid_points": B,
        "model_beats_nearest_neighbour_on_page_case": bool(beats),
        "covers_points_the_grid_cannot": False,
        "covers_note": "the 2 km grid already covers the whole 80 m map, so the model adds no coverage",
        "ships_on_page": bool(beats),
        "served_summary": {
            "tested_on": "13,500 close-up points between the 2 km grid points, held out of training",
            "served_model": "terrain plus nearby grid answers" if use_grid else "terrain only",
            "verdict_accuracy": mb["verdict_accuracy"], "margin_error_days_mean": mb["margin_error_days_mean"],
            "false_yes_share_of_true_no": mb["false_yes_share_of_true_no"],
            "nearest_grid_point_verdict_accuracy": nb["verdict_accuracy"],
            "nearest_grid_point_margin_error_days_mean": nb["margin_error_days_mean"],
            "nearest_grid_point_false_yes_share_of_true_no": nb["false_yes_share_of_true_no"],
            "spatial_block_verdict_accuracy": A["model"]["verdict_accuracy"],
        },
        "model_file_bytes": size, "estimate_ms_per_point": round(per_ms, 1),
        "feature_seconds_all_points": round(feat_s, 1), "seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    print(json.dumps({k: rep[k] for k in ("ships_on_page", "model_file_bytes", "estimate_ms_per_point",
                                          "seconds")}), flush=True)


if __name__ == "__main__":
    main()
