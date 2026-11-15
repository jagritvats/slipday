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

Slipday answers the question a lunar mission team asks when its launch date moves: can we still land at
our site, how many days can we slip, and when is the next good date. For a site, a landing date and a need
(hours of sunlight for power, hours with the Earth above the skyline for a direct radio link) it gives a
slip margin in days and a plain Yes, Not sure or No for every day of slip, on a skyline ray-cast from
NASA's LRO LOLA elevation data. A "Yes" has to be earned: the same question is asked at 13 touchdown
points around the target, on a coarser terrain grid and with a finer sampling of the nearest ground, and
the answer is Yes only when all agree. Click a day of slip and the page draws the Sun and the Earth
against the terrain skyline for that landing, with the time left to sunset and Earthset and the ground
that ends the margin. It then shows what a less precise landing would do to the answer, the ground in
3-D with its shadows, and a map of where near the pole a slip hurts least.

## Link to project demo

`[PUBLIC LINK TO THE DEMO: a 30-second video or 7 slides, viewable without sign-in]`

## Link to final project

`[PUBLIC LINK TO THE PROJECT: repository or hosted app, viewable without sign-in]`

## Detailed description

**What it does**

- **A slip margin in days.** Mission card: site, landing date and hour, sunlit hours and Earth-contact
  hours needed. Output: Yes / Not sure / No, the number of days the landing can slip, a strip with one
  verdict per day of slip, the next three good dates, and what a flat-horizon model would have answered.
  Example (the one the page opens on): a ridge point at 89.010 S, 122.764 E, landing 18 Nov 2026, needing
  240 sunlit hours and 100 hours of Earth contact in 14 days: Yes, and the plan survives a slip of up to
  8 days if the lander touches down within 100 m of the target. NASA's 20 m grid gives the same answer
  for it (13 of 13 touchdown points, 8 days), and the page says so under the verdict. It is the
  first of the map's scatter-robust points whose card is a clear Yes on both grids.
- **A verdict that needs an ensemble to agree.** Thirteen touchdown points within the landing scatter,
  the next coarser grid, and a finer near-field sampling. All pass: Yes. All fail: No. Otherwise Not
  sure, with the reason ("12 of 13 points within 100 m pass").
- **Why it flips: the Sun and the Earth against the horizon, on the first screen.** Click any day of the
  strip and the Sun's and the Earth's paths through that landing window are drawn against the
  360-degree terrain skyline, with their height at touchdown, the time left to sunset and Earthset, and
  a sentence naming what ends the margin and which need does it. In the example, day 9 fails on Earth
  contact, not sunlight: the Earth sets behind high ground 131.6 km away and leaves 95 of the 100 hours
  needed; the card adds that this need is an illustrative figure, not a published requirement. For IM-1
  the sentence names ground 4.7 km to the west that the Sun sets behind, and the need there is the
  mission's published plan.
- **A year of landing dates in one ribbon.** For the example: 41 clear-yes dates of 365 and 3 not sure
  as the page opens (with the station rule on; 42 and 2 without it), and none at all from January to August 2027.
- **What a less precise landing does to the answer.** The chance that the plan holds for three assumed
  landing dispersions (a precision lander, a CLPS-class lander, an unguided one), for each day of slip,
  each with a range: 100 %, 87 % (80 to 94) and 77 % (70 to 85) on the planned date of the example; at
  the knife-edge Shackleton connecting ridge 100 %, 35 % (29 to 43) and 17 % (12 to 24). The three
  dispersions are assumptions sized from one published figure each (JAXA, NASA, ISRO; linked on the
  page) and are labelled so. Without any assumed dispersion: the share of a 100 m, 250 m, 500 m and 1 km
  circle where the plan holds: 100 %, 97 %, 83 % and 81 % at the example; 100 %, 62 %, 27 % and 13 % at the
  connecting ridge; 100 %, 100 %, 100 % and 96 % at the IM-2 site. IM-2 itself came down about 250 m from
  its target.
- **How thin the Earth margin is.** The card says how far the Earth's centre clears the skyline at touchdown and up to which link mask the Yes holds. For the example: 0.64 degrees, and the Yes holds up to a mask of 0.60 degrees (Not sure from 0.65, No from 0.70); the planned date is the thinnest of its nine yes-days. No published elevation mask for a direct-to-Earth link from the lunar surface was found, so every non-zero mask is labelled illustrative.
- **Where you can land beside permanent shadow and still survive a slip.** The scatter-checked map crossed with ground that never sees the Sun (the zero cells of the LOLA team's 60 m average-sunlight map). A point qualifies with at least 10 hectares of permanent shadow within 1 km, all 13 touchdown points keeping at least one day of slip margin, and the point itself not on shadowed ground. For the example's dates 20 map points qualify (7 more stand on shadow and are listed apart); none keeps 5 days. The best, 89.572 S, 19.134 E, keeps 4 days with 10.4 ha of permanent shadow within 1 km, the nearest 221 m away. Permanent shadow is where it is dark, not where ice is: no ice data is used.
- **Earth contact as real station visibility.** An hour of Earth contact counts only when the Earth is above the skyline and one of NASA's three Deep Space Network complexes has the Moon at least 10 degrees up (the low-power transmit limit in the DSN Telecommunications Link Design Handbook 810-005, module 301; station coordinates from its Table 5; checked against JPL Horizons to 0.0006 degrees). For the example Goldstone carries 104 hours of the first 14 days, Madrid 122 and Canberra 85, with no hour lost; over one 18.6-year cycle the hours with no complex in view stay between 0.3 and 1.5 %. The card's verdict and margin do not change under this rule (Yes, 8 days, on both grids).
- **Artemis III regions as options.** NASA keeps nine candidate regions so that a launch date can be matched to a region. NASA names the regions but publishes no points, so each region here is the set of candidate landing sites published by Wueller et al. 2026 (5 to 11 per region, 78 in all), not NASA's own sites; they replace one point per region that we had picked ourselves. For the opening plan, 8 of the 9 regions have a clear-yes landing within three days of the December window (6 of them not fragile), 6 in January (5 not fragile) and 5 in February (4 not fragile). Slater Plain has none in any of the three.
- **How many regions must stay open.** NASA's Artemis III site team writes that "individual regions typically provide limited viable opportunities when all constraints are simultaneously satisfied" and that "more than one landing regions must be maintained" (George et al., LPSC 2026 abstract, NTRS 20250011660). A separate panel puts numbers on this with open data: the 78 candidate landing sites that Wueller et al. 2026 (JGR Planets 131, e2025JE009434, CC BY 4.0) published in NASA's nine regions.

  How it is checked: at landing times every 6 hours from 2027 to 2030, each site gets the card's 13-point check for a 6.25-day stay (the top of NASA's "approximately 5.75 to 6.25 days"). The Sun must be up for the whole stay, with 100 hours of Earth contact and the Sun and the Earth in view at touchdown. A region is open when at least one of its sites is a clear Yes that is not fragile. Fragile results are counted apart.

  What it shows, on the 80 m grid: the best single region (Nobile Rim 1) is open at 28 % of the landing times, the best two at 37 %, the best three at 40 % and all nine at 44 %. With sunlight only, the figures are 48 %, 75 %, 91 % and 92 %. The 44 % ceiling comes from the 100-hour Earth-contact need, which is an illustrative figure. The shares count landing times, not real launch opportunities. Regions are added one at a time, each time the one that covers the most new landing times, and trying every set gives the same answer. A calendar shows the nine regions across the four years.

  How far to trust it: our ephemeris gives the paper's midsummer dates to the day for 2025 to 2032, and the season comes 18.4 days earlier each year on average (18.6 expected from the 346.6-day eclipse year). Against the paper's own sunlight figures, about two in three of 312 comparisons agree within a day, and about three in ten differ by more than 3 days, nearly always with ours longer. Our terrain model (80 m) is coarser than the paper's (60 m), so the shares may be too high; finer terrain would give fewer opportunities.
- **Extra checks beside the main answer.** Five add-ons sit below the card; none changes its verdict. *Flat enough to land?* gives the slope at the 13 touchdown points against NASA's limit for its crewed lander (it may lean at most 8 degrees; 5 is the goal). At the opening example the steepest point is about 5 degrees on 5 m terrain, right at the goal: moving it by one 5 m cell gives 4.4 to 5.8 degrees, and NASA's own slope maps are uncertain by about 2 degrees. IM-1's target reads 12.2 degrees, too steep, where IM-1 tipped over. *Chance of a safe touchdown* gives the chance the ground under the lander is within 8 degrees for three assumed lander accuracies (over 99.9 %, 94 % and 83 % at the opening example; slope only, no boulder data). *Relay satellites* counts the hours a relay circling the Moon could add, on a representative NASA orbit that is not a live service (311 hours with the Earth alone, 336 of 336 with two relays). *Which years suit a landing, 2027 to 2035* runs the region check for nine years. *Listen* plays the landing window as sound, and *Be the mission planner* is a short game for students.

- **Next launch windows, as real slips move.** A south-pole lander's launch window is a few days each month, built so that the landing falls at the right time of the lunar day (Intuitive Machines on IM-1: "each month has a window around three to six days"); we infer (no source says so) that missing it moves the landing about one synodic month, to the same time of the lunar day.

  Under the strip the card says what the next three windows give and which need fails: for the example, "Dec 17 ✓ 6 d · Jan 16 ✕ sunlight · Feb 14 ✕ Sun down, sunlight": January and February fail on sunlight (217 and 151 hours against 240 needed), the polar season, while Earth contact stays above the 100 hours needed.

  One click shows the other options: in January no landing hour within three days works at the example, but 13 of the 20 other sites checked have a Yes hour within three days, 11 of them fragile. The card leads with the steadiest: a map point at 89.498 S, 137.663 W, landing 15 Jan 13:00 with 4 days of margin. The Shackleton ridge C1 also has January Yes hours, all fragile: its 14 Jan 01:00 landing reads 5 days in our model, but two touchdown points sit within 0.08 degrees of the skyline (one at touchdown, one on the second day of slip), and a separate calculation puts the second one just below it, which gives 1 day.

  A real-missions panel judges IM-1's windows (at the same time of the lunar day, a modelled January landing would also have been Yes with one day of margin; across the January window IM-1 published, landings from 21 Jan are Yes and 17 to 20 Jan No, before local sunrise) and VIPER's late-2027 windows on an illustrative point of Nobile crater's west rim (landing at local sunrise, an assumption: every window No, the Earth below the skyline at touchdown; next clear yes 31 Dec 2027). Sources read first-hand are cited on the page.
- **Hours to ride through, for every day of slip.** For each day the landing could slip to, the longest night
  (the Sun down by the card's own rule) and the longest Earth outage the lander meets: whole runs that are under
  way at touchdown or begin inside the mission window, counted to their end, at the worst of the 13 touchdown
  points. For the example: slip 8 days and the night the lander meets grows from 20 to 179 hours, because the
  window then runs into the lunar night; the Earth outage it meets is 323 hours on every passing day. No map of these
  hours is drawn: at 556 of 574 map points the worst passing night is the full lunar night. Hours, not a
  battery model; the run-length code reproduces the existing longest-darkness figures at the Shackleton ridge
  (194 h on 80 m, 110 h on 20 m against a published 112 h).
- **A slip-margin map that carries the landing scatter.** Within 30 km of the pole, the days of slip a
  plan survives at each of 14,400 points 500 m apart, computed for the dates and need on the card, with
  every coloured point re-checked at 13 touchdown points. For the example 733 points pass at the point
  itself; 574 still pass at all 13 touchdown points on the planned date (a margin of 0 days or more) and 159 lose it; 343 of the 574 survive at least one day of slip; a margin of 5 days or more
  survives at 18 points. Re-checked on NASA's 20 m grid, 639 of the 733 points (87 %) give the
  same answer and all 94 that differ lose their margin on 20 m; the page marks them with a red cross. Over 14
  weekly map dates to 17 Feb 2027 the share is 72 to 89 % on the 7 dates with any passing point (86.6 % in
  all), and 452 of the 454 disagreements are the 80 m map being optimistic. One button re-checks the 12 best points with the coarser grid and the near-field
  sampling as well: 5 of them stay a clear Yes.
- **The real ground in 3-D.** The LOLA terrain around the site at true scale, with the directions to the
  Sun and the Earth and the shadows at the chosen time, stepping through the landing window; permanent
  shadow on the map; links from each site to LROC QuickMap and NASA Moon Trek.
- **Not like Earth.** Over the 60 days from the landing the Sun at the opening example never climbs above
  2.4 degrees; the terrain hides it seven times, once for 206 hours. At the same latitude on Earth it
  would stay 18 to 24 degrees up without setting, and a town at 45 degrees north sees 60 sunrises.
- **Four real landings as worked examples** (IM-2 Athena, IM-1 Odysseus, Chandrayaan-3, Blue Ghost
  Mission 1) at their real sites and landing hours, each with its own need where a planned surface
  duration was published. IM-1 planned about seven days on the surface: with that need (168 sunlit hours)
  the card says Yes with one day of slip margin; with the roughly ten days in NASA's press kit (240
  hours) it says No, because terrain cut the sunlight in the window to 208 hours. The page shows both.
  Blue Ghost planned a full 14-day lunar day: Yes, with no slip margin at all. Chandrayaan-3's need on
  the card (240 sunlit hours) is illustrative and gives Yes; its published mission life of 14 days would
  give No. Earth-contact figures are illustrative in every example and the page says so. These are
  replays that show how the card reads a real plan; they are not a confirmation of the model.
- **The same site on five terrain resolutions** (80 m, 240 m, 474 m, 1.9 km, smooth sphere) in every site
  card, with the range found within the landing scatter, so the effect of terrain detail is on screen.
- Slip grid (up to four sites by 30 to 90 landing dates, worst case within the scatter), two sites as one
  power system, CSV exports, and a link that reopens any scenario.

**How it works**

Sun and Earth directions come from the JPL DE421 ephemeris with lunar librations. The skyline is found by
marching 720 rays to 300 km across LOLA grids on the curved Moon; the Sun is treated as a disc. Everything
is computed locally in one Python process. Measured on a laptop: the browser reaches network idle in
about 3 s on a warm server (about 12 s on the first visit after a restart, while the map is worked out);
the slip map with its 13-point re-check takes about 11 s for a new date and 0.03 s after; the
slip-robust list takes 43 s the first time (180 skylines) and 0.2 s after. Answers that are already
worked out do not wait behind slow ones: the first screen's card answered in 0.04 to 0.06 s while twelve
slow requests from other visitors were in flight.

**How we know how far to trust it**

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
- **A finer grid.** Two examples were repeated on NASA's 20 m LOLA mosaic near the pole. The
  opening example gives the same answer there (Yes, 13 of 13 touchdown points, 8 days of margin). The
  best-known ridge site, the Shackleton connecting ridge, does not: the 80 m grid says Yes with 7 days,
  the 20 m grid says "Not sure" for the planned date (11 of 13) and Yes for slips of 1 to 7 days. The page
  prints the 20 m answer under the verdict of each. The same check brings the longest darkness at the
  published ridge point to 110 hours, against the published 112 (194 on the 80 m grid).
- All LOLA files were downloaded from pgda.gsfc.nasa.gov, pds-geosciences.wustl.edu, imbrium.mit.edu and
  svs.gsfc.nasa.gov, and their sha256 values are recorded.

**What it does not do**

It computes on 80 m terrain. Both examples were also run on NASA's 20 m grid and on the LOLA team's 5 m site
models: the opening example stays Yes with 8 days on all three; the Shackleton ridge reads Not sure on the planned
date on 20 m and on 5 m. Ground slope is checked against NASA's lander-tilt limit only where 5 m or 20 m terrain
covers the site (the 80 m grid is too coarse for slope), with no boulder data; it does not model power or temperature; longest-darkness figures on ridge crests are indicative only;
the "how sure" check and the landing circles test stability against landing position and grid resolution,
not errors in the topography itself; the circles are area counts and the three lander classes are
assumed Gaussians, not a dispersion model of any lander. Where the ground that ends a margin is one grid
cell away, the page says so and names no ridge. The slip margin of the example is set by its Earth-contact
need, and that need (100 hours) is illustrative; the card says so. The example is good for two landing
windows in the next two months and then for none from January to August 2027. A "Yes" holds for the
stated landing scatter and no further. On a host too small for the 80 m grid the app runs on a
240 m grid, says so, widens its landing scatter to one grid cell, and the example reads "Yes, 7 days" but only for a landing within 240 m, with no 20 m line. The Earth margin of the example is thin (0.64 degrees at touchdown) and no published link mask was found to judge it by. The 20 m checks exist for the two stored examples, for 14 weekly dates of the map, and for any other map date when the stored 20 m skylines are installed (worked out on request in about 10 to 20 seconds). The opening date, 18 Nov 2026, is a fixed example: after it the page opens on a date in the past, and the card says why.

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
- LOLA south-pole elevation mosaic LDEM_80S_20MPP_ADJ (20 m), same archive: the 71.7 km square around
  the pole, read by range request, for the check of the example on a finer grid. Not what the
  page computes on.
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

- 30-second video: demo/STORYBOARD.md (five frames, captions, timings; 29 seconds in all) and a draft
  rendered from it, demo/slipday_draft_29s.mp4 (five screenshots with the captions burnt in). The draft
  is for you to review and re-record; `[TEAM NAME]` is still in its last caption.
- 7 slides: demo/SLIDES.md. Slide 1 and the last caption carry `[TEAM NAME]` and `[MEMBER NAMES]`
  placeholders.

### Which grid the public link must serve

Every example in this draft, the storyboard and the slides (Yes with 8 days of margin at the opening
example, Yes with 7 days at the connecting ridge, 574 of 733 map points) is on the **80 m grid**, and the
map needs `data/field/scatter_el_i16.npy` (42 MB) for its 13-point re-check. The link must therefore be a
server that has `data/dem/ldem_80s_80m_f32.npy` (231 MB; `python3 scripts/fetch_grid80.py`, or
`docker build --build-arg GRID80=1`). Check before submitting: the badge at the top right of the page
must read "Terrain skyline from LOLA, 80 m/px elevation data", and `/api/health` must give
`terrain.label` starting "LOLA, 80 m/px". On a server without that file the app runs on the 240 m grid:
the badge says "240 m/px", the same example reads "Yes, 7 days" for a landing within 240 m instead of
"Yes, 8 days" within 100 m (measured 15 Nov 2026), the 20 m check line is not shown, and frame 1 of the
storyboard cannot be reproduced.

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
