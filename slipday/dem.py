"""Digital elevation models of the Moon, sampled by latitude and longitude.

Two grid layouts are supported, which between them cover the LOLA gridded
products:

* ``PolarStereoDEM``  polar stereographic grid centred on a pole (the LOLA
  polar LDEM products, e.g. LDEM_80S_80M): x = r sin(lon), y = +/- r cos(lon),
  r = 2 R k0 tan(pi/4 - |lat|/2), on a sphere of radius R.
* ``EquirectDEM``     global simple-cylindrical grid (the LOLA global LDEM_4,
  LDEM_16, ... products): rows are latitude from north to south, columns are
  east longitude starting at ``lon0``.

Heights are metres relative to the reference sphere (R = 1737.4 km).  Sampling
is bilinear and returns NaN outside the grid or next to no-data cells.

``CompositeDEM`` answers from the first member that has data at each point, so
a fine polar grid can be backed by a coarse global one.

The ``synthetic_*`` builders at the bottom make small analytic test surfaces.
They are test fixtures, flagged ``synthetic=True`` and labelled as such
wherever a result derived from them is shown.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np

MOON_RADIUS_M = 1737400.0


def _bilinear(z: np.ndarray, row: np.ndarray, col: np.ndarray, scale: float, offset: float,
              nodata: Optional[float], wrap_cols: bool = False) -> np.ndarray:
    """Bilinear sample of ``z`` at fractional (row, col); NaN outside or beside no-data."""
    ny, nx = z.shape
    row = np.asarray(row, dtype=float)
    col = np.asarray(col, dtype=float)
    out = np.full(row.shape, np.nan)
    if wrap_cols:
        col = np.mod(col, nx)
        ok = (row >= 0) & (row <= ny - 1) & np.isfinite(col)
    else:
        ok = (row >= 0) & (row <= ny - 1) & (col >= 0) & (col <= nx - 1)
    if not ok.any():
        return out
    r, c = row[ok], col[ok]
    r0 = np.minimum(np.floor(r).astype(np.int64), ny - 2)
    c0 = np.floor(c).astype(np.int64)
    if wrap_cols:
        c1 = (c0 + 1) % nx
        c0 = c0 % nx
        fc = c - np.floor(c)
    else:
        c0 = np.minimum(c0, nx - 2)
        c1 = c0 + 1
        fc = c - c0
    fr = r - r0
    z00 = z[r0, c0].astype(float)
    z01 = z[r0, c1].astype(float)
    z10 = z[r0 + 1, c0].astype(float)
    z11 = z[r0 + 1, c1].astype(float)
    val = (z00 * (1 - fr) * (1 - fc) + z01 * (1 - fr) * fc + z10 * fr * (1 - fc) + z11 * fr * fc)
    val = val * scale + offset
    if nodata is not None:
        bad = (z00 == nodata) | (z01 == nodata) | (z10 == nodata) | (z11 == nodata)
        val[bad] = np.nan
    out[ok] = val
    return out


@dataclass
class DEM:
    name: str = "dem"
    source: str = ""             # e.g. "LOLA" for real data, "SYNTHETIC" for test fixtures
    resolution_m: float = 0.0    # grid spacing in metres (at the equator for global grids)
    synthetic: bool = False
    provenance: str = ""         # exactness class and origin, shown in exports

    def height_m(self, lat_deg, lon_deg) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def label(self) -> str:
        res = self.resolution_m
        txt = f"{res:.0f} m" if res < 1000 else f"{res / 1000:.2f} km"
        if self.synthetic:
            return f"SYNTHETIC TEST DEM, {txt}/px"
        return f"{self.source or 'DEM'}, {txt}/px"

    def describe(self) -> dict:
        return {"name": self.name, "source": self.source, "resolution_m": self.resolution_m,
                "synthetic": self.synthetic, "label": self.label(), "provenance": self.provenance}


@dataclass
class PolarStereoDEM(DEM):
    """Polar stereographic grid.  Row 0 is the top line (largest y), column 0 the
    left sample (smallest x).  ``x0_m``/``y0_m`` are the projected coordinates of
    the centre of pixel (row 0, col 0)."""

    z: np.ndarray = field(default=None, repr=False)
    pole: int = -1               # -1 south, +1 north
    pixel_m: float = 0.0
    x0_m: float = 0.0
    y0_m: float = 0.0
    scale: float = 1.0           # stored value * scale + offset = metres
    offset: float = 0.0
    nodata: Optional[float] = None
    radius_m: float = MOON_RADIUS_M
    k0: float = 1.0              # 1 for true scale at the pole (the LOLA convention)

    def __post_init__(self):
        if not self.resolution_m:
            self.resolution_m = self.pixel_m

    def project(self, lat_deg, lon_deg):
        lat = np.deg2rad(np.asarray(lat_deg, dtype=float))
        lon = np.deg2rad(np.asarray(lon_deg, dtype=float))
        r = 2.0 * self.radius_m * self.k0 * np.tan(np.pi / 4 - np.abs(lat) / 2)
        x = r * np.sin(lon)
        y = r * np.cos(lon) if self.pole < 0 else -r * np.cos(lon)
        return x, y

    def unproject(self, x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        r = np.hypot(x, y)
        colat = 2.0 * np.arctan(r / (2.0 * self.radius_m * self.k0))
        lat = np.rad2deg(np.pi / 2 - colat) * (1 if self.pole > 0 else -1)
        lon = np.rad2deg(np.arctan2(x, y if self.pole < 0 else -y))
        return lat, lon

    def extent_m(self):
        ny, nx = self.z.shape
        return (self.x0_m - self.pixel_m / 2, self.x0_m + (nx - 0.5) * self.pixel_m,
                self.y0_m - (ny - 0.5) * self.pixel_m, self.y0_m + self.pixel_m / 2)

    def edge_latitude(self) -> float:
        """Latitude reached at the nearest grid edge (full coverage poleward of it)."""
        xmin, xmax, ymin, ymax = self.extent_m()
        r = min(abs(xmin), abs(xmax), abs(ymin), abs(ymax))
        lat, _ = self.unproject(r, 0.0)
        return float(lat)

    def height_m(self, lat_deg, lon_deg) -> np.ndarray:
        lat = np.asarray(lat_deg, dtype=float)
        x, y = self.project(lat, lon_deg)
        col = (x - self.x0_m) / self.pixel_m
        row = (self.y0_m - y) / self.pixel_m
        out = _bilinear(self.z, row, col, self.scale, self.offset, self.nodata)
        wrong_side = (lat * self.pole) < 0
        if np.any(wrong_side):
            out = np.where(wrong_side, np.nan, out)
        return out


@dataclass
class EquirectDEM(DEM):
    """Global (or banded) simple-cylindrical grid.  Row 0 is the northernmost
    line; ``lat0`` is the latitude of the centre of row 0 and ``lon0`` the east
    longitude of the centre of column 0."""

    z: np.ndarray = field(default=None, repr=False)
    ppd: float = 4.0             # pixels per degree
    lat0: float = 90.0
    lon0: float = 0.0
    scale: float = 1.0
    offset: float = 0.0
    nodata: Optional[float] = None
    radius_m: float = MOON_RADIUS_M

    def __post_init__(self):
        if not self.resolution_m:
            self.resolution_m = 2 * np.pi * self.radius_m / 360.0 / self.ppd

    def height_m(self, lat_deg, lon_deg) -> np.ndarray:
        lat = np.asarray(lat_deg, dtype=float)
        lon = np.asarray(lon_deg, dtype=float)
        ny, nx = self.z.shape
        row = (self.lat0 - lat) * self.ppd
        col = (lon - self.lon0) * self.ppd
        full_wrap = abs(nx / self.ppd - 360.0) < 1e-6
        # the half pixel between the last row centre and a pole: hold the edge value
        if self.lat0 + 0.5 / self.ppd >= 90.0 - 1e-6:
            row = np.where((row < 0) & (row >= -0.5001), 0.0, row)
        if self.lat0 - (ny - 0.5) / self.ppd <= -90.0 + 1e-6:
            row = np.where((row > ny - 1) & (row <= ny - 0.4999), ny - 1.0, row)
        return _bilinear(self.z, row, col, self.scale, self.offset, self.nodata, wrap_cols=full_wrap)


@dataclass
class CompositeDEM(DEM):
    """First member with data wins, so list the finest grid first."""

    members: Sequence[DEM] = ()

    def __post_init__(self):
        if self.members:
            first = self.members[0]
            self.resolution_m = self.resolution_m or first.resolution_m
            self.source = self.source or first.source
            self.synthetic = any(m.synthetic for m in self.members)
            self.name = self.name if self.name != "dem" else "+".join(m.name for m in self.members)

    def height_m(self, lat_deg, lon_deg) -> np.ndarray:
        lat = np.asarray(lat_deg, dtype=float)
        lon = np.asarray(lon_deg, dtype=float)
        lat, lon = np.broadcast_arrays(lat, lon)
        out = np.full(lat.shape, np.nan)
        for m in self.members:
            need = np.isnan(out)
            if not need.any():
                break
            out[need] = m.height_m(lat[need], lon[need])
        return out

    def member_at(self, lat: float, lon: float) -> Optional[DEM]:
        """The finest member that has data at this point."""
        for m in self.members:
            if np.isfinite(m.height_m(np.array([lat]), np.array([lon]))[0]):
                return m
        return None

    def label(self) -> str:
        return self._label(self.members[0]) if self.members else "no DEM"

    def _label(self, first: DEM) -> str:
        coarser = [m for m in self.members if m is not first and m.resolution_m > first.resolution_m]
        if not coarser:
            return first.label()
        def short(m):
            r = m.resolution_m
            return f"{r:.0f} m" if r < 1000 else f"{r / 1000:.2f} km"
        return first.label() + "; beyond its edge " + ", ".join(short(m) for m in coarser)

    def describe(self) -> dict:
        d = super().describe()
        d["members"] = [m.describe() for m in self.members]
        return d

    def describe_for(self, lat: float, lon: float) -> dict:
        """Description as it applies to one site: the grid under the site first."""
        m = self.member_at(lat, lon)
        if m is None:
            return self.describe()
        d = m.describe()
        d["label"] = self._label(m)
        d["name"] = self.name
        d["site_member"] = m.name
        d["provenance"] = "; ".join(x.provenance for x in self.members if x.provenance and
                                    (x is m or x.resolution_m > m.resolution_m))
        return d


# --------------------------------------------------------------------------
# Synthetic test surfaces (labelled; never presented as lunar data)
# --------------------------------------------------------------------------

def great_circle_km(lat1, lon1, lat2, lon2, radius_km: float = MOON_RADIUS_M / 1000.0):
    p1, p2 = np.deg2rad(lat1), np.deg2rad(lat2)
    dl = np.deg2rad(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * radius_km * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def synthetic_polar(shape_fn, half_width_km: float = 150.0, pixel_m: float = 100.0, pole: int = -1,
                    name: str = "synthetic-polar") -> PolarStereoDEM:
    """Polar stereographic test grid whose heights are ``shape_fn(lat, lon)`` in metres."""
    n = int(round(2 * half_width_km * 1000.0 / pixel_m)) + 1
    x0 = -half_width_km * 1000.0
    y0 = half_width_km * 1000.0
    dem = PolarStereoDEM(name=name, source="SYNTHETIC", synthetic=True, pixel_m=pixel_m, pole=pole,
                         x0_m=x0, y0_m=y0, z=np.zeros((2, 2), dtype=np.float32),
                         provenance="synthetic analytic surface generated by slipday.dem (test fixture)")
    xs = x0 + pixel_m * np.arange(n)
    ys = y0 - pixel_m * np.arange(n)
    X, Y = np.meshgrid(xs, ys)
    lat, lon = dem.unproject(X, Y)
    dem.z = np.asarray(shape_fn(lat, lon), dtype=np.float32)
    return dem


def synthetic_equirect(shape_fn, ppd: float = 16.0, lat_top: float = 90.0, lat_bottom: float = -90.0,
                       name: str = "synthetic-global") -> EquirectDEM:
    """Global simple-cylindrical test grid whose heights are ``shape_fn(lat, lon)`` in metres."""
    ny = int(round((lat_top - lat_bottom) * ppd))
    nx = int(round(360 * ppd))
    lat0 = lat_top - 0.5 / ppd
    lon0 = 0.5 / ppd
    lats = lat0 - np.arange(ny) / ppd
    lons = lon0 + np.arange(nx) / ppd
    LON, LAT = np.meshgrid(lons, lats)
    z = np.asarray(shape_fn(LAT, LON), dtype=np.float32)
    return EquirectDEM(name=name, source="SYNTHETIC", synthetic=True, z=z, ppd=ppd, lat0=lat0, lon0=lon0,
                       provenance="synthetic analytic surface generated by slipday.dem (test fixture)")


def cone(lat_c: float, lon_c: float, height_m: float, base_radius_km: float):
    """A single cone of ``height_m`` with its apex at (lat_c, lon_c)."""
    def fn(lat, lon):
        d = great_circle_km(lat_c, lon_c, lat, lon)
        return np.clip(height_m * (1.0 - d / base_radius_km), 0.0, None)
    return fn


def flat(height_m: float = 0.0):
    def fn(lat, lon):
        return np.full(np.shape(lat), float(height_m))
    return fn


def synthetic_south_pole_fixture() -> CompositeDEM:
    """The labelled stand-in used when no real DEM is configured and the server
    is started with SLIPDAY_SYNTHETIC_DEM=1: a 1.5 km mesa-like cone under the
    Shackleton-ridge catalogue point, a 3 km massif near Malapert, and a bowl.
    It is NOT lunar topography."""
    hills = [(-89.4398, -137.17, 1500.0, 12.0), (-85.9876, 2.0528, 3000.0, 40.0),
             (-84.7906, 29.1957, 2500.0, 60.0), (-88.0, 90.0, 2000.0, 25.0)]

    def fn(lat, lon):
        z = np.zeros(np.shape(lat))
        for la, lo, h, r in hills:
            z = np.maximum(z, cone(la, lo, h, r)(lat, lon))
        bowl = great_circle_km(-89.67, 129.2, lat, lon)       # a 10 km crater-like bowl
        z = np.where(bowl < 10.0, np.minimum(z, 0.0) - 2500.0 * (1 - (bowl / 10.0) ** 2), z)
        return z

    polar = synthetic_polar(fn, half_width_km=310.0, pixel_m=400.0, name="synthetic-south-pole")
    return CompositeDEM(members=[polar], name="synthetic-south-pole")
