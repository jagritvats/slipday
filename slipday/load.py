"""Keeps memory bounded on a small host, and keeps stored answers quick while new ones are worked out.

FastAPI runs synchronous endpoints on a pool of 40 threads.  Left alone, a burst of requests for
new sites runs 40 ray-marches at once, each holding tens of megabytes of temporary arrays, and
glibc keeps the freed memory in per-thread arenas.

Two lanes (local review, bug 1: with a single pool of two slots, two visitors asking for new landing
circles made everybody's stored first-screen card wait 23.5 s behind them, and twelve made it 153 s):

  light   work whose terrain skylines are already stored (in memory or in the disk cache).  A request
          always starts here.  ``SLIPDAY_MAX_LIGHT`` at a time (default 4); each takes a fraction of a
          second and holds no ray-march arrays.
  cold    work that needs new skylines, or a new evaluation of the 14,400-point map.  The moment a
          light request finds that out (``require_cold`` raises ``NeedsCold``), it leaves the light lane
          and queues here.  ``SLIPDAY_MAX_HEAVY`` run at a time (default 2, as before: the memory bound is
          unchanged).  Big jobs (landing circles, lander classes, the slip-robust list: 93 to 180 skylines
          each, tens of seconds) are refused at once with ``Busy`` (HTTP 503 with Retry-After) when
          ``SLIPDAY_MAX_COLD_QUEUE`` big jobs are already waiting (default 3), so a burst cannot pile up
          minutes of work.  Only big jobs count towards that limit: a page that asks for six small things
          and two big ones at the same moment (a change of mast height does) is served, not refused.  Small jobs (a card for a new site: 15 skylines, a few seconds) may wait behind up
          to ``SLIPDAY_MAX_COLD_QUEUE_SMALL`` (default 12), so that one visitor's own page, which asks for a
          card, a grid row and a chart for a new site at the same moment, is not refused by itself.

``run(fn, ...)`` does both steps for small jobs, ``run_big(fn, ...)`` for big ones.  Code called outside ``run`` (scripts, tests, the map builder) is in
neither lane and computes whatever it needs.
"""
from __future__ import annotations

import ctypes
import os
import threading
from contextlib import contextmanager

MAX_LIGHT = max(1, int(os.environ.get("SLIPDAY_MAX_LIGHT", "4")))
MAX_COLD = max(1, int(os.environ.get("SLIPDAY_MAX_HEAVY", "2")))
MAX_COLD_QUEUE = max(0, int(os.environ.get("SLIPDAY_MAX_COLD_QUEUE", "3")))
MAX_COLD_QUEUE_SMALL = max(MAX_COLD_QUEUE, int(os.environ.get("SLIPDAY_MAX_COLD_QUEUE_SMALL", "12")))
RETRY_AFTER_S = 20

_light = threading.BoundedSemaphore(MAX_LIGHT)
_cold = threading.BoundedSemaphore(MAX_COLD)
_qlock = threading.Lock()
_counts = {"cold_running": 0, "cold_waiting": 0, "cold_waiting_big": 0, "cold_done": 0, "cold_refused": 0,
           "light_done": 0, "escalated": 0}
_mode = threading.local()

try:
    _libc = ctypes.CDLL("libc.so.6")
    _libc.malloc_trim.argtypes = [ctypes.c_size_t]
except (OSError, AttributeError):          # not glibc: nothing to trim
    _libc = None

# Two malloc arenas instead of one per thread.  This is what MALLOC_ARENA_MAX=2 does, set here as well
# so that a start command without the variable still gets it: without the limit the 240 m configuration
# was killed at a 512 MB memory limit under a burst of requests (round-3 review).  It runs at import,
# before the request threads exist.  ARENA_LIMIT says what was applied; /api/health reports it.
_M_ARENA_MAX = -8
ARENA_LIMIT = None
if os.environ.get("MALLOC_ARENA_MAX"):
    ARENA_LIMIT = "MALLOC_ARENA_MAX=" + os.environ["MALLOC_ARENA_MAX"] + " (environment)"
elif os.environ.get("SLIPDAY_ARENA_LIMIT", "1") == "0":      # only for measuring what the limit is worth
    ARENA_LIMIT = "switched off (SLIPDAY_ARENA_LIMIT=0)"
elif _libc is not None:
    try:
        if _libc.mallopt(_M_ARENA_MAX, 2) == 1:
            ARENA_LIMIT = "mallopt(M_ARENA_MAX, 2) (set in code)"
    except Exception:
        pass


class NeedsCold(Exception):
    """Raised inside the light lane when the work turns out to need a new skyline or map evaluation."""


class Busy(Exception):
    """The cold lane's queue is full.  The API turns this into HTTP 503 with a Retry-After header."""

    def __init__(self, waiting: int, running: int):
        self.waiting, self.running, self.retry_after_s = waiting, running, RETRY_AFTER_S
        super().__init__(
            f"The server is busy working out new terrain skylines for other requests ({running} running, {waiting} "
            f"waiting). Sites and dates that are already worked out still answer at once; please try this one again "
            f"in about {RETRY_AFTER_S} seconds.")


def trim() -> None:
    if _libc is not None:
        try:
            _libc.malloc_trim(0)
        except Exception:
            pass


def require_cold() -> None:
    """Call just before any slow computation (a new skyline, a new map evaluation).

    In the light lane this raises ``NeedsCold`` so that ``run`` can move the request to the cold lane;
    anywhere else it does nothing."""
    if getattr(_mode, "lane", None) == "light":
        raise NeedsCold()


@contextmanager
def light():
    _light.acquire()
    prev = getattr(_mode, "lane", None)
    _mode.lane = "light"
    try:
        yield
    finally:
        _mode.lane = prev
        _light.release()
        with _qlock:
            _counts["light_done"] += 1


@contextmanager
def _cold_slot(kind):
    """``kind`` is "big", "small" or None (no queue limit)."""
    big = kind == "big"
    with _qlock:
        busy = _counts["cold_running"] >= MAX_COLD
        if busy and ((big and _counts["cold_waiting_big"] >= MAX_COLD_QUEUE)
                     or (kind == "small" and _counts["cold_waiting"] >= MAX_COLD_QUEUE_SMALL)):
            _counts["cold_refused"] += 1
            raise Busy(_counts["cold_waiting"], _counts["cold_running"])
        _counts["cold_waiting"] += 1
        if big:
            _counts["cold_waiting_big"] += 1
    acquired = False
    try:
        _cold.acquire()
        acquired = True
    finally:
        with _qlock:
            _counts["cold_waiting"] -= 1
            if big:
                _counts["cold_waiting_big"] -= 1
            if acquired:
                _counts["cold_running"] += 1
    prev = getattr(_mode, "lane", None)
    _mode.lane = "cold"
    try:
        yield
    finally:
        _mode.lane = prev
        with _qlock:
            _counts["cold_running"] -= 1
            _counts["cold_done"] += 1
        _cold.release()
        trim()


def cold(big: bool = True):
    """A slot for slow work: ``MAX_COLD`` at a time, a queue behind them, and ``Busy`` beyond that.
    Big jobs get the short queue, small ones the longer one."""
    return _cold_slot("big" if big else "small")


def heavy():
    """The same slots without the queue limit: waits for as long as it takes (scripts and older callers)."""
    return _cold_slot(None)


def _run(big: bool, fn, args, kwargs):
    if getattr(_mode, "lane", None) is not None:        # already inside a lane (nested call): just run
        return fn(*args, **kwargs)
    try:
        with light():
            return fn(*args, **kwargs)
    except NeedsCold:
        with _qlock:
            _counts["escalated"] += 1
    with cold(big):
        return fn(*args, **kwargs)


def run(fn, *args, **kwargs):
    """Run ``fn`` in the light lane; if it needs something slow, queue it in the cold lane instead.

    The light attempt stops at the first missing skyline, before any ray-march, so what it throws away
    is a few stored-file reads."""
    return _run(False, fn, args, kwargs)


def run_big(fn, *args, **kwargs):
    """The same for jobs that need many new skylines: they get the short queue."""
    return _run(True, fn, args, kwargs)


def lanes() -> dict:
    """What /api/health reports about the two lanes."""
    with _qlock:
        c = dict(_counts)
    c.update({"max_light": MAX_LIGHT, "max_cold": MAX_COLD, "max_cold_queue": MAX_COLD_QUEUE,
              "max_cold_queue_small": MAX_COLD_QUEUE_SMALL,
              "retry_after_s": RETRY_AFTER_S})
    return c


def rss_mb() -> dict:
    """Resident memory of this process, split as the kernel reports it (Linux only)."""
    out = {}
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                k, _, v = line.partition(":")
                if k in ("VmRSS", "RssAnon", "RssFile", "VmHWM"):
                    out[k] = round(int(v.split()[0]) / 1024.0, 1)
    except OSError:
        pass
    return out
