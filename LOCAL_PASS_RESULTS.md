# Local pass results

Run on Saturday 14 Nov 2026, 14:55 to about 17:00 local time (UTC+5:30), by the builder of this entry.
Machine: Windows 11 laptop, Intel Core Ultra 9 275HX (24 cores), 31 GB of memory; Python 3.12.11 in a
private virtual environment (`.venv`: numpy 2.5.4, fastapi 0.162.7, tifffile 2026.11.12, imagecodecs
2026.11.11); Git Bash for the `.sh` script; Node 22 with `puppeteer-core` and Chrome; Docker Desktop
(engine 29.9.3). Two other build jobs were using the same machine throughout, so every timing below is an
upper figure for this hardware.

Every number in this file was measured on that machine with the command given beside it. Commands are
written as they were run, from the entry folder `mvps/slipday`; `py` stands for
`.venv\Scripts\python.exe`. The small measuring scripts are in `scripts/local_pass_tools/` (they were run
from a scratch folder during the pass and copied in afterwards, unchanged); its README says what each prints.
What was not run is in section 11.

## 0. Summary

| Item | Outcome |
|---|---|
| Official downloads | 21 files, 1.27 GB, from pgda.gsfc.nasa.gov, pds-geosciences.wustl.edu, imbrium.mit.edu and svs.gsfc.nasa.gov. All seven files with a recorded hash matched. The Earth-map names in the script were right; the Sun-map folder was wrong and was found by hand. |
| Earth-visibility validation | The label says "any fraction of the Earth disc". With that rule: 60 m map, 200 points, mean absolute difference 0.97 points, correlation 0.9946; 120 m map, 200 points, 0.69 points, 0.9984. The matching rule is also the best-fitting one. On 60 well-lit ridge pixels: 1.57 points, correlation 0.9707 (the Sun check there gives 4.02 and 0.61). |
| 80 m grid | sha256 82030dcb... confirmed against the download from pgda.gsfc.nasa.gov. Working arrays rebuilt from the official files; the rebuilt 14,400-skyline field is byte-identical to the earlier one. |
| Stored validation, re-run | Same headline rows: 0.80 (0.9916), 0.76 (0.9949), ridge pixels 4.02 (0.61), C1 88.01 / 92.06 / 198 h. |
| Fix: 240 m fallback overconfident | Done. Scatter widened to one grid cell, said on the card. Malapert shoulder and ridge C2 now read "Not sure" on the fallback. Side effect: so does the default example C1. |
| Fix: say the Yes assumes a 100 m scatter | Done, in the headline; the landing circles show what a wider miss does. |
| Fix: `MALLOC_ARENA_MAX=2` | Done: run commands, Dockerfile, Procfile, render.yaml, and applied in code when missing. Measured in a 512 MB container on the 240 m grid: killed without the limit, 296 to 299 MB group peak with it. |
| Which grid the public link must serve | The 80 m grid: on the 240 m grid the headline example reads "Not sure". Measured: the 80 m grid answered the whole load test inside a 512 MB container (group peak 431 MB), and inside 768 MB and 1 GB (433 and 421 MB). |
| Fix: each replay its own need | Done for IM-1 (168 h), IM-2 (240 h), Blue Ghost (336 h) from NASA press kits (relayed text); Chandrayaan-3 stays illustrative, and says so. IM-1 now reads Yes with 1 day of margin. Earth-contact hours stay illustrative everywhere. |
| Fix: storyboard to four frames | Done; frames and screenshots retaken. |
| Feature: landing circles per day of slip | Done (100 m, 250 m, 500 m, 1 km). An area count over up to 93 touchdown points, not a lander's dispersion model. |
| Feature: slip-robust site list | Done, on demand from the map panel. 5 of the 12 best map points stay a clear Yes for the default example. |
| Live Horizons cross-check | Run for the first time: largest elevation difference 1.36e-05 degrees (164 rows, two sites). The 218 relayed fixture rows equal the direct download. |
| Tests | 152 passed, 0 failed, 0 skipped with everything installed; 130 passed, 22 skipped, 0 failed as a fresh clone would have it. Browser checks: 43 pass, 0 fail. |
| Docker | Image builds locally (1.33 GB with the 80 m grid) and serves the page; the browser checks pass against the container. Not pushed, not deployed. |

## 1. Downloads

### 1.1 What was downloaded

All with `curl` under the client name `slipday-fetch/1.0` (no personal detail in any request), into
`data/reference/` (git-ignored). A receipt is in `data/reference/DOWNLOADS.tsv`. sha256 computed after
download with `py -I scripts\local_pass_tools\hash_dir.py data\reference` (a 15-line script: `hashlib.sha256` over each file).

| File | Bytes | sha256 | Source |
|---|---|---|---|
| `AVGVISIB_85S_060M_201608_EARTH.IMG` | 51,166,728 | `0958313069d6039b2474c875ff662f28dbcba2bd853d9ea458aa807b7948c11f` | https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608_EARTH.IMG |
| `AVGVISIB_85S_060M_201608_EARTH.LBL` | 4,111 | `45a61697d779fdb9170bca2553f9e0188aeda1159811d3531c348df8f57f68bd` | same folder |
| `AVGVISIB_75S_120M_201608_EARTH.IMG` | 116,250,752 | `443ad251a480dea19e96417dfcfe1cb87a91eb02ee158b262d78abe899258fff` | same folder |
| `AVGVISIB_75S_120M_201608_EARTH.LBL` | 4,112 | `86eabf4611eaf18c4e9b170b205d517b014ec9e694bc93c80d693caf7c0ca015` | same folder |
| `AVGVISIB_65S_240M_201608_EARTH.IMG` | 82,432,800 | `b194b9a1ce0dacdb00dbdc546b99850656c206ba0e13956178831f72cc65d73e` | same folder |
| `AVGVISIB_65S_240M_201608_EARTH.LBL` | 4,114 | `eb99d4e4a0bd3508e95dc87e0f65663452db0c20dcadaf272ebf27c7ce418913` | same folder |
| `AVGVISIB_85S_060M_201608.LBL` | 4,094 | `33decce957d5d4d9608557d8d969d1e1b94056a159b2563624ade4b528a0c917` | same folder |
| `AVGVISIB_75S_120M_201608.LBL` | 4,092 | `1b597f85822c20e349469c9499e7bd85a48efc3a23b9dd9d82b658e59192883c` | same folder |
| `AVGVISIB_65S_240M_201608.LBL` | 4,096 | `10b0d6d881713d6bd4d61a30cc64da6d53934e2c9a8cc702b36a5cd758751b03` | same folder |
| `README_ILLUMINATION_2016.TXT` | 2,016 | `f806f9c7fb410b17dd75c2f44f91755b5ca890ac047004a1e8fbb819c24b9ec6` | https://imbrium.mit.edu/EXTRAS/ILLUMINATION/README_ILLUMINATION_2016.TXT |
| `AVGVISIB_65S_240M_201608.JP2` | 48,625,783 | `4ccaf5ef7cdfc35bbff4d28e0d9b1051d9d56a66181cda633e71bfd42237dd49` | https://imbrium.mit.edu/EXTRAS/ILLUMINATION/JP2/AVGVISIB_65S_240M_201608.JP2 |
| `AVGVISIB_65S_240M_201608_JP2.LBL` | 6,464 | `2d377913872e628f3b27503fd61b3a379046dd85573fba93170e60f5b3257a24` | same folder |
| `AVGVISIB_85S_060M_201608.TIF` | 33,994,464 | `ccf67d4f39e0a970c111196da7d6551ffcf50d075470b93067fb3904c0b05806` | https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608.TIF |
| `AVGVISIB_75S_120M_201608.TIF` | 83,052,039 | `d539467f16ccc5f51b6a904af6be5d16c9b2f194afe619b9f1f81841d9fec0bb` | https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_75S_120M_201608.TIF |
| `LDEM_80S_80MPP_ADJ.TIF` | 189,158,392 | `82030dcbdd7c4bb0c7d858e9b4b293b9f2cda5a543ba31ec0f42784bd6beee5a` | https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF |
| `LDEM_75S_240M.JP2` | 10,766,928 | `a0ebbad0a2650c742ed2d4ec1314aa095f869ba800f817b1b72eeb9194345c36` | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/jp2/ldem_75s_240m.jp2 |
| `LDEM_75S_240M_JP2.LBL` | 6,362 | `e4d340c43a563d300817741428fb1b113a3d1a9fe3f4e3ebe636d25b71b60b09` | same folder, `ldem_75s_240m_jp2.lbl` |
| `LDEM_16.IMG` | 33,177,600 | `a511e40d7a3ea3275945b4da2a1df377133264fab0be94b7434b1cf8907254cb` | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_16.img |
| `LDEM_16.LBL` | 5,121 | `9aef29463ccc6ed3a3fbe0df3ecd830a99c69e16b564f455507dee2697096579` | same folder, `ldem_16.lbl` |
| `ldem_64_uint.tif` | 530,934,146 | `0f40bce8b42864deddb6943a38474879e691d5b20647aa5e54c2612b23106499` | https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/ldem_64_uint.tif |
| `ldem_64_uint_south_60S_90S.npy` | 88,473,728 | `2b5a02c566b30c3aed617c3a1d738009053f3ef4e23cfeb4617db64f7afa1c89` | derived here: rows 9600 to 11519 of `ldem_64_uint.tif` |

Total 1,268,077,942 bytes in 21 files.

JPL Horizons reference tables, downloaded with `py scripts\fetch_horizons_fixtures.py` (client name
`slipday-crosscheck/0.1`) into `fixtures/raw/`; the request address is the first line of each file:

| File | Bytes | sha256 |
|---|---|---|
| `horizons_sun_im1.txt` | 8,174 | `7cc82882e27ee60ad61f855a7778cd1a76cab24ba74523957855aff4c0b922b4` |
| `horizons_earth_im1.txt` | 8,175 | `08d7ef554c3d0b130b13068610c1d86fc4a299db6636318ae7a36c53dfcf235a` |
| `horizons_sun_chandrayaan3.txt` | 8,375 | `8bd49107cb5f57a1433abf321c3969d7a02bf5d79f352d7ca994058fed4bd355` |
| `horizons_earth_chandrayaan3.txt` | 8,376 | `ae85e9892d630c3e660e04b2e91fb52ba82968103d20f7af0b583067abdbaf8f` |
| `horizons_sun_blueghost1.txt` | 8,174 | `f629c36e2a728b3db6ce2433c3ec661ce4dd9dfdd605bc6985254d4f34d38060` |
| `horizons_earth_blueghost1.txt` | 8,175 | `00364640144d5a7cc9cf475ce22cb1a88dccc68a1c5a23e1f1f06634ae6f8de2` |

These are the files of the second download (16:41). The first (15:16) was written in text mode on
Windows, which turned every line end into CRLF, so those files were not the responses as served; the
script now writes the response unchanged, after one added line with the request address. Both downloads
gave the same 218 data rows. A Horizons response carries the time it was produced, so these hashes will
not repeat on another day; the data rows will.

### 1.2 What happened, in order

1. `sh scripts/fetch_on_your_machine.sh` (the untested version) in Git Bash, 14:55. The six Earth-map
   files came down at the first address tried (`https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/`): the
   guessed names were right. The 80 m mosaic came down and printed `hash ok`.
2. The same run printed `got AVGVISIB_85S_060M_201608.TIF` and `got AVGVISIB_75S_120M_201608.TIF`, then
   `hash DIFFERS` for both with the same hash, 57b3ff09.... Each file was 3,789 bytes of HTML:
   `https://pgda.gsfc.nasa.gov/data/LOLA_illumination/...` does not exist, and that server answers a
   wrong path with HTTP 200 and a "PGDA - Not Found" page, which `curl -f` accepts. The real folder was
   read off the links of https://pgda.gsfc.nasa.gov/products/69: `/data/MoonIllumination/`. The two HTML
   files were moved out and the GeoTIFFs downloaded from there; both hashes matched.
3. The PDS and SVS files and the Sun-map labels were downloaded with a second list of `curl` commands
   (addresses in the table). `https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/JP2/` and `/IMG/`, given in the
   scout's notes for the AVGVISIB products, answer 404; the files are under `/EXTRAS/ILLUMINATION/`.
4. The 240 m Sun map as JPEG2000 with its label was added later (15:45) because one reader test uses it.
5. `scripts/fetch_on_your_machine.sh` was then rewritten to fetch everything above from the addresses
   that worked, to refuse a download that starts like a web page, and to check ten hashes.
6. The rewritten script was run from an empty scratch folder to test it end to end. The first attempt
   (16:05) lost one file: `curl: (56) schannel: server closed abruptly` part-way through
   `AVGVISIB_75S_120M_201608.TIF` from pgda.gsfc.nasa.gov, and the script printed `FAILED` for it. The
   script was then given a retry that continues the partial file (up to five attempts). A second attempt
   was spoiled by my own handling: I stopped the first run, its download process kept running, and two
   processes wrote the same partial file. The 80 m file that came out had the right size and the wrong
   hash, and the script's check said `hash DIFFERS`, which is what the check is for. Both scratch
   folders were deleted. The third, undisturbed run (16:23:56 to 16:38:13, 14 minutes) printed `got`
   for all 20 files, `hash ok` for all ten with a recorded hash, and `all files present`; every one of
   the 20 files has the sha256 of its counterpart in `data/reference/` (`sha256sum` over both folders,
   empty `diff`). A fourth pass over that folder printed `have` 20 times and the same ten `hash ok`.
   No transfer was cut in the third run, so the retry in the shell script has not been exercised by a
   real interruption; the same logic in `scripts/fetch_grid80.py` was tested with a seeded partial file
   (section 9).

### 1.3 Against the mirrored copies the earlier builds used

| File | Recorded for the mirrored copy | Official download |
|---|---|---|
| `LDEM_80S_80MPP_ADJ.TIF` | 82030dcb..., 189,158,392 bytes | identical |
| `LDEM_75S_240M.JP2` | a0ebbad0... | identical |
| `LDEM_16.IMG` | a511e40d... | identical |
| `ldem_64_uint.tif` | 0f40bce8..., 530,934,146 bytes | identical |
| crop `ldem_64_uint_south_60S_90S.npy` | 2b5a02c5... | the crop made here from the official file is byte-identical |
| `AVGVISIB_85S_060M_201608.TIF` | ccf67d4f... | identical |
| `AVGVISIB_75S_120M_201608.TIF` | d539467f... | identical |
| `AVGVISIB_65S_240M_201608.JP2` | 4ccaf5ef... | identical |
| `AVGVISIB_65S_240M_201608_JP2.LBL` | fc396d64..., 6,328 bytes | 6,464 bytes: 136 CRLF line ends; with CRLF changed to LF the sha256 is fc396d64... |
| `LDEM_16.LBL` | 3e006f37..., 5,012 bytes | 5,121 bytes: 109 CRLF line ends; normalised sha256 is 3e006f37... |

The mirrored files themselves were not in the handoff folder (`realdata/lunar/data/` held only
`sites_verified.json`), so there was nothing to delete. `realdata/lunar/MANIFEST.md` now opens with the
official addresses, sizes, hashes and the date, and says what is still mirrored or derived: the two
basemap JPEGs (not used by Slipday, not in the folder), `sites_verified.json` (not re-derived), and the
relayed single-point values in GROUND_TRUTH.md.

## 2. The 80 m grid and the rebuild

```
> py -I scripts\prepare_dem.py data\reference          (4 s)
ldem_80s_80m       231040128 bytes  LDEM_80S_80MPP_ADJ.TIF, LOLA south-pole 80 m mosaic, NASA GSFC PGDA product 90 ...
ldem_75s_240m       29062816 bytes  LDEM_75S_240M.JP2, PDS LRO-L-LOLA-4-GDR-V1.0 south-polar DEM to 75S ...
ldem_64_south       88473728 bytes  60S-90S crop (rows 9600 to 11519, no resampling) of NASA SVS CGI Moon Kit ldem_64_uint.tif
ldem_16             33177600 bytes  LDEM_16.IMG, PDS LRO-L-LOLA-4-GDR-V1.0 product LDEM_16; sha256 a511e40d7a3ea327
layer avgvis         1602884 bytes
```

| Array in `data/dem/` | sha256 before (as shipped from the build sandbox) | sha256 after the rebuild from official files |
|---|---|---|
| `ldem_80s_80m_f32.npy` (231,040,128 bytes) | not in the handoff folder (git-ignored) | `1c1e4ac62224f786ad67a01998e6c557309181c9f39770429ad3f16da37b1c34` |
| `ldem_75s_240m_i16.npy` | `671cc86563e516385595501a147a8e8c59d15a5dc596ba8b45865de3bb74007e` | the same |
| `ldem_64_south.npy` | `2b5a02c566b30c3aed617c3a1d738009053f3ef4e23cfeb4617db64f7afa1c89` | the same |
| `LDEM_16.IMG` | `a511e40d7a3ea3275945b4da2a1df377133264fab0be94b7434b1cf8907254cb` | the same |
| `avgvis_80s_480m_u8.npy` (map layer) | `5d98fa1884bc8544cf9fc35dd1da2b2e542dcf6db4a5c21b39f8d5e6f92e323c` | the same |

Because the 80 m array was absent, the folder as handed over ran on the 240 m fallback.

`dems.json` changed in one way: the provenance text of the 474 m grid no longer says "third-party-hosted
copy" and now records the hash of the source file. That text is part of the cache key, so the derived
files were rebuilt:

- Field: `py scripts\build_field.py --procs 10`, 812 s, 14,400 points, 0 without terrain.
  `py -I scripts\local_pass_tools\compare_field.py <old> data\field`: all 10,368,000 stored skyline values identical, sha256
  of `pole_el_i16.npy` `f3ef10c2a27d1f9ee4d1f3214d495502cb292c7bed9c93d1418f15050f2395bc` before and
  after. In `pole_points.npz` the longitudes differ at 1,000 points by at most 2.8e-14 degrees and the
  heights at 3 points by 6e-05 m (last-bit differences between the two machines' maths libraries).
- Skyline cache: the 172 files whose keys could no longer match were removed; `py scripts\warm_cache.py`
  and `py scripts\warm_cache.py --no-80m` rebuilt it. At the end of the pass the cache was emptied
  once more (the browser checks had added skylines for sites that are not part of the shipped set) and
  rebuilt with the same two commands: 554 skylines for the 80 m configuration (109 s) and 486 for the
  240 m one (33 s), 969 files, 8.6 MB. That is the default and replay sites with their scatter, ladder
  and landing-circle points.

## 3. Earth-visibility validation

### 3.1 What the label says

From `AVGVISIB_85S_060M_201608_EARTH.LBL` (the 120 m label differs only in resolution and grid name):

> This data product is a map of the average illumination by the Earth disc of the Lunar South Pole at a
> resolution of 60 m/pix by 60 m/pix, true at the pole in polar stereographic (spherical) projection. The
> calculations are based on the LOLA elevation map LDEM_85S_060M and are described in [MAZARICOETAL2011].
> The values are continuous between 0 (permanent shadow) and 1, and indicate the percentage of timesteps
> where each pixel was sunlit (by any fraction of the Earth disc).

So the map measures the share of time **any part of the Earth's disc** is above the terrain, at the
surface of the LOLA grid. The label names **no observer height** and **no time span** (its START_TIME and
STOP_TIME are the span of the LOLA data, 2009 to 2013). `SCALING_FACTOR = 0.00004`, `DERIVED_MAXIMUM =
25000`, `MAP_SCALE = 60 <m/pix>`, `LINE_PROJECTION_OFFSET = SAMPLE_PROJECTION_OFFSET = 2528.5`,
`CENTER_LONGITUDE = 0` (120 m map: 120, 3811.5).

The model side: observer at 0 m, the 80 m mosaic, one 18.6-year cycle from 2016-08-01 in 3-hour steps
(the settings of the Sun check; the time span is an assumption, since the label gives none), at the same
400 seeded points as the Sun check (200 within about 5 degrees of the pole for the 60 m map, 200 between
80 S and 85 S for the 120 m map), map read at the nearest pixel.

### 3.2 Result

```
> py scripts\validate_more.py data\reference --only e                       (0.1 s: stored model side)
> $env:PROCS = "8"; py scripts\validate_more.py data\reference --recompute  (39.7 s: model side recomputed here)
```

Both runs give the same mean absolute differences and correlations (the stored model side had been
computed in the build sandbox; five 95th-percentile and maximum figures moved by 0.01). Recomputed run:

| Map | Rule computed | Points | Published mean % | Computed mean % | Mean difference | Mean abs. difference | 95th pct | Max | Within 5 points | Correlation |
|---|---|---|---|---|---|---|---|---|---|---|
| 60 m, 85 S to the pole | **any part of the Earth (the map's rule)** | 200 | 25.74 | 26.61 | +0.87 | **0.97** | 5.12 | 18.38 | 94.5 % | **0.9946** |
| 60 m | Earth's centre | 200 | 25.74 | 22.22 | -3.52 | 3.89 | 8.91 | 14.61 | 66.5 % | 0.9873 |
| 60 m | whole disc | 200 | 25.74 | 18.16 | -7.58 | 7.65 | 17.90 | 22.10 | 34.5 % | 0.9662 |
| 60 m | mean visible fraction of the disc | 200 | 25.74 | 22.26 | -3.48 | 3.84 | 9.71 | 12.94 | 66.0 % | 0.9883 |
| 120 m, points 80 S to 85 S | **any part of the Earth (the map's rule)** | 200 | 30.45 | 30.30 | -0.16 | **0.69** | 4.24 | 15.47 | 96.5 % | **0.9984** |
| 120 m | Earth's centre | 200 | 30.45 | 26.37 | -4.09 | 4.11 | 11.19 | 21.61 | 63.0 % | 0.9922 |
| 120 m | whole disc | 200 | 30.45 | 22.54 | -7.91 | 7.91 | 19.31 | 26.96 | 38.5 % | 0.9806 |
| 120 m | mean visible fraction of the disc | 200 | 30.45 | 26.39 | -4.06 | 4.09 | 10.77 | 21.58 | 62.0 % | 0.9931 |

The row for the matching rule is the result, and it is also the best-fitting row on both maps, so the
tile's figure is the same either way. The tile now takes the rule from the label and says so ("Rule: any
part of the Earth's disc above the skyline, the rule the map's own label states"); it shows ±1.0 pts,
which is 0.97 to one decimal. For comparison the Sun check at the same points gives 0.80 (0.9916) and
0.76 (0.9949).

The mission card itself counts Earth contact by the Earth's centre. That is stricter than the map's rule
by about 4 points at these points (22.22 against 26.61, and 26.37 against 30.30), and it is the "Earth's
centre" rows, not the validated ones, that describe what the card reports.

### 3.3 Georeferencing controls

`py -I scripts\local_pass_tools\earth_controls.py .` (reads the maps through `slipday/refmaps.py`, repeats the comparison
with the map array flipped, transposed and shifted):

| Control | 60 m map: mean abs. difference, correlation | 120 m map |
|---|---|---|
| as read | 0.97, +0.9946 | 0.69, +0.9984 |
| flipped up-down | 28.40, -0.2454 | 46.04, -0.5054 |
| flipped left-right | 19.98, +0.3052 | 21.50, +0.5506 |
| transposed | 24.09, +0.0928 | 35.81, +0.0023 |
| rotated 180 degrees | 26.34, -0.1217 | 45.16, -0.5201 |
| shifted one pixel, four directions | 0.97 to 1.26, +0.9870 to +0.9933 | 1.08 to 1.79, +0.9843 to +0.9964 |

Mean Earth visibility of the half of the map towards the Earth (top rows, longitude 0) against the far
half: 0.333 against 0.165 (60 m map), 0.613 against 0.062 (120 m map). The reader places pixel (0, 0) at
x = -151,710 m, y = +151,710 m (60 m map), which is the label's offsets times the scale.

### 3.4 The same check on well-lit ridge pixels

The 400 points above are mostly ordinary, poorly lit ground. For the Sun, the agreement on the well-lit
ridge pixels where landers would go is much worse than on ordinary ground (4.02 points, correlation 0.61).
The same 60 seeded pixels (the 60 m Sun map above 60 %, seed 20261115) were therefore compared with the
60 m Earth map; this was added to `scripts/validate_more.py` as check f.

```
> $env:PROCS = "8"; py scripts\validate_more.py data\reference --only f        (5.9 s)
```

| Rule computed | Pixels | Published mean % | Computed mean % | Mean difference | Mean abs. difference | 95th pct | Max | Within 5 points | Correlation |
|---|---|---|---|---|---|---|---|---|---|
| **any part of the Earth (the map's rule)** | 60 | 52.82 | 52.59 | -0.24 | **1.57** | 6.21 | 10.05 | 91.7 % | **0.9707** |
| Earth's centre | 60 | 52.82 | 47.64 | -5.18 | 5.22 | 9.38 | 15.50 | 56.7 % | 0.9743 |
| whole disc | 60 | 52.82 | 42.64 | -10.18 | 10.18 | 15.73 | 21.74 | 1.7 % | 0.9714 |
| mean visible fraction of the disc | 60 | 52.82 | 47.63 | -5.19 | 5.24 | 9.33 | 15.60 | 56.7 % | 0.9741 |

So on ridge pixels the Earth side agrees to 1.57 points where the Sun side agrees to 4.02. The tile now
quotes this figure beside the others. On these pixels the centre rule the mission card uses reads about
5 points lower than the map's rule.

### 3.5 What this does and does not show

It shows that the skyline, the Earth's direction and the disc rule together reproduce the LOLA team's
Earth maps as closely as they reproduce the Sun maps on ordinary terrain, and more closely on well-lit
ridge pixels. It does not test the mission card's centre rule against anything, or the topography itself
(both sides are ray-cast from LOLA grids: 60 m and 120 m for the maps, 80 m here). The 240 m Earth map
was downloaded and not used. Nothing in the model was changed for these checks.

## 4. Stored validation re-run from the official maps

```
> py scripts\validate_terrain.py data\reference       (15:08:37 to 15:26:34, one process, machine busy)
> $env:PROCS = "8"; py scripts\validate_more.py data\reference --recompute       (39.7 s)
```

| Row | Stored before | Re-run here |
|---|---|---|
| 60 m Sun map, 80 m grid, 200 points | 0.80, correlation 0.9916 | 0.80, 0.9916 (mean difference +0.39, 95th pct 3.76) |
| 120 m Sun map, 80 m grid, 200 points | 0.76, 0.9949 | 0.76, 0.9949 (mean difference -0.45) |
| 60 m map on the 240 m / 474 m / 1.9 km grids / smooth sphere | | 1.37 / 2.42 / 6.19 / 33.2 |
| 120 m map on the 240 m / 474 m / 1.9 km grids / smooth sphere | | 0.86 / 2.26 / 6.08 / 20.92 |
| Ridge pixels above 60 % (60 seeded) | 4.0, mean -2.8, correlation 0.61, 68 % within 5 | 4.02, -2.78, 0.6085, 68.3 % |
| C1 at 2 m, 2017 to 2037: average illumination / any Sun / longest darkness | 88.01 / 92.06 / 198 h | 88.01 / 92.06 / 198 h |
| C1 within the 100 m scatter: any Sun | 72.5 to 92.5 % | 72.51 to 92.52 % |
| C1 at 0 m by first ray sample 80 / 40 / 20 / 10 m | 75.5 / 67.1 / 50.0 / 42.7 | 75.51 / 67.13 / 50.02 / 42.70 |
| Blocker of the 198 h dark run | 0.24 to 0.40 km | median 0.40 km, 10th to 90th percentile 0.24 to 0.40 km |

Also re-measured on the running server (`/api/stats?site=shackleton&start=2026-11-18&days=365&ladder=true&scatter_m=100`,
`/api/pairs`): any Sun 92.51 % at C1, 74.0 to 92.95 % within 100 m; longest darkness 194 h, 145 to 509 h
within 100 m; ladder 92.51 (80 m), 89.19 (240 m), 89.34 (474 m), 95.34 (1.9 km), 57.12 (smooth sphere);
Earth's centre in view 53.32 %, longest outage 321 h; C1 with the Shackleton rim: either lit 97.29 %,
longest joint darkness 39 h.

What limits the plan through a year (`py scripts\local_pass_tools\season.py .`: the mission card at C1,
default need, 365 landing dates from 18 Nov 2026): 62 clear-yes dates, 54 not sure, 249 no. Of the 303
that are not a clear yes, the stated point fails on the Earth alone on 177, on the Sun alone on 31, on
both on 49, and on 46 it passes while the scatter or the other grid disagrees. By month the clear-yes
dates are 8, 9, 6 (November to January), 0, 0, 0, 0, 0 (February to June), 1 (July), 9, 9, 10, 10 (August
to mid-November). The Sun fails only from February to July, on 1, 15, 21, 23, 18 and 2 dates; from August
to January each failure at the stated point is the Earth. The totals are the round-3 reviewer's exactly.
So "the slip margin is set by the Earth" is true from August to January, and from March to June the Sun
fails on half to three quarters of the dates.

`py scripts\local_pass_tools\verify_map.py .`: slip map for 18 Nov 2026, 733 of 14,400 points
coloured (5.09 %), largest margin 9 days, most good dates 26; the point with the most good dates
(89.4748 S, 137.5448 W) is 28 m from the maximum of the LOLA 60 m Sun map (0.8844 at 89.4749 S,
137.4431 W), the next best 0.71 km away.

## 5. Fixes

### 5.1 The 240 m fallback was overconfident

Change (`slipday/robust.py`, `effective_scatter_m`): the landing scatter is never smaller than one cell
of the grid under the site (80, 240, 474 or 1896 m). The card, the slip grid and the year table report
the radius used; the card adds a sentence when it was widened. `SLIPDAY_SKIP_DEMS=ldem_80s_80m` runs the
fallback without moving files. Measured with `py scripts\local_pass_tools\measure_cards.py . --scatter 100` (posts
`/api/mission` through the app's test client; default need, 60 days of slip), before any code change and
after:

| Site and landing | 80 m grid, 100 m scatter | 240 m fallback before | 240 m fallback after (scatter 240 m) |
|---|---|---|---|
| C1, 18 Nov 2026 | Yes 7; 20 yes, 6 not sure | Yes 7; 22 yes, 4 not sure | **Not sure** (9 of 13); 0 yes, 26 not sure |
| Malapert, Earth-facing shoulder | Not sure (12 of 13); 11 yes, 9 not sure | **Yes 7**; 15 yes, 4 not sure | Not sure (11 of 13); 11 yes, 10 not sure |
| Connecting ridge C2 | Not sure (9 of 13); 0 yes, 21 not sure | **Yes 8**; 21 yes, 0 not sure | Not sure (11 of 13); 7 yes, 14 not sure |
| Shackleton rim | Not sure (9 of 13); 0 yes, 24 not sure | Not sure (11 of 13); 9 yes, 15 not sure | Not sure (5 of 13); 0 yes, 24 not sure |
| IM-2, 6 Mar 2025 17:00, 240 h | Yes 2; 6 yes, 2 not sure | Yes 3; 7 yes, 1 not sure | Yes 2; 6 yes, 2 not sure |
| IM-1, 22 Feb 2024 23:00, 240 h | No | No | No |

The two sites the review named now agree with the 80 m grid. The price is the first row: on the fallback
the default example is "Not sure" with no clear-yes date in 60. That matches what the 80 m grid says at
a scatter of that size (next table), so it is the fallback being honest about a 100 m-wide crest, but a
deployment on the 240 m grid would open on "Not sure".

What a first visit to a fallback server looks like was checked in the browser
(`screenshots/desktop_1280x800_top_240m_fallback.png`, server started with
`SLIPDAY_SKIP_DEMS=ldem_80s_80m` on port 8102). At first it opened on a red "No" for today's date,
because the page only moved the plan forward when a clear-yes date existed. It now moves to the first
date that is not a clear no and says why: "Not sure, no clear-yes landing date in the 60 days checked",
17 Nov 2026, 6 of 13 points within 240 m pass, landing circles 49 % / 20 % / 10 % for 250 m, 500 m and
1 km, with the note "no date in the next 60 days is a clear yes on this elevation grid". The browser
check script is written for the 80 m configuration: against the fallback server it reported 20 pass and
4 fail (the three checks that expect a Yes with a margin and next good dates, and the five-grid ladder),
then stopped at a step that presses a next-good-date button the fallback does not have, so its last
check (console errors and failed requests) did not run there. The server's error log stayed empty.

### 5.2 The headline Yes assumes a 100 m scatter

The verdict line now ends "if it touches down within 100 m of the target" (the radius used), and the
card has a field `sure.assumes`. C1, 18 Nov 2026, default need, on the 80 m grid
(`py scripts\local_pass_tools\measure_cards.py . --scatter 100,150,200,250`):

| Scatter | Verdict | Points passing | Clear-yes / not-sure dates in 60 |
|---|---|---|---|
| 100 m | Yes, 7 days | 13 of 13 | 20 / 6 |
| 150 m | Not sure | 11 of 13 | 8 / 18 |
| 200 m | Not sure | 7 of 13 | 0 / 26 |
| 250 m | Not sure | 6 of 13 | 0 / 26 |

### 5.3 `MALLOC_ARENA_MAX=2`

In the README's run command, `run.sh`, `run.ps1`, `Procfile`, `render.yaml` and the Dockerfile; and
`slipday/load.py` calls `mallopt(M_ARENA_MAX, 2)` at import when the variable is missing, so a start
command cannot forget it. `/api/health` reports which is in force (`malloc_arena_limit`). Measured in
section 9.

### 5.4 Each replay its own need

`slipday/replay.py`. Sources were read through a web-fetch tool by a research step on 14 Nov 2026
(relayed text, not byte-exact):

| Replay | Sunlit need | Basis | Card on the 80 m configuration |
|---|---|---|---|
| IM-1 Odysseus, 22 Feb 2024 23:00 | 168 h | About seven days of surface operations: NASA's post-landing article says the instruments stopped seven days after landing, "meeting pre-launch projected mission operations"; the company's press kit says "roughly seven days" (seen only as a third-party transcript). NASA's CLPS press kit says "approx. 10 days". | **Yes, 1 day of margin**; 208 sunlit and 336 Earth hours; 9 yes, 2 not sure; smooth sphere 17 yes. With 240 h: No ("only 208 sunlit hours of the 240 needed"). |
| IM-2 Athena, 6 Mar 2025 17:00 | 240 h | NASA CLPS press kit: "Surface Operations: Approximately 10 days" | Yes, 2 days; 315 / 300 h; 6 yes, 2 not sure; smooth sphere 8 yes |
| Blue Ghost Mission 1, 2 Mar 2025 08:00 | 336 h | NASA CLPS press kit: "Surface operations: 14 days" | Yes, no slip margin; 336 / 336 h; 3 yes; 1.9 km grid, not validated; scatter 1896 m |
| Chandrayaan-3, 23 Aug 2023 12:00 | 240 h, illustrative | ISRO gives a mission life of "one lunar day (~14 Earth days)", a design life, not sunlit hours after touchdown. Taken literally (336 h): No, 283 sunlit hours in the window. | Yes, 1 day; 283 / 336 h; 9 yes; 474 m grid, not validated; scatter 474 m |

(`py scripts\local_pass_tools\measure_replays_final.py .`; on the 240 m fallback the four cards read the same: IM-1 Yes with
1 day, IM-2 Yes with 2, Blue Ghost Yes with no margin, Chandrayaan-3 Yes with 1.) The
100 hours of Earth contact are illustrative in every replay: no published requirement was found. The card
prints a note with the basis whenever the scenario on it is one of these landings, also when opened from
a link. The source addresses are in `slipday/replay.py`.

### 5.5 Storyboard

`scripts/storyboard.js` makes four frames instead of eight: the answer (with the landing circles), IM-1
with its own need, the validation tiles, the slip-margin map as the last frame. `demo/STORYBOARD.md` has
the captions and what each frame shows. The seven superseded frames were deleted after the new ones were
in place.

### 5.6 Smaller corrections

- The slip-grid note called the smooth sphere "the model most tools use"; it now says "a smooth sphere
  with no terrain, for comparison".
- The Earth tile reports the rule in the map's label, not the best-fitting rule (`scripts/validate_more.py`).
- A card with a margin of zero used to say "survives a slip of up to 0 days"; it says "no slip margin".
- `scripts/fetch_lola.sh` saved into a folder the instructions did not use; it now calls the one download
  script. `LOCAL_PASS.md` was rewritten around the commands that ran.
- Eight older tests assumed the 80 m grid and failed without it; they are skipped there with a reason.
- `scripts/warm_cache.py --no-80m` and `scripts/memory_check.py --no-80m` used symbolic links (not
  available to an ordinary Windows user); they use `SLIPDAY_SKIP_DEMS`.
- `.gitignore` no longer hides `fixtures/raw/`; `.dockerignore` keeps `data/reference/` and `.venv/` out
  of the image.
- `.gitattributes` asks git to store text with LF line ends, so that a commit made on Windows cannot
  give the shell scripts, the Dockerfile or the Procfile CRLF ends. It was written and not exercised: no
  git command was run in this pass. On disk the scripts and deploy files are LF. Four JSON files written
  by Python on this machine (`data/dem/dems.json`, `data/field/pole_field.json` and the two files in
  `data/validation/`) have CRLF line ends; that changes nothing for a JSON reader or for the cache keys.

## 6. Features

### 6.1 Landing circles (`/api/landing-circles`, under the mission card)

For circles of 100 m, 250 m, 500 m and 1 km around the target: the share of the circle's area in which
the plan meets the need, for each day of slip. Touchdown points on eight rings (50, 100, 150, 250, 375,
500, 750, 1000 m; 8, 8, 8, 12, 12, 12, 16, 16 points) plus the target, each ring weighted by the area of
the annulus it stands for, touchdown equally likely anywhere in the circle. Rings closer than half a
grid cell are left out and a circle smaller than one cell is reported as not resolvable. It is a count
on this elevation grid, not a dispersion model of any lander, and the page says so. The default and
replay sites load it by themselves (their skylines are in the shipped cache); any other site has a button.

`py scripts\local_pass_tools\measure_circles.py .` (posts `/api/landing-circles`; 80 m grid, 93 points):

| Site, landing, sunlit need | Within 100 m | 250 m | 500 m | 1 km | Days of slip with 90 % or more (100 m / 250 m / 500 m / 1 km) |
|---|---|---|---|---|---|
| C1, 18 Nov 2026, 240 h | 100 % | 62.1 % | 26.9 % | 12.9 % | 8 / none / none / none |
| Malapert shoulder, 18 Nov 2026, 240 h | 94.5 % | 76.2 % | 65.9 % | 61.0 % | 6 / none / none / none |
| Ridge C2, 18 Nov 2026, 240 h | 78.1 % | 51.5 % | 32.0 % | 20.3 % | none |
| IM-2, 6 Mar 2025 17:00, 240 h | 100 % | 100 % | 100 % | 95.6 % | 3 / 2 / 2 / 0 |
| IM-1, 22 Feb 2024 23:00, 168 h | 100 % | 100 % | 98.0 % | 88.4 % | 1 / 1 / 0 / none |

On the 240 m fallback (77 points): C1 not resolvable / 73.0 % / 30.0 % / 16.3 %; IM-2 not resolvable /
100 % / 100 % / 95.6 %. Chandrayaan-3 (474 m grid): 100 % within 500 m and 1 km. Blue Ghost (1.9 km
grid): no circle resolvable. Time for a site not in the cache: 43 to 50 s for 93 skylines while the
machine was rebuilding the field with ten processes, 6 to 11 s on the fallback; 0.15 to 0.19 s once the
skylines are stored.

### 6.2 Slip-robust site list (`/api/robust-sites`, button under the map)

The 12 map points with the largest single-point margin, at least 1 km apart, each re-checked with the
full mission card. `py -I scripts\local_pass_tools\call_robust.py http://127.0.0.1:8100` (default need, landing 18 Nov 2026,
60 dates): first call 42.8 s (180 skylines), second 0.24 s.

| Map point | With the scatter | Margin (days) | Map alone said | Clear-yes dates (not sure) | Points passing |
|---|---|---|---|---|---|
| 89.010 S, 122.764 E | Yes | 8 | 8 | 16 (0) | 13 of 13 |
| 89.475 S, 137.545 W (the connecting ridge) | Yes | 7 | 8 | 9 (17) | 13 of 13 |
| 89.060 S, 123.551 E | Yes | 4 | 8 | 5 (5) | 13 of 13 |
| 89.018 S, 92.406 W | Yes | 2 | 8 | 10 (12) | 13 of 13 |
| 89.413 S, 114.044 W | Yes | 2 | 8 | 5 (13) | 13 of 13 |
| 88.877 S, 122.407 E | Not sure | none | 8 | 11 (6) | 9 of 13 |
| 88.940 S, 120.353 E | Not sure | none | 8 | 7 (16) | 12 of 13 |
| 89.028 S, 124.634 E | Not sure | none | 8 | 7 (10) | 11 of 13 |
| 89.022 S, 126.773 E | Not sure | none | 8 | 7 (3) | 12 of 13 |
| 89.774 S, 56.889 E (the map's largest margin) | Not sure | none | 9 | 0 (22) | 11 of 13 |
| 89.893 S, 147.529 W | Not sure | none | 8 | 0 (24) | 12 of 13 |
| 89.298 S, 130.236 E | Not sure | none | 8 | 0 (23) | 7 of 13 |

5 of 12 stay a clear Yes. The list covers 12 candidates, not the whole map.

## 7. JPL Horizons

- Live cross-check, through the app's own endpoint with `SLIPDAY_HORIZONS=1`
  (`py scripts\local_pass_tools\horizons_live.py .` calls `/api/horizons/check`; this is what the page button does). First
  real requests this client has made; all four answered.

  | Site, span, step | Target | Rows | Largest elevation difference | Largest azimuth difference |
  |---|---|---|---|---|
  | C1, 18 to 28 Nov 2026, 6 h | Sun | 41 | 1.36e-05 deg | 3.9e-06 deg |
  | C1 | Earth | 41 | 1.16e-05 deg | 4.4e-06 deg |
  | IM-1 site, 22 Feb to 3 Mar 2024, 6 h | Sun | 41 | 1.06e-05 deg | 1.1e-06 deg |
  | IM-1 site | Earth | 41 | 1.05e-05 deg | 1.3e-06 deg |

- Stored fixtures: `py scripts\fetch_horizons_fixtures.py` downloaded the six tables;
  `py scripts\local_pass_tools\compare_fixtures.py .` found all 218 rows identical to the relayed fixtures, and the model
  within 1.26e-05 degrees in elevation and 1.27e-05 in azimuth of the direct tables. Each fixture header
  now carries a dated line saying so.

## 8. Tests

```
> py -m pytest -q -p no:cacheprovider -rs                                    (last run, 16:52)
152 passed, 1 warning in 124.49s                    80 m grid, field and data/reference in place

> (SLIPDAY_DEM_DIR = a copy of data/dem without the 80 m file; SLIPDAY_REALDATA_DIR = an empty folder)
130 passed, 22 skipped, 1 warning in 42.30s         what a fresh clone has (last run, 16:35)

> node scripts\ui_check.js http://127.0.0.1:8100/ <folder>          (NODE_PATH and CHROME set)
43 PASS, 0 FAIL, "ALL UI CHECKS PASSED"             last run 16:31; also against the Docker container
```

No test failed in the final state. 152 is 141 earlier tests plus 11 new ones in
`tests/test_local_pass.py`; TEST_REPORT.md lists what the new ones pin down. The 22 skips in the clone
state: 19 need the 80 m grid, 3 need the reference maps. The warning is a deprecation notice from the
test client library. Four browser checks were added (the scatter in the headline, the landing circles,
IM-1 with its own need, the slip-robust list), which takes the 39 of round 3 to 43, and one was changed:
the slip-grid rows now begin just under the first 800 px, so the tooltip check scrolls to them first.

## 9. Memory and Docker

`docker build -t slipday-local:pass .` succeeded (Docker Desktop, linux/amd64, Python 3.13-slim base);
the image is 1.33 GB because the 80 m grid was in `data/dem/`. Not pushed anywhere.

Load test: `py -I scripts\stress_check.py http://127.0.0.1:8101 --docker <container>` from the host
against a container started with a memory limit and two CPUs
(`docker run -d -m 512m --memory-swap 512m --cpuset-cpus 0,1 -p 127.0.0.1:8101:8000 ...`). Memory is read
inside the container: the cgroup's `memory.peak` and `oom_kill` count and `/proc/1/status` of the server.
The six runs were driven by `scripts\local_pass_tools\docker_mem.ps1`. Megabytes:

| Configuration | Arena limit | Requests | cgroup peak | Peak resident (VmHWM) | Own allocations at the end (RssAnon) | Kernel kills |
|---|---|---|---|---|---|---|
| 240 m (`SLIPDAY_SKIP_DEMS`), 512 MB | off (`MALLOC_ARENA_MAX=` and `SLIPDAY_ARENA_LIMIT=0`) | all answered up to the 12 cards at new points; then 4 of 24 dropped and every later request refused | 393 at the last reading | 527 at the last reading | 363 at the last reading | **container killed, `OOMKilled=true`, exit 137** |
| 240 m, 512 MB | in code (`MALLOC_ARENA_MAX=` empty) | all 205 answered 200 | 296 | 431 | 119 | 0 |
| 240 m, 512 MB | `MALLOC_ARENA_MAX=2` (image default) | all 205 answered 200 | 299 | 439 | 141 | 0 |
| 80 m, 1 GB | `MALLOC_ARENA_MAX=2` | all 205 answered 200 | 421 | 736 | 117 | 0 |
| 80 m, 768 MB | `MALLOC_ARENA_MAX=2` | all 205 answered 200 | 433 | 692 | 142 | 0 |
| **80 m, 512 MB** | `MALLOC_ARENA_MAX=2` | all 205 answered 200 | **431** | 691 | 117 | 0 |

The first four rows ran on the first image build (15:44), the last two on the build of 16:43, which
differs from the final one only in comments and documents.

**What the 80 m grid needs.** The validated 80 m configuration passed the whole load test inside a
512 MB memory limit, with the memory group peaking at 431 MB, 81 MB under the limit. Its peak resident
size is larger (691 to 736 MB) because that figure counts the memory-mapped grid files, which the kernel
can drop and does drop under a limit; the group figure is what a memory limit acts on, and it is the
same 421 to 433 MB at 512 MB, 768 MB and 1 GB. The peak comes in one phase, twelve mission cards at
never-seen points at once (the group's peak goes from about 210 to 431 MB); no other phase takes it
above about 210 MB. So 512 MB was enough here, without much to spare, and 768 MB or 1 GB leaves real
room.

These are Linux figures from containers on one machine (Docker Desktop, two CPUs), not from a hosting
provider: a provider's "512 MB" plan may count memory differently from a Docker memory group, and a host
with a fraction of a CPU was not tested. The load is this repository's script (the review's phases plus
the two new endpoints), not the reviewer's own. The round-3 review reported 392 MB peak resident for the
240 m configuration and 665 MB for the 80 m one with the variable set, and a kill without it; the kill
reproduced, and the resident figures here are somewhat higher. **No memory figure was taken on
Windows**: `MALLOC_ARENA_MAX` is a glibc setting and means nothing there.

The image was built six times as the files changed (15:44, 16:15, 16:24, 16:33, 16:43, 16:50). The
first build's memory-related code is the final code; later changes were card wording, the replay notes,
the page, the stored validation and, in the last build, comments. The second build (16:15) was
smoke-tested with
`docker run -d -m 1g -p 127.0.0.1:8101:8000 slipday-local:pass`: `/api/health` ok, terrain "LOLA,
80 m/px", arena limit "MALLOC_ARENA_MAX=2 (environment)"; `/api/mission` for C1 on 18 Nov 2026: Yes,
margin 7, scatter 100 m; `/api/landing-circles`: 100 / 62.1 / 26.9 / 12.9 %; the page answers HTTP 200.
The lighter sequence of the earlier rounds, inside that container
(`docker exec ... python scripts/memory_check.py --no-80m`, 240 m configuration, not memory-limited to
512 MB in this run): cold start 0.33 s at 61 MB, peak resident 293 MB, 261 MB at the end of which 96 MB
are the process's own allocations (the build sandbox measured 296 MB for this sequence). The last build
(16:50, id 6825a92dddd8, 1.33 GB) is from the final files and was run with the 80 m grid in a container
limited to 512 MB (`docker run -d -m 512m --memory-swap 512m -p 127.0.0.1:8101:8000 slipday-local:pass`):
`/api/health` ok with terrain "LOLA, 80 m/px" and "MALLOC_ARENA_MAX=2 (environment)", `/api/mission` for
C1 on 18 Nov 2026 Yes with margin 7 and scatter 100 m, and the browser checks run from the host against
that container passed 43 of 43 (first page load 6.8 s, phone 2.3 s) with the memory group peaking at
290 MB and no kernel kill. The builds of 16:33 and 16:43 had passed the same browser checks in 1 GB
containers. All test containers were removed (at 16:52 `docker ps -a` listed none named slipday) and the
image `slipday-local:pass` was left in place. At a last look at 16:55 the Docker engine no longer
answered from the shell ("failed to connect to the docker API"); nothing in this pass stopped it, and
the image's presence was not re-checked after that.

`scripts/fetch_grid80.py` (what `--build-arg GRID80=1` runs) was tested outside Docker with a real
download into a scratch folder: 189,158,392 bytes in 9 minutes, `hash ok`, and the array it wrote has the
sha256 of the installed one (1c1e4ac6...). After one long transfer from that server was cut during the
pass (section 1.2), the script was given a resume: a second test started from a seeded partial file of
150,000,000 bytes, continued with a Range request, and finished in 81 s with the same two hashes.

## 10. Timings on this machine

| What | Time |
|---|---|
| Page to network idle in headless Chrome, 1280x800 / 390x844 | 2.4 to 2.8 s warm; 9.5 to 10.6 s on the first visit after a server restart (the slip map for the date is worked out) |
| Slip map, new date / repeat | 5.75 s / 0.07 s |
| Mission card for a site with no stored skylines (15 skylines), through the test client | 1.2 to 2.2 s on the 240 m grid; 2.9 to 5.0 s on the 80 m grid while the field was being rebuilt; not timed warm |
| Landing circles, site not in the cache / in the cache | 43 to 50 s under load on the 80 m grid, 6 to 11 s on the fallback / 0.15 to 0.19 s |
| Slip-robust list, first call / repeat | 42.8 s / 0.24 s |
| `build_field.py --procs 10` | 812 s |
| `validate_terrain.py` | 18 minutes (one process, machine busy) |
| `validate_more.py --recompute`, 8 processes | 39.7 s |
| `warm_cache.py` / `--no-80m` | 101 to 110 s (554 skylines) / 36 to 45 s (486 skylines) |

## 11. What was not run

- No deployment to any public host; `render.yaml` and `Procfile` were written and not exercised.
- `docker build --build-arg GRID80=1` (the build that downloads the 80 m grid) was not run; the script it
  calls was tested separately (section 9).
- No memory measurement on Windows; no measurement on a host with a fraction of a CPU, and none on any
  hosting provider: the 512 MB result for the 80 m grid is a Docker container on this machine.
- The retry added to `fetch_on_your_machine.sh` for a cut transfer was not exercised by a real
  interruption (section 1.2). `.gitattributes` was not exercised: no git command was run.
- The page was not opened on a real phone or with a screen reader; only headless Chrome at two sizes, in
  light and dark.
- The 240 m Earth map was not used. The mission card's centre rule for the Earth was not checked against
  any reference (the maps use another rule).
- The 20 m mosaic was not downloaded. No north-polar grid.
- The planned surface durations were not checked against a second source by me; they came back from one
  research step that read the NASA and ISRO pages through a web-fetch tool.
- No video was recorded. The AI-use field in SUBMISSION_DRAFT.md is untouched.
- Nothing was committed, pushed, published or sent to anyone.

## 12. Where the handoff notes turned out different

- "The Earth-map file names are guesses": the names and the folder were right. What was wrong was the
  Sun-map folder at pgda.gsfc.nasa.gov, and the script could not see it fail because that server answers
  a wrong path with HTTP 200.
- The handoff folder had no 80 m array (it is git-ignored), so as delivered the app ran on the 240 m
  fallback, and in that state eight tests failed instead of skipping.
- The review's table gives IM-2 on the 240 m fallback as "Yes 2". Measured here before any change: Yes
  with a margin of 3 (7 yes, 1 not sure). After the fix it is Yes 2.
- `LOCAL_PASS.md` expected `validate_terrain.py` to take about 9 minutes; it took 18 here with the
  machine shared.
- The handoff expected the replay needs to wait for a teammate's research. Published plans for three of
  the four were found. For IM-1 two different figures were published (about seven days, and
  approximately ten); which one is used decides whether the card says Yes or No, and the card says so.
- The handoff's memory figures (392 MB and 665 MB peak resident with the variable) are lower than the
  431 to 439 MB and 691 to 736 MB measured here with a slightly longer load script. The kill without the
  variable reproduced.
- The handoff reads as if the 80 m grid cannot run on a 512 MB host ("a small free host would run the
  240 m grid"; "80 m peaks at 665 MB"). Measured here, it can: inside a 512 MB container the 80 m server
  answered the whole load test with the memory group peaking at 431 MB. The 665 MB (here 691 MB) is the
  resident size, which counts the memory-mapped grid files that the kernel drops under a limit. This was
  tested in Docker on one machine only, not on any hosting provider.

## 13. What a judge would still see that is wrong or weak

- There is no public link and no video yet.
- If the public link is deployed without the 80 m grid, the first screen opens on "Not sure" with no
  clear-yes date in 60 days, and a 100 m landing circle is "not resolvable". That is the honest answer of
  a 240 m grid, but it is a poor first impression and it is not what the storyboard shows. The link must
  serve the 80 m grid (431 MB of a 512 MB limit in the container test; 768 MB or 1 GB is safer).
- The slip-grid rows start just below the first 1280x800 screen (heading, controls and date axis are on
  it). The page is long: about 9,750 px on desktop and 20,600 px on a phone.
- The landing circles and the slip-robust list take tens of seconds the first time for a site or date
  that is not in the cache; on a small host that will be minutes.
- IM-1's "Yes" rests on the seven-day figure; NASA's own press kit says ten, which gives "No". The note
  under the card says this, in small type.
- Chandrayaan-3 and Blue Ghost are on coarse grids outside the validated area (tagged "not validated"),
  and their landing circles are partly or wholly "not resolvable".
- The terrain is still 80 m, and there is still no 3-D view.
- The Earth tile reads ±1.0 pts where the exact figure is 0.97; the table under it has the decimals.
- The validation panel is long and dense (five tiles, then a series of tables); a judge who does not
  scroll sees the tiles only.

## 14. Needs the participant

1. Choose a host and deploy with the 80 m grid in the image (the Dockerfile is the tested route; in the
   container test the 80 m grid needed 431 MB of a 512 MB limit, so 512 MB can work and 768 MB or 1 GB
   is safer). After deploying, check that the badge on the page says "80 m/px" and that the first
   screen reads "Yes ... 7 days" for 18 Nov 2026, then put the link in SUBMISSION_DRAFT.md. Nothing was
   published in this pass.
2. Write the AI-use disclosure in SUBMISSION_DRAFT.md.
3. Record the 30-second video from `demo/STORYBOARD.md` against a server on the 80 m grid, or build the
   seven slides from `demo/SLIDES.md`.
4. Decide whether to keep seven days for IM-1 or show the ten-day figure as the example; and if a
   teammate can confirm the planned durations from the original press kits, replace "relayed" in the notes.
5. Register the second team member; check the 2026 form's fields against the draft.
6. `data/reference/` (1.27 GB) is on disk for the reviewer. The local image `slipday-local:pass`
   (1.33 GB, id 6825a92dddd8) was left in Docker; Docker Desktop had stopped answering by 16:55 and may
   need starting again before it can be used or removed (`docker rmi slipday-local:pass`). `.venv/` is
   inside the entry folder and git-ignored.

## 15. Files changed in this pass

Code: `slipday/robust.py` (scatter widening, card wording, landing circles, slip-robust list),
`slipday/api.py` (two endpoints, health field), `slipday/replay.py`, `slipday/demstore.py`
(`SLIPDAY_SKIP_DEMS`), `slipday/load.py` (arena limit), `static/app.js`, `static/index.html`,
`static/style.css`. Scripts: `fetch_on_your_machine.sh`, `fetch_lola.sh`, `prepare_dem.py`,
`validate_more.py`, `warm_cache.py`, `memory_check.py`, `storyboard.js`, `ui_check.js`; new
`fetch_grid80.py`, `stress_check.py` and the folder `local_pass_tools/` (the measuring scripts behind
this file). Tests: new `tests/test_local_pass.py`; `test_round3.py`,
`test_round3_real.py`, `test_realdata.py` adjusted. Deploy: `Dockerfile`, new `.dockerignore`, `Procfile`,
`render.yaml`, `run.sh`, `run.ps1`; `.gitignore`. Data: `data/dem/` rebuilt (plus the 80 m array),
`data/field/` rebuilt, `data/horizon_cache/` rebuilt, `data/validation/*.json` re-run, `fixtures/*.csv`
headers, new `fixtures/raw/`, new `data/reference/`. Documents: this file, `README.md`, `LIMITATIONS.md`,
`SUBMISSION_DRAFT.md`, `LOCAL_PASS.md`, `DISCOVERIES.md`, `TEST_REPORT.md`, `REALDATA.md`,
`PRODUCT_PLAN.md`, `demo/STORYBOARD.md`, `demo/SLIDES.md`; `demo/*.png` and `screenshots/*.png` retaken
(18 screenshots, one of them the first screen on the 240 m fallback). Outside the entry:
`realdata/lunar/MANIFEST.md`, `GROUND_TRUTH.md` and `fetch_on_your_machine.sh` (dated notes).
