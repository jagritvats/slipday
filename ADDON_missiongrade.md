# Add-on pass "mission grade": battery, darkness, launch windows, rocks

Four add-ons, each in its own router under `slipday/addons/`, registered in the optional-router loop of
`slipday/api.py`. None of them changes the card's verdict. Done on 15 Nov 2026 in one hour.

| Feature | Router | Endpoints | Front end and container |
|---|---|---|---|
| Battery through the night | `slipday/addons/power.py` | `GET /api/addons/power`, `GET /api/addons/power/site` | `static/addons/power.js` into `<div id="addon-power"></div>` |
| Darkness check | `slipday/addons/darkness.py` | `GET /api/addons/darkness`, `GET /api/addons/darkness/site` | the same `static/addons/power.js` into `<div id="addon-darkness"></div>` |
| Launch windows from orbital mechanics | `slipday/addons/trajwindows.py` | `GET /api/addons/trajwindows`, `GET /api/addons/trajwindows/windows` | `static/addons/trajwindows.js` into `<div id="addon-trajwindows"></div>` |
| Boulder hazard | `slipday/addons/rocks.py` | `GET /api/addons/rocks`, `GET /api/addons/rocks/site` | none: no product covers the pole (see below) |

## Where the containers go (for the front-end owner)

The page itself was not touched. Suggested places in `static/index.html`:

- `<div id="addon-power"></div>` and `<div id="addon-darkness"></div>`: a new fold next to `#foldSlip` (the
  "how the nights change with slip" panel), for example
  `<details class="fold panel" id="foldPower"><summary><b>Battery and darkness</b> ...</summary> <div id="addon-power"></div> <div id="addon-darkness"></div></details>`.
  Then `<script src="/static/addons/power.js"></script>` after `/static/app.js`. It follows the site and landing on
  the card the same way `relay.js` does (it watches the page's own `/api/mission` requests, cloned, never changed).
- `<div id="addon-trajwindows"></div>`: inside or right after `#realPanel` ("Real missions: what a missed launch
  window does"), with `<script src="/static/addons/trajwindows.js"></script>`. It shows the opening example by
  default and takes its own site and transfer-time inputs.
- Nothing for rocks. The line "there is no boulder data" in `#touchNote` stays true.

## 1. Battery through the night (`power.py`)

What it does. Hour by hour from touchdown, for each of 30 slip days (up to 60):

- solar power = array power x share of the Sun's disc above the terrain skyline x cosine of the angle between the
  Sun and the panel x (1 AU / Sun distance)^2. The Sun is the app's DE421 Sun; the skyline is the app's LOLA skyline
  2 m above the ground. Panel choices: fixed vertical faces (default, 4 faces sharing the array), one vertical panel
  turned to the Sun, or a flat top panel.
- load: the day load while at least half the Sun's disc is above the skyline (the card's Sun rule), the night load
  otherwise.
- battery: full at touchdown; charges with the surplus x charge efficiency; only the usable share of the capacity
  (depth of discharge) is drawn.
- the run covers the 14-day window and, if a night is under way when it ends, on until that night ends (up to 45
  days).
- answer per slip day: "survives the longest night (N h) with X % of the usable charge left", "no night in the run",
  or "battery empties N hours after touchdown".

**No published battery capacity, array power or night load was found for a flown lunar lander.** The Astrobotic
user guide gives none, the NASA press kits tried returned 404, and the Nova-C, Blue Ghost and HAKUTO-R pages gave
no figures. So this is a calculator: every figure can be changed in the request (`battery_kwh`, `night_load_w`,
`day_load_w`, `array_w`, `charge_eff`, `usable_frac`, `panel`, `faces`) and in the page. The defaults, each
labelled in the JSON and on the page:

| Figure | Default | Label |
|---|---|---|
| battery capacity | 20 kWh | NASA Glenn design study of a small lander built to survive the night, not a flown lander: "1568 cells in 8s-196p configuration, ~20 kWh capacity" |
| usable share | 0.9 | same study: "Use 90% DoD to reduce battery mass" |
| night load | 46 W | same study: "Operational nighttime power is ~40 W, EPS losses total ~6W" |
| panels | fixed vertical | Astrobotic user guide: "whereas polar missions utilize side-mounted panels" |
| array power | 400 W | illustrative (no figure found) |
| day load | 46 W | illustrative (no figure found; set equal to the night load) |
| faces | 4 | illustrative |
| charge efficiency | 0.9 | illustrative |

The study sizes its battery for a mid-latitude night of 354 hours, not for a polar site. Not modelled: cell
temperature and ageing, dust, shadowing by the lander itself, battery temperature, light reflected from the ground,
and load changes the operators would make.

## 2. Darkness check (`darkness.py`, endpoint `/api/addons/darkness`)

What it does. For each slip day, the longest run of hours with **no part** of the Sun's disc above the terrain
skyline (total darkness, stricter than the card's night), under way at touchdown or starting inside the 14-day
window, measured to its end (up to 45 days). It is compared with an hour limit. No temperature is computed.

- Default limit: **96 hours**, NASA VIPER's design figure, "Dark Survivability: 96hrs" (Vaughan 2020). This is a
  polar **rover's** figure; no survival-in-darkness figure was found for a lander. The user can set any limit
  (`limit_h`).
- For context only: the NASA Glenn design study keeps the electronics above -40 C through the night ("kept > -40C").

## 3. Launch windows from orbital mechanics (`trajwindows.py`)

What it does. This is a simplified patched-conic geometry check, not a mission design.

1. Lighting windows. A window is a run of at least 12 h in which the Sun is up over the terrain skyline, its disc
   centre is 0 to 10 degrees above the skyline, and it is rising. Touchdown is allowed in the first 48 h. All of
   these numbers are illustrative.
2. Arrival is taken as touchdown. The Moon's position at arrival comes from DE421.
3. Launch = arrival minus a 4-day direct transfer (an assumption; it can be set from 2.5 to 6 days). Minute by minute,
   the plane holding the Earth's centre, Kennedy (rotated by GMST) and the Moon at arrival is found. A minute counts
   when the launch azimuth is within 35 to 120 degrees (illustrative). This gives about two launch periods a day. The
   declination check (|dec| no more than the highest reachable inclination) never binds from Kennedy.

Limits, stated in the JSON:

- two-body legs and a fixed transfer time;
- the Moon's direction is used as the target, with no lunar-orbit insertion;
- no rocket performance, range or weather rules;
- the J2000 equator is used as the equator of date, and UT1 is taken as UTC.

The error these add has not been measured, and no published window rule was fetched to check the results against.

Parameters of `/windows`:

| Parameter | Default |
|---|---|
| `site` (or `lat`, `lon`, `name`) | `robust_pick` |
| `landing` | `2026-11-18T00:00:00Z` |
| `launch_lat`, `launch_lon` | 28.573, -80.649 |
| `transfer_days` | 4 |
| `months` | 3 (range 1 to 6) |

## 4. Boulder hazard (`rocks.py`)

**No public NASA rock-abundance or boulder product, reachable without a login, covers the south-pole sites.**
Checked on 15 Nov 2026 with plain HTTP:

- Diviner rock abundance, `https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_gdr_l3/cylindrical/img/dgdr_ra_avg_cyl_128_img.lbl`.
  The label gives latitudes -80 to 80, and the description says the data cover "latitudes between 80N and 80S".
- The Diviner high-resolution rock mosaic (`dghrm_ra_sam_70s70n`) stops at 70 S.
- The Diviner polar products are temperature and resource products, with no rock abundance.
- The LROC RDR products (on `pds.mcp.nasa.gov`) are mosaics, DTMs and photometry, with no boulder layer.
- PGDA product 78 (the LOLA 5 m site models) holds height, slope and errors, with no rock layer. The PGDA product
  list has no rock product.

All four points are poleward of 88.4 S: Site01 and Site07 (the 5 m tiles), robust_pick and C1. The router returns
`{"available": false, "why": ..., "checked": [...]}` and "no coverage here" for every point. No file was
downloaded, so there is no sha256 to record.

## Sources stored (`data/addons/power/`)

The PDFs were downloaded and hashed, then left out because of their size. Only the extracted text
(`pdftotext -layout`, line ends turned to LF) is committed.

**NASA Glenn design study.** Oleson, Colozza and Uguccini, "Overnight Power & Thermal Solutions for Lunar Landers",
Survive The Night Technology Workshop, 6 Dec 2022.
- Record: https://ntrs.nasa.gov/citations/20220018215
- PDF: https://ntrs.nasa.gov/api/citations/20220018215/downloads/Overnight%20Power%20and%20Thermal%20Solutions%20for%20Small%20Landers%20final2.pdf
  (11.9 MB), sha256 `da6c1c46bca7c7779f03660ad5453ea2e78c628a9f0fd503843f0065f8446ef3`
- Stored text: `ntrs_20220018215.txt`, sha256 `e9d3684f25baa5483d8feb3e9a7a01119fd9bfd15435ac8a064c014d49986845`

**NASA VIPER.** Vaughan, "VIPER: Mission Overview", ISSC, 11 May 2020.
- Record: https://ntrs.nasa.gov/citations/20205001794
- PDF: https://ntrs.nasa.gov/api/citations/20205001794/downloads/VIPER_Mission_Overview_ISSC_Vaughan_05-11-2020.pptx.pdf
  (26.5 MB), sha256 `4ce17f1dca23d438900f55745be0b9d3a4fc099505d617e321beea1cef24f765`
- Stored text: `ntrs_20205001794.txt`, sha256 `9832b898c65281f4b7a8ff290c4e7848d1e131af7755aaece6f70917f7862d0f`

**Astrobotic Lunar Landers Payload User's Guide** (PUGLanders_011222).
- PDF: https://www.astrobotic.com/wp-content/uploads/2022/01/PUGLanders_011222.pdf (10.4 MB), sha256
  `bbb21c232b2dcfbf262996c745f2c28b30f8bc73fc7ccb18eac34f9f33234a24`
- Stored text: `astrobotic_PUGLanders_011222.txt`, sha256
  `636243df7445def7ea4b087e3f881c2fb56518fc9d152fb46ece50d9c30a247e`

The tests check every stored sha256 and that every quote used is in the stored text.

## Results

All results use real terrain: LOLA 5 m site models, then 20 m, 80 m and coarser. The landing is on 18 Nov 2026,
with 30 slip days and the defaults above.

### Opening example (robust_pick, 89.010 S, 122.764 E)

**Battery.** All 30 slip days survive.
- Slip days 0 to 8: "survives the longest night (13 h) with 99 % of the usable charge left".
- Slip days 9 to 22: the night grows to 155 h, and the lowest charge is 62 %.
- Slip days 23 to 29: the lowest charge is 66 to 85 %.
- As a calculator check with a 2 kWh battery (other defaults unchanged), the first 9 slip days survive. Slip day 9
  fails: "battery empties 360 hours after touchdown".

**Darkness.** Slip days 0 to 8 have no total darkness. Slip days 9 to 22 have 115 h, which is 19 h past the 96 h
limit, so slip day 9 is the first over the limit. Slip days 23 to 29 have 102, 78, 54, 30, 48, 48 and 48 h.

**Launch windows** (Kennedy, 4-day transfer). No lighting window contains 18 Nov, so window 0 is the next one to
open. The steps between windows are 29.92 and 30.21 d, against the card's 29.53 d rule.

| Window | Opens (UTC) | Sun elevation at opening | Moon declination | First launch (UTC) | Later than the 29.53 d rule |
|---|---|---|---|---|---|
| 0 | 2026-12-01 10:00 | 0.59 deg | -6.0 to 6.1 deg | 2026-11-27 12:51 | (start) |
| 1 | 2026-12-31 08:00 | 0.18 deg | -19.9 to -10.1 deg | 2026-12-27 08:00 | 0.39 d |
| 2 | 2027-01-30 13:00 | -0.51 deg | -27.5 to -23.5 deg | 2027-01-26 14:31 | 1.06 d |

**Rocks.** No coverage.

### C1 (Shackleton connecting ridge, 89.440 S, 137.17 W)

**Battery.** All 30 slip days: "no night in the run; the lowest charge is 100 % of the usable charge". The Sun
stays up under the card's rule for the whole run.

**Darkness.** 0 h on every slip day, within the limit.

**Launch windows.** The steps between windows are 30.33, 30.12, 29.75 and 29.96 d. By window 4 the window opens
2.04 d later than the 29.53 d rule gives.

| Window | Opens (UTC) | Sun elevation at opening | Moon declination | First launch (UTC) | Later than the 29.53 d rule |
|---|---|---|---|---|---|
| 0 | 2026-11-21 02:00 | 0.98 deg | 7.7 to 19.1 deg | 2026-11-17 03:10 | (start) |
| 1 | 2026-12-21 10:00 | 0.70 deg | 23.2 to 27.6 deg | 2026-12-17 10:00 | 0.80 d |
| 2 | 2027-01-20 13:00 | 0.04 deg | 21.2 to 27.4 deg | 2027-01-16 18:26 | 1.40 d |
| 3 | 2027-02-19 07:00 | -0.80 deg | 7.8 to 19.8 deg | 2027-02-15 07:00 | 1.62 d |
| 4 (`months=4`) | 2027-03-21 06:00 | -1.55 deg | -0.2 to 4.2 deg | 2027-03-17 06:00 | 2.04 d |

The Sun elevation is the true elevation; the band is measured above the terrain skyline, which can sit below the
level horizon, so a slightly negative elevation can still be in the band.

**Rocks.** No coverage.

## Tests

The new tests are `tests/addons/test_power_darkness.py` (16), `tests/addons/test_trajwindows.py` (10) and
`tests/addons/test_rocks.py` (2). All 28 pass. The full-suite result is below.

Full suite (`python -m pytest tests -q`, run in this worktree, where the git-ignored data folders are only
partly present): **348 passed, 110 skipped, 5 failed**. The 5 failures are:

- `tests/addons/test_fullmap.py::test_recompute_three_points_from_the_lola_files`
- `tests/addons/test_impact.py::test_every_quote_is_in_the_saved_first_hand_page`
- `tests/addons/test_impact.py::test_source_hashes_match_the_files_and_the_download_log`
- `tests/addons/test_safety.py::test_far_from_any_polar_grid_is_unknown`
- `tests/test_live_terrain.py::test_the_default_stack_is_the_live_one_when_installed`

They fail the same way with this pass's files removed and `api.py` restored, because they need data that is not in
the worktree (for example `data/reference/DOWNLOADS.tsv`). They are not caused by this pass.

## Left out, and why

- **A real lander's battery, array and loads.** No first-hand figures were found. The array power, day load, face
  count and charge efficiency are illustrative. The battery and night load come from a design study, not a flown
  lander.
- **A temperature model.** No published thermal figures were found for a lander, so only darkness hours are
  compared. The 96 h limit is a rover's.
- **A cited launch-window rule, and any check of the launch periods against a real mission's dates.** There was not
  time to find a first-hand source.
- **Rocks.** No product covers the pole without a login. No boulder line was added at the 5 m sites, and none was
  invented.
- **Changes to `static/index.html`.** The page belongs to another agent; the containers above are for them to place.
