# Real data in Slipday (v2 results, with the round-3 corrections and additions)

**Local pass, 14 Nov 2026.** After this file was written, every LOLA file in section 1 was downloaded
again from its official host on a machine with direct access (pgda.gsfc.nasa.gov,
pds-geosciences.wustl.edu, imbrium.mit.edu, svs.gsfc.nasa.gov). All seven recorded sha256 values matched,
the 60 S to 90 S crop of the SVS grid and the working arrays came out byte-identical, the 14,400-skyline
field was rebuilt and is byte-identical, and `validate_terrain.py` and `validate_more.py` were re-run
against the official maps with the same headline rows. The LOLA Earth-visibility maps were downloaded for
the first time and the Earth check now has a result (0.97 and 0.69 points with the rule in the maps'
labels). So where this file says "byte-exactness rests on one recorded hash", "not independently
confirmed", "third-party-hosted copy" or "could not be fetched", read: confirmed against the official
download on 14 Nov 2026. Addresses, sizes, hashes and the new results are in LOCAL_PASS_RESULTS.md. The
rest of this file is the build sandbox's text, unchanged.

Measured on 2026-11-14 in the build sandbox. Everything in this file comes from files that were opened and
commands that were run; the commands are in TEST_REPORT.md. The scout's notes on where each file came from
and how it was checked are in `realdata/lunar/MANIFEST.md` and `GROUND_TRUTH.md` (not part of this folder).

## 1. Real files used

All are LRO Lunar Orbiter Laser Altimeter (LOLA) products, frame Moon Mean Earth / polar axis, heights in
metres above the 1737.4 km sphere. Credit: NASA/GSFC/MIT, LRO LOLA.

| File from the manifest | sha256 (first 16) | What it is | Exactness (scout's class) | How Slipday uses it |
|---|---|---|---|---|
| LDEM_80S_80MPP_ADJ.TIF | 82030dcbdd7c4bb0 | LOLA south-pole mosaic, 80 m, 80 S to the pole. NASA GSFC PGDA product 90 (Barker et al. 2023, PSJ 4, 183) | byte-exact copy of the NASA file | default terrain grid for polar sites; shaded-relief site map |
| LDEM_75S_240M.JP2 | a0ebbad0a2650c74 | PDS LOLA GDR south-polar DEM, 240 m, to 75 S | PDS file; byte-exactness rests on one recorded hash | terrain between 75 S and 80 S and beyond the edge of the 80 m grid; fallback when the 80 m file is absent |
| ldem_64_uint_south_60S_90S.npy | 2b5a02c566b30c3a | rows 60 S to 90 S of NASA SVS CGI Moon Kit `ldem_64_uint.tif` (LOLA), 474 m | derived by the scout (row crop, no resampling) from a byte-exact SVS file | terrain between 60 S and 75 S (Chandrayaan-3) and far field |
| LDEM_16.IMG | a511e40d7a3ea327 | PDS LOLA GDR global DEM, 16 px/deg (1.9 km) | byte-exact copy of the PDS product | coarse skyline everywhere else; far field |
| AVGVISIB_85S_060M_201608.TIF | ccf67d4f39e0a970 | LOLA team average Sun visibility, 60 m, 85 S to the pole (method of Mazarico et al. 2011) | NASA GeoTIFF of the PDS product; hash seen in unrelated repositories | reference for validation only |
| AVGVISIB_75S_120M_201608.TIF | d539467f16ccc5f5 | same product, 120 m, 75 S to the pole | genuine by content; byte-exactness not independently confirmed | reference for validation; "published average sunlight" map layer (4 x 4 mean, 480 m, display only) |
| AVGVISIB_65S_240M_201608_JP2.LBL | fc396d645e9c7919 | PDS label of the same product family | byte-exact | the definition of the map values ("sunlit by any fraction of the solar disc") |
| sites_verified.json | 8cb7f9d7250a47a2 | 52 sites with sources (LROC, NSSDCA, IAU gazetteer, papers) | coordinates from web pages are relayed via web fetch; IAU centres from the official shapefile | the curated site list in `slipday/sites.py` |

Where the copies came from: the NASA, PDS and SVS hosts were not reachable from the build sandbox, so the
data scout took untouched copies from public GitHub repositories and checked each against the published
product. The 80 m mosaic and both AVGVISIB GeoTIFFs came from another Space Apps 2026 team's repository
(k-shopnil/apolloharness, Git LFS; only NASA's own files were taken, none of that team's code or derived
data); the 240 m JP2 and the 240 m AVGVISIB label from adityatiwari-legend/Nakshastra-bitcoders; the 474 m
grid is a row crop of a copy of the SVS file in VeljkoS2/3D-Orbital-Physics-Engine; LDEM_16 from
andrmoel/astronomy-bundle-js. Hashes, commits and the evidence for each are in the scout's manifest. Before
submission the files should be fetched again from the official hosts and the hashes compared
(`scripts/fetch_on_your_machine.sh`, LOCAL_PASS.md).

Not used: `lroc_color_poles_*.jpg` (too coarse near the pole; the map is shaded relief made from the 80 m
grid instead) and `AVGVISIB_65S_240M_201608.JP2` (the two finer maps cover the validation).

`scripts/prepare_dem.py` turns the first four into memory-mappable arrays in `data/dem/` without changing a
value (the TIFF is re-saved as float32 .npy; the JPEG2000 is decoded to its int16 half-metres), and writes
`data/dem/dems.json`. Its output in this sandbox:

```
ldem_80s_80m       231040128 bytes  LDEM_80S_80MPP_ADJ.TIF, LOLA south-pole 80 m mosaic, NASA GSFC PGDA product 90 (Barker et al. 2023)...
ldem_75s_240m       29062816 bytes  LDEM_75S_240M.JP2, PDS LRO-L-LOLA-4-GDR-V1.0 south-polar DEM to 75S; JPEG2000 decoded...
ldem_64_south       88473728 bytes  60S-90S crop of NASA SVS CGI Moon Kit ldem_64_uint.tif (LOLA)...
ldem_16             33177600 bytes  LDEM_16.IMG, PDS LRO-L-LOLA-4-GDR-V1.0 product LDEM_16; sha256 a511e40d7a3ea327
layer avgvis         1602884 bytes
```

The georeferencing of LDEM_75S_240M.JP2 was not yet in the manifest when it was integrated, so it was
checked here: against the 80 m mosaic at 4000 random points south of 80.5 S the difference is 0.1 m mean,
3.0 m standard deviation; against the 474 m grid between 75.5 S and 79.8 S, 0.0 m mean, 12.9 m standard
deviation. The scout's later entry agrees (correlation 0.99997).

Spot heights read through Slipday's own loader equal the manifest's cross-check table to 0.1 m (Shackleton
floor -2788.4 m, connecting ridge 1948.8 m, Malapert summit 5172.5 m, IM-2 5321.5 m, LCROSS site
-3829.4 m, Chandrayaan-3 528.3 m on the 474 m grid, Apollo 11 -1921.6 m on LDEM_16). These are tests in
`tests/test_realdata.py`.

## 2. What is computed from them

For a site, `slipday/terrain.py` marches outward along 720 great-circle azimuths to 300 km, sampling the
finest grid that has data at each point, and takes the largest elevation angle along each ray using
spherical geometry (observer at radius R + ground height + mast height). The result is a 360-degree skyline.
The Sun is a disc; its visible fraction above the skyline is computed at every time step. The Earth is
judged at its centre. Sun and Earth directions come from JPL DE421, as in v1. One site takes 0.15 s for the
skyline and 0.01 s for a year of hourly statistics on this machine.

## 3. Results against the references

Produced by `python3 scripts/validate_terrain.py <folder with the LOLA reference maps>` (514 s), stored
in `data/validation/terrain_validation.json` and shown in the app. No model setting was adjusted to fit any
reference. Published single-point values reached this build through a web-fetch tool (not byte-exact); the
maps are real files.

Headline:

- Against the LOLA team's own maps of "share of time any part of the Sun is visible from the surface", at
  200 seeded random points per map, the 80 m terrain model differs by 0.80 points on average near the pole
  (correlation 0.992) and 0.76 points between 80 S and 85 S (correlation 0.995). The smooth sphere, which v1
  used, differs by 33.2 and 20.9 points and is uncorrelated with the maps (-0.39, -0.09).
  **This figure describes ordinary terrain.** The published mean at those points is 20 to 30 % and about a
  tenth of them are in permanent shadow. On well-lit ridge pixels, where a lander would be sent, the
  agreement is about 4 points with a correlation of 0.61 (section 5; the reviewer's independent sample gave
  4.3 points and 0.58). The reference maps were themselves ray-cast from LOLA topography, so the check
  validates the method, the georeferencing and the ephemeris, not the topography.
- Shackleton connecting ridge C1, 2 m above ground, 2017-2037 hourly: average illumination 88.0 %, solar
  visibility 92.1 %. Glaser et al. 2018 publish 88.0 % and 92.1 % from a 20 m DEM. **The match is not
  firm**: moving the point 20 m gives 86.4 to 88.3 % / 91.0 to 93.0 %, 40 m gives 83.7 to 88.2 % / 88.3 to
  92.7 %, and across the 13-point landing scatter at 100 m the range is 67.8 to 88.0 % / 72.5 to 92.5 %
  (section 5). The published point is the best pixel of its neighbourhood. Longest shadow: 198 h
  here against 112 h published; the blocking terrain is 0.2 to 0.4 km away, which an 80 m grid resolves
  poorly, and the figure moves between 118 and 292 h for 20 to 40 m shifts. At 10 m (Glaser et al. 2014, spot 4): 91.8 % / 95.7 % / 73 h here against
  91.9 % / 95.66 % / 76 h. The smooth sphere gives 55.6 % visibility at C1.
- Six of the nine published ridge-top points agree within 1.1 points of average illumination. The two 0 m
  rows among them rest on the near-field convention (first ray sample one grid spacing out): with the first
  sample at 40, 20 or 10 m the C1 0 m value falls from 75.5 to 67.1, 50.0 and 42.7 % (section 5). Three read
  low: connecting ridge C2 at 0 m (-5.5), a second Shackleton-rim point at 2 m (-9.9) and the Shackleton rim
  at 0 m (-24.7). The best-lit point within 160 m of the last two reaches 84.8 % and 75.7 %. This is the
  80 m grid failing to resolve a narrow crest, as expected; the published figures are from 20 m grids.
- The v1 review quoted the smooth sphere at 52 % sunlit with a 165-day dark run on the connecting ridge.
  Reproduced (51.97 % by the half-disc rule, 164.7 days). With terrain at the published C1 point for 2027:
  92.5 % with any Sun, 88.5 % by the half-disc rule, longest darkness 8.1 days.
- Resolution: at the same random points the mean difference from the published maps grows from 0.8 points
  (80 m) to 1.4 / 0.9 (240 m), 2.4 / 2.3 (474 m) and 6.2 / 6.1 (1.9 km). Coarser grids over-state light on
  average, because they smooth away nearby obstacles; Glaser et al. 2018 say the same of the 240 m model.
- Earth visibility could not be validated against a published number in v2; round 3 computed this build's
  side of a check against the LOLA team's Earth maps and waits for the files (section 5). It could not be validated (see the collapsed table below and
  LIMITATIONS.md). In the LOLA frame the model gives the Earth in view 51 % of 2027 from the connecting
  ridge with outages of 13 days, 80 % from the Malapert summit, and 100 % from a point 540 m towards the
  Earth from that summit. Bryant 2009 reports 55 to 64 % (half-disc rule) at near-pole ridge sites and
  100 % at Malapert on a radar DEM; the pattern is the same, the sites could not be matched.
- Hindcast with terrain: IM-1's predicted sunset moves from 79.2 h to 62.3 h after the reported power loss
  (the lander was tipped; terrain explains 17 of the 79 hours). Chandrayaan-3's moves from 13.6 h to 4.1 h
  after the sleep command (474 m grid). Blue Ghost is unchanged within 15 minutes (1.9 km grid).

The DEM used by the published single-point studies is 20 m (Glaser et al.); by the published maps, the LOLA
team's own 60 m and 120 m grids; here, 80 m with 240 m, 474 m and 1.9 km beyond its edge.

### Terrain model against the LOLA team's published average-sunlight maps (real data)

200 seeded random points per map. Published: share of time any part of the solar disc is visible from the surface (PDS LOLA GDR maps AVGVISIB_85S_060M_201608 and AVGVISIB_75S_120M_201608, LOLA team, method of Mazarico et al. 2011), read at the nearest map pixel. Computed: the same quantity from this app's ray-cast skyline, observer at 0 m, one 18.6-year cycle from 2016-08-01 in 3-hour steps. Differences are in percentage points. 'DEM used here' is the grid under the point (80 m: PGDA LDEM_80S_80MPP_ADJ; 240 m: PDS LDEM_75S_240M; 474 m: SVS ldem_64; 1.9 km: PDS LDEM_16), with coarser grids beyond its edge. The published maps were computed on the LOLA team's own 60 m and 120 m grids, so part of the difference is the DEM, not the method.

| Published map | DEM used here | Points | Published mean % | Computed mean % | Mean difference | Mean \|difference\| | 95th pct \|difference\| | Correlation | Same call on permanent shadow % |
|---|---|---|---|---|---|---|---|---|---|
| 60 m map, 85 S to the pole | 80 m | 200 | 20.01 | 20.39 | 0.39 | 0.8 | 3.76 | 0.9916 | 98.5 |
| 60 m map, 85 S to the pole | 240 m | 200 | 20.01 | 21.18 | 1.17 | 1.37 | 6.08 | 0.9786 | 97.5 |
| 60 m map, 85 S to the pole | 474 m | 200 | 20.01 | 22.26 | 2.26 | 2.42 | 11.16 | 0.9564 | 95.0 |
| 60 m map, 85 S to the pole | 1.9 km | 200 | 20.01 | 26.14 | 6.13 | 6.19 | 23.93 | 0.8616 | 92.5 |
| 60 m map, 85 S to the pole | smooth sphere | 200 | 20.01 | 53.2 | 33.2 | 33.2 | 55.17 | -0.3928 | 84.5 |
| 120 m map, 80 S to 85 S | 80 m | 200 | 30.14 | 29.68 | -0.45 | 0.76 | 2.97 | 0.9949 | 99.5 |
| 120 m map, 80 S to 85 S | 240 m | 200 | 30.14 | 30.68 | 0.54 | 0.86 | 3.73 | 0.9931 | 99.5 |
| 120 m map, 80 S to 85 S | 474 m | 200 | 30.14 | 32.14 | 2.0 | 2.26 | 8.0 | 0.9436 | 98.5 |
| 120 m map, 80 S to 85 S | 1.9 km | 200 | 30.14 | 36.13 | 6.0 | 6.08 | 25.37 | 0.8322 | 98.5 |
| 120 m map, 80 S to 85 S | smooth sphere | 200 | 30.14 | 51.06 | 20.92 | 20.92 | 49.02 | -0.0943 | 97.5 |

### Published ridge-top results at the stated coordinates and heights (real data, 80 m DEM here against 20 m DEMs there)

Each cell: average illumination % / solar visibility % (any part of the disc) / longest shadow. Computed with the 80 m LOLA mosaic from 2017-01-01 for 20 years in 1-hour steps, the period of Glaser et al. 2018. The published figures are each paper's best pixel on a 20 m DEM; an 80 m grid cannot place an observer on a crest a few tens of metres wide, so single points differ by several points either way. 'Best nearby' is the best-lit point on a 5 x 5 neighbourhood of 80 m steps around the published coordinates. Published values were read through a web-fetch tool (not byte-exact).

| Point | Lat, east lon | Height | Published | Computed at the point | Difference (avg / visibility, pts) | Computed, best nearby | Source |
|---|---|---|---|---|---|---|---|
| Connecting ridge C1 | -89.4505, 222.84 | 0 m | 76.0 / 81.3 / 268 h | 75.5 / 81.2 / 266 h | -0.5 / -0.1 | 75.5 / 81.2 / 266 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM |
| Connecting ridge C2 | -89.3157, 245.94 | 0 m | 75.6 / 80.6 / 166 h | 70.1 / 77.6 / 176 h | -5.5 / -3.0 | 70.1 / 77.6 / 176 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM |
| Shackleton rim S | -89.7849, 203.97 | 0 m | 81.0 / 85.5 / 221 h | 56.3 / 60.1 / 389 h | -24.7 / -25.4 | 75.7 / 80.9 / 266 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM |
| Connecting ridge C1 | -89.4398, 222.83 | 2 m | 88.0 / 92.1 / 112 h | 88.0 / 92.1 / 198 h | +0.0 / -0.0 | 88.0 / 92.1 / 198 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM |
| Connecting ridge C2 | -89.3130, 245.98 | 2 m | 78.1 / 82.0 / 165 h | 77.3 / 81.2 / 230 h | -0.8 / -0.8 | 77.9 / 81.9 / 166 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM |
| Shackleton rim S | -89.6866, 197.19 | 2 m | 85.5 / 89.4 / 66 h | 84.4 / 88.7 / 67 h | -1.1 / -0.7 | 84.4 / 88.7 / 67 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM |
| Shackleton rim S, second point | -89.7815, 204.70 | 2 m | 82.1 / 89.8 / 65 h | 72.2 / 78.3 / 363 h | -9.9 / -11.5 | 84.8 / 90.4 / 64 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM |
| Connecting ridge CR1 spot 2 | -89.4399, 222.85 | 2 m | 87.9 / 92.3 / 111 h | 87.9 / 92.2 / 199 h | +0.0 / -0.1 | 87.9 / 92.2 / 199 h | Glaser et al. 2014 EPSC2014-136 (20 m LOLA DTM |
| Connecting ridge CR1 spot 4 | -89.4544, 222.84 | 10 m | 91.9 / 95.7 / 76 h | 91.8 / 95.7 / 73 h | -0.1 / +0.0 | 91.8 / 95.7 / 73 h | Glaser et al. 2014 EPSC2014-136 (20 m LOLA DTM |

### Earth visibility: the one published per-site table found (Bryant 2009) could not be co-located, so it tests nothing

Shown so the gap is visible. Each cell: share of time with at least 0 % / 50 % / 100 % of the disc above the skyline, observer 2 m above ground. Published: Bryant 2009, JPL IPN PR 42-176, Goldstone radar DEM at 40 m, 2009-2028, daily steps. Computed here: LOLA 80 m mosaic, one 18.6-year cycle in 3-hour steps. Bryant's sites are illumination maxima on a radar DEM in a different frame. At the stated coordinates the LOLA terrain is off the crest (Sun 14 to 40 % against a published 77 to 95 %), and the best-lit point within 1.2 km on the LOLA grid (160 m search steps, chosen on sunlight only) still does not reach the published sunlight, so these are not the same places and the Earth columns cannot be compared. (Corrected 14 Nov 2026: the LOLA team's own Earth-visibility maps were downloaded in the local pass and are the Earth check now; see the Earth-visibility table in the validation panel and LOCAL_PASS_RESULTS.md section 3.) What is tested: the skyline (against the sunlight maps above, in every direction) and the direction of the Earth (against JPL Horizons). Published values were read through a web-fetch tool (not byte-exact).

| Site (Bryant 2009) | Stated lat, east lon | Published Earth | Computed Earth at stated point | Computed Earth at best-lit point nearby | Earth difference at 50 % (pts), not meaningful | Published Sun | Computed Sun at stated point | Computed Sun at best-lit point nearby | Distance moved |
|---|---|---|---|---|---|---|---|---|---|
| A1 Shackleton rim | -89.633, -160.388 | 62.2 / 55.3 / 48.4 | 0.0 / 0.0 / 0.0 | 20.8 / 10.4 / 0.0 | -44.9 | 93.5 / 90.4 / 86.3 | 15.7 / 14.4 / 12.9 | 59.0 / 55.7 / 52.5 | 1131 m |
| A2 Shackleton rim | -89.723, -153.925 | 63.9 / 57.0 / 50.1 | 34.9 / 29.2 / 21.7 | 39.8 / 35.0 / 29.6 | -22.0 | 93.0 / 89.5 / 84.8 | 25.7 / 23.1 / 20.7 | 72.2 / 67.4 / 61.8 | 816 m |
| B1 connecting ridge | -89.388, -137.810 | 65.2 / 58.2 / 51.3 | 0.0 / 0.0 / 0.0 | 28.6 / 22.2 / 13.4 | -36.0 | 97.0 / 94.8 / 91.7 | 31.5 / 30.4 / 29.2 | 66.2 / 64.4 / 62.8 | 716 m |
| C1 de Gerlache rim | -88.657, -70.688 | 71.0 / 64.0 / 57.1 | 0.0 / 0.0 / 0.0 | 3.6 / 0.0 / 0.0 | -64.0 | 90.0 / 87.0 / 83.1 | 41.2 / 39.5 / 37.5 | 48.6 / 47.1 / 45.7 | 1165 m |
| F peak near Shackleton | -88.813, 126.601 | 67.3 / 60.4 / 53.5 | 0.0 / 0.0 / 0.0 | 49.5 / 44.9 / 40.2 | -15.5 | 89.3 / 86.0 / 81.8 | 42.0 / 40.3 / 38.8 | 68.5 / 65.1 / 61.6 | 1131 m |
| Malapert alpha | -86.037, 1.704 | 100.0 / 100.0 / 94.7 | 35.9 / 30.7 / 24.7 | 55.8 / 51.2 / 46.7 | -48.8 | 82.1 / 78.4 / 74.5 | 42.0 / 39.1 / 35.9 | 69.3 / 63.5 / 57.6 | 1073 m |
| Leibnitz beta (Mons Mouton) | -84.722, 39.470 | 100.0 / 100.0 / 100.0 | 40.7 / 35.8 / 30.6 | 74.8 / 68.9 / 63.7 | -31.1 | 79.1 / 77.4 / 75.8 | 30.1 / 28.2 / 26.4 | 75.4 / 73.5 / 71.6 | 1012 m |

### How the answer changes with DEM resolution: calendar year 2027, observer 2 m above ground

Each site computed four times from real LOLA grids of different resolution, then on the smooth sphere. Hourly samples. 'Sunlit' uses the half-disc rule; darkness means no part of the Sun visible.

| Site | DEM at the site | Any Sun visible % | Sunlit % (half disc) | Longest darkness (d) | Longest light (d) | Earth in view % | Longest Earth outage (d) |
|---|---|---|---|---|---|---|---|
| Shackleton connecting ridge (C1) | 80 m | 92.51 | 88.49 | 8.1 | 169.0 | 51.11 | 13.3 |
|  | 240 m | 89.19 | 85.42 | 9.0 | 168.5 | 51.1 | 13.3 |
|  | 474 m | 89.34 | 86.84 | 7.1 | 139.6 | 51.11 | 13.3 |
|  | 1.9 km | 95.34 | 92.63 | 3.3 | 192.0 | 51.18 | 13.3 |
|  | smooth sphere | 57.12 | 51.97 | 137.3 | 139.3 | 45.18 | 15.0 |
| Shackleton rim (S) | 80 m | 88.88 | 85.01 | 2.8 | 117.7 | 45.92 | 14.7 |
|  | 240 m | 89.11 | 85.37 | 2.8 | 117.6 | 45.3 | 14.8 |
|  | 474 m | 85.7 | 81.66 | 3.6 | 117.4 | 43.14 | 15.4 |
|  | 1.9 km | 79.37 | 75.15 | 4.1 | 28.1 | 36.63 | 17.2 |
|  | smooth sphere | 56.14 | 53.53 | 160.1 | 160.0 | 45.65 | 14.9 |
| Connecting ridge (C2) | 80 m | 81.97 | 78.25 | 9.5 | 28.3 | 52.83 | 13.1 |
|  | 240 m | 82.67 | 78.88 | 6.8 | 28.3 | 52.81 | 13.1 |
|  | 474 m | 82.21 | 77.82 | 6.8 | 28.3 | 52.83 | 13.1 |
|  | 1.9 km | 81.82 | 78.49 | 7.0 | 28.0 | 52.84 | 13.1 |
|  | smooth sphere | 57.37 | 52.4 | 113.0 | 139.2 | 45.8 | 14.9 |
| Malapert massif summit | 80 m | 67.87 | 64.97 | 13.7 | 25.8 | 80.13 | 5.8 |
|  | 240 m | 69.7 | 64.47 | 14.5 | 111.7 | 76.24 | 6.8 |
|  | 474 m | 73.97 | 70.1 | 14.4 | 28.0 | 72.26 | 7.9 |
|  | 1.9 km | 80.07 | 77.12 | 10.9 | 28.3 | 100.0 | 0.0 |
|  | smooth sphere | 50.95 | 48.76 | 17.7 | 19.0 | 67.65 | 9.1 |
| Malapert massif, Earth-facing shoulder | 80 m | 57.99 | 56.44 | 14.2 | 19.6 | 100.0 | 0.0 |
|  | 240 m | 55.76 | 54.22 | 14.8 | 18.8 | 100.0 | 0.0 |
|  | 474 m | 59.71 | 58.25 | 13.5 | 19.8 | 100.0 | 0.0 |
|  | 1.9 km | 75.59 | 73.3 | 10.8 | 26.2 | 100.0 | 0.0 |
|  | smooth sphere | 50.96 | 48.76 | 17.8 | 19.0 | 67.75 | 9.1 |
| IM-2 Athena (Mons Mouton) | 80 m | 45.55 | 43.77 | 17.1 | 15.8 | 80.43 | 5.8 |
|  | 240 m | 45.7 | 43.92 | 17.1 | 15.8 | 80.5 | 5.7 |
|  | 474 m | 46.88 | 44.93 | 16.8 | 16.1 | 81.03 | 5.6 |
|  | 1.9 km | 47.58 | 45.75 | 18.0 | 16.9 | 81.97 | 5.4 |
|  | smooth sphere | 50.23 | 48.62 | 17.0 | 18.0 | 71.92 | 8.0 |
| Mons Mouton (VIPER area) | 80 m | 32.08 | 29.43 | 22.9 | 12.4 | 56.15 | 12.2 |
|  | 240 m | 32.57 | 29.81 | 22.6 | 12.5 | 56.45 | 12.1 |
|  | 474 m | 32.83 | 30.23 | 22.2 | 12.0 | 56.77 | 12.0 |
|  | 1.9 km | 39.49 | 37.79 | 20.0 | 14.3 | 60.17 | 11.1 |
|  | smooth sphere | 50.18 | 48.63 | 16.9 | 17.9 | 72.57 | 7.8 |
| IM-1 Odysseus (Malapert A) | 80 m | 38.72 | 38.07 | 18.8 | 12.9 | 100.0 | 0.0 |
|  | 240 m | 38.6 | 37.93 | 18.8 | 12.8 | 100.0 | 0.0 |
|  | 474 m | 40.81 | 40.18 | 18.2 | 13.5 | 100.0 | 0.0 |
|  | 1.9 km | 45.17 | 44.49 | 17.0 | 14.9 | 100.0 | 0.0 |
|  | smooth sphere | 49.49 | 48.63 | 15.9 | 16.5 | 100.0 | 0.0 |
| Haworth (crater centre) | 80 m | 0.0 | 0.0 | 365.0 | 0.0 | 0.0 | 365.0 |
|  | 240 m | 0.0 | 0.0 | 365.0 | 0.0 | 0.0 | 365.0 |
|  | 474 m | 0.0 | 0.0 | 365.0 | 0.0 | 0.0 | 365.0 |
|  | 1.9 km | 0.0 | 0.0 | 365.0 | 0.0 | 0.4 | 206.5 |
|  | smooth sphere | 52.77 | 49.03 | 19.6 | 21.8 | 59.58 | 11.2 |
| Nobile (crater centre) | 80 m | 35.46 | 34.45 | 21.2 | 12.1 | 20.76 | 21.7 |
|  | 240 m | 35.51 | 34.52 | 21.1 | 12.2 | 20.87 | 21.6 |
|  | 474 m | 35.65 | 34.54 | 21.1 | 12.2 | 21.07 | 21.6 |
|  | 1.9 km | 36.2 | 35.02 | 21.0 | 12.3 | 22.44 | 21.2 |
|  | smooth sphere | 50.88 | 49.01 | 17.2 | 18.4 | 61.87 | 10.6 |
| de Gerlache (crater centre) | 80 m | 0.0 | 0.0 | 365.0 | 0.0 | 0.0 | 365.0 |
|  | 240 m | 0.0 | 0.0 | 365.0 | 0.0 | 0.0 | 365.0 |
|  | 474 m | 0.0 | 0.0 | 365.0 | 0.0 | 0.0 | 365.0 |
|  | 1.9 km | 0.0 | 0.0 | 365.0 | 0.0 | 0.0 | 365.0 |
|  | smooth sphere | 59.78 | 51.03 | 23.9 | 85.5 | 47.35 | 14.5 |
| Shackleton crater floor (always dark) | 80 m | 0.0 | 0.0 | 365.0 | 0.0 | 0.0 | 365.0 |
|  | 240 m | 0.0 | 0.0 | 365.0 | 0.0 | 0.0 | 365.0 |
|  | 474 m | 0.0 | 0.0 | 365.0 | 0.0 | 0.0 | 365.0 |
|  | 1.9 km | 0.0 | 0.0 | 365.0 | 0.0 | 0.0 | 365.0 |
|  | smooth sphere | 56.02 | 54.58 | 160.5 | 156.0 | 46.1 | 14.8 |
| LCROSS impact, Cabeus (always dark) | 80 m | 0.0 | 0.0 | 365.0 | 0.0 | 15.08 | 23.9 |
|  | 240 m | 0.0 | 0.0 | 365.0 | 0.0 | 15.15 | 23.8 |
|  | 474 m | 0.0 | 0.0 | 365.0 | 0.0 | 15.37 | 23.8 |
|  | 1.9 km | 0.0 | 0.0 | 365.0 | 0.0 | 16.77 | 23.1 |
|  | smooth sphere | 51.39 | 49.78 | 17.0 | 17.9 | 63.82 | 10.1 |

## 4. What remains simulated, relayed or unverified

- Nothing shown in the app is simulated when the real grids are installed. The synthetic DEM
  (`slipday.dem.synthetic_south_pole_fixture`) exists only for tests and for running without data
  (`SLIPDAY_SYNTHETIC_DEM=1`); every label, badge and CSV header then says SYNTHETIC.
- Relayed via web fetch, not byte-exact: the JPL Horizons reference tables in `fixtures/`, the published
  values from Glaser et al. and Bryant, the LROC and NSSDCA site coordinates, the mission event times in the
  hindcast.
- Derived by this project for display only: the 480 m average-sunlight map layer (4 x 4 mean of
  AVGVISIB_75S_120M) and the shaded-relief picture (hill shading of the 80 m grid).
- Chosen by this project, not published anywhere: the "Malapert massif, Earth-facing shoulder" site.
- Unverified: Earth visibility against any published per-site number; anything at the north pole (no fine
  grid); the live Horizons cross-check; deployment.

## 5. Round 3: corrections, the "how sure" ensemble, the slip map

Produced by `python3 scripts/validate_more.py <folder with the LOLA reference maps>` (89.5 s on two
cores; stored in `data/validation/more_validation.json`, merged into the tiles and tables the app shows) and
by the running app. All on the real LOLA grids; nothing here is simulated.

### Well-lit ridge pixels (real data)

The 60 m LOLA map rates 1,612 pixels (0.0063 % of the map) above 60 % sunlit. A seeded sample of 60 of them
(seed 20261115), computed exactly as the 400-point check (0 m, any part of the disc, one 18.6-year cycle in
3-hour steps):

| Pixels | Published mean % | Computed mean % | Mean difference | Mean abs. difference | 95th pct | Largest | Within 5 points | Correlation |
|---|---|---|---|---|---|---|---|---|
| 60 | 63.95 | 61.17 | -2.78 | 4.02 | 10.05 | 18.1 | 68.3 % | 0.61 |

Selecting on a high published value pulls the computed mean down by itself, so part of the -2.8 is
selection; the scatter is real. The reviewer's independent sample of 60 gave 4.3 / -3.3 / 0.58.

### How firm the C1 match is (real data; 2017-01-01, 7,305 days, hourly, as in the ridge-top table)

| Variant | Average illumination % | Any Sun visible % | Longest darkness (h) |
|---|---|---|---|
| published (Glaser et al. 2018, 20 m DEM; relayed via web fetch) | 88.0 | 92.1 | 112 |
| this build at the stated point, 2 m, first sample 80 m | 88.01 | 92.06 | 198 |
| moved 20 m (8 directions) | 86.42 to 88.26 | 90.98 to 93.00 | 118 to 221 |
| moved 40 m (8 directions) | 83.65 to 88.19 | 88.26 to 92.66 | 145 to 292 |
| the app's landing scatter: 12 points at 50 and 100 m | 67.79 to 86.37 | 72.51 to 92.52 | 147 to 509 |
| observer at 1.5 m / 2.5 m / 3 m | 86.05 / 89.30 / 90.19 | 90.85 / 93.26 / 93.66 | 227 / 137 / 108 |
| first ray sample at 40 m / 20 m | 87.16 / 86.89 | 91.74 / 91.52 | 198 / 209 |

### Ground-level crest values and the near-field convention (real data)

Average illumination, 0 m observer, against the distance of the first ray sample:

| Point | Published % | 80 m (the app) | 40 m | 20 m | 10 m |
|---|---|---|---|---|---|
| Connecting ridge C1, 0 m | 76.0 | 75.51 | 67.13 | 50.02 | 42.70 |
| Connecting ridge C2, 0 m | 75.6 | 70.07 | 60.54 | 44.92 | 44.28 |

The convention is now named in the code and reported with every skyline (`first_sample_m`): one spacing of
the grid under the site, node to node, as the LOLA team's maps are computed. A grid holds no information
about ground nearer than its spacing, so sampling the interpolated surface more closely measures the
interpolation. It is a convention, not a converged result: 0 m values on crests are not offered on the
page, the API attaches a warning to any request below 1 m, and the half-spacing variant is one member of
the "how sure" check on every verdict. At random (non-crest) points the convention does not matter (the
reviewer measured 0.84 against 0.87 points).

### What sets the longest darkness at C1 (real data)

The longest dark run (198 h, 2030-03-09 21:00 to 2030-03-18 02:00 UTC): the terrain that sets the skyline
under the Sun is at a median distance of 0.40 km (10th to 90th percentile 0.24 to 0.40 km; 90.9 % of the
hours are blocked from under 1 km), with the Sun's upper limb a median 0.35 degrees below it. The ten
longest dark runs are 195 to 198 h, so it is a recurring graze past nearby ground, not one event. The v2
text that attributed it to far-away terrain was wrong and has been removed.

### Earth visibility: this build's side, waiting for the reference (needs official data download)

At the same 400 seeded points as the Sun check, 0 m, one 18.6-year cycle in 3-hour steps:

| Region | Points | Earth's centre in view % | Any part of the Earth % | Whole Earth % | Never see the Earth | Any Sun (same points) % |
|---|---|---|---|---|---|---|
| 85 S to the pole | 200 | 22.22 | 26.61 | 18.16 | 26.5 % of points | 20.39 |
| 80 S to 85 S | 200 | 26.37 | 30.30 | 22.54 | 33.5 % of points | 29.68 |

The last column equals the "computed mean" of the Sun check (20.39 and 29.68), which confirms the points
are the same. The LOLA team's Earth maps (`AVGVISIB_*_201608_EARTH`) are not in the sandbox. The readers
for them are tested on the real Sun products in all three containers (GeoTIFF; JPEG2000 with its PDS label;
the same samples written back as the raw `.IMG` that label describes). When the files are present,
`scripts/validate_more.py <folder> --only e` compares all three rules, reports which one the map's own
label describes, and replaces the "needs official data download" tile.

### The "how sure" ensemble on real sites (model output)

| Site, 365 days from 2026-11-18, 2 m | Stated point | Range over 13 points within 100 m | 240 m grid | First sample 40 m |
|---|---|---|---|---|
| C1: any part of the Sun visible % | 92.51 | 74.00 to 92.95 | 89.19 | 92.45 |
| C1: sunlit, half-disc rule % | 88.49 | 69.36 to 88.49 | 85.42 | 87.69 |
| C1: longest darkness (h) | 194 | 145 to 509 | 215 | 194 |
| C1: Earth in view % | 53.32 | 49.74 to 53.36 | 53.31 | 53.32 |

Mission card, need 240 sunlit hours and 100 hours of Earth contact in 14 days, landing in sunlight with the
Earth in view (model output; the need is illustrative):

| Site and planned landing | Verdict | Slip margin | Planned date: sunlit / Earth h | Good dates of 60 (terrain; smooth sphere) | Next good date |
|---|---|---|---|---|---|
| C1, 2026-11-18 00:00 | Yes | 7 days | 336 / 295 | 20 yes, 6 not sure; 20 | 15 Dec 2026 |
| Malapert Earth-facing shoulder, 2026-11-18 | Not sure | none | 336 (323 to 336) / 336 | 11 yes, 9 not sure; 16 | 19 Nov 2026 |
| IM-2 Athena site, 2026-11-18 | Yes | 2 days | 309 (290 to 310) | 9 yes, 2 not sure; 15 | 16 Dec 2026 |
| IM-1 Odysseus site, 2026-11-18 | No | none | 305 (292 to 311) | 4 yes, 2 not sure; 13 | 20 Nov 2026 |
| IM-2 Athena, real landing hour 2025-03-06 17:00 | Yes | 2 days (day 3: 12 of 13 points pass) | 315 / 300 | 6 yes, 2 not sure; 8 | 5 Apr 2025 |
| IM-1 Odysseus, real landing hour 2024-02-22 23:00 | No (208 sunlit hours of 240) | none | 208 / 336 | | 20 Mar 2024 |
| Chandrayaan-3, 2023-08-23 12:00 (474 m grid, not validated) | Yes | 1 day | 283 / 336 | | 20 Sep 2023 |
| Blue Ghost 1, 2025-03-02 08:00 (1.9 km grid, not validated) | Yes | 4 days | 336 / 336 | | 1 Apr 2025 |

Landing times are the real ones snapped down to the hour (sources in `slipday/replay.py`; relayed via web
fetch). Away from the pole each day of slip costs 24 sunlit hours, because the lunar day does not move;
on the connecting ridge the Sun is up through the whole window and the margin is set by the Earth.

### The slip map (model output from real terrain)

`scripts/build_field.py`: 14,400 skylines (120 x 120 points, 500 m apart, 30 km either side of the pole,
2 m observer, the same ray-march as a single site) in 1,383 s on two cores, 21 MB. For the 60 landing dates
from 2026-11-18 and the need above: 5.1 % of the mapped points meet the need on the planned date; the
largest slip margin is 9 days; the point with the most good dates (26 of 60) is at 89.4748 S, 137.545 W, on
the connecting ridge, 28 m from the maximum of the LOLA 60 m illumination map (89.4749 S, 222.557 E, as
located by the reviewer). Four
points keep 240 sunlit hours on every one of the 60 dates. A test checks that the map value at a point
equals the mission card computed for that point (`tests/test_round3_real.py`).

### Two sites as one power system (model output; 365 days from 2026-11-18, any part of the disc)

| Pair | Apart | At least one has Sun | Each alone | Longest time both dark | Each alone |
|---|---|---|---|---|---|
| C1 + Shackleton rim S | 9.4 km | 97.29 % | 92.51 / 88.95 % | 39 h | 194 h / 66 h |
| C1 + C2 | 8.5 km | 94.37 % | 92.51 / 82.02 % | 172 h | 194 h / 227 h |
| Shackleton rim S + C2 | 16.2 km | 97.52 % | 88.95 / 82.02 % | 31 h | 66 h / 227 h |

No published figure was available to check these against; longest darkness carries the caveat above.

