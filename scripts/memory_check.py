"""Start a Slipday server, run a fixed request sequence (including bursts of new sites) and report memory.

    python3 scripts/memory_check.py --port 8190                 # the installed grids
    python3 scripts/memory_check.py --port 8191 --no-80m        # the 240 m configuration (free-host deployment)

Memory is read from /proc/<pid>/status of the server process: VmRSS (resident), RssAnon (the part that
is the process's own allocations), RssFile (mapped files, which the kernel can drop) and VmHWM (peak).
Linux only (it needs /proc).  On Windows or macOS run it inside the container:
    docker run --rm slipday python scripts/memory_check.py --no-80m
For a heavier, concurrent load against a memory-limited container see scripts/stress_check.py.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mem(pid):
    out = {}
    with open(f"/proc/{pid}/status") as fh:
        for line in fh:
            k, _, v = line.partition(":")
            if k in ("VmRSS", "RssAnon", "RssFile", "VmHWM"):
                out[k] = round(int(v.split()[0]) / 1024)
    return out


def call(base, path, body=None, timeout=300):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"} if body is not None else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, len(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8190)
    ap.add_argument("--no-80m", action="store_true")
    ap.add_argument("--no-field", action="store_true")
    a = ap.parse_args()
    env = dict(os.environ)
    tmp = tempfile.mkdtemp(prefix="slipday_mem_")
    env["SLIPDAY_HORIZON_CACHE"] = os.path.join(tmp, "hcache")           # empty skyline cache: every site is new
    env.setdefault("MALLOC_ARENA_MAX", "2")
    if a.no_80m:
        env["SLIPDAY_SKIP_DEMS"] = "ldem_80s_80m"          # as if the 80 m file were not installed
    if a.no_field:
        env["SLIPDAY_FIELD_DIR"] = os.path.join(tmp, "nofield")
    t0 = time.time()
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "slipday.api:app", "--host", "127.0.0.1", "--port", str(a.port),
                             "--log-level", "warning"], cwd=HERE, env=env)
    base = f"http://127.0.0.1:{a.port}"
    rows = []
    try:
        for _ in range(100):
            try:
                call(base, "/api/health")
                break
            except Exception:
                time.sleep(0.1)
        rows.append(("cold start to first /api/health", round(time.time() - t0, 2), mem(proc.pid)))

        def step(label, fn):
            t = time.time()
            fn()
            rows.append((label, round(time.time() - t, 2), mem(proc.pid)))

        polar = [{"id": i} for i in ("shackleton", "malapert_earth", "im2", "im1", "shackleton_rim", "ridge_c2")]
        opts = {"start": "2026-11-14T00:00:00Z"}
        step("page load: /api/sites, /api/map, map image", lambda: [call(base, p) for p in ("/api/sites", "/api/map", "/api/map/image", "/api/validation", "/api/terrain/validation", "/api/hindcast")])
        step("slip grid, 4 sites x 60 dates with the 13-point scatter band", lambda: call(base, "/api/slipgrid", {"sites": polar[:4], "n_dates": 60, "scatter_m": 100, **opts}))
        step("mission card x 4 sites", lambda: [call(base, "/api/mission", {"site": s, "landing": opts["start"]}) for s in polar[:4]])
        step("compare 4 sites x 60 days", lambda: call(base, "/api/compare", {"sites": polar[:4], "hours": 1440, **opts}))
        step("year table x 4 (ladder + scatter band)", lambda: [call(base, f"/api/stats?site={s['id']}&start=2026-11-14&days=365&ladder=true&scatter_m=100") for s in polar[:4]])
        step("site pairs, 4 sites x 365 days", lambda: call(base, "/api/pairs", {"sites": polar[:4], "days": 365, **opts}))
        step("slip map (every field point x 60 dates)", lambda: call(base, "/api/slipmap", {"n_dates": 60, **opts}))
        step("20-year hourly statistics, one site", lambda: call(base, "/api/stats?site=shackleton&start=2017-01-01&days=7300"))

        def burst(n, seed):
            def one(i):
                return call(base, f"/api/stats?lat={-89.0 + 0.007 * i - 0.3 * seed:.4f}&lon={(37 * i + 11 * seed) % 360 - 180}&start=2026-11-14&days=365")
            with cf.ThreadPoolExecutor(n) as ex:
                res = list(ex.map(one, range(n)))
            assert all(r[0] == 200 for r in res)
        step("24 parallel year statistics at never-seen polar points", lambda: burst(24, 0))
        step("96 parallel year statistics at never-seen polar points", lambda: burst(96, 1))
        step("second slip map (another date) + 4 more mission cards", lambda: [call(base, "/api/slipmap", {"n_dates": 60, "start": "2027-03-01"})] +
             [call(base, "/api/mission", {"site": s, "landing": "2027-03-01"}) for s in polar[2:]])
        time.sleep(1.0)
        rows.append(("idle, 1 s later", 0.0, mem(proc.pid)))
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{'step':68s} {'s':>7s} {'RSS':>6s} {'anon':>6s} {'file':>6s} {'peak':>6s}   (MB)")
    for label, sec, m in rows:
        print(f"{label:68s} {sec:7.2f} {m.get('VmRSS', 0):6d} {m.get('RssAnon', 0):6d} {m.get('RssFile', 0):6d} {m.get('VmHWM', 0):6d}")


if __name__ == "__main__":
    main()
