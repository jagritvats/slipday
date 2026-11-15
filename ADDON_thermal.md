# Add-on: Temperature (NASA Diviner)

A second NASA instrument next to LOLA terrain: surface temperature measured by the Diviner Lunar Radiometer
Experiment on NASA's Lunar Reconnaissance Orbiter. For any south-polar site (80 S to the pole) it reports the
highest and lowest measured temperature, the coldest night, the average, and whether the site is in or near a
cold trap (ground whose highest measured temperature stays below 110 K).

## Products (NASA PDS Geosciences Node, no login, fetched with plain curl, generic client name)

Start page: https://pds-geosciences.wustl.edu/missions/lro/diviner.htm

1. **Diviner Polar Resource Product, south** (LRO-L-DLRE-5-PRP-V2.0, UCLA Diviner team, created 2018-02-21).
   A triangle mesh of the south polar region (spacing about 0.5 km) with, per triangle, the multi-year
   average and maximum bolometric temperature and the ice stability depth.
   - https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/extras/prp/dlre_prp_south.zip
     (116.6 MB, holds DLRE_PRP_SOUTH.TAB, 604.8 MB) sha256 `324adf0596b9539207ad16d12836217a8a095424a21a0f944f3ecc6745090f32`
   - .../data_derived_prp/dlre_prp_south.lbl sha256 `6bb8d7fbdb6450608a163ffbc1871739e0e23e2dcd153b22424cc18456e364c7`
   - .../data_derived_prp/dlre_prp_south.xml sha256 `24a7bba837bbf013f59dc657a8766b6c4d1d06c0d4eea35a5f497908b17beece`
2. **Diviner Gridded Data Record level 3, night-time average bolometric temperature, south polar
   stereographic, 240 m/pixel** (LRO-L-DLRE-5-GDR-V1.0), one map per lunar month, local time 18:00-06:00,
   3812 x 3812 int16, DN x 0.02 = K. 25 maps: all 15 night maps of 2010 and all 10 of 2016 (the 2016 maps
   alone have no coverage within about 2.5 degrees of the pole, so 2010 was added).
   Base URLs: https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_gdr_l3/2010/polar/img/
   and .../data_derived_gdr_l3/2016/polar/img/ ; file names `dgdr_tbol_avg_pols_<date>n_240_img.img` (+ `.lbl`).

| file (.img, 29,062,688 bytes each) | sha256 |
|---|---|
| dgdr_tbol_avg_pols_20100107n_240_img | 60294cdc11403017cadcef556c0befa45531fee83920f2d2d6f102814717f295 |
| dgdr_tbol_avg_pols_20100203n_240_img | e75165efa618610eaea332ac4752554cd4cf0ab77d4f7b31346e6c8c14c1235c |
| dgdr_tbol_avg_pols_20100303n_240_img | 01d635eb945d29ca1324a4c1633a4a006794899dec22b2e80bfbf136b01730f1 |
| dgdr_tbol_avg_pols_20100330n_240_img | f7ede6cf409f8c7ce43aba62601a3c7fc86409ddf455acd0a8366274744faf30 |
| dgdr_tbol_avg_pols_20100426n_240_img | 6da4a618816c526c95ed98e905621f4d6bc8d58c928eb4c3115872718b16bd54 |
| dgdr_tbol_avg_pols_20100523n_240_img | c5c3ca6567cb70e927e8c79b11488db140f48ff66f9c7bbeb36b713b36b39a60 |
| dgdr_tbol_avg_pols_20100620n_240_img | 14d58e562b5b932af5c8c65aaed9f3703c6b74a2bd9bb82f0b91b3d998e1c4c5 |
| dgdr_tbol_avg_pols_20100703n_240_img | 54f8423ed9a0a56478d6d6696a5eda86972badbef551129834fc66eb211276da |
| dgdr_tbol_avg_pols_20100731n_240_img | 69d48157121d36a93be4dab14c2ca3dc6a2f5bb665f220cde2d1d6840b55d9ea |
| dgdr_tbol_avg_pols_20100827n_240_img | ca382eb1678c49b3bdfc39c2273b3846cc05dcffb891c52031566320521215f9 |
| dgdr_tbol_avg_pols_20100923n_240_img | 14853fd6b076a0577d773423b8e03dc4ba03dd52a348f4dfbc14e34a73f10123 |
| dgdr_tbol_avg_pols_20101021n_240_img | 0f932f5006215ca9fc6eb4285198ab6b7ff1ea860763be34482206d09449ae00 |
| dgdr_tbol_avg_pols_20101117n_240_img | 8fee7eb88bda7da20e6aa1fcc75c75d5f3edd8bc9c44dddd1c8d1a16d2051ed2 |
| dgdr_tbol_avg_pols_20101214n_240_img | 77f0911f354dce87b6ef45a18df661b9b97901d3d99dbea7344d831ab8602113 |
| dgdr_tbol_avg_pols_20101228n_240_img | ce1439e8aab0c32afc579009a7ed433e0a1a400241736438bf15c74c3d2e1e68 |
| dgdr_tbol_avg_pols_20160125n_240_img | c81b31a35c57c2e10402cbe92d34cf7241a024534fc86a3e238f48af6359e282 |
| dgdr_tbol_avg_pols_20160221n_240_img | bd62c9c79c3534fbe8a937540cdec87af2f0348ac7f201e0bd877880b122bdea |
| dgdr_tbol_avg_pols_20160319n_240_img | 4e62771480c32d226c47461b601f742d48f8d116742417d8ee9b5a9ca8e5f4ea |
| dgdr_tbol_avg_pols_20160416n_240_img | d73f4eccca30c4d26416e405d65d5e03cb51003f945f5df42d5cfe9e7f9e4fbf |
| dgdr_tbol_avg_pols_20160504n_240_img | 933169f0360316e7b4c50a26a1d404980b884a1f9b3595c65a956c86cadf93bf |
| dgdr_tbol_avg_pols_20160527n_240_img | f77c85025459e6fcefa481938579475cd3b5a80b44803e560b2262868553732d |
| dgdr_tbol_avg_pols_20160623n_240_img | 4ad360b8561d94b951847c561752bf2f2369dc38d21b9ff067a4998765d76db0 |
| dgdr_tbol_avg_pols_20160720n_240_img | c352e56d3b537accc0450edbe9c43d70102137e42eca06ad0873f9176f35e279 |
| dgdr_tbol_avg_pols_20160816n_240_img | 45442e9cc6ced7a836234ee7bdcd96d093fc5615632a13113af6fc18ea9d7e70 |
| dgdr_tbol_avg_pols_20160913n_240_img | 62e0bd8a5f4f9d84f0a35078889c44c4e1d0ef14788c818ac8855938ac531299 |

The `.lbl` labels are kept beside the images in `data/addons/thermal/raw/` (their sha256 values can be
listed with `sha256sum data/addons/thermal/raw/*.lbl`).

Not used: the GDR polar maps have no multi-year maximum or minimum summary map in this archive; the
multi-year maximum comes from the polar resource product. The polar cumulative products (PCP) are
200+ MB per file and were not downloaded.

## Stored data (`data/addons/thermal/`)

- `raw/` - the downloads above. `.img`, `.zip`, `.tab` are git-ignored (`data/addons/thermal/.gitignore`).
- `prp_south_84.npz` (10.3 MB) - PRP triangles poleward of 84 S: lat, lon, temp_avg, temp_max.
  sha256 `63e9368be28d54ccf4d4a2f658bc9b4cd7a0844e8639a8914a83813c76cd315d`
- `night_min_240m.npy` (6.5 MB) - per pixel, the lowest value over the 25 night maps, int16 DN (x 0.02 K),
  1800 x 1800 crop centred on the pole (about 83 S to the pole). sha256 `84032a61a95f08b86316eee550ba42f6ff7b3f6aa8dee2bb63029f7a5f8f17f1`
- `night_count_240m.npy` (3.2 MB) - how many of the 25 maps have data at each pixel.
  sha256 `94a56d0c5f8bef2c23b7d391773500b20ca0d9eeed4804908334eab79f74f20f`

Rebuild: `.venv\Scripts\python -I slipday\addons\thermal_build.py` (reads `raw/`).

## Method

- Site to map: south polar stereographic, R = 1737.4 km, x = 2R tan(45 deg + lat/2) sin(lon),
  y = 2R tan(45 deg + lat/2) cos(lon); grid column = 1905.5 + x/0.24 km, row = 1905.5 - y/0.24 km.
  The orientation was checked against the PRP (which carries its own lat/lon): night-map values and PRP
  average temperatures correlate at r = 0.86 with this orientation and r = 0.02 with the row flipped.
- **Highest measured** (`max_k`): largest PRP maximum temperature among triangles within 0.36 km.
- **Average** (`avg_k`): mean PRP average temperature among the same triangles.
- **Lowest measured** (`min_k`): lowest night-map value in the 3 x 3 pixel box (720 m) around the site.
- **Coldest night** (`coldest_night_k`): lowest night-map value at the site pixel. Each map is a
  month-long night-time average, so the true instantaneous minimum may be lower.
- **Cold trap** (`cold_trap`): `in` = nearest PRP triangle has a maximum below 110 K; `near` = any triangle
  within 2 km does; `nearest_km` = distance to the nearest such triangle; `share_within` = fraction of
  triangles within 2 km below 110 K.

## Figures

| site | highest | lowest | coldest night | average | cold trap |
|---|---|---|---|---|---|
| Opening example (89.010 S, 122.764 E) | 217.8 K | 43.6 K | 47.2 K (12 maps) | 97.7 K | no, none within 2 km |
| C1, Shackleton connecting ridge (89.4398 S, 137.17 W) | 245.8 K | 54.0 K | 56.2 K (10 maps) | 123.6 K | no, none within 2 km |
| Shackleton floor (89.67 S, 129.78 E) | 91.7 K | 41.3 K | 42.4 K | 51.6 K | in |
| Faustini floor (87.18 S, 84.31 E) | 69.1 K | 28.9 K | 29.5 K | 44.4 K | in |
| LCROSS impact site (84.675 S, 48.703 W) | 45.8 K | 28.4 K | 30.1 K | 36.3 K | in |

## Check against published values

Paige et al. 2010, "Diviner Lunar Radiometer Observations of Cold Traps in the Moon's South Polar Region",
Science 330, 479-482 (doi:10.1126/science.1187726), at the LCROSS impact site: "Diviner-measured summer
solstice daytime and nighttime surface bolometric brightness temperatures of 46.7 and 38.7 K", and annual
average surface temperatures "close to 38 K".

- Our highest measured there: **45.8 K** vs published summer daytime **46.7 K** (0.9 K lower).
- Our average there: **36.3 K** vs published **about 38 K** (1.7 K lower).
- The paper also reports mid-day temperatures "as low as 29 K" in the coldest crater floors; the lowest
  values in our Faustini and LCROSS figures are 28-30 K at night.

Shackleton: a published non-Diviner (model) estimate gives floor temperatures below about 90 K; Diviner's
highest measured on the floor centre here is 91.7 K, so not a like-for-like check, noted only.
(The paper text was read from a reproduction of the article; the figures quoted match the abstract record.)

## Endpoint and container

- `GET /api/addons/thermal?lat=..&lon=..` (lat must be -90 to -80; longitude east, any range, wrapped).
  Router: `slipday/addons/thermal.py`, exposes `router` (not yet registered in `api.py`; add
  `"addons.thermal"` to the add-on list there). Returns `max_k`, `min_k`, `coldest_night_k`, `avg_k`,
  `night_maps`, `cold_trap{in,near,nearest_km,within_km,share_within,label}`, `measured_by: "Diviner"`,
  `source`. 422 outside the south polar cap, 503 if the data files are missing.
- Front end: `static/addons/thermal.js`, container `<div id="addon-thermal"></div>`, then
  `<script src="/static/addons/thermal.js"></script>` after `app.js`. It follows the card's chosen site by
  watching the page's own `/api/mission` answers and the `#mSite` menu, and reads the page's CSS variables.
- Tests: `tests/addons/test_thermal.py`.

## Limits

- South polar cap only (data kept from 84 S for the PRP and about 83 S for night maps; endpoint accepts 80 S
  and returns nulls with a note where there is no data).
- Night maps are monthly averages of night-time passes, 240 m pixels; small cold spots finer than that are
  smoothed.
- The PRP gives no minimum; the minimum comes from the 25 night maps only (2010 and 2016).
