"""Client for the JPL Horizons API, used to cross-check Slipday's own geometry.

Off by default.  Set SLIPDAY_HORIZONS=1 to let the server call
https://ssd.jpl.nasa.gov/api/horizons.api (no key needed).  Only the standard
library is used, so proxies set through HTTPS_PROXY are honoured.
"""
from __future__ import annotations

import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import numpy as np

from .ephem import compute_table, iso, parse_utc
from .geometry import Site, track

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
TARGETS = {"sun": "10", "earth": "399"}


def enabled() -> bool:
    return os.environ.get("SLIPDAY_HORIZONS", "").lower() in ("1", "true", "yes", "on")


def build_url(target: str, lat: float, lon: float, start: str, stop: str, step: str = "6h",
              alt_km: float = 0.0) -> str:
    """Observer table of airless apparent azimuth/elevation (quantity 4) for a
    point on the lunar surface.  SITE_COORD is east longitude, latitude, altitude."""
    params = {
        "format": "text", "COMMAND": f"'{TARGETS[target]}'", "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'OBSERVER'", "CENTER": "'coord@301'",
        "COORD_TYPE": "'GEODETIC'", "SITE_COORD": f"'{lon:.6f},{lat:.6f},{alt_km:.4f}'",
        "START_TIME": f"'{start}'", "STOP_TIME": f"'{stop}'", "STEP_SIZE": f"'{step}'",
        "QUANTITIES": "'4'", "CSV_FORMAT": "'YES'", "CAL_FORMAT": "'CAL'", "TIME_DIGITS": "'MINUTES'",
    }
    return API + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote, safe="'@,:")


_ROW = re.compile(r"^\s*(\d{4}-[A-Za-z]{3}-\d{2} \d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)\s*,(.*)$")


def parse_table(text: str) -> list[tuple[float, float, float]]:
    """Rows between $$SOE and $$EOE -> (unix seconds UTC, azimuth deg, elevation deg).

    Accepts the native CSV layout (date, sun flag, moon flag, azimuth,
    elevation,) and the trimmed 'date, azimuth, elevation' layout used by the
    saved fixtures: the two numeric fields after the date are taken.
    """
    m = re.search(r"^\$\$SOE\s*$(.*?)^\$\$EOE", text, re.S | re.M)
    if m:
        text = m.group(1)
    rows = []
    for line in text.splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        stamp = m.group(1)
        fmt = "%Y-%b-%d %H:%M:%S.%f" if "." in stamp else ("%Y-%b-%d %H:%M:%S" if stamp.count(":") == 2 else "%Y-%b-%d %H:%M")
        t = datetime.strptime(stamp, fmt).replace(tzinfo=timezone.utc).timestamp()
        nums = []
        for field in m.group(2).split(","):
            try:
                nums.append(float(field))
            except ValueError:
                continue
        if len(nums) >= 2:
            rows.append((t, nums[0], nums[1]))
    return rows


def fetch(target: str, lat: float, lon: float, start: str, stop: str, step: str = "6h",
          timeout: float = 30.0) -> tuple[str, str]:
    url = build_url(target, lat, lon, start, stop, step)
    req = urllib.request.Request(url, headers={"User-Agent": "slipday-crosscheck/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return url, resp.read().decode("utf-8", "replace")


def compare_rows(site: Site, target: str, rows, orientation: str = "de421") -> dict:
    arr = np.array(rows, dtype=float)
    tr = track(site, compute_table(arr[:, 0], orientation=orientation))
    az = tr.sun_az if target == "sun" else tr.earth_az
    el = tr.sun_el if target == "sun" else tr.earth_el
    d_az = (az - arr[:, 1] + 180.0) % 360.0 - 180.0
    d_el = el - arr[:, 2]
    return {
        "target": target, "rows": int(len(arr)), "orientation": orientation,
        "max_abs_el_deg": float(np.abs(d_el).max()), "max_abs_az_deg": float(np.abs(d_az).max()),
        "rms_el_deg": float(np.sqrt((d_el ** 2).mean())),
        "first_utc": iso(arr[0, 0]), "last_utc": iso(arr[-1, 0]),
    }


def crosscheck(site: Site, start: str, stop: str, step: str = "6h") -> dict:
    """Fetch Sun and Earth tables for the site from Horizons and report the
    largest difference from Slipday's own values."""
    if not enabled():
        raise RuntimeError("Horizons cross-check is disabled; start the server with SLIPDAY_HORIZONS=1")
    a = parse_utc(start).strftime("%Y-%m-%d %H:%M")
    b = parse_utc(stop).strftime("%Y-%m-%d %H:%M")
    out = {"site": {"name": site.name, "lat": site.lat, "lon": site.lon}, "results": []}
    for target in ("sun", "earth"):
        url, text = fetch(target, site.lat, site.lon, a, b, step)
        rows = parse_table(text)
        if not rows:
            raise RuntimeError(f"Horizons returned no data rows for {target}: {text[:300]!r}")
        res = compare_rows(site, target, rows)
        res["url"] = url
        out["results"].append(res)
    return out
