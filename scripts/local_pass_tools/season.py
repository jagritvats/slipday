"""What limits the plan at C1 through a year: the Sun or the Earth?  python season.py <entry root>

The mission card for the connecting ridge C1 with the default need, for 365 landing dates from 18 Nov 2026
(one call to slipday.robust.mission_card with slip_days=365), counted by month and by what fails at the
stated point.
"""
import os
import sys
import tempfile
from collections import Counter, OrderedDict

root = sys.argv[1]
sys.path.insert(0, root)
os.environ.setdefault("SLIPDAY_HORIZON_CACHE", tempfile.mkdtemp(prefix="slipday_measure_cache_"))
from slipday import demstore, robust  # noqa: E402
from slipday.metrics import Criteria  # noqa: E402
from slipday.sites import get_site  # noqa: E402

print("grids:", demstore.status()["label"])
need_sun, need_earth = 240.0, 100.0
m = robust.mission_card(get_site("shackleton"), "2026-11-18", need_sun, need_earth, 14.0, Criteria(), 0.0, 2.0, 100.0, 365)
days = m["days"]
print("verdicts over", len(days), "landing dates:", dict(Counter(d["verdict"] for d in days)))
why = Counter()
months: "OrderedDict[str, Counter]" = OrderedDict()
for d in days:
    mon = d["landing_utc"][:7]
    months.setdefault(mon, Counter())[d["verdict"]] += 1
    if d["verdict"] == "yes":
        continue
    sun_short = d["sunlit_h"] < need_sun or any("Sun is behind" in r for r in d["reasons"])
    earth_short = d["earth_h"] < need_earth or any("Earth is behind" in r for r in d["reasons"])
    key = ("Sun and Earth" if sun_short and earth_short else "Sun only" if sun_short else "Earth only" if earth_short
           else "stated point passes; scatter or grid disagrees")
    why[key] += 1
    months[mon]["fails on " + key] += 1
print("the", sum(why.values()), "dates that are not a clear yes, by what fails at the stated point:", dict(why))
for mon, c in months.items():
    print(f"  {mon}: yes {c['yes']:2d}  not sure {c['not sure']:2d}  no {c['no']:2d}   |  Sun only {c['fails on Sun only']:2d}  "
          f"Earth only {c['fails on Earth only']:2d}  both {c['fails on Sun and Earth']:2d}  scatter/grid {c['fails on stated point passes; scatter or grid disagrees']:2d}")
