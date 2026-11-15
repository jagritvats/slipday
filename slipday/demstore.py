"""Which DEMs this installation has, read from ``data/dem/dems.json``.

The file lists real elevation grids (LOLA products) with their layout.  Paths
are relative to the folder holding the JSON unless absolute.  Example entry:

    {"name": "ldem_80s_80m", "kind": "polar_stereo", "path": "LDEM_80S_80M.IMG",
     "format": "raw", "dtype": "<i2", "shape": [7600, 7600], "header_bytes": 0,
     "pole": -1, "pixel_m": 80.0, "scale": 0.5, "offset": 0.0, "nodata": -32768,
     "source": "LOLA", "product": "LDEM_80S_80M", "provenance": "byte-exact copy of ..."}

    {"name": "ldem_16", "kind": "equirect", "path": "LDEM_16.IMG", "format": "raw",
     "dtype": "<i2", "shape": [2880, 5760], "ppd": 16, "lat0": 89.96875, "lon0": 0.03125,
     "scale": 0.5, "source": "LOLA", "product": "LDEM_16"}

Formats: ``raw`` (flat binary, memory-mapped), ``npy`` (memory-mapped),
``tiff`` (read with tifffile or Pillow).  The finest grid is consulted first.

With no configuration the app has no terrain and says so.  Setting
SLIPDAY_SYNTHETIC_DEM=1 registers a labelled synthetic surface instead; it is
a test fixture and every label derived from it says SYNTHETIC.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from typing import Optional

import numpy as np

from .dem import DEM, CompositeDEM, EquirectDEM, PolarStereoDEM, synthetic_south_pole_fixture

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_lock = threading.Lock()
_state: dict = {"loaded": False, "dem": None, "members": [], "all": [], "missing": [], "config": None, "error": None}


def dem_dir() -> str:
    return os.environ.get("SLIPDAY_DEM_DIR", os.path.join(ROOT, "data", "dem"))


def _read_array(entry: dict, base: str) -> np.ndarray:
    path = entry["path"] if os.path.isabs(entry["path"]) else os.path.join(base, entry["path"])
    fmt = entry.get("format", "raw")
    if fmt == "raw":
        shape = tuple(entry["shape"])
        return np.memmap(path, dtype=np.dtype(entry.get("dtype", "<i2")), mode="r",
                         offset=int(entry.get("header_bytes", 0)), shape=shape)
    if fmt == "npy":
        return np.load(path, mmap_mode="r")
    if fmt == "tiff":
        try:
            import tifffile
            arr = tifffile.imread(path)
        except Exception:
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None
            arr = np.asarray(Image.open(path))
        return arr[..., 0] if arr.ndim == 3 else arr
    raise ValueError(f"unknown DEM format {fmt!r}")


def _build(entry: dict, base: str) -> DEM:
    z = _read_array(entry, base)
    common = dict(name=entry["name"], source=entry.get("source", "DEM"), synthetic=bool(entry.get("synthetic", False)),
                  provenance=entry.get("provenance", ""), z=z, scale=float(entry.get("scale", 1.0)),
                  offset=float(entry.get("offset", 0.0)), nodata=entry.get("nodata"))
    if entry["kind"] == "polar_stereo":
        ny, nx = z.shape
        px = float(entry["pixel_m"])
        dem = PolarStereoDEM(pole=int(entry.get("pole", -1)), pixel_m=px,
                             x0_m=float(entry.get("x0_m", -(nx - 1) / 2.0 * px)),
                             y0_m=float(entry.get("y0_m", (ny - 1) / 2.0 * px)),
                             k0=float(entry.get("k0", 1.0)), **common)
    elif entry["kind"] == "equirect":
        ppd = float(entry["ppd"])
        dem = EquirectDEM(ppd=ppd, lat0=float(entry.get("lat0", 90.0 - 0.5 / ppd)),
                          lon0=float(entry.get("lon0", 0.5 / ppd)), **common)
    else:
        raise ValueError(f"unknown DEM kind {entry['kind']!r}")
    if entry.get("resolution_m"):
        dem.resolution_m = float(entry["resolution_m"])
    dem.product = entry.get("product", entry["name"])
    dem.fingerprint = hashlib.sha1(json.dumps(entry, sort_keys=True).encode()).hexdigest()[:10]
    return dem


def _load() -> None:
    cfg_path = os.path.join(dem_dir(), "dems.json")
    members: list[DEM] = []
    everything: list[DEM] = []
    missing: list[str] = []
    config = None
    error = None
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path) as fh:
                config = json.load(fh)
            base = os.path.dirname(cfg_path)
            # SLIPDAY_SKIP_DEMS=ldem_80s_80m runs as if that grid were not installed (the small-host
            # configuration), without moving files; the other grids keep their cache keys.
            skip = {n.strip() for n in os.environ.get("SLIPDAY_SKIP_DEMS", "").split(",") if n.strip()}
            for entry in config.get("dems", []):
                path = entry["path"] if os.path.isabs(entry["path"]) else os.path.join(base, entry["path"])
                if entry.get("disabled") or entry["name"] in skip or not os.path.exists(path):
                    missing.append(entry["name"])        # e.g. the 231 MB grid is not shipped in git
                    continue
                everything.append(_build(entry, base))
            have = {m.name for m in everything}
            # a grid marked as a stand-in for a finer one is left out of the default stack when the finer one is here
            stand_ins = {e["name"] for e in config.get("dems", []) if e.get("fallback_for") in have}
            members = [m for m in everything if m.name not in stand_ins]
        except Exception as exc:  # a broken config must not take the app down
            error = f"could not load {cfg_path}: {exc}"
            members, everything = [], []
    if not members and os.environ.get("SLIPDAY_SYNTHETIC_DEM", "").lower() in ("1", "true", "yes", "on"):
        fixture = synthetic_south_pole_fixture()
        members = everything = list(fixture.members)
    members.sort(key=lambda m: m.resolution_m)
    dem = None
    if members:
        dem = CompositeDEM(members=members, name="+".join(m.name for m in members))
        dem.fingerprint = "+".join(getattr(m, "fingerprint", "syn") for m in members)
    _state.update({"loaded": True, "dem": dem, "members": members, "all": everything, "missing": missing,
                   "config": config, "error": error})


def reload() -> None:
    with _lock:
        _state["loaded"] = False
        _load()


def get_dem() -> Optional[CompositeDEM]:
    """All configured grids, finest first, or None when there is no terrain data."""
    with _lock:
        if not _state["loaded"]:
            _load()
        return _state["dem"]


def members() -> list[DEM]:
    get_dem()
    return list(_state["members"])


def member(name: str) -> Optional[DEM]:
    """Any installed grid by name, including stand-ins left out of the default stack."""
    get_dem()
    for m in _state["all"]:
        if m.name == name:
            return m
    return None


def stack(names) -> Optional[CompositeDEM]:
    """A specific stack of grids (finest first), e.g. for a resolution study."""
    ms = [member(n) for n in names]
    if not ms or any(m is None for m in ms):
        return None
    ms.sort(key=lambda m: m.resolution_m)
    dem = CompositeDEM(members=ms, name="+".join(m.name for m in ms))
    dem.fingerprint = "+".join(getattr(m, "fingerprint", "syn") for m in ms)
    return dem


def layer(name: str):
    """An optional reference raster listed under "layers" in dems.json (array, entry) or None."""
    cfg = config()
    if not cfg or name not in cfg.get("layers", {}):
        return None
    entry = cfg["layers"][name]
    path = entry["path"] if os.path.isabs(entry["path"]) else os.path.join(dem_dir(), entry["path"])
    if not os.path.exists(path):
        return None
    return np.load(path, mmap_mode="r"), entry


def config() -> Optional[dict]:
    get_dem()
    return _state["config"]


def status() -> dict:
    dem = get_dem()
    return {
        "available": dem is not None,
        "synthetic": bool(dem.synthetic) if dem else False,
        "label": dem.label() if dem else "no terrain data installed",
        "dems": [dict(m.describe(), product=getattr(m, "product", m.name), kind=type(m).__name__,
                      shape=list(m.z.shape)) for m in members()],
        "not_installed": list(_state["missing"]),
        "error": _state["error"],
    }
