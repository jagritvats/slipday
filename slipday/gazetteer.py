"""Names for a point on the ground, from the USGS / IAU Gazetteer of Planetary Nomenclature.

``data/gazetteer/moon_south_features.json`` holds the named features south of 80 S (centre point and diameter;
REAL, cut from the official Moon nomenclature shapefile, URL and sha256 in its "source" block).  A point is
named "inside" a feature only within 90 % of its radius of the centre on the sphere (the smallest such feature
wins); between 90 % and 110 % it is "on the rim of" a crater (or "near" another kind of feature), because a
centre and a diameter cannot place a rim more closely than that.  Beyond, no name: the page keeps to direction
and distance.  Craters are written "<name> crater", so that Malapert crater cannot be read as Mons Malapert.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Optional

import numpy as np

from .dem import MOON_RADIUS_M

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "gazetteer",
                    "moon_south_features.json")
_lock = threading.Lock()
_state: dict = {"loaded": False, "features": None}


def features() -> Optional[list]:
    with _lock:
        if not _state["loaded"]:
            _state["loaded"] = True
            try:
                with open(PATH, encoding="utf-8") as fh:
                    d = json.load(fh)
                _state["features"] = [f for f in d["features"] if f.get("diameter_km")]
            except (OSError, ValueError, KeyError):
                _state["features"] = None
        return _state["features"]


def _dist_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    p1, p2 = np.deg2rad(lat1), np.deg2rad(lat2)
    dl = np.deg2rad(np.asarray(lon2) - lon1)
    c = np.sin(p1) * np.sin(p2) + np.cos(p1) * np.cos(p2) * np.cos(dl)
    return np.arccos(np.clip(c, -1.0, 1.0)) * MOON_RADIUS_M / 1000.0


INSIDE = 0.9      # within 90 % of the radius: "inside"
RIM = 1.1         # 90 to 110 %: "on the rim of" (craters), "near" (other kinds); beyond: no name (rule R7, pass 4)


def _kind(f: dict) -> str:
    t = f["type"].split(",")[0]
    return {"Crater": "crater", "Satellite Feature": "crater", "Mons": "mountain", "Vallis": "valley",
            "Lacus": "lacus", "Statio": "statio"}.get(t, t.lower())


def label(f: dict) -> str:
    """A name that cannot be confused with a neighbour of the same name: craters carry the word."""
    return f"{f['name']} crater" if _kind(f) == "crater" else f["name"]


def containing(lat: float, lon: float) -> Optional[dict]:
    """The named feature the point lies in or on the rim of, or None (rule R7).

    "inside": within 90 % of the feature's radius of its centre (the smallest such feature wins);
    "rim": between 90 % and 110 % of the radius of a crater; "near": the same band for other kinds."""
    fs = features()
    if not fs:
        return None
    la = np.array([f["lat"] for f in fs])
    lo = np.array([f["lon"] for f in fs])
    rad = np.array([f["diameter_km"] for f in fs]) / 2.0
    d = _dist_km(lat, lon, la, lo)
    inside = np.nonzero(d <= INSIDE * rad)[0]
    if len(inside):
        i, rel = int(inside[np.argmin(rad[inside])]), "inside"
    else:
        band = np.nonzero(d <= RIM * rad)[0]
        if not len(band):
            return None
        i = int(band[np.argmin(rad[band])])
        rel = "rim" if _kind(fs[i]) == "crater" else "near"
    f = fs[i]
    words = {"inside": "inside", "rim": "on the rim of", "near": "near"}[rel]
    phrase = f"{words} {label(f)}"
    rim_also = None
    if rel == "inside":            # also on a crater's rim line? say both, so neither reads as the whole truth
        band = [j for j in np.nonzero((d > INSIDE * rad) & (d <= RIM * rad))[0] if _kind(fs[j]) == "crater" and j != i]
        if band:
            j = int(min(band, key=lambda j: rad[j]))
            rim_also = {"name": fs[j]["name"], "label": label(fs[j]), "diameter_km": round(float(fs[j]["diameter_km"]), 1),
                        "share_of_radius": round(float(d[j] / rad[j]), 3)}
            phrase = f"{phrase}, on the rim of {label(fs[j])}"
    return {"name": f["name"], "label": label(f), "relation": rel, "phrase": phrase, "rim_also": rim_also,
            "type": f["type"], "kind": _kind(f), "diameter_km": round(float(f["diameter_km"]), 1),
            "centre_lat": f["lat"], "centre_lon": f["lon"], "km_from_centre": round(float(d[i]), 1),
            "share_of_radius": round(float(d[i] / rad[i]), 3),
            "link": f.get("link"), "source": "USGS / IAU Gazetteer of Planetary Nomenclature (centre point and diameter)"}
