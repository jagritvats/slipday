"""Fill data/horizon_cache/ with the skylines the default page needs, so a fresh deployment answers at once.

    python3 scripts/warm_cache.py            # for the grids installed in data/dem
    python3 scripts/warm_cache.py --no-80m   # for the 240 m configuration (what a deployment without the 231 MB grid uses)

For each default and replay site: the target, the 12 landing-scatter points (at 100 m, or one grid cell
where that is larger), the coarser-grid and near-field variants, the resolution ladder, and the ring
points of the landing circles (up to 92 more) and of the lander classes (up to 48 more, out to 2.5 km).
About 150 small files per site and configuration.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

if "--no-80m" in sys.argv:
    os.environ["SLIPDAY_SKIP_DEMS"] = "ldem_80s_80m"        # as if the 80 m file were not installed; same cache keys

from slipday import demstore, replay, robust  # noqa: E402
from slipday.metrics import Criteria  # noqa: E402
from slipday.sites import get_site, horizon_for  # noqa: E402

SITES = ["robust_pick", "shackleton", "malapert_earth", "im2", "im1"] + [m["site"] for m in replay.MISSIONS]
t0 = time.time()
n = 0
for sid in dict.fromkeys(SITES):
    s = get_site(sid)
    ens = robust.ensemble(s, 0.0, 2.0, 100.0)
    n += 1 + len(ens["scatter"]) + (ens["coarse"] is not None) + (ens["near"] is not None)
    for k in range(1, 5):
        if not horizon_for(s.lat, s.lon, 0.0, 2.0, True, variant=f"drop{k}").is_terrain:
            break
        n += 1
    circles = robust.landing_circles(s, "2026-11-18", 240.0, 100.0, 14.0, Criteria(), 0.0, 2.0, 2)
    n += max(0, circles.get("points", 1) - 1)
    classes = robust.lander_classes(s, "2026-11-18", 240.0, 100.0, 14.0, Criteria(), 0.0, 2.0, 2)
    n += max(0, classes.get("points", 0) - circles.get("points", 0))
print(f"{demstore.status()['label']}: {n} skylines ready in {time.time() - t0:.1f} s")
