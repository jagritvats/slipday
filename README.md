# Slipday

What a launch slip costs at a lunar south-pole landing site, and how sure that answer is.

Built for the NASA Space Apps 2026 challenge "Lunar Landing Site Navigator" (CLPS Lunar Mission Browser).
You give it a site, a landing date and what the mission needs (sunlit hours for power, hours with the
Earth above the skyline for a direct radio link). It answers Yes, Not sure or No, says how many days the
landing can slip before the answer changes, and lists the next good dates.

The skyline is real: it is ray-cast over the curved Moon from LRO LOLA elevation grids, always the finest one
that covers each piece of ground: the LOLA team's 5 m site models at two places near Shackleton, the 20 m mosaic
near the pole, 80 m out to 80 S, and coarser grids beyond. The Sun is treated as a disc, and every number is
shown beside the smooth-sphere answer. Each verdict is worked out at 13 points within 100 m of the target, again
on the next coarser grid, and again with a finer sampling of the nearest ground, and is only "Yes" when all
agree. The API says which grid each answer used (`terrain_grid` in `/api/mission` and `/api/why`). The headline states the landing scatter the "Yes" assumes, and the card
shows what a less precise landing (250 m, 500 m, 1 km) would do to it.

Four things lead the pitch:

1. a **slip margin in days** for a site, date and need;
2. a **three-state verdict for every day of slip** that is "Yes" only when an ensemble agrees (13
   touchdown points, a coarser grid, a finer near-field sampling);
3. a **slip-margin map** of the ground within 30 km of the pole;
4. the **same site on five terrain resolutions**, so the effect of terrain detail is on screen.

The main pieces, each on the real LOLA terrain:

- **The first screen.** The input sentence (site, date, hour, sunlit and Earth-contact hours, days on the surface,
  landing scatter, "launch slipped by N days"), the verdict, one line labelled "Challenge objective" with the Sun's
  and the Earth's direction and height above the skyline at touchdown, the skyline chart with a legend, the line
  on what ends the margin, the next monthly windows, and two buttons: "Other sites, other hours" and "Download
  this answer" (CSV or JSON: inputs, verdict, margin, every day of slip, the windows and the other sites). A jump
  bar reaches the map, the 3-D view, the regions and the checks in one click; the specialist tools are folded at
  the end. Any curated site can be picked on the card, or your own coordinates (latitude in degrees south).

- **A verdict for every day of slip.** A site counts as Yes only if all 13 touchdown points within the
  landing scatter get enough sunlight and Earth contact, on two terrain grids. The page opens on a ridge
  point at 89.010 S, 122.764 E, landing 18 Nov 2026: Yes, with 8 days of slip margin on the live terrain (NASA's 5 m site model
  here), and also on the 20 m and 80 m grids. The date is fixed, so the page keeps opening on it after it has passed. Site 2, the
  Shackleton connecting ridge, shows a case where the grids disagree: Yes on 80 m, Not sure on 20 m and 5 m.
- **Why it flips.** The Sun and the Earth against the terrain skyline for any day of slip, with the time
  left to sunset and Earthset and the ground that ends the margin.
- **Next launch windows.** A lander gets a launch window of a few days each month. We infer that a missed
  window moves the landing about one synodic month (29.5 days). The card shows what the next three windows
  give, which need fails in each, and, on request, which other site and landing hour still work.
- **Real missions.** IM-1's windows (the flown one, and the January one it missed, at a modelled date) and
  VIPER's late-2027 windows on an illustrative point, with first-hand sources. NASA's nine south-pole landing regions (chosen for the first crewed landing, now planned for Artemis IV, early 2028) in each missed
  window, judged on the published candidate landing sites of Wueller et al. 2026 (they replace one point per
  region that we had picked ourselves).
- **Hours to ride through.** The longest night and the longest Earth outage a lander meets, for every day of
  slip, at the worst touchdown point. Hours, not a battery model.
- **The Earth margin.** How far the Earth clears the skyline at touchdown, and up to which link mask the Yes
  holds (masks illustrative). Earth contact can also require a Deep Space Network station to see the Moon.
- **A slip-margin map with landing scatter**, checked on NASA's 20 m grid, and sites that survive a slip
  beside permanent shadow (dark ground, not proven ice).
- **A 3-D view** of the ground with the Sun, the Earth and the shadows at the chosen time.
- **How many regions must stay open.** NASA writes that "individual regions typically provide limited viable
  opportunities" and that "more than one landing regions must be maintained" (LPSC 2026 abstract, NTRS
  20250011660). A separate panel checks the 78 published candidate landing sites in NASA's nine regions
  (Wueller et al. 2026, JGR Planets, CC BY 4.0; data on Zenodo, record 17084058) at landing times every
  6 hours from 2027 to 2030. Each site gets the card's 13-point check for a 6.25-day stay (NASA:
  "approximately 5.75 to 6.25 days"), with the Sun up for the whole stay and 100 hours of Earth contact. A
  region is open when one of its sites is a clear Yes that is not fragile.
  - On the live terrain (every site on NASA's 20 m mosaic), the best single region (Nobile Rim 1) is open at
    26.0 % of the landing times, the best three at 37.0 % and all nine at 39.9 %. With sunlight only: 44.8 %,
    89.4 % and 91.1 %.
  - The 39.9 % ceiling is set by the 100-hour Earth-contact need, which is an illustrative figure.
  - The shares count landing times every 6 hours, not real launch opportunities.
  - Regions are added one at a time, each time the one that covers the most new landing times; trying every
    set gives the same answer. On the 80 m grid the shares were higher (28 %, 40 %, 44 %): finer terrain gives
    fewer opportunities.
  - The panel also shows a calendar of the nine regions. As a check of the geometry, the season moves 18.65
    days earlier each year against 18.63 expected from the 346.6-day eclipse year.
  - Cross-check against the paper's sunlight figures: of 312 comparisons, about two in three agree within a
    day and about three in ten differ by more than 3 days, nearly always with ours longer.

  The rest of the page works for any site, as before.
- **Which years suit a landing, 2027 to 2035.** The same check as the region calendar, run for nine years
  on the 78 published sites and the page's own south-pole sites. All nine regions together are open at 42 % of
  landing times in the best year (2028) and 36 % in the worst (2032); with sunlight only, 89 to 92 % in every
  year (live terrain, every site on the 20 m mosaic). Shares count landing times every 6 hours,
  not real launch opportunities.
- **Listen to the landing window.** A button turns the card's 14 days into about 20 seconds of sound: a high
  tone for the Sun, a low tone for the Earth, going quiet when the ground hides them. The same window can be
  read as text, and the card's answer is read out to screen readers. Nobody has tested it with a real screen
  reader yet.
- **Flat enough to land?** For the site on the card, the slope at each of the 13 touchdown points, against
  NASA's limit for its crewed lander: it must stand within 8 degrees of upright (5 is the goal). That limit is
  about how far the lander may lean; site studies use it for ground slope too. The opening example is flat
  enough at all 13 points, and its steepest point is 4.9 degrees on 5 m terrain, just inside the 5-degree
  goal: moving it by one 5 m cell gives 4.4 to 5.8 degrees, and NASA's own slope maps give about 2 degrees of
  uncertainty per point. IM-1's target reads 12.2 degrees,
  too steep; IM-1 landed on a slope and tipped over. 76 of the 78 published Artemis region sites have only 80 m
  terrain here, too coarse for slope. A map switch shows which slip-tolerant points are also flat enough.
- **Chance of a safe touchdown.** Where the 5 m terrain covers the site, the chance that the ground under the
  lander is within NASA's 8-degree limit, for three assumed lander accuracies. For the opening example: 100 %
  for a precision lander, 93.7 % for a CLPS-class lander and 82.9 % for an unguided one (the panel itself rounds
  them to "over 99.9 %", 94 % and 83 %). Slope only, no
  boulder data; a 2-degree error in NASA's slope map changes the 5-degree figures a lot.
- **Relay satellites.** How many hours a relay satellite circling the Moon could add when the Earth is hidden,
  using a representative orbit from NASA's LCRNS Reference Constellation 3.1 (not final, not a live service).
  For the opening example: 311 hours of contact with the Earth alone, 336 of 336 with the Earth or two relays.
  The card's answer stays Earth-only; the relay figure is an extra line. Where a relay is at a given hour is
  illustrative only.
- **Be the mission planner.** A short game for students aged 12 and up: the launch slips by 1 to 12 days, you
  pick one of three sites, and the app gives the real answer for each, with one plain reason.

Nothing is deployed publicly yet. The Docker container figures below are for older code.
LOCAL_PASS_RESULTS.md and LOCAL_PASS_2_RESULTS.md have every number with the command that produced it.

## What is on the page

- **Mission card** (first thing on the page). A sentence with the site, landing date and hour, sunlit
  hours and Earth-contact hours needed, and the window they are counted over. Beside it: the verdict, the
  slip margin in days and the landing scatter it holds for, a strip with one cell per day of slip (yes /
  not sure / no), what a smooth-sphere model would have answered and on how many dates terrain changes
  that answer, the next three good dates as buttons, and a "how sure" line. For the default example a
  line under the verdict says what NASA's 20 m grid answers for it.
  **Why it flips**: click a cell of the strip and the Sun's and the Earth's paths are drawn against the
  360-degree terrain skyline for that landing window, with the time left to sunset and Earthset, the
  hours counted and the rule each uses, and a sentence naming what ends the margin: which touchdown
  point, which body, and the direction, distance and position of the ground it goes behind. Where that
  ground is one or two cells of the elevation grid away, the sentence says so instead of naming a ridge.
  Under the inputs: **a year of landing dates** as one ribbon; the **chance that the plan holds by
  lander class** (a precision lander, a CLPS-class lander, an unguided one: three assumed Gaussian
  dispersions, tagged as assumptions, each with a range); and **landing circles**, the share of a 100 m,
  250 m, 500 m and 1 km circle around the target in which the plan still holds, one bar per day of slip,
  with a sampling range. Four real
  landings (IM-2, IM-1, Chandrayaan-3, Blue Ghost 1) load as worked examples, each with its own need
  where a planned surface duration was published, and a note saying where the figure comes from and
  what the other published figure would give. IM-1: its plan of about seven days fits with one day to
  spare; the roughly ten days in NASA's press kit would not (the card then says No). Chandrayaan-3: the
  240 hours on the card are illustrative and give Yes; its published mission life of 14 days would give
  No. The replays show how the card reads a real plan. They are not a confirmation of the model.
- **Slip grid.** Up to four sites down the side, 30 to 90 landing dates across. Each cell is coloured by
  hours after a landing on that date (usable, sunlit, Earth contact, or unbroken from touchdown), by
  default the worst of 13 points within 100 m of the target. Under each row: how far the answer moves
  within that scatter, and the same site on a smooth sphere. The right-hand column gives each site's
  verdict. CSV export.
- **3-D view.** The real LOLA ground around the card's site as a surface that can be turned, at true
  scale (2x and 3x are offered and labelled), with the directions to the Sun and the Earth, the cells in
  shadow at the chosen time (ray-cast on the same grid), the ground the Sun or the Earth goes behind,
  and a slider that steps the shadows through the landing window.
- **Slip map.** A close-up of the pole (60 km across) coloured by the days of slip the planned landing
  survives, the number of good landing dates, or the sunlit hours on the worst or median date, at 14,400
  points 500 m apart. It is computed for the dates and need on the card. Click a point to add it as a site.
  By default every coloured point is **re-checked at 13 touchdown points** (the point, 8 on a 100 m circle,
  4 at 50 m) and coloured by the days of slip that all 13 survive, in five steps of one colour; a hollow
  amber cell is a point that passes by itself and loses its margin within the scatter, and the legend
  counts each class. Switch the re-check off to see the single-point map. A second switch marks
  **permanent shadow** (480 m cells in which the LOLA team's average-illumination map is zero). The
  button under the map re-checks its 12 best points with the full "how sure" check, coarser grid and
  near-field sampling included, and lists the ones that stay a clear yes (**slip-robust sites**).
- **Site cards.** Sun and Earth elevation over time with the terrain skyline, a 360-degree skyline strip,
  tiles for time to sunset and Earthset, and a year table that shows the same site on every elevation grid
  installed (80 m, 240 m, 474 m, 1.9 km, smooth sphere) with the range found within the landing scatter.
- **Two sites as one power system.** Share of the year at least one of two sites has Sun, and the longest
  time both are dark.
- **Not like Earth.** The Sun's height over the same 60 days at the site, at a place on Earth at the same
  latitude and at a town at 45 degrees north (the Earth curves are a textbook formula and labelled so),
  with a small table: length of a day, range of the Sun's height, number of sunrises, twilight.
- **Can you trust it?** The terrain model against the LOLA team's published illumination maps (ordinary
  terrain and well-lit ridge pixels separately), against the LOLA team's Earth-visibility maps (with the
  rule the maps' own labels state), published ridge-top results with their sensitivity, a hindcast of
  three real landings, and JPL Horizons (stored tables and a live cross-check button).
- **Shareable link.** The address holds the whole scenario; "Copy link to this scenario" copies it.

Every figure carries a tag: `terrain (LOLA, 80 m/px)`, `smooth sphere`, or `geometry (JPL DE421)`; sites
outside the area checked against the LOLA maps are tagged `not validated`. Read LIMITATIONS.md first.

## Run it

```
pip install -r requirements.txt
python3 scripts/fetch_grid80.py                          # once: NASA's 80 m grid, 189 MB, sha256 checked
MALLOC_ARENA_MAX=2 uvicorn slipday.api:app --port 8000   # or: sh run.sh    (Windows: .\run.ps1)
```

Then open http://localhost:8000. On a system Python that refuses to install packages use a virtual
environment (`python3 -m venv .venv`). The ephemeris ships inside the `de421` pip package.
`MALLOC_ARENA_MAX=2` matters on Linux (see "Deploy"); the code applies the same limit itself if the
variable is missing, and `/api/health` reports which one is in force. Without the second line the app
runs on the 240 m grid.

Data under `data/` (see REALDATA.md):

- `dem/ldem_75s_240m_i16.npy` (29 MB), `dem/ldem_64_south.npy` (88 MB), `dem/LDEM_16.IMG` (33 MB) and the
  map layer are small enough for git.
- `dem/ldem_80s_80m_f32.npy` (231 MB) is over GitHub's file limit and is git-ignored.
  `python3 scripts/fetch_grid80.py` downloads `LDEM_80S_80MPP_ADJ.TIF` from pgda.gsfc.nasa.gov, checks
  its sha256 and builds the array. Without it the app uses the 240 m grid, says so in every label, and
  widens its landing scatter to one 240 m cell (the default example then reads "Yes, 7 days" for a
  landing within 240 m, instead of "Yes, 8 days" within 100 m; measured 15 Nov 2026).
- `reference/` (1.27 GB, git-ignored): the official downloads, fetched by
  `sh scripts/fetch_on_your_machine.sh`; `python3 scripts/prepare_dem.py data/reference` rebuilds `dem/`
  from them. Needed only for re-running the validation and three tests.
- `field/` (62 MB): one terrain skyline for each of 14,400 points around the pole, built from the 80 m
  grid by `python3 scripts/build_field.py --procs 10` (14 minutes with 10 processes on a laptop; 23
  minutes on two cores in the build sandbox). The slip map needs it; without it the map offers shaded
  relief only. It also holds 12 landing-scatter skylines for each of 2,407 map
  points (`scatter_el_i16.npy`, 42 MB; `python3 scripts/build_scatter_field.py --procs 6`, 29 minutes
  with 6 processes): the points that pass on at least one landing date from 14 Nov 2026 to 16 Jan 2027
  for the default need. Without it the map is the single-point one.
- `horizon_cache/` (19 MB, about 1,550 files): skylines for the default and replay sites including their
  landing circles and lander-class rings, on both grid configurations, so a fresh server answers at once.
  Rebuild with `python3 scripts/warm_cache.py` and `python3 scripts/warm_cache.py --no-80m`.
- `dem20/` (optional, git-ignored): `ldem_80s_20m_f32.npy` (3.7 GB), NASA's whole 20 m mosaic from 80° S to the
  pole, made by `python3 scripts/build_live_stack.py --convert` from `reference/LDEM_80S_20MPP_ADJ.TIF`; with it,
  `build_live_stack.py` writes `dem_live/dems.json`, the stack the app uses by default (5 m site models, 20 m,
  80 m and coarser). Also the older 71.7 km square around the pole (`scripts/fetch_ldem20_crop.py`). `python3 scripts/ridge_20m.py --save` works the
  default example out on it and stores the comparison the page shows
  (`validation/finer_grid_check.json`); `SLIPDAY_DEM_DIR=data/dem20` runs the whole app on it.
- `validation/`: stored validation results shown in the app.
- With no `dem/dems.json` the app runs on the smooth sphere only and says so.
  `SLIPDAY_SYNTHETIC_DEM=1` installs a labelled synthetic test surface instead (for development).
  `SLIPDAY_SKIP_DEMS=ldem_80s_80m` runs as if the 80 m grid were not installed.

Tests and checks:

```
python3 -m pytest -q                         # 207 tests with everything installed (80 m grid, field,
                                             # scatter skylines, data/reference, the 20 m crop); a clone
                                             # without the 80 m grid and data/reference passes 170 and
                                             # skips 37, each with its reason
python3 scripts/compare_horizons.py          # Sun/Earth directions against JPL Horizons tables
python3 scripts/validate_terrain.py data/reference   # terrain against published results, 9 to 18 min
PROCS=8 python3 scripts/validate_more.py data/reference --recompute   # ridge pixels, C1 sensitivity,
                                             # near field, Earth checks; about 45 s with 8 processes
python3 scripts/stress_check.py http://127.0.0.1:8000 --docker <container>   # load test with memory
python3 scripts/memory_check.py --no-80m     # lighter sequence; Linux only (reads /proc)
NODE_PATH=<node_modules with puppeteer-core> CHROME=<browser> node scripts/ui_check.js http://127.0.0.1:8000/ shots
NODE_PATH=<...> CHROME=<...> node scripts/storyboard.js http://127.0.0.1:8000/ demo   # the five video frames
python3 scripts/make_draft_video.py --ffmpeg <ffmpeg>   # a 29-second draft video from those frames and captions
python3 scripts/local_pass_tools/measure_blocking.py http://127.0.0.1:8000   # stored answers while slow work runs
```

`SLIPDAY_HORIZONS=1` enables the live cross-check against the JPL Horizons API (a button at the bottom of
the page). On Windows set variables with `$env:NAME = "value"` first, and use `python` for `python3`.

## Deploy

One Python process, no database; it serves the API and the static page.

**Nothing is deployed.** There is no public link and no hosting account behind this entry. The
`Dockerfile`, `render.yaml` and `Procfile` are written. The Docker image was last built and run on
14 Nov 2026, before later changes to the code and data; `render.yaml` and
`Procfile` have never been run anywhere.

**What a host needs.**

- **Memory: 1 GB is the least to try.** Three figures exist, all the peak working set of the Python
  process on Windows: 498 MB in one of our sessions, 627 MB in a second
  session, and 579 MiB (607,453,184 bytes; peak commit 1,214 MiB) in a later session under the review's own
  load: three bursts of 10 cold requests, a mixed burst of 15, map variants, the shadow-site list, the
  station panel and both browser suites (LOCAL_PASS_2_RESULTS.md). Neither is a container
  figure: a Windows working set and a Linux memory group count memory differently, and the glibc arena
  setting does nothing on Windows. So a 512 MB plan cannot be relied on. Measure in a container first
  (the command is below), and take more than 1 GB if that run comes close to its limit.
- **The 80 m grid, there every time the process starts.** `data/dem/ldem_80s_80m_f32.npy` (231 MB) is
  not in the repository (see the table at the end of this section). It has to be inside the image or
  the build output, or on a disk that survives a restart. The three ways to get it there are listed
  below.
- **One process.** One `uvicorn` process, no `--workers`: the two lanes that bound slow work and the
  caches live inside the process, so each further worker would have its own, and a memory figure
  measured for one process would no longer hold.
- **The start command**: `MALLOC_ARENA_MAX=2 uvicorn slipday.api:app --host 0.0.0.0 --port $PORT`
  (this is the `Procfile`; `render.yaml` sets the variable in its own list; the Docker image sets it and
  listens on port 8000 unless `PORT` is given). The health check path is `/api/health`.

**The public link should serve the live terrain stack** (`data/dem_live/`, see `dem20/` above). Every example in
the storyboard, the slides and the submission draft is on it (the opening example reads "Yes, 8 days" on 5 m
terrain; the connecting ridge "Not sure", 12 of 13). With the 80 m grid alone the opening example is the same
but the ridge reads "Yes, 7 days" and other figures differ.
To check a deployment: the badge names the finest grid installed, "Real Moon terrain: NASA LOLA laser heights, one
every 5 m" on the live stack (each answer names the grid it used beside the verdict, which depends on the site:
"on 5 m terrain" at the opening example, "on 20 m terrain" at IM-1), and `/api/mission` for the opening example
gives `terrain_grid.resolution_m` 5. A server with the 80 m grid alone shows "one every 80 m".

**Every container figure in the table below belongs to earlier code and data (14 Nov 2026).** Since it was
measured, the code gained the scatter skylines (42 MB, memory-mapped), the 3-D
view, the light lane and several panels, and the Docker engine was not run again. The table is kept as a
record of that pass; it is not a figure for the present code. The same goes for the image size measured
then, 1.33 GB.

Earlier code and data: measured on 14 Nov 2026 in Linux containers on Docker Desktop, two CPUs each, with
`scripts/stress_check.py` (205 requests: first-visitor sequence, 12 cards at once, landing circles at
four sites, the slip-robust list, 6 slip maps at once, 12 cards at never-seen points, bursts of 24 and
96 new-site statistics, four 20-year requests, a mixed burst of 29):

| Grid, memory limit | Arena limit | Result | Peak of the container's memory group | Peak resident size of the server |
|---|---|---|---|---|
| **80 m, 512 MB** | `MALLOC_ARENA_MAX=2` | every request answered | **431 MB** | 691 MB |
| 80 m, 768 MB | `MALLOC_ARENA_MAX=2` | every request answered | 433 MB | 692 MB |
| 80 m, 1 GB | `MALLOC_ARENA_MAX=2` | every request answered | 421 MB | 736 MB |
| 240 m, 512 MB | `MALLOC_ARENA_MAX=2` | every request answered | 299 MB | 439 MB |
| 240 m, 512 MB | set in code (variable missing) | every request answered | 296 MB | 431 MB |
| 240 m, 512 MB | off | killed by the kernel (exit 137) during the burst of 24 new-site statistics | 393 MB at the last reading before the kill | 527 MB at that reading |

In that pass the 80 m grid ran inside a 512 MB limit with about 80 MB to spare. That does not carry over
to the present code (see the two Windows figures above). The resident size is above the limit because it
counts the memory-mapped grid files, which the kernel drops under pressure; the memory group is what a
limit acts on. "MB" in this table is 1,048,576 bytes. These were container figures from one machine: a
hosting plan's limit may be counted differently, and a host with a fraction of a CPU was not tested.

The arena limit is what keeps even the 240 m configuration inside 512 MB, and it no longer depends on
the start command: `slipday/load.py` applies it when the variable is missing, and the Dockerfile,
`Procfile`, `render.yaml`, `run.sh` and the command above all set it. Two more settings help: at most
two slow computations run at once (`SLIPDAY_MAX_HEAVY`), and freed memory is handed back after each.
A request that only needs stored skylines never waits for those two slots: it
runs in a separate light lane (`SLIPDAY_MAX_LIGHT`, 4 at a time). Slow work queues behind the two slots;
a big job (landing circles, lander classes, the slip-robust list) is refused at once with HTTP 503 and
a Retry-After header when three big jobs are already waiting (`SLIPDAY_MAX_COLD_QUEUE`), a small one (a
card for a new site) when twelve jobs are (`SLIPDAY_MAX_COLD_QUEUE_SMALL`). The page asks again by itself and says so.
`/api/health` reports the lane counters. The memory figures in the table above were measured before
this change and before the scatter skylines (42 MB, memory-mapped) and the 3-D view were added. On
a slow host set `SLIPDAY_FIELD_STRIDE=2` to evaluate every second map point each way (a quarter of the
work).

On the 240 m configuration the numbers are not the validated 80 m ones (the validation panel says so),
the landing scatter is widened to 240 m (the card says so), and the slip map still shows skylines built
from the 80 m grid (the map note says so).

**What the repository carries** (measured 15 Nov 2026 by walking the folder with the `.gitignore` rules:
248 MB in all, MB = 10^6 bytes). The largest single file is `data/dem/ldem_64_south.npy`, 88.5 MB, under
GitHub's 100 MB limit but over its 50 MB warning.

| Folder | Size | What |
|---|---|---|
| `data/dem/` | 152.3 MB | the 240 m, 1.9 km and whole-Moon grids and the 480 m average-sunlight map (the 80 m array is not carried) |
| `data/field/` | 63.4 MB | the stored skylines of the slip-margin map (20.7 MB), the scatter skylines (41.6 MB), the permanent-shadow cut (0.35 MB) |
| `data/horizon_cache/` | 17.0 MB | stored skylines of the curated sites and examples |
| `screenshots/`, `demo/` | 13.4 MB | pictures and the draft video |
| code, tests, page, docs | about 2 MB | |

Not carried, made again by a script: the 80 m array (231 MB, `scripts/fetch_grid80.py`, sha256 checked),
the official downloads in `data/reference/` (1.2 GB) and the 20 m crop in `data/dem20/` (85 MB, by HTTP
range requests, `scripts/fetch_ldem20_crop.py` and `scripts/fetch_ldem20_tiles.py`; it is only needed to
re-run the 20 m checks).

**Container check, written and not run.** `scripts/container_check.sh` (and `.ps1`) builds the image, runs
it under a memory limit (`bash scripts/container_check.sh 1g`), asks for the first screen and one cold
request and prints the peak of the container's memory group. The Docker engine was not started on the
machine this work was done on, so the script has never run and no container figure for the present code
exists.

## Architecture

```
slipday/ephem.py      UTC -> TDB, DE421 positions, lunar orientation, light-time and aberration; cached,
                      size-capped tables of Sun/Earth vectors in the Moon-fixed frame
slipday/dem.py        elevation grids: polar stereographic and global simple-cylindrical, bilinear sampling,
                      a composite that uses the finest grid first; labelled synthetic test surfaces
slipday/demstore.py   which grids are installed (data/dem/dems.json)
slipday/terrain.py    the skyline: 720 azimuths, rays to 300 km, exact spherical geometry, disk cache
slipday/geometry.py   Site, Horizon (smooth sphere | flat mask | terrain profile), azimuth/elevation,
                      visible fraction of the solar disc
slipday/metrics.py    rise/set events, summaries, long-span statistics (in blocks), slip grid
slipday/robust.py     the "how sure" ensemble (13-point landing scatter, never smaller than one grid cell;
                      coarser grid; finer near field), the banded slip grid, the mission card, the landing
                      circles and the slip-robust site list
slipday/why.py        "why it flips": Sun and Earth against the skyline for one landing window, time to
                      sunset and Earthset, and the ground that ends the margin
slipday/field.py      the slip map: every stored skyline against the landing dates, vectorised
slipday/scatterfield.py  the slip map re-checked at 13 touchdown points per coloured cell
slipday/view3d.py     the 3-D view: a patch of the grid, Sun and Earth directions, per-cell shadow
slipday/contrast.py   the Sun at the site beside the Sun at two places on Earth (textbook formula)
slipday/replay.py     real landings offered as worked examples, each with its own need and its source
slipday/refmaps.py    readers for the LOLA reference maps (GeoTIFF, PDS IMG + label, JPEG2000 + label)
slipday/load.py       two lanes: stored answers never wait behind slow work; at most two slow
                      computations at a time with a short queue; memory handed back afterwards; the
                      malloc-arena limit when the start command did not set it
slipday/sites.py      curated sites with sources; terrain or smooth-sphere horizon per site
slipday/hindcast.py   three real landings, predicted with and without terrain
slipday/moonmap.py    shaded-relief polar map (whole cap or close-up) and reference layer
slipday/horizons.py   JPL Horizons API client (off unless SLIPDAY_HORIZONS=1)
slipday/api.py        FastAPI: /api/mission /api/why /api/lander-classes /api/year-ribbon /api/robust-map
                      /api/terrain3d /api/contrast /api/map/shadow /api/finer-grid
                      /api/landing-circles /api/slipgrid /api/slipmap
                      /api/robust-sites /api/pairs /api/replays /api/stats /api/compare /api/series
                      /api/metrics /api/horizon /api/map /api/map/image /api/sites /api/export/*.csv
                      /api/hindcast /api/validation /api/terrain/validation /api/horizons/check
                      /api/health, and the front end
static/               index.html, style.css, app.js, view3d.js + view3d.css (Canvas 2-D, no library),
                      contrast.js, links.js (vanilla JS, hand-built SVG, no external requests; the two
                      links out open QuickMap and Moon Trek only when clicked)
scripts/              fetch_on_your_machine.sh (all official downloads), fetch_grid80.py (the 80 m grid
                      only), fetch_ldem20_crop.py and fetch_ldem20_tiles.py (tiles of the 20 m mosaic by
                      range request), pick_opening_example.py (the rule that chose the opening example),
                      ridge_20m.py (the default example on that grid), build_scatter_field.py,
                      make_draft_video.py, prepare_dem.py, build_field.py, warm_cache.py, validate_terrain.py,
                      validate_more.py, stress_check.py, memory_check.py, compare_horizons.py,
                      fetch_horizons_fixtures.py, ui_check.js, storyboard.js, shot.js
tests/                207 pytest tests
Dockerfile, .dockerignore, Procfile, render.yaml, run.sh, run.ps1
```

How the skyline works: from the site, march outward along great circles in 720 azimuths. The first sample
is one grid spacing out (node to node, the convention of the LOLA team's maps: a grid holds no information
about nearer ground); spacing then grows with distance. A terrain point at central angle theta and radius
R + h, seen from an observer at radius R + ground + mast, has elevation
`atan2((R + h) cos(theta) - r0, (R + h) sin(theta))`; the skyline is the largest value along each ray. The
Sun counts as up when a chosen share of its disc (any part, half, all) is above the skyline at its
azimuth; the Earth when its centre clears the skyline by a chosen margin.

How a verdict is made: the need is checked for the stated point, 12 more points (8 on a 100 m circle, 4 at
50 m), the stated point on the next coarser grid, and the stated point with the first ray sample at half a
grid spacing. All pass: Yes. All fail: No. Otherwise: Not sure, with the reason. The circle is never
smaller than one cell of the grid under the site (points closer together than a cell cannot disagree),
so on the 240 m grid it is 240 m, and the card says it was widened.

How the landing circles are made: touchdown points on eight rings from 50 m to 1 km around the target (up
to 93 points with the target). Each ring stands for the annulus between the mid-radii to its neighbours,
weighted by area, so each figure is the share of the circle's area in which the plan meets the need, with
touchdown equally likely anywhere inside. It is a count on this elevation grid, not a dispersion model.

Measured on a 2-core sandbox (round 3): one skyline 0.16 s; a mission card 0.04 s warm, 2.3 s for a site
never seen (14 new skylines); 4 sites x 60 dates with the scatter band 0.17 s warm; the slip map 4.2 s per
new date and then cached. Measured on a 24-core Windows laptop: the slip map 5.8 s for a new
date and 0.07 s after; the landing circles 0.15 to 0.19 s warm; the slip-robust list 43 s the first time
(180 skylines) and 0.24 s after. Accuracy figures are in LOCAL_PASS_RESULTS.md, REALDATA.md and
TEST_REPORT.md.

## Challenge resources

The challenge page lists four resources. What each one did here:

- **LROC QuickMap** (the Lunar Reconnaissance Orbiter Camera team's online map of the Moon): every site on
  the page has a link that opens the same spot in QuickMap, so you can look at the ground in detail. No data
  is taken from it.
- **JPL Horizons** (NASA JPL's service that gives the position of the Sun, Earth and Moon at any time):
  tables downloaded from it check our Sun and Earth directions, and the page can run a live check against
  it. They agree to 0.00001 degrees.
- **NASA Moon Trek** (NASA's online 3-D Moon viewer): every site has a link that opens the same spot in Moon
  Trek. No data is taken from it.
- **CSA Moon exploration page** (the Canadian Space Agency): background reading only. It holds no data, and
  nothing in the app comes from it.

## NASA data and tools

- **LRO LOLA elevation models** (NASA/GSFC/MIT): LDEM_80S_80MPP_ADJ (PGDA product 90, Barker et al. 2023),
  LDEM_75S_240M and LDEM_16 (PDS LOLA GDR), and the 64 px/deg grid from NASA SVS's CGI Moon Kit. Used to
  ray-cast the terrain skyline at every polar site and map point, and to draw the site map.
- **LOLA average solar visibility maps** AVGVISIB_85S_060M_201608 and AVGVISIB_75S_120M_201608 (LOLA team,
  Mazarico et al. 2011): the reference the terrain model's sunlight is validated against, and a map layer.
- **LOLA average Earth visibility maps** AVGVISIB_85S_060M_201608_EARTH and AVGVISIB_75S_120M_201608_EARTH
  (LOLA team): the reference the Earth-in-view results are validated against (0.97 and 0.69 points mean
  absolute difference at 200 points each, or 1.31 and 1.11 once the points where map and model are both
  exactly 0 or 1 are left out; 1.3 to 2.0 on well-lit ridge pixels over ten random draws of 60, 1.57 on
  the first; all with the any-part-of-the-disc rule their labels state). The mission card counts the
  Earth's centre, a stricter rule that reads 3.5 to 6.4 points below these maps. The matching Sun check
  on ridge pixels gives 3.8 to 5.2 points over the same ten draws, correlation 0.41 to 0.75.
- **JPL DE421** planetary and lunar ephemeris (positions and lunar libration angles), through the `de421`
  and `jplephem` packages: the Sun and Earth directions.
- **JPL Horizons** (https://ssd.jpl.nasa.gov/horizons/): reference tables in `fixtures/` that validate
  those directions (the direct downloads are in `fixtures/raw/`), and the live cross-check.
- **LROC and NSSDCA** pages: coordinates of landed hardware. **USGS/IAU Gazetteer of Planetary
  Nomenclature**: feature centres.
- **NASA's Artemis III site-selection update** (George, Rubio, Lawrence, Curell, LPSC 2026 abstract, NTRS
  20250011660; those regions are now planned for Artemis IV): the nine regions, the 5.75 to 6.25-day stay and the statement that more than one region must
  be kept. **Candidate landing sites: Wueller et al. 2026**, "Assessing Potential Landing Sites With
  Favorable Illumination and Accessible, Potentially Volatile-Rich Permanently Shadowed Regions Within
  Artemis Candidate Landing Regions", JGR Planets 131(3) e2025JE009434, https://doi.org/10.1029/2025JE009434,
  CC BY 4.0; data https://doi.org/10.5281/zenodo.17084058 (`data/regions/wueller2026_sites.json` is written
  from its shapefile by `scripts/build_wueller_sites.py`; only the site names, regions, coordinates and the
  sunlight-day columns are used, their meaning taken from the paper's section 2.3 and the dataset's READ_ME).
- **NASA CLPS press kits** (IM-1, IM-2, Blue Ghost Mission 1) and a NASA article on IM-1's surface science:
  the planned surface durations behind the need of three real-landing examples.

How the files reached this build: the first builds ran in a sandbox that could not reach the NASA hosts
and used untouched copies of the NASA files from public mirrors. On 14 Nov 2026 every file was downloaded again
from its official host (pgda.gsfc.nasa.gov, pds-geosciences.wustl.edu, imbrium.mit.edu, svs.gsfc.nasa.gov,
ssd.jpl.nasa.gov), every recorded sha256 matched, and the working arrays, the 14,400-skyline field and the
stored validation were rebuilt from the official downloads. The rebuilt field is byte-identical to the
earlier one. Addresses, sizes and hashes: LOCAL_PASS_RESULTS.md section 1 and `realdata/lunar/MANIFEST.md`.
Copied from web pages, not byte-exact: published single-point values (Glaser, Bryant,
LROC), landing times, and the press-kit sentences.

Other sources: Glaser et al. 2014 and 2018, Bryant 2009 (published illumination and Earth-visibility
figures used for validation); mission event reports for the hindcast (URLs in `slipday/hindcast.py`); the
IM-2 landing time from its Wikipedia page; ISRO's Chandrayaan-3 page (mission life). Python packages:
FastAPI, Uvicorn, NumPy, Pillow, jplephem, de421, tifffile, imagecodecs, pytest, httpx.

Licence: Apache-2.0 (`LICENSE`). NASA data carries no copyright; credit lines are in REALDATA.md.

## Use of AI tools

`[PARTICIPANT TO WRITE: statement of AI use]`

This placeholder is for the participant, who knows which tools were used and for what. The 2026 rules ask
for AI use to be acknowledged in the project itself, so replace it before the repository is made public.
