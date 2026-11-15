"""Does heavy work asked for by other visitors hold up the first screen?

Usage:  python measure_blocking.py http://127.0.0.1:8100 [k k ...]      (default: 0 1 2 6 12)

For each k it starts k landing-circle requests for points nobody has asked for before (so each needs
93 new skylines), waits two seconds so that they are in flight, and then times what a new visitor's
first screen asks for: the default mission card (three times), the page, the health check and the
default landing circles.  It prints one line per k.  The cold points are different on every run
(they are seeded from the clock), so a second run does not find them stored.

A cold request that the server refuses because its queue is full (HTTP 503) is counted, not hidden.
"""
import concurrent.futures as cf
import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1].rstrip("/")
KS = [int(a) for a in sys.argv[2:]] or [0, 1, 2, 6, 12]
LANDING = "2026-11-18T00:00:00Z"
CARD = {"site": {"id": "shackleton"}, "landing": LANDING}


def call(path, body=None, timeout=1800):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json", "User-Agent": "slipday-measure/1.0"})
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            return r.status, round(time.perf_counter() - t, 2)
    except urllib.error.HTTPError as e:
        e.read()
        return e.code, round(time.perf_counter() - t, 2)


seed = int(time.time()) % 100000
n = 0
call("/api/mission", CARD)                      # make sure the default card itself is stored before timing it
call("/api/landing-circles", CARD)
print("server %s, seed %d" % (BASE, seed))
for k in KS:
    pts = []
    for _ in range(k):
        n += 1
        pts.append({"name": "cold", "lat": round(-86.2 - 0.0137 * n - (seed % 97) * 0.001, 5),
                    "lon": round(((seed * 0.37 + n * 23.71) % 360.0) - 180.0, 5)})
    with cf.ThreadPoolExecutor(max(1, k)) as ex:
        t_all = time.perf_counter()
        futs = [ex.submit(call, "/api/landing-circles", {"site": p, "landing": LANDING}) for p in pts]
        time.sleep(2.0 if k else 0.0)
        cards = [call("/api/mission", CARD) for _ in range(3)]
        page = call("/")
        health = call("/api/health")
        circles = call("/api/landing-circles", CARD)
        res = [f.result() for f in futs]
        total = round(time.perf_counter() - t_all, 1)
    done = sorted(r[1] for r in res if r[0] == 200)
    refused = sum(1 for r in res if r[0] == 503)
    other = [r for r in res if r[0] not in (200, 503)]
    print("cold in flight %2d | default card %s s (status %s) | page %.2f s | health %.2f s | default circles %.2f s (%d) | "
          "cold answered %d in %s s, refused (503) %d%s | all done after %.1f s"
          % (k, [c[1] for c in cards], sorted(set(c[0] for c in cards)), page[1], health[1], circles[1], circles[0],
             len(done), ("%.1f to %.1f" % (done[0], done[-1])) if done else "-", refused,
             (", other %s" % other) if other else "", total))
