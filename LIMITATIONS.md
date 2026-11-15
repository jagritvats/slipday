# Limitations

Numbers quoted here were measured in this build; the commands and outputs are in TEST_REPORT.md,
REALDATA.md and, for everything dated 14 Nov 2026 "local pass", LOCAL_PASS_RESULTS.md. The local pass
ran on a Windows machine with direct access to the NASA hosts: every LOLA file was downloaded again from
its official host and every recorded hash matched.

## Second local pass (14 Nov 2026, late): what the new views are, and what they found

Every number here is in LOCAL_PASS_2_RESULTS.md with the command that produced it.

- **The opening example is one site and one date that two grids agree on, no more.** After the finding
  in the next point the page was made to open on an example chosen by a written rule applied to the 20 m answer
  was computed (LOCAL_PASS_2_RESULTS.md, section H): the map's scatter-robust points in the order of the
  slip-robust list, the first whose full card is a clear "Yes" with at least a day of margin on the 80 m
  grid and on NASA's 20 m grid. The first candidate passed (89.010 S, 122.764 E: Yes, 13 of 13 touchdown
  points, 8 days of margin on both grids), so only one of 18 candidates was tried and nothing is known
  about the other 17 on the finer grid. It is not a published site and the feature was not looked up.
  Its margin is ended by the Earth-contact need (95 of 100 hours on day 9), which is an illustrative
  figure; the card says so. It is a seasonal place: 41 clear-yes landing dates in a year (3 not sure; 42 and 2 without the station rule), none from
  January to August 2027. A first visit opens on that fixed example (landing 18 Nov 2026), not on
  today's date. The 20 m answer is an off-line check stored in a file; the page itself computes on 80 m.
- **The best-known ridge example does not survive a finer grid unchanged.** The page computes on NASA's
  80 m mosaic. The former opening example (Shackleton connecting ridge, landing 18 Nov 2026, 240 sunlit
  hours and 100 hours of Earth contact in 14 days; now site 2) was worked out off-line on a terrain stack whose finest grid is the
  71.7 km square around the pole from NASA's 20 m mosaic (`scripts/fetch_ldem20_crop.py`,
  `scripts/ridge_20m.py`). On the 80 m grid: Yes, 13 of 13 touchdown points, 7 days of margin. On the
  20 m grid: **Not sure on the planned date, 11 of 13 touchdown points** (two lose the Earth at
  touchdown); slips of 1 to 7 days pass at all 13; day 8 fails on both. Clear-yes landing dates in a
  year: 35 on 20 m against 62 on 80 m. Share of a 250 m landing circle where the plan holds: 49 % against
  62 %; of a 100 m circle: 88 % against 100 %. The page prints the 20 m answer under the verdict of that
  example and in a validation tile; every other number on the page is still the 80 m one. What the finer
  grid confirms: time with any Sun at the published point, 92.4 % on 20 m and 92.5 % on 80 m (published
  92.1 %); longest darkness there, 110 h on 20 m against 194 h on 80 m (published 112 h), so that old
  mismatch was the grid. What it makes worse: the spread within 100 m (64 to 92 % of the year with Sun on
  20 m, 74 to 93 % on 80 m). The crop was checked against the 80 m grid at 20,000 random points: mean
  absolute height difference 0.72 m as placed, 2.8 m when shifted by one 20 m pixel in any direction.
  Not done on the 20 m grid: the slip-margin map, the scatter skylines, the validation against the LOLA
  maps, the other sites.
- **"Why it flips" reads the same skylines; it is not a new model.** The Sun's and the Earth's paths are
  hourly positions from DE421; "hidden" is the card's own rule; the ground named is whatever sets the
  skyline at the azimuth where the body goes behind it, with the distance the ray-march recorded. At
  three of the five examples looked at, that ground is one cell of the elevation grid away (80 m): the
  crest the lander stands on. The sentence then says exactly that and names no ridge, because an 80 m
  grid cannot say more about ground that close. Where the ground is far (IM-1: 4.72 km to the west,
  130 m above the site) the direction, distance and position are given; none of these positions was
  checked against an image or a named feature.
- **At the connecting ridge it is the Earth, not the Sun, that ends the margin.** Day 8 fails because one
  touchdown point 100 m north-west of the target gets 97 hours of Earth contact of the 100 needed. The
  100 hours are an illustrative need, so the 7-day margin of the headline example is set by an
  illustrative number.
- **The scatter-checked map is the 13-point part of the check only.** The coarser grid and the finer
  near-field sampling of the mission card are not applied to the map (the slip-robust list applies them
  to 12 points). Scatter skylines are stored for 2,407 map points: those that pass on at least one
  landing date from 14 Nov 2026 to 16 Jan 2027 for the default need. For another need or season a
  coloured point outside that set is drawn hollow grey and counted as "not re-checked" (593 of 1,733
  points for a 168-hour need on 18 Nov 2026). For the default example the re-check removes a fifth of the
  coloured points: of 733 that pass at the point, 574 keep a margin at all 13 touchdown points (454 the
  same margin, 120 a shorter one) and 159 lose it; a margin of 5 days or more survives at 18 points, not
  74; the largest margin is 8 days, not 9. At 12 map points picked at random the map's figure equals the
  mission card's 13-point count exactly.
- **The three lander classes are assumptions.** Each is a two-dimensional Gaussian whose size is taken
  from one published figure, read first-hand on 15 Nov 2026 and linked on the page: 99 % within 100 m
  ("pinpoint landing within an accuracy of 100m", the main mission of SLIM; JAXA press release of 25 Jan
  2024), one standard deviation of 250 m (IM-2 "on its side about 820 feet from the intended landing
  site"; NASA news release of 7 Mar 2025), and an ellipse of 670 m by 400 m (a third of the "Landing Site
  (Prime) 4 km x 2.4 km" on ISRO's Chandrayaan-3 details page). The figures are sourced; turning each
  into a Gaussian of that size is this project's choice, and Chandrayaan-3 itself was guided. None is a
  model of a named lander, real dispersions are not Gaussian, and the outcome at each touchdown point
  still comes from an 80 m grid. The range beside each chance covers the direction of the ellipse's long
  axis and the choice of touchdown points; it says nothing about the terrain data.
- **The range beside a landing-circle share** is the 5th to 95th percentile over 400 resamplings of the
  touchdown points, ring by ring. It answers the review's point that 62 % on 37 points was 55 % on 68: the
  printed range is 54 to 70. It is a sampling range of this count, not an error bar on the terrain.
- **The 3-D view** draws real LOLA heights (true scale by default; 2x and 3x are labelled on the view).
  A cell is drawn in shadow when the centre of the Sun's disc is behind terrain along a ray from 2 m
  above that cell; the far part of that ray is sampled more coarsely than the skylines the numbers come
  from (step fraction 0.01 against 0.002). Its centre cell agreed with the app's skyline at every hour
  of the windows compared (IM-1: 337 of 337 hours; Malapert shoulder over 60 days: 1,441 of 1,441). The
  brightness of sunlit slopes is illustrative. Buttons and keys zoom and tilt; there is no pinch zoom.
- **Permanent shadow** on the map is every 480 m cell in which the LOLA team's average-illumination map
  (120 m, averaged 4 by 4) reads zero. Shadowed patches smaller than a cell are not drawn, and distances
  to the nearest shadowed cell are good to about half a cell.
- **"Not like Earth"** sets the app's own Sun curve for the site beside two curves for places on Earth
  from a textbook solar-position formula. The Earth curves are for comparison only and are not NASA data.
- **The year ribbon** is one year from the planned date: a sample of the 18.6-year cycle, not a
  long-term calendar. Each cell is the card's own three-state check.
- **Two request lanes.** A request that needs only stored skylines no longer waits behind slow work.
  Slow work is queued, and a big job is refused with a "busy, try again" answer (HTTP 503) when three
  are already waiting; the page asks again by itself. On a small host a visitor adding a new site while
  others do the same will see that sentence. The container memory figures further down were measured
  before this change, before the scatter skylines (42 MB, memory-mapped) and before the 3-D view; the
  Docker engine was down in this pass, so they were not re-measured.
- **Links out** to LROC QuickMap and NASA Moon Trek use address formats that were confirmed once each on
  a screenshot on 14 Nov 2026 (south-polar and equirectangular views; the north-polar views were not
  checked). Those sites can change their formats.
- **The phone page** is 12,908 px tall (it was 21,303): all but the first site card and the validation
  tables are folded, one tap away. Checked in headless Chrome at 390x844 only; no real phone.
- **The draft video** (`demo/slipday_draft_29s.mp4`) is screenshots with their captions, 29 seconds. It is
  a draft: the team name is a placeholder, and the only movement is ten screenshots of the 3-D view shown
  one after another.

## Deep pass (15 Nov 2026): launch windows and real missions

- **Windows are one synodic month apart at the same solar phase: our inference.** The sources give a few
  launch days a month and a landing pinned to the Sun and the Earth at the site; none says "one synodic month"
  or "the same time of the lunar day", and south-polar lighting shifts 2 to 3 weeks a year (LPSC 2026), so a
  planner re-picks the hour. The card's "other options" searches the hours within three days of each window.
  IM-1's January date (24 Jan 10:00) is modelled, not published.
- **VIPER's point and phase are assumptions.** The point is on Nobile crater's west rim from the gazetteer, not
  VIPER's landing ellipse (not found first-hand); landing 24 hours after local sunrise is our choice. Every
  late-2027 window reads No there because the Earth is below the skyline at touchdown; a different point or
  phase may well read Yes.
- **The map does not reach these sites.** The slip-margin map covers the 30 km round the pole; IM-1 (80.1 S)
  and Nobile (85.1 S) are outside it.
- **The 20 m mark on request** needs the stored 20 m skylines (git-ignored, with the 20 m crop); without them
  only the 14 stored dates are marked.

## Pass 4 (15 Nov 2026): ride-through hours

- **Hours, not energy.** The longest night and the longest Earth outage are whole runs that are under way at
  touchdown or begin inside the card's window, counted to their end, at the worst of the 13 touchdown points
  (pass 4 first showed only the part inside the window, which understated a late landing's night: 21 h of a
  179 h night at the opening example's day 8). No battery, heater or power model is used and no battery size
  is shown.
- **The night follows the card's Sun rule** (half the disc above the skyline): a partly lit Sun counts as
  night here. With "no part of the disc visible" the figures are shorter (at C1 over a year: 194 h against
  253 h on 80 m).
- **The map layer is on 80 m** and on the 13-point part of the check only, like the scatter map; its colour
  classes (24, 48, 72, 120 h) were chosen at the start of pass 4. With whole nights 568 of the 574 coloured
  points fall in the top class (120 h or more; range 14 to 468 h), so the colours separate little and the
  hover gives the hours.
- **A link margin.** No lander-side Earth mask could be cited (LunaNet Interoperability Specification v5 gives
  none); JPL IPN Progress Report 42-243 describes fading at grazing angles. The card says a real link would
  want more than the 0.6 degrees the opening Yes holds for.

## Pass 3 (15 Nov 2026): what the new views are, and what they found

- **The Earth margin of the opening example is thin.** At touchdown the Earth's centre is 0.64 degrees above
  the skyline; the Yes holds up to a link mask of 0.60 degrees, is Not sure from 0.65 and No from 0.70. No
  published elevation mask for a direct-to-Earth link from the lunar surface was found first-hand, so the
  page uses the Earth's centre (mask 0) and labels every other mask illustrative. A real link budget could
  well need more than 0.6 degrees, and then the planned date of the example would fail.
- **The station rule is a mask at the ground, not at the lander.** It uses the DSN handbook's 10-degree
  low-power transmit limit as one flat angle at all azimuths; the per-antenna horizon masks, antenna
  schedules and other users of the network are not modelled. The receive limit (6 degrees) would give more
  hours. For the opening example the rule removes no hour, so the card does not change.
- **Permanent shadow is where it is dark, not where ice is.** The shadow-site list uses the zero cells of
  the LOLA team's 60 m average-sunlight map (an 18.6-year model). It says nothing about ice, about the
  slope down into the shadow or about whether a rover could get there. Its 10 ha and 1 km thresholds were
  taken from a planning note dated 14 Nov 2026 19:36, before the list was built; other thresholds give other lists.
- **The 20 m checks are few.** The 20 m grid is used off-line for the two stored examples and, since pass 4,
  for 14 weekly dates of the slip-margin map (18 Nov 2026 to 17 Feb 2027, default need and rules, station rule
  on); any other date, site or rule is on 80 m only, and the page marks nothing then.
- **The opening date is fixed.** 18 Nov 2026 was chosen by a written rule (LOCAL_PASS_2_RESULTS.md, H.1); from
  19 Nov 2026 it is in the past and the page still opens on it, and says so.

## What is real

- **Sun and Earth directions** from any point on the Moon: JPL DE421 positions and lunar libration angles,
  Mean Earth frame, light-time and aberration. Checked against 218 rows of JPL Horizons at three sites
  (largest difference 1.3e-05 degrees) and, by the v1 reviewer, against an independent SPICE computation
  (1.7e-06 degrees). Local pass: the 218 rows were downloaded again directly from ssd.jpl.nasa.gov and are
  identical to the relayed tables, and the live cross-check on the page ran for the first time (164 rows
  at two sites, largest elevation difference 1.4e-05 degrees).
- **Earth visibility** at south-polar sites (local pass). Against the LOLA team's Earth-visibility maps,
  at the same 400 seeded points as the Sun check and with the rule the maps' own labels state (any part
  of the Earth's disc above the skyline, at the surface): mean absolute difference 0.97 points and
  correlation 0.9946 on the 60 m map (200 points within 5 degrees of the pole), 0.69 points and 0.9984 on
  the 120 m map (200 points between 80 S and 85 S). That rule is also the best-fitting of the four
  computed. The largest single differences are 18 and 15 points, and 5.5 % and 3.5 % of the points differ
  by more than 5. With the map flipped or transposed the correlation falls to between -0.52 and +0.55, so
  the agreement is not an accident of the georeferencing. On the 60 well-lit ridge pixels of the Sun
  check the Earth side agrees to 1.57 points (correlation 0.9707, 92 % within 5 points), better than the
  Sun side does there (4.0 points). All of this tests the method, not the topography: the maps were
  ray-cast from LOLA grids too (the 60 m and 120 m grids, against this build's 80 m mosaic). The labels
  name no time span, so the 18.6-year cycle used here is an assumption carried over from the Sun maps.
- **Terrain skyline** at south-polar sites: ray-cast over the curved Moon from real LOLA elevation grids
  (80 m PGDA mosaic to 80 S, PDS 240 m grid to 75 S, 474 m SVS grid to 60 S, PDS 16 px/deg grid globally).
  On ordinary terrain the share of time with any Sun visible agrees with the LOLA team's own published
  illumination maps to 0.8 percentage points on average (mean absolute difference at 400 seeded random
  points, correlation 0.992 and 0.995 for the two maps); the smooth sphere misses the same maps by 21 and
  33 points. Most of those points are poorly lit. On the well-lit ridge pixels a lander would be sent to
  the agreement is about 4 points (4.0 mean absolute difference, mean difference -2.8, correlation 0.61,
  68 % within 5 points, at 60 seeded pixels the 60 m map rates above 60 %). The reference maps were
  ray-cast from LOLA topography too, so this checks the method, not the topography.
- **The solar disc** is an extended source: the visible fraction of the disc above the skyline is computed
  in 15 vertical strips, so a notch or peak narrower than the Sun is handled.
- Every number on the page, in the API and in the CSV exports says which horizon model produced it.

## What is approximate

- **DEM resolution.** The finest grid here is 80 m. Published ridge-top studies use 5 m to 20 m grids. An
  80 m grid cannot place an observer on a crest that is a few tens of metres wide, and it smooths the
  nearest few hundred metres of terrain, which matters most for an observer 2 m above ground. Measured
  effect at nine published ridge-top points (Glaser et al. 2014, 2018): six agree within 1.1 points of
  average illumination (the connecting ridge C1 at 0, 2 and 10 m, C2 and the Shackleton rim at 2 m), and
  three single points on narrow crests read 5.5, 9.9 and 24.7 points low. With coarser grids the same
  sites drift by up to 10 points in either direction (table in REALDATA.md). Treat a single ridge-top
  point as good to about 5 points of illumination, and look at the neighbourhood.
- **Longest darkness** on a ridge site is indicative only. At the connecting ridge C1 (2 m) this build
  gets 198 h over 2017-2037 where Glaser et al. 2018 publish 112 h. During that run the Sun's upper limb
  sits a median 0.35 degrees under a skyline set by ground 0.2 to 0.4 km away, which an 80 m grid resolves
  poorly, and the ten longest dark runs are all 195 to 198 h: it is a recurring graze past nearby terrain.
  Moving the point 20 to 40 m gives 118 to 292 h; a 2.5 m or 3 m mast gives 137 or 108 h; across the
  13-point landing scatter the year figure runs from 6 to 21 days. The page prints that range under the
  figure and says so in the caption. Treat longest darkness on a crest as good to a factor of about two.
- **The exact match at C1 is not firm.** The stated point gives 88.0 % average illumination and 92.1 %
  visibility, the published values. A 20 m shift gives 86.4 to 88.3 / 91.0 to 93.0, a 40 m shift 83.7 to
  88.2 / 88.3 to 92.7, and the 100 m landing scatter 67.8 to 88.0 / 72.5 to 92.5. The published point is
  the best pixel of its neighbourhood, and the agreement sits at the top of that range.
- **Near-field sampling is a convention.** The first ray sample is one grid spacing from the observer
  (80 m on the 80 m grid), node to node as in the LOLA team's maps, because a grid holds no information
  about nearer ground. For an observer at 0 m on a crest the result depends on that choice: C1 gives 75.5,
  67.1, 50.0 and 42.7 % with the first sample at 80, 40, 20 and 10 m (published 76.0). So the 0 m rows of
  the ridge-top table agree by convention, the page offers 2 m and 10 m only, and the API attaches a
  warning below 1 m. At 2 m the effect is under 1.2 points at C1, and at random non-crest points it does
  not matter.
- **Position sensitivity.** Moving 80 m on a ridge can change illumination by tens of points. Catalogue
  coordinates for regions (Artemis III candidates) are IAU feature centres, not landing points; three of
  them are permanently shadowed crater floors. The "Malapert massif, Earth-facing shoulder" site was chosen
  by this project on the DEM and is labelled as such.
- **Between LOLA tracks** the 80 m mosaic is an interpolated surface; away from the pole the gaps are wider.
- **Outside the south-polar grids** the skyline comes from the 474 m grid (60 S to 75 S) or the 1.9 km
  global grid. At 1.9 km the skyline is only the large-scale relief: fine for telling a mare site from a
  mountain front, wrong for local slopes and nearby craters. There is no north-polar grid finer than
  1.9 km in this build, so north-polar results are not validated. Sites outside the checked area (north of
  80 S, or on a grid coarser than 474 m) carry a "not validated" tag on the page.
- **Smooth-sphere numbers** (always shown beside the terrain ones, and the only ones where no grid covers
  the site) are not a bound in either direction near the poles. High ground sees over the sphere's
  horizon: the connecting ridge has some Sun 92 % of the time against 56 % on the sphere (2017-2037). Low
  ground and crater floors see less: Shackleton's floor gets none against 56 % (2027). A ranking of polar sites made on the
  smooth sphere can be backwards.
- **The "how sure" check is a sensitivity test, not an error bar.** Thirteen points within 100 m, one
  coarser grid and one finer near-field sampling say whether the answer is stable against where the lander
  comes down and how the terrain is gridded. They say nothing about errors common to all members: the LOLA
  topography itself between tracks, the 80 m smoothing of every crest, lander tilt. A "Yes" means the model
  is stable, not that the mission is safe.
- **A "Yes" is conditional on the landing scatter, and the headline now says so.** The default is 100 m.
  At the default example (connecting ridge C1, 18 Nov 2026, 240 sunlit hours and 100 hours of Earth
  contact in 14 days) the card reads Yes with 7 days of margin at 100 m, Not sure at 150 m (11 of 13
  points pass), and Not sure with no clear-yes date in 60 at 200 m and 250 m. IM-2 came down about 250 m
  from its target. The **landing circles** under the card put a number on this: the share of a circle of
  100 m, 250 m, 500 m and 1 km radius in which the plan holds, for each day of slip. At C1 on the planned
  date: 100 %, 62 %, 27 % and 13 %. At the IM-2 site (its landing hour, 240 h): 100 %, 100 %, 100 % and
  96 %. These are area shares counted over up to 93 touchdown points on rings, with touchdown equally
  likely anywhere in the circle. They are not a dispersion model of any lander, the elevation data are not
  perturbed, and with 17 to 93 points a share is good to a few points at best. The labels "precision
  landing" and "no precision landing" are descriptions, not lander specifications.
- **On a grid coarser than the scatter the scatter is widened.** Points closer together than one grid
  cell sit on the same interpolated patch and cannot disagree, which made the check overconfident on the
  240 m fallback (two ridge sites read "Yes" with 7 and 8 days of margin where the 80 m grid says "Not
  sure"). The scatter is now never smaller than one cell of the grid under the site (80, 240, 474 or
  1896 m), and the card says when it was widened. With that, the two sites read "Not sure" on the
  fallback as on the 80 m grid. The cost: on the fallback the default example C1 also reads "Not sure",
  with no clear-yes date in 60, where the 80 m grid says "Yes, 7 days". The fallback cannot confirm
  anything about a 100 m scatter, and it now says so instead of guessing. A first visit to a fallback
  server opens on the first date that is not a clear no, with a note saying that no date is a clear yes
  on that grid. A landing circle smaller than one cell is reported as not resolvable.
- **The slip map** is one point every 500 m. A crest narrower than that can fall between points (the
  connecting ridge shows as a few pixels), so an uncoloured area is not proof that no good spot exists
  there. It is for a 2 m observer and for the stated point only (no scatter), so its margins are
  upper-side figures. The button under the map re-checks its 12 best points (at least 1 km apart) with
  the full ensemble: for the default example 5 of the 12 stay a clear yes, and the map's own best point
  (9 days) is one of the 7 that do not. The list covers 12 candidates, not the whole map. On a deployment
  without the 80 m grid the map still shows skylines built from the 80 m grid while site rows use 240 m;
  the map note says so.
- **The need on the mission card** is a simple rule: hours of Sun and hours of Earth in a window, and
  optionally both up at touchdown. Landings are on the hour. Each real-landing example now carries its own
  sunlit-hours need where a planned surface duration was published before landing: IM-1 about 7 days
  (168 h), IM-2 about 10 days (240 h), Blue Ghost Mission 1 14 days (336 h). Chandrayaan-3 keeps the
  illustrative 240 h, because ISRO's "one lunar day" is a design life, not a number of sunlit hours after
  touchdown; taken literally (336 h) the card would say No, with 283 sunlit hours left in the window. The
  100 hours of Earth contact are illustrative in every example: no published requirement was found. The
  plan documents were read through a web-fetch tool (relayed text). For IM-1 two figures were published:
  about seven days (the company's kit, and NASA's account after landing) and approximately 10 days
  (NASA's press kit). The example uses seven and says that with ten the answer is No.
- **Site pairs** count a site as lit when any part of the Sun is visible and have no published figure to
  check against.
- **The Earth** is judged at its disc centre on the mission card, with an optional margin in degrees
  above the skyline. That is a stricter rule than the one the LOLA team's Earth maps use (any part of the
  disc) and gives about 4 points less time in view at the validation points. The validated quantity is
  the any-part one. Real links also depend on antenna pattern, lander attitude, the ground station and
  relay satellites.
- **"The slip margin is set by the Earth, not the Sun"** holds for the dates on the default page and from
  August to January generally. For 365 landing dates from 18 Nov 2026 at C1 with the default need there
  are 62 clear-yes dates, none of them from February to June 2027 and one in July; from March to June
  the Sun fails on 15 to 23 dates a month, alone or together with the Earth. The page does not make the
  general claim; DISCOVERIES.md did, and is corrected.
- **"Usable"** means Sun and Earth above the skyline by the chosen rules. It ignores lander tilt, panel
  pointing, thermal limits and battery. The IM-1 hindcast shows the size of that gap: with terrain the
  predicted sunset is still 62 h after the lander lost power (79 h on the smooth sphere); the lander lay
  tipped about 30 degrees.
- **Site height and parallax.** The observer's height above the reference sphere is used for the skyline
  but not for the direction to the Sun and Earth (the effect is below 0.001 degrees).
- **No multiple scattering, no thermal model, no Earthshine.** Light means direct sunlight only.
- Metrics use hourly samples, so hour counts are good to about an hour per rise or set; event times are
  refined to about a second on the modelled skyline. Slip-grid landings are at 00:00 UTC.
- One year is one sample of the 18.6-year cycle of the lunar orbit. The year table on each card can differ
  from the long-run average by several points; the validation runs use a full cycle.
- Supported dates are 1900 to 2050 (the span of the `de421` package). Windows that would run past the end
  are cut short and marked.

## What is unverified

- **Earth visibility per published site.** The map checks above cover 400 mostly ordinary points and 60
  ridge pixels, all against the LOLA team's own maps. The
  one published per-site table found (Bryant 2009) is on a radar DEM in a different frame: at its stated
  coordinates the LOLA terrain is off the crest, and even the best-lit point within 1.2 km does not reach
  the published sunlight (55 to 74 % against 77 to 95 %), so the sites could not be co-located and the
  table tests nothing (it is in REALDATA.md so the gap is visible). The 240 m Earth map was downloaded but
  not used in a check.
- **Published reference values** (Glaser et al., Bryant, LROC elevations) and the planned surface
  durations of the four real landings reached this build through a web-fetch tool that relays pages
  through a reading model. They are not byte-exact. The LOLA maps and grids are real files with recorded
  hashes, downloaded from the official hosts on 14 Nov 2026.
- **Hindcast reports** are operational events (sleep commands, power loss, last contact), not measured
  sunsets. Two are dates without a time of day, compared at 00:00 UTC.
- **Deployment.** Nothing has been deployed to a public host. The public link has to serve the 80 m
  grid: on the 240 m grid the headline example reads "Yes, 7 days" only for a landing within 240 m.
  Local pass: the Dockerfile builds
  (1.33 GB image with the 80 m grid) and serves the page. Under a concurrent load test in Linux
  containers with two CPUs and the malloc-arena limit on, the 80 m grid answered every request inside a
  512 MB limit with the memory group peaking at 431 MB (433 MB inside 768 MB, 421 MB inside 1 GB), and
  the 240 m grid peaked at 296 to 299 MB. With the arena limit off the 240 m server was killed by the
  kernel at 512 MB. So 512 MB held the 80 m grid here with about 80 MB to spare. These are Docker
  Desktop figures on one machine: a hosting plan's "512 MB" may be counted differently, and no host with
  a fraction of a CPU was tried. `render.yaml`, `Procfile` and the `GRID80=1` build argument (which
  downloads the 80 m file during the build) were written and not run. A host with a fraction of a CPU
  will take several times longer than measured here for the first slip map of a date
  (`SLIPDAY_FIELD_STRIDE=2` quarters it), for the landing circles of a site not in the stored cache (93
  skylines) and for the slip-robust list (180 skylines).
- **The Windows machine** the local pass ran on is not the deployment target: `MALLOC_ARENA_MAX` does
  nothing there, and no memory figure was taken on Windows.
- Front end: checked in headless Chrome at 1280x800 and 390x844 (scripts/ui_check.js, 65 checks since
  the second pass). No screen-reader pass and no real phone.
- The 2026 judging and submission guides had not been published in readable form when the challenge notes
  were compiled; requirements quoted in SUBMISSION_DRAFT.md are from the previous cycle.

## Next steps

1. Deploy with the 80 m grid in the image, so the page runs on the validated grid; without it the 240 m
   grid runs and the default example reads "Yes, 7 days" only within 240 m. In a container the 80 m grid needed 431 MB of a
   512 MB limit; a host with 768 MB or 1 GB is the safer choice.
2. Make the 20 m grid the default near the pole. The crop is fetched and the default example has been
   repeated on it (see the top of this file); still to do on it: the ridge-pixel check against the LOLA
   maps, the slip-margin map and its scatter skylines (about 16 times the work at 20 m spacing of the
   near field), and the tests, which are pinned to 80 m values.
3. The 240 m Earth map for sites north of 80 S, and a check of the mission card's centre rule.
4. A north-polar grid (LDEM_80N_80M) so the north pole gets terrain too.
5. Each mission's real landing ellipse in place of the four fixed circles, and a "survive N hours of
   darkness" rule on the mission card.
