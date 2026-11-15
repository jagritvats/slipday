"""Slip-map headline figures on the rebuilt field.  python verify_map.py <entry root>"""
import os
import sys
import tempfile
import time

import numpy as np

root = sys.argv[1]
sys.path.insert(0, root)
os.environ.setdefault("SLIPDAY_HORIZON_CACHE", tempfile.mkdtemp(prefix="slipday_measure_cache_"))
from fastapi.testclient import TestClient  # noqa: E402

from slipday import field, refmaps  # noqa: E402
from slipday.api import app  # noqa: E402
from slipday.dem import MOON_RADIUS_M  # noqa: E402

client = TestClient(app)
body = {"start": "2026-11-18T00:00:00Z", "n_dates": 60, "need_sun_h": 240, "need_earth_h": 100, "window_days": 14}
t0 = time.time()
r = client.post("/api/slipmap", json=body).json()
t1 = time.time()
client.post("/api/slipmap", json=body)
print(f"slip map 18 Nov 2026: first call {t1 - t0:.2f} s, second {time.time() - t1:.2f} s; notes {r['notes']}")
margin, good = np.array(r["layers"]["margin"]), np.array(r["layers"]["good"])
print("points", margin.size, "| coloured (margin >= 0)", int((margin >= 0).sum()), f"= {100 * (margin >= 0).mean():.2f} %",
      "| largest margin", int(margin.max()), "| most good dates", int(good.max()))
fld = field.load()
k = int(np.argmax(good))
la, lo = float(fld["lat"][k]), float(fld["lon"][k])
m = refmaps.load(os.path.join(root, "data", "reference", "AVGVISIB_85S_060M_201608.TIF"))
z = np.asarray(m.z)
row, col = np.unravel_index(int(np.argmax(z)), z.shape)
x, y = m.x0_m + col * m.pixel_m, m.y0_m - row * m.pixel_m
rr = np.hypot(x, y)
mla, mlo = -(90.0 - np.rad2deg(2.0 * np.arctan(rr / (2.0 * MOON_RADIUS_M)))), np.rad2deg(np.arctan2(x, y))
c = np.sin(np.deg2rad(la)) * np.sin(np.deg2rad(mla)) + np.cos(np.deg2rad(la)) * np.cos(np.deg2rad(mla)) * np.cos(np.deg2rad(lo - mlo))
print(f"map point with the most good dates: {la:.4f}, {lo:.4f} (margin {int(margin[k])}, good {int(good[k])}); "
      f"maximum of the LOLA 60 m Sun map: {mla:.4f}, {mlo:.4f} (value {z.max() * m.scale:.4f}); "
      f"distance {float(np.arccos(np.clip(c, -1, 1))) * MOON_RADIUS_M:.0f} m")
order = np.argsort(-good)
k2 = int(order[1])
c2 = (np.sin(np.deg2rad(fld['lat'][k2])) * np.sin(np.deg2rad(mla))
      + np.cos(np.deg2rad(fld['lat'][k2])) * np.cos(np.deg2rad(mla)) * np.cos(np.deg2rad(fld['lon'][k2] - mlo)))
print(f"second-best map point is {float(np.arccos(np.clip(c2, -1, 1))) * MOON_RADIUS_M / 1000:.2f} km from that maximum")
