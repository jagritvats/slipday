"""Print the Earth-check rows and the tile from the stored validation.  python -I show_earth.py <entry root>"""
import json
import os
import sys

root = sys.argv[1]
more = json.load(open(os.path.join(root, "data", "validation", "more_validation.json")))
for m in more["e"]["maps"]:
    ref = m["reference"]
    print(m["map"], "| file", ref["file"], "| points inside", ref["points_inside_map"], "| model means", m["model_mean_pct"])
    for rule, st in ref["by_rule"].items():
        print(f"   {rule:26s} n {st['n']} published {st['published_mean_pct']} computed {st['computed_mean_pct']} bias {st['bias_pts']:+} "
              f"MAE {st['mae_pts']} p95 {st['p95_abs_pts']} max {st['max_abs_pts']} within5 {st['within_5_pts_pct']} r {st['correlation']}")
print("tile_rule", more["e"].get("tile_rule"), "| generated", more["generated_utc"], "| seconds", more["seconds"])
print("dems", [d["label"] for d in more["dems"]])
main = json.load(open(os.path.join(root, "data", "validation", "terrain_validation.json")))
for h in main["headline"]:
    print("TILE:", h.get("k"), "|", h.get("v"), "|", h.get("s"), "|", h.get("tag"))
