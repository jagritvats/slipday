"""Add-on: boulder / rock hazard -- NOT AVAILABLE at the south-pole sites.

This module reports that no public NASA rock-abundance or boulder product, reachable without a login, covers the
app's south-pole sites.  It does not invent a value.  What was checked (15 Nov 2026, plain HTTP, no login):

  1. LRO Diviner rock abundance, PDS Geosciences node, product DGDR_RA_AVG_CYL_128_IMG (Bandfield et al. 2011,
     2016).  Its label says MINIMUM_LATITUDE = -80, MAXIMUM_LATITUDE = 80, simple cylindrical, 128 px/deg, and the
     description says data were restricted to "latitudes between 80N and 80S".  The 32 px/deg version is the same
     product family.  The Diviner Global High-Resolution Mosaic rock abundance (DGHRM_RA_SAM_70S70N) stops at 70 S.
     The Diviner polar products (PCP, PRP, polar GDR) are temperature / resource products, not rock abundance.
  2. LROC RDR (now served from pds.mcp.nasa.gov): BDR = mosaics (NAC_POLE, NAC_ROI, WAC_POLE, ...), SDP = NAC_DTM,
     NAC_PHO, WAC_GLD100, WAC_TIO2, ...  No boulder or rock-abundance layer.
  3. PGDA product 78 (LOLA 5 m/px south-pole site models, Barker et al. 2021), files for Site01: surface height,
     slope, slope error, total error, ldec, ROIs.  No rock or boulder layer.  The PGDA product list has no rock or
     boulder product (the "Large-Scale Roughness" product is km-scale LOLA roughness, not rocks).

The four app points all lie poleward of 88.4 S (Site01 and Site07 5 m tiles: corners computed from their dems.json
origin and 3200 x 3200 cells at 5 m, assuming rows run from y0 downward; robust_pick 89.010 S; shackleton C1
89.440 S), i.e. more than ~250 km poleward of the 80 S edge of the Diviner map.

    GET /api/addons/rocks          {"available": false, "why": ..., "checked": [...]}
    GET /api/addons/rocks/site     same answer for any site or point: "no coverage here"
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/addons/rocks")

WHY = ("No public NASA rock-abundance or boulder map reachable without a login covers the lunar south pole. "
       "The Diviner rock-abundance map (the only gridded rock product found) stops at 80 S; the app's sites are "
       "near 89 S. No value is shown rather than a made-up one.")

CHECKED = [
    {
        "url": ("https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_gdr_l3/"
                "cylindrical/img/dgdr_ra_avg_cyl_128_img.lbl"),
        "offers": "Diviner rock abundance (areal rock fraction), 128 px/deg, simple cylindrical",
        "coverage": "80 S to 80 N (label MINIMUM_LATITUDE = -80, MAXIMUM_LATITUDE = 80)",
        "covers_sites": False,
    },
    {
        "url": "https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_ghrm/",
        "offers": "Diviner global high-resolution mosaic of rock abundance (dghrm_ra_sam_70s70n)",
        "coverage": "70 S to 70 N (from the product name)",
        "covers_sites": False,
    },
    {
        "url": "https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_prp/",
        "offers": "Diviner south polar resource product (temperature-based), no rock abundance",
        "coverage": "south pole",
        "covers_sites": False,
    },
    {
        "url": ("https://pds.mcp.nasa.gov/data/store/img/?list-type=2&delimiter=/&prefix="
                "lunar_reconnaissance_orbiter/pds4/lroc/lro-l-lroc-5-rdr/LROLRC_2001/DATA/"),
        "offers": "LROC RDR: BDR mosaics and SDP (NAC_DTM, NAC_PHO, WAC_GLD100, WAC_TIO2, ...); no boulder layer",
        "coverage": "various",
        "covers_sites": False,
    },
    {
        "url": "https://pgda.gsfc.nasa.gov/products/78",
        "offers": "LOLA 5 m/px south-pole site models: height, slope, errors; no rock or boulder layer",
        "coverage": "south-pole sites",
        "covers_sites": False,
    },
    {
        "url": "https://pgda.gsfc.nasa.gov/products",
        "offers": "PGDA product list: no rock or boulder product",
        "coverage": "-",
        "covers_sites": False,
    },
]


def _answer() -> dict:
    return {"available": False, "why": WHY, "checked_on": "2026-11-15", "checked": CHECKED}


@router.get("")
def rocks_info() -> dict:
    return _answer()


@router.get("/site")
def rocks_site(site: Optional[str] = Query(None), lat: Optional[float] = Query(None),
               lon: Optional[float] = Query(None)) -> dict:
    out = _answer()
    out.update({"site": site, "lat": lat, "lon": lon, "value": None, "result": "no coverage here"})
    return out
