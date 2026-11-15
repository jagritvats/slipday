"""Cold and warm response time and peak memory of the main card on one terrain stack.

    SLIPDAY_DEM_DIR=<stack dir> SLIPDAY_HORIZON_CACHE=<empty dir> python scripts/bench_live_terrain.py [site ...]

Runs in its own process so the peak working set belongs to this stack alone.  Prints one JSON line.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def peak_mb() -> float:
    if os.name == "nt":
        class PMC(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        c = PMC(); c.cb = ctypes.sizeof(PMC)
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), ctypes.c_ulong]
        k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return round(c.PeakWorkingSetSize / 1e6, 1)
    import resource
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e3, 1)


def main() -> None:
    from fastapi.testclient import TestClient
    from slipday.api import app
    c = TestClient(app)
    sites = sys.argv[1:] or ["robust_pick"]
    out = {"dem_dir": os.environ.get("SLIPDAY_DEM_DIR"), "rows": []}
    for sid in sites:
        body = {"site": {"id": sid}, "landing": "2026-11-18T00:00:00Z", "earth_stations": True}
        t = time.time(); m1 = c.post("/api/mission", json=body).json(); cold = time.time() - t
        t = time.time(); c.post("/api/mission", json=body).json(); warm = time.time() - t
        out["rows"].append({"site": sid, "cold_s": round(cold, 2), "warm_s": round(warm, 2), "verdict": m1["verdict"],
                            "margin": m1["slip_margin_days"], "grid": m1["horizon"].get("dem_label"),
                            "points_passing": m1["sure"]["points_passing"], "terrain_grid": m1.get("terrain_grid")})
    out["peak_mb"] = peak_mb()
    print(json.dumps(out))


if __name__ == "__main__":
    main()
