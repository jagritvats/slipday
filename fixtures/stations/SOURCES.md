# Sources for the Deep Space Network station rule

## Station coordinates and the elevation mask (read first-hand)

File: `data/reference/DSN_810-005_module301_RevP.pdf`, 2,745,535 bytes,
sha256 `53d8c28eddde48a2212b403422689a11fc0ff75fcab830a1e2ec00cdf8a4e160`,
from https://deepspace.jpl.nasa.gov/dsndocs/810-005/301/301P.pdf (fetched 15 Nov 2026, 02:15 IST).
DSN Telecommunications Link Design Handbook, DSN No. 810-005, module 301 "Coverage and Geometry",
Rev. P, issue date May 22, 2026, Jet Propulsion Laboratory.

Text read from the file (pass 3, by extracting the page text and reading it):

* Section 2.2.3: "The spacecraft coverage spreadsheet uses generic elevation limits for the receive and
  transmit elevations. These are 6.0 degrees for receive, 10.0 degrees for low-power transmit, and
  13.5 degrees for high-power transmit. There is no azimuth variation of these elevation limits, ..."
* Table 5, geodetic coordinates with respect to the WGS 84 ellipsoid (latitude d m s, east longitude
  d m s, height m):
  * DSS 14 70-m: 35 25 33.24312, 243 6 37.66244, 1001.390 (Goldstone)
  * DSS 63 70-m: 40 25 52.35510, 355 45 7.16924, 864.816 (Madrid)
  * DSS 43 70-m: -35 24 8.72724, 148 58 52.56231, 688.867 (Canberra)

The app uses 10.0 degrees (low-power transmit: a lander needs commands up as well as data down) as
one flat angle at every azimuth. The handbook's per-antenna horizon masks are not applied, and this
is a mask at the ground station, not at the lander: the lander's own horizon is the terrain skyline.

## JPL Horizons tables used to check the geometry

Six observer tables of the Moon (target 301) from DSS-14, DSS-63 and DSS-43, hourly, airless apparent
azimuth and elevation, from the Horizons API (https://ssd.jpl.nasa.gov/api/horizons.api), fetched
14 Nov 2026 11:36 UTC. The query parameters are printed in each file's header (target, site, start,
stop, step, refraction); the full query strings were not recorded.

| file | sha256 |
|---|---|
| horizons_moon_goldstone_2026nov.txt (20 to 22 Nov 2026) | b42661914053d6295739ecf0da127d712cccc8a39df46dadb0056ab20ba74067 |
| horizons_moon_madrid_2026nov.txt | b9ade65de6896c7c90fdde3f4e05cb786fe52ebf31b6cb91c275abad5b2f5057 |
| horizons_moon_canberra_2026nov.txt | 6518c8cc3665924e5919862a0dea7be8f395db1767865acb1517f1b6996bc87d |
| horizons_moon_goldstone_2034jun.txt (10 to 12 Jun 2034) | 3586a3a92f2ba6efaffac5d907c261e82a32b1dad621d52d43bbd415a7a5af42 |
| horizons_moon_madrid_2034jun.txt | 3bfba449c7b67bd3d3720ab8155cc0a0b42ae29f31a2c0e31404eb8ec7d21291 |
| horizons_moon_canberra_2034jun.txt | 3a16d2f9379ba61b14e59c44e2239467c2b734ae2146a3d1f4fdece14276bda6 |

`scripts/check_stations_horizons.py` compares them with `slipday.stations`: largest difference in
the Moon's elevation over 294 hourly rows 0.00060 degrees (run 15 Nov 2026, 02:10 IST).
