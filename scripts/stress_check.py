"""Concurrent load on a running Slipday server, phase by phase, with the server's memory after each phase.

    python3 scripts/stress_check.py http://127.0.0.1:8000                      # timings and status codes only
    python3 scripts/stress_check.py http://127.0.0.1:8000 --docker <container> # plus memory read inside the container

The phases follow the load test described in the round-3 review (first-visitor sequence, 12 cards at once,
6 slip maps at once, 12 cards at never-seen points, bursts of 24 and 96 new-site statistics, four 20-year
requests, a mixed burst of 29), with two phases added for the local pass: landing circles at four sites and
the slip-robust site list.  With --docker the memory figures come from the container's cgroup (v2:
memory.current, memory.peak, the oom_kill count) and from /proc/1/status of the server process, read with
`docker exec`; they are megabytes.  Works from Windows, macOS and Linux (only the standard library).
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

base = sys.argv[1].rstrip("/")
container = sys.argv[sys.argv.index("--docker") + 1] if "--docker" in sys.argv else None


def mem() -> dict:
    if not container:
        return {}
    sh = ("cat /sys/fs/cgroup/memory.current /sys/fs/cgroup/memory.peak 2>/dev/null; "
          "grep oom_kill /sys/fs/cgroup/memory.events 2>/dev/null; grep -E 'VmHWM|VmRSS|RssAnon|RssFile' /proc/1/status")
    try:
        out = subprocess.run(["docker", "exec", container, "sh", "-c", sh], capture_output=True, text=True, timeout=30).stdout.split("\n")
    except Exception as exc:
        return {"error": repr(exc)[:60]}
    res = {}
    nums = [ln for ln in out if ln.strip().isdigit()]
    if len(nums) >= 2:
        res["cg_now"], res["cg_peak"] = round(int(nums[0]) / 2 ** 20), round(int(nums[1]) / 2 ** 20)
    for ln in out:
        if ln.startswith("oom_kill "):
            res["oom_kills"] = int(ln.split()[1])
        for k in ("VmHWM", "VmRSS", "RssAnon", "RssFile"):
            if ln.startswith(k + ":"):
                res[k] = round(int(ln.split()[1]) / 1024)
    return res or {"error": "container not running"}


def call(path, body=None, timeout=900):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"} if body is not None else {})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            return r.status, time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, time.time() - t
    except Exception as e:
        return repr(e)[:50], time.time() - t


def phase(label, jobs, workers):
    t = time.time()
    with cf.ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(lambda j: call(*j), jobs))
    codes: dict = {}
    for c, _ in res:
        codes[c] = codes.get(c, 0) + 1
    print(f"{label:66s} {time.time() - t:6.1f} s  slowest {max(r[1] for r in res):5.1f} s  {codes}  {mem()}", flush=True)


polar = ["shackleton", "malapert_earth", "im2", "im1", "shackleton_rim", "ridge_c2", "malapert", "mouton"]
S = "2026-11-18T00:00:00Z"
ids = lambda names: [{"id": i} for i in names]  # noqa: E731
print("health", json.loads(urllib.request.urlopen(base + "/api/health", timeout=60).read()).get("malloc_arena_limit"), "| start", mem(), flush=True)
phase("first visitor: sites, map, image, validation, hindcast, replays",
      [("/api/sites",), ("/api/map",), ("/api/map/image",), ("/api/validation",), ("/api/terrain/validation",), ("/api/hindcast",), ("/api/replays",)], 4)
phase("first visitor: mission + slip grid (band) + slip map + landing circles",
      [("/api/mission", {"site": {"id": "shackleton"}, "landing": S}),
       ("/api/slipgrid", {"sites": ids(polar[:4]), "start": S, "n_dates": 60, "scatter_m": 100}), ("/api/slipmap", {"start": S}),
       ("/api/landing-circles", {"site": {"id": "shackleton"}, "landing": S})], 4)
phase("first visitor: 4 year tables (ladder+band), pairs, compare",
      [(f"/api/stats?site={i}&start={S}&days=365&ladder=true&scatter_m=100",) for i in polar[:4]] +
      [("/api/pairs", {"sites": ids(polar[:4]), "start": S, "days": 365}), ("/api/compare", {"sites": ids(polar[:4]), "start": S, "hours": 1440})], 6)
phase("8 visitors at once: mission cards at 8 sites, 4 replays",
      [("/api/mission", {"site": {"id": i}, "landing": S}) for i in polar] +
      [("/api/mission", {"site": {"id": i}, "landing": t}) for i, t in (("im2", "2025-03-06T17:00:00Z"), ("im1", "2024-02-22T23:00:00Z"),
                                                                       ("chandrayaan3", "2023-08-23T12:00:00Z"), ("blueghost1", "2025-03-02T08:00:00Z"))], 12)
phase("landing circles at 4 sites at once (up to 372 skylines)",
      [("/api/landing-circles", {"site": {"id": i}, "landing": S}) for i in polar[4:8]], 4)
phase("slip-robust site list (12 map points re-checked)", [("/api/robust-sites", {"start": S, "n_dates": 60})], 1)
phase("6 slip maps for 6 different dates at once", [("/api/slipmap", {"start": f"2027-0{k}-11T00:00:00Z"}) for k in range(1, 7)], 6)
phase("12 mission cards at never-seen points at once (168 skylines)",
      [("/api/mission", {"site": {"lat": -89.1 + 0.031 * k, "lon": -170 + 29 * k}, "landing": S}) for k in range(12)], 12)
phase("24 year statistics at never-seen points at once",
      [(f"/api/stats?lat={-88.7 + 0.011 * k:.4f}&lon={(41 * k) % 360 - 180}&start={S}&days=365",) for k in range(24)], 24)
phase("96 year statistics at never-seen points at once",
      [(f"/api/stats?lat={-88.2 + 0.006 * k:.4f}&lon={(53 * k) % 360 - 180}&start={S}&days=365",) for k in range(96)], 96)
phase("4 twenty-year hourly statistics at once", [(f"/api/stats?site={i}&start=2017-01-01&days=7300",) for i in polar[:4]], 4)
phase("mixed: 3 slip maps, 6 banded grids, 12 ladders, 8 new cards",
      [("/api/slipmap", {"start": f"2028-0{k}-05T00:00:00Z"}) for k in range(1, 4)] +
      [("/api/slipgrid", {"sites": [{"lat": -89.3 + 0.02 * k, "lon": 20.0 * k + j} for j in range(4)], "start": S, "n_dates": 90, "scatter_m": 100}) for k in range(6)] +
      [(f"/api/stats?lat={-89.6 + 0.02 * k:.3f}&lon={31 * k - 150}&start={S}&days=365&ladder=true&scatter_m=100",) for k in range(12)] +
      [("/api/mission", {"site": {"lat": -86.0 + 0.05 * k, "lon": 3 * k}, "landing": S, "slip_days": 120}) for k in range(8)], 29)
time.sleep(2)
print("idle 2 s later", mem(), flush=True)
