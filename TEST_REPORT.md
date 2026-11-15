# Test report (local pass first; round 3 and the v2 report kept below)

## Fourth local pass (2026-11-15)

Counts and commands: LOCAL_PASS_2_RESULTS.md, "Pass 4". With everything installed: **258 passed**; as a fresh clone: **210 passed, 48 skipped**; browser checks **74 of 74**. New: `tests/test_pass4.py` (run-length code, ride-through
hours of the opening example, the check against the existing longest-darkness figure at C1, the night map
layer, the naming rule R7, the year ribbon with and without the station rule, the corrected documents, the page
pieces, the 20 m mark for 14 dates) and 4 browser checks (the ride-through line and chart, the link-margin note,
the night layer, the 3-D time label while playing). Two pass-3 tests that encoded "inside Malapert" were
changed to the corrected naming (rule R7); no test was removed.

## Third local pass (2026-11-15)

With everything installed: **248 passed, 0 failed** (205 s). As a fresh clone has it (no 80 m grid, no
reference maps): **205 passed, 43 skipped**. Browser checks (`scripts/ui_check.js`): **70 pass, 0 fail**
(65 earlier ones unchanged, 5 new: the Earth margin on the card, a skyline chart of at least 130 px with
no overlapping labels, the station panel, the shadow-site list, the 3-D view playing). 41 new tests:
`tests/test_stations.py` (26: station coordinates and mask as cited, geometry against six JPL Horizons
tables) and `tests/test_pass3.py` (15: the Earth-mask sweep, the shadow-site rule and counts, the
permanent-shadow cut, the observer-height refusal, station contact for the opening example and that the
rule leaves its verdict unchanged but is live, crediting to the highest complex, gazetteer containment,
the named ground that ends the margin, the opening map kept in memory, the 20 m map mark and its scenario
check, the station rule leaving the default map unchanged, the page's new controls). No existing test was
weakened or removed.

## Second local pass (2026-11-14, late)

Current counts, with commands: LOCAL_PASS_2_RESULTS.md, section "Tests". With everything installed
(80 m grid, skyline field, scatter skylines, data/reference, the optional 20 m crop): 207 passed, 0
failed; as a fresh clone has it (no 80 m grid, no reference maps): 170 passed, 37 skipped. Browser
checks: 65 pass, 0 fail. The 55 new tests are in `tests/test_pass2.py` (two request
lanes, why it flips, lander classes and sampling ranges, year ribbon, the scatter-checked map against the
mission card, permanent shadow, the 20 m note), `tests/test_view3d.py` (the 3-D view) and
`tests/test_pass2_text.py` (validation panel, document rules, the lunar against terrestrial view). No
existing test was changed. The sections below are the first local pass and earlier rounds, unchanged.

## Local pass (2026-11-14, Windows 11 laptop, 24 cores, Python 3.12.11 in a virtual environment, Chrome)

Full detail, with the command behind every number: LOCAL_PASS_RESULTS.md. Summary of the tests:

```
> .venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -rs
152 passed, 1 warning in 124.49s          everything installed (80 m grid, field, data/reference)

> the same with SLIPDAY_DEM_DIR pointing at a copy of data/dem without the 80 m file, and
  SLIPDAY_REALDATA_DIR at an empty folder (what a fresh clone has)
130 passed, 22 skipped, 1 warning in 42.30s

tests/test_geometry.py      14      tests/test_realdata.py      21   REAL LOLA grids
tests/test_horizons.py      16      tests/test_round3.py        22
tests/test_hindcast.py       7      tests/test_round3_real.py   11   REAL LOLA grids
tests/test_metrics_api.py   12      tests/test_local_pass.py    11   new, REAL LOLA grids
tests/test_regressions.py    9      tests/test_terrain.py       21   SYNTHETIC analytic surfaces
                                    tests/test_terrain_api.py    8   SYNTHETIC test DEM

> node scripts\ui_check.js http://127.0.0.1:8100/ <folder>      (headless Chrome, 1280x800 and 390x844)
43 PASS, 0 FAIL: ALL UI CHECKS PASSED
```

The one warning is a deprecation notice from the test client library. When the fresh-clone state was
first run on this machine, eight older tests that state 80 m figures (labels, hours, the ladder) failed;
they are now skipped there with the reason given. What the eleven new tests pin down on the real grids:

- On the 240 m fallback the landing scatter is widened from 100 m to 240 m and the card says so; the two
  ridge sites the round-3 review named (Malapert shoulder, ridge C2) read "not sure", not "yes".
- On the 80 m grid the scatter is not widened; C1 on 18 Nov 2026 is Yes with 7 days (8 for the stated
  point alone), "not sure" at a 150 m scatter; a 50 m request is computed at 80 m, one cell.
- IM-1 with its own need (168 h) is Yes with 1 day of margin, 208 sunlit and 336 Earth-contact hours, and
  No with 240 h; the other three replays are Yes; Blue Ghost's 336 h plan has no slip margin, its scatter
  is one 1896 m cell, and every landing circle there is reported as not resolvable.
- Landing circles on the 80 m grid: 93 touchdown points, 17 / 37 / 61 / 93 per circle, shares between 0
  and 100, the 100 m share above the 1 km share at C1; all-pass and none-pass sites read 100 and 0; on the
  fallback the 100 m circle is not resolvable; unknown site 404, unreadable date 422.
- Slip-robust list: each row's verdict and margin equal the mission card at that point, and the margin
  with the scatter never exceeds the map's single-point margin.
- The Earth tile in the stored validation names the rule in the map's label, the rows marked as the
  map's rule are the "any part" rows, and the ridge-pixel figure is on the tile as well as in the table.
- `/api/health` reports which malloc-arena limit is in force.

Not covered by a test: the Dockerfile and the container load test (run by hand, results in the README),
the download scripts (run by hand), the live Horizons request.

# Round 3 report

Section 0 is new in round 3. Sections 1 to 6 are the v2 report, corrected where the review found a claim
too strong; numbers there were measured in v2 and still hold unless section 0 or the local pass above says
otherwise.

## 0. Round 3 (2026-11-14, same sandbox: 2 cores, Python 3.13, headless Chrome)

### Tests

```
$ python3 -m pytest -q
141 passed in 60.50s        (131 s when the shared machine was busy)

tests/test_geometry.py      14 passed
tests/test_horizons.py      16 passed
tests/test_hindcast.py       7 passed
tests/test_metrics_api.py   12 passed
tests/test_regressions.py    9 passed
tests/test_terrain.py       21 passed   SYNTHETIC analytic surfaces
tests/test_terrain_api.py    8 passed   SYNTHETIC test DEM
tests/test_realdata.py      21 passed   REAL LOLA grids
tests/test_round3.py        22 passed   new: mission-card logic, slip-map statistics, long spans in blocks,
                                        reference-map readers on the real Sun maps, memory guard, stated claims
tests/test_round3_real.py   11 passed   new, REAL LOLA grids: landing-scatter band, mission card pinned to the
                                        IM-2 landing, slip map against the mission card, ladder, pairs
```

What the new tests pin down on real data:

- The vectorised slip-map evaluator returns the same Sun-up and Earth-up flags as the single-site code at
  five polar sites, three rule sets, 1,753 hourly samples each: 0 mismatches.
- For three map points (the largest slip margin, the most good dates, a corner) the map's slip margin,
  number of good dates and worst-date sunlit hours equal the mission card computed for that point.
- IM-2 Athena at its real landing hour: Yes, margin 2 days, 315 sunlit and 300 Earth-contact hours; day 3
  is "not sure" with 12 of 13 points passing.
- Every "yes" day has all 13 points, the 240 m grid and the near-field variant passing; every "not sure"
  day states which members disagree.
- The scatter band encloses the stated point; C1's year figure for any Sun (92.51 %) equals the reviewer's.
- Long-span statistics computed in blocks equal the single-block result exactly.
- The reference-map readers reproduce the scout's values from the real GeoTIFF (0.769 at CR1), from the
  real JPEG2000 with its PDS label (0.9348 at the Mazarico site), and from the same samples written back
  as the raw `.IMG` that label describes; a point outside a map is refused, not wrapped.
- The corrected claims do not reappear in the documents, and the stored validation carries the ridge-pixel
  tile, the C1 sensitivity and the Earth-check status.

### Browser checks

```
$ NODE_PATH=/opt/npm-tools/node_modules node scripts/ui_check.js http://127.0.0.1:8100/ /tmp/slipday_shots
desktop load to network idle: 3725 ms      (10490 ms on a freshly started server on a busy machine: the first
                                              visit of a day computes the slip map once)
PASS the mission card is the first panel
PASS the verdict is on the first 1280x800 screen without scrolling  [Yes, it survives a slip of up to 7 days (bottom 154 px)]
PASS first visit lands on a plan with a slip margin  [planned 2026-11-18]
PASS one verdict cell per day of slip, and three next good dates  [60 cells; next Dec 15, Dec 16, Dec 17]
PASS the card says how sure it is  [How sure: 13 of 13 points within 100 m of the target pass; the coarser grid (LOLA, 240 m/px) says yes; finer near-field sampling says yes.]
PASS the slip grid starts on the first screen (4 rows x 60 dates)  [grid top 609]
PASS default measure is total usable hours, not the unbroken run
PASS each terrain row has a landing-scatter strip and a verdict  [Yes, slip up to 7 d ; Not sure, next Nov 19 ; Yes, slip up to 2 d ; No, next Nov 20]
PASS every slip row is tagged terrain(...) or smooth sphere
PASS every tile carries a provenance tag  [32 of 32]
PASS slip-cell tooltip shows hours, the scatter range and the verdict
PASS first visit shows the slip-margin map of the pole  [0 to 9 days of slip; 5% of the mapped points are coloured]
PASS the map says what it is made from
PASS map tooltip gives the numbers of the point under the cursor
PASS a skyline strip and a year table per terrain site
PASS year table is a resolution ladder (80 m, 240 m, 474 m, 1.9 km, sphere) with ranges
PASS longest darkness carries its caveat on the ridge site
PASS site pairs table (6 pairs of 4 sites)
PASS validation tiles: ordinary terrain, ridge pixels, C1 with its range, Earth check status
Earth check tile: labelled "needs official data download"
PASS window tiles refresh while Play is running
PASS clicking a slip cell moves the scrubber
PASS a next-good-date button re-plans for that date  [Dec 15 -> 2026-12-15: Yes, it survives a slip of up to 8 days]
PASS asking for more sunlight than the window holds gives a plain No with the reason
PASS real-landing replay: IM-2 Athena, 6 Mar 2025 17:00 UTC  [Yes, it survives a slip of up to 2 days]
PASS the address carries the scenario
PASS opening that link in a new tab reproduces the scenario
PASS clearing the date throws nothing and explains itself
PASS setting a date again recovers
PASS height above ground switches to 10 m
PASS clicking the map adds a site there
PASS the map zooms out to 80 S
PASS slip grid CSV export with the scatter band
phone load to network idle: 4389 ms
PASS phone: the verdict is on the first screen  [bottom 478 px]
PASS phone: all 60 slip days of the card and of a grid row are on screen  [narrowest grid cell 4.5 px]
PASS phone: the verdict column of the grid is on screen
PASS phone: no horizontal page overflow  [390 vs 390]
PASS phone: every wide table sits in a sideways-scrolling box
PASS phone: chart axis text is at least 9.5 px
PASS no console errors, page errors or failed requests
ALL UI CHECKS PASSED
```

Screenshots from that run are in `screenshots/`; the storyboard frames (1280x720) are in `demo/`.

### Memory and speed

`python3 scripts/memory_check.py` starts a server with an empty skyline cache and runs a fixed sequence.
Megabytes from /proc/<pid>/status:

```
240 m configuration (--no-80m)                                           s    RSS   anon   file   peak
cold start to first /api/health                                         0.53     65     41     24     65
page load: /api/sites, /api/map, map image                              0.61    251    171     80    251
slip grid, 4 sites x 60 dates with the 13-point scatter band            4.73    179     64    115    287
mission card x 4 sites                                                  0.17    179     64    115    287
compare 4 sites x 60 days                                               0.50    184     69    115    287
year table x 4 (ladder + scatter band)                                  0.67    185     66    119    287
site pairs, 4 sites x 365 days                                          0.03    185     66    119    287
slip map (every field point x 60 dates)                                 4.21    216     77    139    287
20-year hourly statistics, one site                                     0.74    221     82    139    287
24 parallel year statistics at never-seen polar points                  1.48    238     99    139    287
96 parallel year statistics at never-seen polar points                  6.00    254    116    139    296
second slip map (another date) + 4 more mission cards                   6.82    263    124    139    296

80 m grid installed
page load                                                               0.74    406    171    235    406
slip grid, 4 sites x 60 dates with the 13-point scatter band            8.96    360     64    296    468
slip map (every field point x 60 dates)                                 4.16    430     75    355    468
24 parallel year statistics at never-seen polar points                  2.77    485    130    356    534
96 parallel year statistics at never-seen polar points                  9.81    454     98    356    534
second slip map (another date) + 4 more mission cards                   8.62    462    106    356    534
```

The v2 reviewer measured 692 to 704 MB of the process's own memory on the 240 m configuration after a
20-year request and 24 to 96 parallel new-site requests, and 920 MB with the 80 m grid. The same kind of
sequence now peaks at 171 MB of its own memory in both configurations (296 MB and 534 MB resident). Three
changes did it: long spans are processed in blocks of 17,544 samples, at most two heavy computations run at
a time, and freed memory is returned to the system after each (`slipday/load.py`).

With the shipped skyline cache (default and replay sites), warm: mission card 0.03 to 0.04 s; slip grid
4 x 60 with the scatter band 0.17 s (0.016 s without it); year table with ladder and band 0.15 s; site
pairs 0.03 s; slip map 0.075 s once its date is cached. A site never seen before costs 14 new skylines
(2.2 to 2.4 s) for its first mission card.

### Not run or not possible here (round 3)

- The Earth-visibility comparison: the reference maps are not in the sandbox. The model side ran (400
  points) and the readers are tested on the real Sun products.
- `scripts/fetch_on_your_machine.sh`: syntax-checked only (`sh -n`); no download could be attempted.
- Docker build, any deployment, a real phone, the live Horizons check: as in v2.
- The 240 m configuration was exercised by `memory_check.py --no-80m` and `warm_cache.py --no-80m` and
  opened once in the browser (two screenshots): every label reads 240 m, the validation panel carries the
  note that its figures were run on the 80 m grid, the slip-map note says its skylines come from the 80 m
  grid, and the C1 mission card for 2026-11-18 gives the same verdict and margin (Yes, 7 days), with the
  474 m grid as its coarser member. The full browser script was not run in that state.

# Test report (v2)

Run on 2026-11-14 in the build sandbox: Python 3.13, numpy 2.5.3, fastapi 0.162.7, pytest 9.1.1, Node 22,
headless Chrome. Outputs are trimmed, not edited. Real LOLA grids were installed in `data/dem/` by
`scripts/prepare_dem.py` (see REALDATA.md).

## 1. Unit and API tests

```
$ python3 -m pytest -q
108 passed in 31.23s

tests/test_geometry.py      14 passed   Sun/Earth geometry sanity (unchanged from v1)
tests/test_horizons.py      16 passed   against the JPL Horizons tables (unchanged from v1)
tests/test_hindcast.py       7 passed   three real landings; no pass/fail tolerance labels
tests/test_metrics_api.py   12 passed   metrics, slip grid, API shapes
tests/test_regressions.py    9 passed   one test per bug in the v1 review, plus one found in v2
tests/test_terrain.py       21 passed   horizon module on SYNTHETIC analytic surfaces
tests/test_terrain_api.py    8 passed   API with the SYNTHETIC test DEM; labels; CSV exports
tests/test_realdata.py      21 passed   REAL LOLA grids (skipped when they are not installed)
```

v1 had 51 tests. The 108 include those (two were rewritten: the hindcast "within tolerance" test is now a
test that no tolerance label exists, and the series-event test allows events past the chart).

Unit tests run with no DEM unless a test asks for one (`tests/conftest.py`), so smooth-sphere
expectations do not depend on installed data.

### Analytic checks of the horizon module (synthetic surfaces, labelled as such)

| Case | Expected | Tolerance met |
|---|---|---|
| Flat sphere, observer 2 / 10 / 100 / 1000 m up | dip of the horizon -acos(R/(R+h)): -0.0869, -0.1944, -0.6148, -1.9435 deg | 2e-4 deg at all 720 azimuths |
| Cone, 1500 m at 30 km, 2 m observer | apex angle from spherical geometry | 0.012 deg; azimuth within one step; distance within 0.6 km |
| Cone, 2000 m at 50 km, 2 m and 10 m observers | same | 0.012 deg |
| Cone, 2000 m at 100 km, observer 3000 m up | same (a flat-plane formula is off by more than 0.4 deg in every case) | 0.012 deg |
| Cone, 2000 m at 100 km, 2 m observer | hidden: apex at -0.5 deg, below the observer's own -0.087 deg horizon; flat plane would say +1.1 deg | profile equals the dip everywhere |
| Gaussian ridge on a global grid | dense 5 m sampling of the same function along the ray | 0.02 deg |
| Same cone on a polar-stereographic and a global grid | equal skylines | 0.03 deg |
| Solar disc over a level horizon | circular-segment formula | 0.012 in fraction; exactly 0.5 at the centre |
| 0.2 deg notch in a wall | only the strip in the notch shows | fraction between 0.2 and 0.6 |
| 5 deg wall to the east at the equator | sunrise delayed 5 / 0.508 = 9.8 h | between 9.0 and 10.6 h |

### Regression tests for the v1 review

| Review item | Test | What it asserts |
|---|---|---|
| medium: two tiles disagree on time to sunset | test_time_to_sunset_and_lunar_day_use_one_event_list | the chart's event list reaches 200 days past the chart and gives the same sunset as the summary (Shackleton ridge, 2027-01-12) |
| medium: IM-1's 79 h miss labelled "within" | test_no_row_is_labelled_as_passing_a_tolerance | no tolerance fields; IM-1 reads "off by 3.3 days" |
| medium: LIMITATIONS "upper bound" | (document) | rewritten; see LIMITATIONS.md, "Smooth-sphere numbers" |
| low: /api/horizons/check 500 on a bad date | test_horizons_check_with_a_bad_date_is_422_not_500 | 422 for bad start, bad stop, stop before start |
| low: late-2049 dates rejected | test_dates_in_late_2049_are_accepted | metrics at 2049-12-01 and a slip grid from 2049-11-14 return 200; cut-short windows are marked or blank |
| low: longitude 180 shown as 180 W | test_longitude_180_stays_east | 180 stays 180 E |
| low: unbounded table size and cache | test_oversized_requests_are_refused_and_the_cache_is_bounded | 422 "request too large" above 180,000 samples; cache bounded by samples |
| low: "no sunset within 62 days" when the Sun is down | test_no_sunrise_ahead_is_not_reported_as_a_missing_sunset | summary names the missing event and the search length |
| low: favicon 404, no licence | test_favicon_and_licence_exist | both present |
| low: clearing the date throws; Play does not refresh tiles; phone slip grid | scripts/ui_check.js (section 4) | browser checks |
| found in v2 on real terrain | test_sun_above_a_low_skyline_counts_even_at_negative_elevation | a default "minimum Sun elevation 0 deg" zeroed every usable hour on high polar ground in winter; the extra minimum is now off unless asked for |

## 2. Sun and Earth directions against JPL Horizons (unchanged from v1)

```
$ python3 scripts/compare_horizons.py
orientation model: de421     overall: 218 rows, max|dEl| = 1.26e-05 deg, max|dAz| = 1.27e-05 deg
orientation model: iau2009   overall: 218 rows, max|dEl| = 3.38e-03 deg, max|dAz| = 4.48e-03 deg
```

## 3. Terrain against published LOLA results (real data)

```
$ python3 scripts/validate_terrain.py <folder with the LOLA reference maps>
...
wrote data/validation/terrain_validation.json in 513.7 s

Terrain model against the LOLA team's published average-sunlight maps (real data)
Published map | DEM used here | Points | Published mean % | Computed mean % | Mean difference | Mean |difference| | 95th pct |difference| | Correlation | Same call on permanent shadow %
60 m map, 85 S to the pole | 80 m | 200 | 20.01 | 20.39 | 0.39 | 0.8 | 3.76 | 0.9916 | 98.5
60 m map, 85 S to the pole | 240 m | 200 | 20.01 | 21.18 | 1.17 | 1.37 | 6.08 | 0.9786 | 97.5
60 m map, 85 S to the pole | 474 m | 200 | 20.01 | 22.26 | 2.26 | 2.42 | 11.16 | 0.9564 | 95.0
60 m map, 85 S to the pole | 1.9 km | 200 | 20.01 | 26.14 | 6.13 | 6.19 | 23.93 | 0.8616 | 92.5
60 m map, 85 S to the pole | smooth sphere | 200 | 20.01 | 53.2 | 33.2 | 33.2 | 55.17 | -0.3928 | 84.5
120 m map, 80 S to 85 S | 80 m | 200 | 30.14 | 29.68 | -0.45 | 0.76 | 2.97 | 0.9949 | 99.5
120 m map, 80 S to 85 S | 240 m | 200 | 30.14 | 30.68 | 0.54 | 0.86 | 3.73 | 0.9931 | 99.5
120 m map, 80 S to 85 S | 474 m | 200 | 30.14 | 32.14 | 2.0 | 2.26 | 8.0 | 0.9436 | 98.5
120 m map, 80 S to 85 S | 1.9 km | 200 | 30.14 | 36.13 | 6.0 | 6.08 | 25.37 | 0.8322 | 98.5
120 m map, 80 S to 85 S | smooth sphere | 200 | 30.14 | 51.06 | 20.92 | 20.92 | 49.02 | -0.0943 | 97.5

Published ridge-top results at the stated coordinates and heights (real data, 80 m DEM here against 20 m DEMs there)
Point | Lat, east lon | Height | Published | Computed at the point | Difference (avg / visibility, pts) | Computed, best nearby | Source
Connecting ridge C1 | -89.4505, 222.84 | 0 m | 76.0 / 81.3 / 268 h | 75.5 / 81.2 / 266 h | -0.5 / -0.1 | 75.5 / 81.2 / 266 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM
Connecting ridge C2 | -89.3157, 245.94 | 0 m | 75.6 / 80.6 / 166 h | 70.1 / 77.6 / 176 h | -5.5 / -3.0 | 70.1 / 77.6 / 176 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM
Shackleton rim S | -89.7849, 203.97 | 0 m | 81.0 / 85.5 / 221 h | 56.3 / 60.1 / 389 h | -24.7 / -25.4 | 75.7 / 80.9 / 266 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM
Connecting ridge C1 | -89.4398, 222.83 | 2 m | 88.0 / 92.1 / 112 h | 88.0 / 92.1 / 198 h | +0.0 / -0.0 | 88.0 / 92.1 / 198 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM
Connecting ridge C2 | -89.3130, 245.98 | 2 m | 78.1 / 82.0 / 165 h | 77.3 / 81.2 / 230 h | -0.8 / -0.8 | 77.9 / 81.9 / 166 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM
Shackleton rim S | -89.6866, 197.19 | 2 m | 85.5 / 89.4 / 66 h | 84.4 / 88.7 / 67 h | -1.1 / -0.7 | 84.4 / 88.7 / 67 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM
Shackleton rim S, second point | -89.7815, 204.70 | 2 m | 82.1 / 89.8 / 65 h | 72.2 / 78.3 / 363 h | -9.9 / -11.5 | 84.8 / 90.4 / 64 h | Glaser et al. 2018 PSS 162 (20 m LOLA DTM
Connecting ridge CR1 spot 2 | -89.4399, 222.85 | 2 m | 87.9 / 92.3 / 111 h | 87.9 / 92.2 / 199 h | +0.0 / -0.1 | 87.9 / 92.2 / 199 h | Glaser et al. 2014 EPSC2014-136 (20 m LOLA DTM
Connecting ridge CR1 spot 4 | -89.4544, 222.84 | 10 m | 91.9 / 95.7 / 76 h | 91.8 / 95.7 / 73 h | -0.1 / +0.0 | 91.8 / 95.7 / 73 h | Glaser et al. 2014 EPSC2014-136 (20 m LOLA DTM
```

The Earth-visibility table (Bryant 2009), the per-site resolution table and the reading of all of these are
in REALDATA.md. In short: on ordinary terrain sunlight agrees with the LOLA team's maps to 0.8 points on
average (about 4 points on well-lit ridge pixels, see REALDATA.md section 5); six of nine
published ridge-top points agree within 1.1 points and three narrow-crest points read 5.5 to 24.7 points
low on the 80 m grid; Earth visibility could not be checked against a published per-site value.

## 4. Browser checks (headless Chrome, 1280x800 and 390x844)

```
$ NODE_PATH=/tmp/slipday_ui/node_modules node scripts/ui_check.js http://127.0.0.1:8101/ /tmp/slipday_shots
desktop load to network idle: 3184 ms
PASS slip grid is the first panel on the page  [Slip grid: land on this date, get this many usable hours]
PASS slip grid is inside the first 1280x800 screen  [top 234 bottom 529]
PASS default sites are south-polar (4 rows x 60 dates)  [1 Shackleton connecting ridge (C1) 89.440 S, 137.170 W ; 2 Malapert massif, Earth-facing shou
badge: Terrain skyline from LOLA, 80 m/px elevation data; smooth sphere shown beside it
PASS every slip row is tagged terrain(...) or smooth sphere  [terrain (LOLA, 80 m/px) ; smooth sphere ; terrain (LOLA, 80 m/px) ; smooth sphere ; terr
PASS every tile carries a provenance tag  [32 of 32]
PASS polar map image with 4 site markers  [{"img":true,"pts":4,"sky":4,"year":4}]
PASS a skyline strip and a year table per terrain site  [{"img":true,"pts":4,"sky":4,"year":4}]
PASS window tiles refresh while Play is running  [709 h,450 h,360 h,299 h -> 709 h,438 h,353 h,299 h]
PASS clicking a slip cell moves the scrubber  [2026-12-21 10:00 UTC -> 2026-12-04 00:00 UTC]
PASS clearing the date throws nothing and explains itself  [Choose a first landing date to update the page. | cells kept: 240]
PASS setting a date again recovers  [240 cells]
PASS height above ground switches to 10 m  [ground +1958 m, observer 10 m above it, skyline -3.9° to -0.9°]
PASS clicking the map adds a site there  [4 Map pick 88.363 S, 0.000 E 88.363 S, 0.000 E]
PASS slip grid CSV export  [text/csv; charset=utf-8]
phone load to network idle: 2613 ms
PASS phone: all 60 dates of a slip row are on screen  [60 of 60, narrowest cell 4.5 px]
PASS phone: best-date column is on screen  [275..361]
PASS phone: no horizontal page overflow  [390 vs 390]
PASS phone: chart axis text is at least 9.5 px  [9.6 px]
PASS no console errors, page errors or failed requests  []
ALL UI CHECKS PASSED
```

Screenshots from this run are in `screenshots/` and were opened and inspected: slip grid first on desktop
and phone (all four default site rows are on the first phone screen), polar relief map with markers,
skyline strips, year tables, validation tables, dark theme.

## 5. Server and endpoints (uvicorn on 127.0.0.1:8101, real grids)

```
/api/health   horizon_default: terrain (LOLA, 80 m/px; beyond its edge 240 m, 474 m, 1.90 km) where the DEM
              covers the site, smooth sphere elsewhere
              dems: LDEM_80S_80MPP_ADJ 7600x7600, LDEM_75S_240M 3812x3812, SVS ldem_64 1920x23040, LDEM_16 2880x5760

/api/horizon?site=shackleton
              terrain (LOLA, 80 m/px; ...), 2 m above ground; ground +1957.6 m; skyline -2.596 to -0.687 deg
              (mean -1.719); 720 azimuths; DEM data along every ray to 300 km

/api/stats?site=shackleton&start=2027-01-01&days=365
  terrain  any Sun 92.51 %  sunlit (half disc) 88.49 %  mean disc 88.63 %  longest dark 194 h  longest light 4056 h
           Earth 51.11 %  longest outage 319 h
  smooth   any Sun 57.12 %  sunlit 51.97 %              mean disc 51.85 %  longest dark 3296 h longest light 3344 h
           Earth 45.18 %  longest outage 360 h
  mast_m=10  any Sun 95.17 %  sunlit 92.67 %  longest dark 76 h  Earth 51.11 %

POST /api/slipgrid, 4 sites x 60 dates from 2027-04-20, 14-day window: 200 in 0.011 s (warm)
  best "unbroken usable hours from touchdown" and the sum of usable hours over the 60 dates:
  Shackleton connecting ridge (C1)        terrain 2027-05-27 312 h | smooth sphere none (0 h) | sums 9497 vs 0
  Malapert massif, Earth-facing shoulder  terrain 2027-06-14 336 h | smooth sphere 2027-05-24 55 h | sums 9992 vs 2193
  IM-2 Athena (Mons Mouton)               terrain 2027-05-14  72 h | smooth sphere 2027-05-13 68 h | sums 3849 vs 3033
  IM-1 Odysseus (Malapert A)              terrain 2027-06-15 249 h | smooth sphere 2027-06-13 314 h | sums 7313 vs 9252

POST /api/compare, 4 polar sites x 60 days with both models: 200 in 1.17 s cold (four new skylines), 0.55 s warm, 427 kB
/api/metrics for coordinates never seen before (-87.3, 71.2): 200 in 0.24 s, including the skyline
/api/metrics?site=apollo11&at=2049-12-01T00:00:00Z        200
/api/series?lat=0&lon=180&start=2026-01-01&hours=24       200 (lon reported as 180.0)
/api/metrics?site=apollo11&at=2090-01-01                  422
With SLIPDAY_HORIZONS=1 (port 8102):
/api/horizons/check?site=im1&start=bad&stop=2027-01-01    422 "start is not a date or time I can read ..."
/api/horizons/check?site=im1&start=2026-11-14&stop=2026-11-24
                                                          502 "Horizons request failed: ... Tunnel connection failed: 403 Forbidden"
```

Process memory after the v2 browser run: 523 MB resident, most of it pages of the memory-mapped 80 m grid.
That single figure understated the worst case; see section 0 for the measured sequence and the fix.

## 6. Not run or not possible here

- Live JPL Horizons cross-check: the sandbox proxy refuses ssd.jpl.nasa.gov (502 above). Never seen to
  succeed.
- Docker build and any deployment: no Docker daemon; not run.
- `scripts/fetch_lola.sh`: written for a machine with open internet; untested.
- Byte-exact refresh of the Horizons fixtures: needs JPL access.
- No screen-reader or keyboard-only pass.
- The app without the 80 m grid (240 m fallback) is covered by a test and by the validation script's
  240 m rows; it was not browsed in that state.
