# Submission draft

How to use this file. It has two parts, and only the first is meant for the project page:

1. **Text for the form**: from "Project name" down to the line `END OF TEXT FOR THE FORM`. Each heading
   is one field. Anything in square brackets, such as `[PUBLIC LINK TO THE DEMO]` or
   `[PARTICIPANT TO WRITE: statement of AI use]`, is a placeholder the participant must replace; nothing
   in square brackets may be pasted as it stands.
2. **NOT FOR PASTING: notes for the team**, at the very end of the file, inside a fence of `=` signs.

Field names follow the previous cycle's submission guide (the 2026 guide was not readable when the
challenge notes were compiled); check them against the live form. Numbers are from this build on the real
LOLA grids, measured on 14 Nov 2026 on files downloaded directly from the NASA hosts
(LOCAL_PASS_RESULTS.md and LOCAL_PASS_2_RESULTS.md have every number with the command that produced it;
REALDATA.md and TEST_REPORT.md have the earlier ones).

## Project name

Slipday

## High-level summary

NASA says it must keep more than one south-pole landing region open for the first crewed landing, now
Artemis IV (early 2028). Slipday measures why: on the candidate sites published for NASA's nine regions, the
best single region works at 26 % of landing times from 2027 to 2030, the best three together at 37 % (the Sun
up for a 6.25-day stay plus an illustrative 100 hours of Earth contact; landing times every 6 hours, not real
launch opportunities). IM-1, replayed: its seven-day plan had one day of slip to spare. VIPER at Mons Mouton:
a one-week slip leaves 14 of 124 good landing times (the page's illustrative default need).

Slipday answers the question a lunar mission team asks when its launch date moves: can we still land at
our site, how many days can we slip, and when is the next good date. The page opens on a map of the lunar
south pole. Click a site (or search one), pick a date and time, and it draws the Sun and the Earth against
the real terrain skyline, ray-cast from NASA's LRO LOLA elevation data on the finest grid that covers the
place. Below that, one decision path in four steps (Answer, How sure, Why, What to do) gives a plain Yes,
Not sure or No, the number of days the launch can slip, the ground that ends the margin, and the options:
wait for a later good date or move to another site. A "Yes" has to be earned: the same question is asked
at 13 touchdown points around the target and on more than one grid, and the answer is Yes only when all
agree. The page also compares up to four sites side by side, maps how many days of slip each spot near the
pole survives, checks the slope and the chance of a safe touchdown, counts what a relay satellite would
add, and follows the real missions planned for the next two years.

## Link to project demo

`[PUBLIC LINK TO THE DEMO: a 30-second video or 7 slides, viewable without sign-in]`

## Link to final project

`[PUBLIC LINK TO THE PROJECT: repository or hosted app, viewable without sign-in]`

## Detailed description

**What it does**

Every number below is for the example the page opens on (a ridge point at 89.010 S, 122.764 E, landing
18 Nov 2026, needing 240 sunlit hours and 100 hours of Earth contact in 14 days) unless another site is
named, on NASA's LOLA terrain at the finest grid that covers the place: 5 m site models at two places near
Shackleton, the 20 m mosaic out to 80° S, 80 m beyond. The page names the grid beside every answer ("on 5 m
terrain").

- **Map first: the Sun and the Earth over the real skyline.** The first screen follows the challenge's own
  steps. Step 1: click the south-polar map or search a site (or type coordinates). Step 2: pick a date and
  time. Step 3: read the chart: the Sun's and the Earth's paths against the 360-degree terrain skyline, with
  a time slider, a table of their heights and directions, and a sky view of what you would see standing
  there. For the example: "Sun 2.3° high, 1.0° over the skyline; Earth -0.2° high, 0.6° over the skyline".
  A 3-D view shows the ground with its shadows at the chosen time.
- **One decision path: Answer, How sure, Why, What to do.**
  - *Answer*: landing 18 Nov works, and the launch can slip up to **8 days**, if the lander touches down
    within 100 m of the target.
  - *How sure*: 13 of 13 touchdown points within 100 m pass on 5 m terrain, and the next coarser grid (20 m)
    and a finer sampling of the nearest ground agree; the slope; the chance
    of a safe touchdown. All pass: Yes. All fail: No. Otherwise Not sure, with the reason.
  - *Why*: a slip of 9 days fails on Earth contact, not sunlight: the Earth goes behind ground 131.4 km
    away to the west-south-west and leaves 95 of the 100 hours needed. The page says this need is an
    illustrative figure, not a published requirement.
  - *What to do*: the real options, ranked, with their verdicts, slip margins and distances: wait for a
    later good date, or move to another south-pole site. It also names the real missions facing this
    choice soon: VIPER on Blue Moon MK1 lands at Mons Mouton by late 2027, 167 km from this site.
- **Monthly launch windows, as real slips move.** A south-pole lander's launch window is a few days each
  month, built so that the landing falls at the right time of the lunar day (Intuitive Machines on IM-1:
  "each month has a window around three to six days"); we infer (no source says so) that missing it moves
  the landing about one synodic month. For the example: "Dec 17 ✓ 6 d · Jan 16 ✕ sunlight · Feb 14 ✕ Sun
  down, sunlight": January and February fail on sunlight (217 and 148 hours against 240 needed), the polar
  season, while Earth contact stays above the 100 hours needed. A year of landing dates in one ribbon: 39
  clear-yes dates of 365 and 4 not sure, and none at all from January to August 2027.
- **Compare sites side by side.** Up to four sites in one table, each with its number (the same as its
  marker on the map) and the best value in each row shaded: verdict, slip margin, hours, darkness and
  Earth gaps, sunset and Earthset times, slope, next good dates, a per-day strip and a small skyline. One
  "launch slipped by N days" control applies to every column. Ready-made comparisons: the worked example, a
  ridge against a crater floor, Apollo 11 against the pole, IM-1 as flown, a week's slip.
- **The slip-day map, whole map and close-up.** How many days of slip a plan survives at each spot.
  - *Whole map*, from 80° S to the pole, a point every 2 km (92,416 points, each checked at its own spot):
    for the example plan 95.4 % cannot land on the planned date, 84 points survive 5 days of slip or more,
    and the largest margin is 8 days.
  - *Close-up* of the pole, 14,400 points 500 m apart, every coloured point re-checked at 13 touchdown
    points: 733 points pass at the point itself; 574 still pass at all 13 on the planned date and 159 lose
    it; 343 survive at least one day of slip. Re-checked on NASA's 20 m grid, 639 of the 733 (87.2 %) give
    the same answer; the 94 that differ are marked with a red cross. A layer marks permanent shadow: 20
    points survive a slip beside at least 10 hectares of it (dark ground, not proven ice).
- **Is it safe to land there?** *Flat enough to land?* gives the slope at the 13 touchdown points against
  NASA's limit for its crewed lander (it may stand at most 8 degrees from upright; 5 is the goal): 4.9
  degrees at the example on 5 m terrain, just inside the goal. *Chance of a safe touchdown* gives the chance
  the ground under the lander is under 8 degrees for three assumed lander accuracies: 100 % for a
  precision lander, 93.7 % for a CLPS-class lander and 82.9 % for an unguided one (slope only, no boulder
  data; each accuracy is sized from one published figure and labelled as an assumption). *How precise must
  the landing be?* shows what a less precise landing does to the answer.
- **Talking to Earth.** An hour of Earth contact counts only when the Earth is above the skyline and one of
  NASA's three Deep Space Network complexes has the Moon at least 10 degrees up (DSN handbook 810-005; checked
  against JPL Horizons to 0.0006 degrees): Goldstone 104 hours of the first 14 days, Madrid 122, Canberra
  85. *Relay satellites*: with the Earth alone, 311 hours of contact in 14 days; with two relays on a
  representative NASA orbit (the LCRNS reference design, not a live service), 336 of 336.
- **Real missions ahead.** A missions board for Griffin-1 (late 2026), IM-4 (2027), VIPER on Blue Moon MK1
  (landing by late 2027, at Mons Mouton) and Artemis IV (early 2028, NASA's nine candidate regions): for
  each, how many of the good landing times in its period survive a week's slip and a month's slip, at the
  published candidate sites of its region. VIPER: 14 of its 124 good landing times survive a week's slip,
  102 a month's. Places and periods are NASA's published ones; the landing times are spread over the
  period, not the missions' own plans.
- **NASA's nine south-pole landing regions.** NASA keeps nine candidate landing regions, chosen for the
  first crewed landing (now planned for Artemis IV, early 2028), and says that "more than one landing
  regions must be maintained" (George et al., LPSC 2026 abstract, NTRS 20250011660). On the 78 candidate
  sites that Wueller et al. 2026 (JGR Planets 131, e2025JE009434, CC BY 4.0) published in those regions,
  at landing times every 6 hours from 2027 to 2030, each with the 13-point check: with sunlight alone, the
  best single NASA region allows a 6.25-day stay at 45 % of landing times, the best three at 89 %. With the
  illustrative 100 hours of Earth contact added: 26 % and 37 % (all nine: 40 %). About 3 in 10 of the 312
  site comparisons with the paper's own sunlight figures differ by more than 3 days. As a check of the
  geometry, our ephemeris gives the paper's midsummer dates to the day, and the season moves 18.65 days
  earlier each year against 18.63 expected from the 346.6-day eclipse year. The shares count landing times, not real launch opportunities. For the example plan, 7 of the 9 regions have a clear-yes landing within three days of the
  December window (6 of them not fragile), 6 in January (5 not fragile) and 5 in February (4 not fragile);
  Peak near Cabeus B and Slater Plain have none in any of the three. A calendar shows the nine regions
  across the four years, and the *atlas* runs the same check for 2027 to 2035.
- **Real landings as worked examples** (IM-2 Athena, IM-1 Odysseus, Chandrayaan-3, Blue Ghost Mission 1)
  at their real sites and landing hours. IM-1 planned about seven days on the surface: with that need (168
  sunlit hours) the card says Yes with one day of slip margin, on NASA's 20 m terrain; with the roughly ten
  days in NASA's press kit (240 hours) it says No, because terrain leaves 207 sunlit hours. Chandrayaan-3's
  published mission life of 14 days would give No. Earth-contact figures are illustrative in every example.
  These are replays of published plans, not a confirmation of the model.
- **Be the mission planner.** A five-scenario game for students (a small slip, a slip past the 8-day
  margin, the IM-1 replay, a south-pole site choice, a low-Sun January): a briefing, three or four options
  to inspect (skyline, hours, slope, next window, relay), the real outcome with its reason, and a stated
  scoring rule. *Listen* plays the landing window as sound; *Not like Earth* puts the same days at home
  beside the site.
- Slip grid (up to four sites by 30 to 90 landing dates), CSV and JSON exports, and a link that reopens
  any scenario.

**How it works**

The whole-map layer is 92,416 terrain skylines, 720 rays each out to 300 km, on four LOLA grids (80 m to
1.9 km); once an answer is worked out it comes back in 0.04 s. Sun and Earth directions come from the JPL DE421 ephemeris with lunar librations. The skyline is found by
marching 720 rays to 300 km across LOLA grids on the curved Moon; the Sun is treated as a disc. Everything
is computed locally in one Python process. Measured on a laptop: the browser reaches network idle in
about 3 s on a warm server (about 12 s on the first visit after a restart, while the map is worked out);
the slip map with its 13-point re-check takes about 11 s for a new date and 0.03 s after; the
slip-robust list takes 43 s the first time (180 skylines) and 0.2 s after. Answers that are already
worked out do not wait behind slow ones: the first screen's card answered in 0.04 to 0.06 s while twelve
slow requests from other visitors were in flight.

**How we know how far to trust it**

- **A finding of our own: coarse terrain is optimistic, not noisy.** Over 14 weekly dates, 452 of the 454
  points where 80 m and 20 m terrain disagree are called landable on 80 m and rejected on 20 m. At the
  Shackleton ridge, the longest darkness is 194 h on 80 m, 110 h on 20 m, and 112 h published. The finer 5 m
  grid covers only two sites (the opening example and the Shackleton ridge).
- Every answer names the NASA terrain grid it used, and is checked against the LOLA team's own maps: sunlight
  within 0.8 points on ordinary terrain, Earth view within 0.97 points.

- Sun and Earth directions agree with JPL Horizons to 0.00001 degrees (218 stored reference rows,
  downloaded directly from JPL; a live check on 14 Nov 2026 gave the same over 164 more rows).
- **Sunlight.** The share of time with any Sun agrees with the LOLA team's own published illumination
  maps to 0.8 percentage points on average at 200 random polar points on each of the two maps, 60 m and 120 m (correlation 0.992 and 0.995; a
  flat horizon is off by 21 to 33 points). That figure is for ordinary terrain. On well-lit ridge pixels,
  where landers would go, it is 3.8 to 5.2 points over ten random draws of 60 pixels (4.0 on the first),
  with a correlation of only 0.41 to 0.75. The page shows both.
- **Earth in view.** Against the LOLA team's Earth-visibility maps at the same 200 points on each map, using the rule
  the maps' own labels state (any part of the Earth's disc above the skyline): 0.97 points mean absolute
  difference, correlation 0.995, on the 60 m map, and 1.31 points (correlation 0.990) once the 53 points
  where the Earth never rises on either side are left out; 0.69 points, correlation 0.998, on the 120 m
  map, and 1.11 without 76 such points; 1.3 to 2.0 points on well-lit ridge pixels (ten draws of 60;
  1.57 on the first). The mission card itself uses a stricter rule (the Earth's centre), which has no
  published reference of its own and reads 3.5 to 6.4 points below these maps.
- At the best-known ridge site (Shackleton connecting ridge, 2 m above ground) the model gives the
  published 92.1 % of time with Sun at the published point, and 72.5 to 92.5 % within 100 m of it. The
  page shows the range instead of the single match.
- **Finer terrain.** Each answer is computed on the finest LOLA grid that covers the place: the LOLA
  team's 5 m site models at two places near Shackleton, NASA's 20 m mosaic out to 80° S, 80 m beyond. The
  opening example is Yes with 8 days on 5 m, 20 m and 80 m alike. The best-known ridge site, the Shackleton
  connecting ridge, is not: the 80 m grid alone would say Yes, but on the 5 m site model the planned date is
  "Not sure" (12 of 13 touchdown points pass) and slips of 1 to 7 days are Yes. The 20 m check brings the
  longest darkness at the published ridge point to 110 hours, against the published 112 (194 on 80 m).
- All LOLA files were downloaded from pgda.gsfc.nasa.gov, pds-geosciences.wustl.edu, imbrium.mit.edu and
  svs.gsfc.nasa.gov, and their sha256 values are recorded.

**What it does not do**

It computes on the finest LOLA grid that covers each piece of ground: 5 m site models at two places near Shackleton,
20 m out to 80° S, 80 m and coarser beyond. Ground slope is checked against NASA's lander-tilt limit only where 5 m or 20 m terrain
covers the site (the 80 m grid is too coarse for slope), with no boulder data; it does not model power or temperature; longest-darkness figures on ridge crests are indicative only;
the "how sure" check and the landing circles test stability against landing position and grid resolution,
not errors in the topography itself; the circles are area counts and the three lander classes are
assumed Gaussians, not a dispersion model of any lander. Where the ground that ends a margin is one grid
cell away, the page says so and names no ridge. The slip margin of the example is set by its Earth-contact
need, and that need (100 hours) is illustrative; the card says so. The example is good for two landing
windows in the next two months and then for none from January to August 2027. A "Yes" holds for the
stated landing scatter and no further. The Earth margin of the example is thin (0.6 degrees over the skyline at touchdown) and no published link mask was found to judge it by. The 20 m checks exist for the two stored examples, for 14 weekly dates of the map, and for any other map date when the stored 20 m skylines are installed (worked out on request in about 10 to 20 seconds). The opening date, 18 Nov 2026, is a fixed example: after it the page opens on a date in the past, and the card says why.

**Who it is for**

Mission and payload planners who need a fast answer after a schedule change, and educators or the public
who want to see, with real missions, why a few days matter at the lunar south pole.

**Tools**

Python (FastAPI, NumPy), vanilla JavaScript and SVG. Apache-2.0.

## NASA data

- LRO Lunar Orbiter Laser Altimeter (LOLA) south-pole elevation mosaic LDEM_80S_80MPP_ADJ, NASA GSFC
  Planetary Geodesy Data Archive (Barker et al. 2023), from pgda.gsfc.nasa.gov: ray-cast into the terrain
  skyline for every polar site and for the 14,400 map points; also drawn as the shaded-relief map.
- LOLA gridded data records LDEM_75S_240M and LDEM_16 (PDS Geosciences Node, LRO-L-LOLA-4-GDR-V1.0) and the
  64 px/deg LOLA grid from NASA's Scientific Visualization Studio CGI Moon Kit: terrain beyond the edge of
  the 80 m mosaic and at lower latitudes, and the coarser grids of the resolution comparison.
- LOLA average solar visibility maps AVGVISIB_85S_060M_201608 and AVGVISIB_75S_120M_201608 (LOLA team,
  method of Mazarico et al. 2011), from pgda.gsfc.nasa.gov: the reference our sunlight results are checked
  against; shown as a map layer.
- LOLA average Earth visibility maps AVGVISIB_85S_060M_201608_EARTH and AVGVISIB_75S_120M_201608_EARTH
  (LOLA team), from imbrium.mit.edu: the reference our Earth-contact results are checked against.
- LOLA south-pole elevation mosaic LDEM_80S_20MPP_ADJ (20 m), same archive: the whole mosaic, 80° S to the
  pole. The page computes on it everywhere south of 80° S, under the 5 m site models.
- LOLA 5 m site models of two places near Shackleton (LOLA team, pgda.gsfc.nasa.gov): the finest terrain the
  page uses, at the opening example and the Shackleton connecting ridge.
- JPL DE421 planetary and lunar ephemeris: positions of the Sun, Earth and Moon and the Moon's libration.
- JPL Horizons: reference azimuth/elevation tables used to validate the geometry, and a live cross-check.
- LROC and NSSDCA landing-site coordinates (Apollo, IM-1, IM-2, Blue Ghost Mission 1 and others).
- NASA CLPS press kits for IM-1, IM-2 and Blue Ghost Mission 1, and a NASA article on IM-1's surface
  science: the planned surface durations used as the need of the real-landing examples.

Source addresses, sizes and sha256 values of every downloaded file: LOCAL_PASS_RESULTS.md, section 1,
and LOCAL_PASS_2_RESULTS.md, "New downloads".

## Space agency partner and other data

- USGS/IAU Gazetteer of Planetary Nomenclature: feature centres (public domain).
- ISRO: Chandrayaan-3 mission life ("one lunar day") from isro.gov.in; statements on the mission as
  reported by SpacePolicyOnline; Chandrayaan-3 site per LROC.
- Landing times of IM-1, IM-2, Chandrayaan-3 and Blue Ghost Mission 1 from Wikipedia and Spaceflight Now
  (URLs in `slipday/replay.py` and `slipday/hindcast.py`). These pages, the press kits and the published
  single-point values were copied from the web pages, not byte-exact copies.
- Published results used for validation: Glaser et al. 2014 (EPSC2014-136) and 2018 (PSS 162); Bryant 2009
  (JPL IPN Progress Report 42-176).
- Open-source software: FastAPI, Uvicorn, NumPy, Pillow, jplephem, de421, tifffile, imagecodecs, pytest
  (their own licences). Project code: Apache-2.0.
- LROC QuickMap and NASA Moon Trek: linked from every site (the same place opened in those tools); no
  data is taken from them.
- JAXA press release of 25 Jan 2024 ("pinpoint landing within an accuracy of 100m", SLIM) and ISRO's
  Chandrayaan-3 details page ("Landing Site (Prime) 4 km x 2.4 km"): the figures behind two of the three
  assumed landing dispersions; the third is NASA's news release of 7 Mar 2025 on IM-2 ("about 820 feet
  from the intended landing site"). Each was read first-hand on 15 Nov 2026 and is linked on the page.
- CSA Moon exploration page: background reading only (see Challenge resources below).

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

## Use of artificial intelligence

`[PARTICIPANT TO WRITE: statement of AI use]`

END OF TEXT FOR THE FORM

```
==========================================================================================
NOT FOR PASTING: notes for the team. Nothing below this line belongs on the project page.
==========================================================================================
```

### The statement of AI use is yours to write

The field above is left empty on purpose. The 2026 rules ask for AI use to be acknowledged in the project
itself (COMPLIANCE_CHECK.md rows 16 and 17): say which tools were used and for what, in your own words,
in that field and in the README section "Use of AI tools", which carries the same placeholder.

### Where the demo material is

- 30-second video: demo/slipday_draft_voiceover.mp4 (29.5 s, recorded from the live page on 15 Nov 2026,
  with a voice-over and captions; every caption number is on screen at that moment) and demo/STORYBOARD.md
  (the seven steps, captions and timings). `[TEAM NAME]` is still in its last caption.
- Explainer video: demo/slipday_explainer.mp4, and docs/EXPLAINER.html.
- 7 slides: demo/SLIDES.md. Slide 1 and the last caption carry `[TEAM NAME]` and `[MEMBER NAMES]`
  placeholders.

### Which grid the public link must serve

Every example in this draft, the storyboard and the slides is computed on the **live terrain stack**
(`data/dem_live/dems.json`, made by `python scripts/build_live_stack.py`): the 5 m site models, the full
20 m mosaic (`data/dem20/ldem_80s_20m_f32.npy`, 3.7 GB on disk, memory-mapped, made by
`build_live_stack.py --convert` from NASA's 20 m GeoTIFF), and the 80 m grid and coarser beyond. The map
also needs `data/field/scatter_el_i16.npy` (42 MB) for its 13-point re-check. Check before submitting: the
verdict reads "on 5 m terrain" at the opening example, and `/api/mission` gives `terrain_grid`. A server
with the 80 m grid alone gives the same opening answer (Yes, 8 days) but other figures in this draft
(the Shackleton ridge, the IM-1 hours, the region shares) differ; a server with only the 240 m grid widens
the landing scatter to one grid cell and reads "Yes, 7 days" for a landing within 240 m.

Memory with the full 20 m mosaic was not measured under a container limit: the file is memory-mapped, so
only the pages read stay in memory, but measure before choosing a host. The figures below are for the 80 m
grid alone.

Memory the 80 m grid needs. **These figures are from the first local pass and belong to the code as it
was then.** The second pass added a 42 MB memory-mapped file, the 3-D view and a different way of queueing
slow requests, and the Docker engine was down, so nothing below was re-measured: measure again before
choosing a host. Measured on 14 Nov 2026 (first pass) in Linux containers on one machine (Docker Desktop,
two CPUs, `MALLOC_ARENA_MAX=2`, the load test of `scripts/stress_check.py`, 205 requests, all answered):

| Memory limit of the container | Peak of the container's memory group | Killed by the kernel |
|---|---|---|
| 512 MB | 431 MB | no |
| 768 MB | 433 MB | no |
| 1 GB | 421 MB | no |

So the 80 m grid ran inside 512 MB here, with about 80 MB to spare; 768 MB or 1 GB leaves real room and
is the safer choice if the host offers it. The image with the grid is 1.33 GB on disk. Not measured: any
hosting provider (a plan's "512 MB" may be counted differently from a Docker memory group), and a host
with a fraction of a CPU, where the first slip map of a date and the landing circles of a new site will
take much longer than the seconds measured here. The arena limit must be on (the Dockerfile sets it and
the code applies it if a start command does not): without it even the 240 m grid was killed at 512 MB.
Nothing has been deployed yet; this is the choice to make before the link goes on the page.
