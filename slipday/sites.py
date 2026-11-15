"""Curated landing sites.

Coordinates were re-sourced for v2 by the data scout (realdata/lunar/data/
sites_verified.json).  ``confidence`` says what kind of point each one is:
  landed point      hardware position published by LROC or NSSDCA
  literature point  a point analysed in a paper (source gives the table)
  DEM summit        highest point of a named feature in the LOLA 80 m mosaic
  model-selected point  a point this project chose on the DEM (not published anywhere)
  feature centre    IAU gazetteer centre of a named feature; NASA has published
                    no landing coordinates for its south-pole landing regions, so the
                    parent feature is used as an anchor
  definition        a reference point defined by its coordinates
``relayed`` is True where the source page was read through a web-fetch tool
(not byte-exact); the IAU centres were read from the official shapefile.
All coordinates are Moon Mean Earth frame, planetocentric, east-positive.
"""
from __future__ import annotations

from functools import lru_cache

from . import demstore, terrain
from .geometry import Horizon, Site

_NSSDCA = "https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html"
_NSSDCA_ART = "https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html"
_GLASER18 = "https://ntrs.nasa.gov/api/citations/20170007365/downloads/20170007365.pdf"
_IAU = "http://planetarynames.wr.usgs.gov/Feature/"
_ARTEMIS = "NASA south-pole candidate landing region (Oct 2024 list, made for Artemis III; the first crewed landing is now planned for Artemis IV, early 2028); no coordinates published, IAU feature centre used. "


def _s(id_, name, group, lat, lon, confidence, source, relayed=True, note=""):
    return {"id": id_, "name": name, "group": group, "lat": lat, "lon": lon, "confidence": confidence,
            "source": source, "relayed": relayed, "note": note}


SITES = [
    # --- south pole: ridges, massifs and landed CLPS missions ---
    _s("shackleton", "Shackleton connecting ridge (C1)", "South pole", -89.4398, -137.17, "literature point", _GLASER18,
       note="Glaser et al. 2018, Table 2: best-lit point on the connecting ridge at 2 m above ground."),
    _s("shackleton_rim", "Shackleton rim (S)", "South pole", -89.6866, -162.81, "literature point", _GLASER18,
       note="Glaser et al. 2018, Table 2 (2 m above ground)."),
    _s("ridge_c2", "Connecting ridge (C2)", "South pole", -89.313, -114.02, "literature point", _GLASER18,
       note="Glaser et al. 2018, Table 2 (2 m above ground)."),
    _s("robust_pick", "Slip-robust ridge point (89.010 S, 122.764 E)", "South pole", -89.0098, 122.76389, "model-selected point",
       "chosen by a written rule from this project's scatter-checked slip-margin map (LOCAL_PASS_2_RESULTS.md, "
       "section H): the map point that keeps the largest slip margin at all 13 touchdown points for a landing on "
       "18 Nov 2026 with the default need", relayed=False,
       note="Not a published site; what the feature is called was not looked up. The page opens on it because the "
            "80 m grid and NASA's 20 m grid give the same answer here for that landing (Yes, 8 days of slip margin)."),
    _s("malapert", "Malapert massif summit", "South pole", -85.9876, 2.0528, "DEM summit",
       "highest point of the massif in LDEM_80S_80MPP_ADJ (+5172 m), located by the data scout", relayed=False,
       note=_ARTEMIS + "The IAU centre of Mons Malapert is 85.98 S, 1.67 W."),
    _s("malapert_earth", "Malapert massif, Earth-facing shoulder", "South pole", -85.9721, 1.9323, "model-selected point",
       "chosen by this project on LDEM_80S_80MPP_ADJ: about 540 m from the summit towards the Earth, +5150 m",
       relayed=False, note="Not a published site. Picked because the terrain model keeps the Earth in view all of 2027 "
                           "from here, while the summit itself loses it for days at a time."),
    _s("im2", "IM-2 Athena (Mons Mouton)", "South pole", -84.7906, 29.1957, "landed point",
       "https://lroc.im-ldi.com/images/1408", note="LROC, 10 Mar 2025; landed 6 Mar 2025 on its side in a 20 m crater."),
    _s("mouton", "Mons Mouton (VIPER area)", "South pole", -84.6, 31.0, "feature centre", _IAU + "16070", relayed=False,
       note=_ARTEMIS),
    _s("im1", "IM-1 Odysseus (Malapert A)", "South pole", -80.13, 1.44, "landed point",
       "https://lroc.im-ldi.com/images/1360", note="LROC, 26 Feb 2024: 80.13 S, 1.44 E, 2579 m, local slope 12 deg."),
    _s("haworth", "Haworth (crater centre)", "South pole", -87.45, -5.17, "feature centre", _IAU + "14502", relayed=False,
       note=_ARTEMIS + "The centre is the permanently shadowed floor."),
    _s("nobile", "Nobile (crater centre)", "South pole", -85.2752, 53.2725, "feature centre", _IAU + "4321", relayed=False,
       note=_ARTEMIS),
    _s("degerlache", "de Gerlache (crater centre)", "South pole", -88.4849, -88.3447, "feature centre", _IAU + "1439",
       relayed=False, note=_ARTEMIS + "The centre is the permanently shadowed floor."),
    _s("shackleton_floor", "Shackleton crater floor (always dark)", "South pole", -89.67, 129.78, "feature centre",
       _IAU + "5450", relayed=False, note="IAU crater centre; permanently shadowed."),
    _s("lcross", "LCROSS impact, Cabeus (always dark)", "South pole", -84.6796, -48.7093, "landed point", _NSSDCA_ART,
       note="NSSDCA artifacts table; permanently shadowed."),
    # --- other CLPS and commercial targets ---
    _s("blueghost1", "Blue Ghost M1 (Mare Crisium)", "CLPS", 18.5623, 61.8103, "landed point",
       "https://lroc.im-ldi.com/images/1407", note="LROC, 7 Mar 2025."),
    _s("reiner", "Reiner Gamma", "CLPS", 7.3853, -58.9583, "feature centre", _IAU + "4987", relayed=False),
    _s("gruithuisen", "Mons Gruithuisen Gamma", "CLPS", 36.5585, -40.7213, "feature centre", _IAU + "3982", relayed=False),
    _s("schrodinger", "Schrodinger basin (far side)", "CLPS", -74.7326, 132.9252, "feature centre", _IAU + "5381",
       relayed=False),
    # --- Apollo ---
    _s("apollo11", "Apollo 11 (Tranquility Base)", "Apollo", 0.67416, 23.47314, "landed point", _NSSDCA),
    _s("apollo12", "Apollo 12", "Apollo", -3.0128, -23.4219, "landed point", _NSSDCA),
    _s("apollo14", "Apollo 14", "Apollo", -3.64589, -17.47194, "landed point", _NSSDCA),
    _s("apollo15", "Apollo 15 (Hadley)", "Apollo", 26.13239, 3.6333, "landed point", _NSSDCA),
    _s("apollo16", "Apollo 16 (Descartes)", "Apollo", -8.9734, 15.5011, "landed point", _NSSDCA),
    _s("apollo17", "Apollo 17 (Taurus-Littrow)", "Apollo", 20.1911, 30.7723, "landed point", _NSSDCA),
    # --- other nations ---
    _s("chandrayaan3", "Chandrayaan-3 (Shiv Shakti)", "Other nations", -69.3741, 32.32, "landed point",
       "https://lroc.im-ldi.com/images/1314", note="LROC, 5 Sep 2023: 69.3741 S, 32.32 E, 532 m."),
    _s("change3", "Chang'e 3", "Other nations", 44.1214, -19.5117, "landed point", _NSSDCA_ART),
    _s("change4", "Chang'e 4 (far side)", "Other nations", -45.4561, 177.5885, "landed point", _NSSDCA_ART),
    _s("change5", "Chang'e 5", "Other nations", 43.0576, -51.9161, "landed point", _NSSDCA_ART),
    _s("change6", "Chang'e 6 (far side)", "Other nations", -41.6385, -153.9852, "landed point",
       "https://lroc.im-ldi.com/images/1374"),
    _s("slim", "SLIM (Shioli)", "Other nations", -13.316, 25.251, "landed point", "https://lroc.im-ldi.com/images/1358"),
    # --- reference points ---
    _s("subearth", "Sub-Earth reference (0, 0)", "Reference", 0.0, 0.0, "definition", "definition of the Mean Earth frame",
       relayed=False),
    _s("southpole", "South pole (89.9 S)", "Reference", -89.9, 0.0, "definition", "definition", relayed=False),
]

_BY_ID = {s["id"]: s for s in SITES}


def normalise_lon(lon: float) -> float:
    """East longitude in (-180, 180]; 180 stays 180 E."""
    v = ((float(lon) + 180.0) % 360.0) - 180.0
    if v == -180.0:
        v = 180.0
    return round(v, 6)


@lru_cache(maxsize=512)
def _terrain_profile(lat: float, lon: float, mast_m: float, dem_key: str, variant: str = ""):
    dem = demstore.get_dem()
    if not variant:
        return terrain.cached_profile(dem, lat, lon, mast_m)
    here = dem.member_at(lat, lon)
    if here is None:
        raise ValueError("no DEM covers this point")
    if variant == "near":                 # first ray sample at half the grid spacing instead of one spacing
        return terrain.cached_profile(dem, lat, lon, mast_m, min_step_m=here.resolution_m / 2.0)
    if variant.startswith("drop"):        # the same point with the finest 1, 2, ... grids left out
        k = int(variant[4:])
        order = [m for m in dem.members]
        i = order.index(here)
        rest = order[i + k:]
        if not rest:
            raise ValueError("no coarser grid")
        sub = demstore.stack([m.name for m in rest])
        return terrain.cached_profile(sub, lat, lon, mast_m)
    raise ValueError(f"unknown profile variant {variant!r}")


def terrain_profile(lat: float, lon: float, mast_m: float = 2.0, variant: str = ""):
    """360-degree terrain horizon for a point, or None when no DEM covers it.

    ``variant`` selects a deliberately different computation of the same point, used to show how
    sure a result is: "near" samples the nearest ground more finely, "drop1" leaves out the finest
    grid under the site ("drop2" the finest two, and so on).
    """
    dem = demstore.get_dem()
    if dem is None:
        return None
    try:
        return _terrain_profile(round(float(lat), 5), round(float(lon), 5), round(float(mast_m), 2),
                                dem.name + getattr(dem, "fingerprint", ""), variant)
    except ValueError:
        return None


def horizon_from_profile(prof, mask_deg: float = 0.0) -> Horizon:
    dem = prof.dem
    meta = {"dem_label": dem["label"], "resolution_m": dem["resolution_m"], "synthetic": dem["synthetic"],
            "mast_m": prof.mast_m, "site_height_m": round(prof.site_height_m, 1),
            "min_el_deg": round(float(prof.el_deg.min()), 3), "max_el_deg": round(float(prof.el_deg.max()), 3),
            "min_coverage_km": round(float(prof.coverage_km.min()), 1), "provenance": dem.get("provenance", ""),
            "first_sample_m": dem.get("first_sample_m", dem["resolution_m"]),
            "validated": bool(dem["resolution_m"] <= 500.0 and prof.lat <= -80.0)}
    return Horizon(mask_deg=mask_deg, profile_az_deg=prof.az_deg, profile_el_deg=prof.el_deg,
                   source=dem["label"], meta=meta)


def horizon_for(lat: float, lon: float, mask_deg: float = 0.0, mast_m: float = 2.0,
                use_terrain: bool = True, variant: str = "") -> Horizon:
    """Terrain horizon when a DEM covers the point and terrain is wanted,
    otherwise the smooth sphere (optionally raised by a flat user mask)."""
    prof = terrain_profile(lat, lon, mast_m, variant) if use_terrain else None
    if prof is None:
        return Horizon(mask_deg=mask_deg)
    return horizon_from_profile(prof, mask_deg)


def get_site(site_id: str, mask_deg: float = 0.0, mast_m: float = 2.0, use_terrain: bool = True) -> Site:
    if site_id not in _BY_ID:
        raise KeyError(site_id)
    s = _BY_ID[site_id]
    return Site(s["name"], s["lat"], s["lon"], horizon=horizon_for(s["lat"], s["lon"], mask_deg, mast_m, use_terrain))


def custom_site(name: str, lat: float, lon: float, mask_deg: float = 0.0, mast_m: float = 2.0,
                use_terrain: bool = True) -> Site:
    lon = normalise_lon(lon)
    return Site(name or f"{lat:.3f}, {lon:.3f}", float(lat), lon,
                horizon=horizon_for(float(lat), lon, mask_deg, mast_m, use_terrain))


def smooth_twin(site: Site, mask_deg: float = 0.0) -> Site:
    """The same point over the smooth sphere, for side-by-side comparison."""
    return Site(site.name, site.lat, site.lon, horizon=Horizon(mask_deg=mask_deg))
