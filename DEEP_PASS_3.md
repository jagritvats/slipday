# Slipday feature build: region availability on published landing sites (Sunday 15 Nov 2026, from 12:28 IST; hard stop 17:45 IST)

Process notes for this build, written as it goes. Judge-facing text is elsewhere.

## F0. Start (12:28)

Read `BIG_FEATURE_SLIPDAY.md` (candidate 1, availability portfolio; candidate 3, the yearly drift). The
wording fixes were finished first and recorded in DEEP_PASS_2.md, "Final fixes".

## F1. Data and sources (12:28 to 12:32)

Downloaded with curl, client name `slipday-fetch/1.0`, into `data/reference/wueller2026/` (hashes in
DOWNLOADS.tsv and realdata/lunar/MANIFEST.md):
- Zenodo record 17084058 (API JSON), `Landing_Sites.zip` and `Illumination_Modeling.zip`; the md5 values
  match the ones Zenodo lists. CC BY 4.0. Only the small shapefile parts were extracted (to `x/`); the
  885 MB slope raster inside the zip was not unpacked.
- Crossref metadata with the abstract (10.1029/2025JE009434). Wiley's full text answers 403 to curl.
- An open copy of the paper: University of Zurich repository (ZORA), CC BY 4.0 PDF, and the ETH Research
  Collection's text extract of the same PDF (found through OpenAlex's repository list).
- NASA LPSC 2026 abstract (NTRS 20250011660): the local docx already recorded in the deep pass.

What the columns mean, and from where:
- `Landing_Re` region code, `Name`, `Latitude`, `Longitude`: self-evident and matching the paper's
  Table A1 description ("geographic locations of all 130 candidate landing sites").
- `SunDaysYY` and `SunEarthYY` (`Sun_Earth2` is `SunEarth25`, the field name cut to 10 characters): the
  paper, section 2.3: illumination modelled with ACT's QuickMap TerrainShadows, 60 m/pixel, 12-hour steps,
  2 m above the surface, shadows from up to 150 km; "For each pixel, our output contains the maximum number
  of days with consecutive (a) Sun visibility and (b) combined Sun and Earth visibility", per midsummer
  period (subsolar latitude at or below -1.5 degrees; Table 2 gives the dates, e.g. 2027: 15 Oct to 14 Nov).
  The dataset's READ_ME: the raster counts 12-hour steps; "The values in the attribute tables have already
  been divided and indicate the number of consecutive illuminated days." "Sun visibility" is a non-zero
  illumination value, so any part of the disc (our rule asks for half the disc).
- Not used, meaning not established: `StereoX`, `StereoY` (small integers, not the projected metres),
  `coldest_te`, `oldest_PSR`, `PSR_AREA`, `ID`.
- 78 of the 130 sites are in NASA's nine current regions: HW 11, SP 11, MMP 11, MMO 10, NR1 9, NR2 9,
  dGR2 7, MMA 5, PCB 5.

NASA, LPSC 2026 abstract, quoted from the docx: "End-to-end mission availability analyses demonstrate that
individual regions typically provide limited viable opportunities when all constraints are simultaneously
satisfied. To support acceptable annual mission availability and increase flexibility in launch timing, more
than one landing regions must be maintained for Artemis III specifically." Stay: "Surface stay duration
varies approximately 5.75 to 6.25 days depending on mission epoch". Light: "Solar illumination remains a
critical requirement for the entire crewed surface stay".

## F2. The rule (the shell clock read 12:32 when it was appended; see the note below)

Note (final fixes): the order cannot be checked from file times. This file was last written after
`slipday/regions.py` (12:35), `scripts/region_availability.py` (12:36) and the results file (12:41), so its
own time proves nothing about when this section was written. Read the rule as stated, not as shown to come first.


- Landing times: every 6 hours from 2027-01-01 00:00 UTC to 2030-12-31 18:00 UTC (5,844 times). 6 h is
  the step the page's best-hour search already uses.
- Stay: 6.25 days = 150 hours (the top of NASA's "approximately 5.75 to 6.25 days").
- A site is a clear Yes at a landing time when every member of the card's check passes (the 13 touchdown
  points within 100 m, the coarser grid, the near-field sampling; 2 m mast; Earth contact needs a DSN complex
  with the Moon 10 degrees up, the card's default):
  - the Sun counts as up (half the disc above the skyline) at every hour of the 150 (NASA: illumination is
    required for the entire stay; this replaces the card's 240-of-336-hour sunlight need, which cannot fit
    in 150 hours);
  - at least 100 hours of Earth contact within the 150 (the card's Earth need, unchanged);
  - the Sun and the Earth in view at touchdown (as on the card).
- Fragile: a clear Yes where, at any of the 13 touchdown points, the Sun's centre is less than 0.27 degrees
  above the skyline at some hour of the stay, or the Earth's centre less than 0.27 degrees above it at
  touchdown. (The card's rule looks at touchdown only; here the sunlight need covers the whole stay, so the
  Sun check does too.)
- A region is open at a time when at least one of its published sites is a clear Yes that is not fragile.
  A time where the region has only fragile Yes sites is counted separately and is not open.
- Coverage of k regions: share of the 5,844 times at which at least one of the k regions is open. Regions
  chosen greedily: first the region open most often, then each time the region that adds the most times not
  yet covered. The best set found by trying all 511 sets is printed beside it.
- One sensitivity row: the same with no Earth-contact need (sunlight only), because NASA calls Earth
  visibility a preference ("If Artemis III employs a Direct-to-Earth (DTE) communication architecture").
- Cross-check: for each published site, our longest run of consecutive Sun visibility inside each midsummer
  period of Table 2 (2027 to 2030), sampled every 12 hours at the site centre, any part of the disc above
  the 80 m skyline, 2 m height, against SunDaysYY. Printed as exact matches, within 1 day, and the
  10-day "favourable" threshold the paper uses.

## F3. Code (about 12:33 to 12:41, by file times)

- `scripts/build_wueller_sites.py`: reads `LandingSites.dbf` from inside the nested zip, in memory, and
  writes `data/regions/wueller2026_sites.json` (130 sites; only the columns whose meaning is established).
  Two cells are empty in the file (SunEarth32 of dGKM01 and HW07); they stay empty.
- `slipday/regions.py`: `site_flags` is the card's check written with running sums over one hourly table,
  so 78 sites x 5,844 landing times take seconds per site instead of one card call per landing.
  `tests/test_regions.py` compares it with `robust.mission_card` landing by landing.
- `scripts/region_availability.py`: availability, coverage, a 48-pair re-check with `mission_card`, the
  SunDays cross-check and the drift from the ephemeris.
- `scripts/artemis_regions.py`: the Artemis III panel now uses the 78 published sites (best site per region:
  non-fragile first, then margin). The anchor version is kept as a scratch copy only.
- Page: a separate panel "How many regions must stay open?" (loaded on a button), placed after the Real
  missions panel. Nothing else on the page reads it. Skylines for the 78 x 15 points went to the scratch
  horizon cache, so the shipped cache is unchanged.

## F4. Results (run 12:37 to 12:42, 308 s; data/validation/region_availability.json)

Share of the 5,844 landing times (2027 to 2030, every 6 h) with at least one of the k regions open:

| k | with the Earth need (100 h of 150) | added (greedy) | sunlight only | added (greedy) |
|---|---|---|---|---|
| 1 | 28.1 % | Nobile Rim 1 | 47.8 % | Nobile Rim 1 |
| 2 | 36.8 % | Peak near Cabeus B | 74.7 % | Peak near Cabeus B |
| 3 | 40.1 % | Malapert Massif | 91.1 % | Slater Plain |
| 4 | 42.6 % | Slater Plain | 91.7 % | Malapert Massif |
| 5 | 43.6 % | de Gerlache Rim 2 | 92.0 % | de Gerlache Rim 2 |
| 9 | 44.1 % | (all) | 92.0 % | (all) |

- The greedy set equals the best set found by trying all sets at every k, in both variants.
- Each region alone (Earth need): 6.9 % (Slater Plain) to 28.1 % (Nobile Rim 1). Fragile-only time per
  region: 0.8 to 2.1 %. Fragile Yes results: 4,112 of 34,553 site-times with a clear Yes (11.9 %); none
  counted as open.
- What it says: NASA's sentence holds on these data. One region gives at most 28 % of landing times (48 %
  without the Earth need); keeping three regions raises it to 40 % (91 %). With the Earth need, the Earth,
  not the Sun, caps the total at 44 %: 100 hours of Earth contact in a 150-hour stay is a hard need at the
  pole. By year the curve changes little (k = 1: 27.1 to 29.9 %).
- Re-check: 48 of 48 sampled (site, time) pairs give the same answer from `robust.mission_card`.
- Cross-check against SunDaysYY (312 site-years): 92 differ by more than 3 days, and they cluster by region
  and year (all 9 Nobile Rim 2 sites and 9 of 11 Mons Mouton Plateau sites in 2027; 6 of 7 de Gerlache Rim 2
  sites in 2028; 7 of 11 Haworth sites in 2028 and 2029; 4 of 5 Peak near Cabeus B sites in 2028 and 2029);
  in almost all of them our run is the longer one (e.g. 15.5 days against 2). Of the other 220, 206 agree
  within 1 day (median: ours 0.5 day longer, as expected from sampling any part of the disc on an 80 m grid
  against their 60 m). Within 1 day overall: 40, 54, 60, 52 of 78 for 2027 to 2030. We cannot tell from
  here which model is right in the clustered cases; it is shown on the page as it came out.
- Drift (item 5): the midsummer periods from our ephemeris (subsolar latitude at or below -1.5 degrees)
  match the paper's Table 2 to the day in all eight years, 2025 to 2032. The day of the most southerly Sun
  moves 31, 7, 33, 11, 12, 27, 10 days earlier from year to year (it jumps because the Moon's monthly
  wobble moves the minimum); the straight-line fit gives 18.4 days a year, against 18.63 expected from the
  346.62-day eclipse year. Printed on the page with both numbers.

## F5. Artemis III panel on the published sites (run 118 s, file written 12:44)

Opening plan, regions with a clear-yes landing within 72 h (of them not fragile; Yes at the window hour):
December 8 of 9 (6; 5), January 6 (5; 5), February 5 (4; 3). IM-1: 9, 8, 7 for January, February, March 2024.
Slater Plain has no site with a Yes hour in any of the three opening windows. The anchor version gave 7, 7, 5
(3, 1, 2 not fragile). `tests/test_deep2.py`'s Artemis test was rewritten for the published sites (same
strictness: the nine names in NASA order, every site from the published file and in its own region, the
counts above, the API); the anchor-only checks (10 km spacing, "1.1 km" rule text) no longer apply because the
feature removes the anchors. `scripts/ui_check.js`: the Artemis check now looks for the published-sites text
(54 cells as before), and a new check covers the regions panel.

## F6. Page, documents (12:44 to 12:53)

- Page: the regions panel sits after the Real missions panel, visible, with a "Show the calendar" button;
  calendar (canvas, nine rows, 2027 to 2030; green open, darker with more sites; amber fragile only), the
  coverage table with greedy and best sets and the four years, the drift paragraph, the cross-check table and
  the citation. A switch shows the sunlight-only variant. First screen unchanged (#slip top 798 px). Phone
  390 px: no horizontal scroll; region codes as row labels.
- A custom site 92 km from every published site (86.0 S, 160.0 W) gets the full card, windows and slip grid
  (`tests/test_regions.py`).
- README, SUBMISSION_DRAFT, SLIDES (slide 5 now "What comes next: NASA's nine regions, and VIPER in late
  2027"; the Artemis line left slide 4; still 7 slides), STORYBOARD (a note only; no caption changes, so the
  video is not re-recorded), DISCOVERIES. Screenshots: `screenshots/desktop_1280x800_regions.png`,
  `screenshots/phone_390x844_regions.png`.

## F7. State at the end (12:58)

- Full suite: 283 passed (275 before; 8 new in `tests/test_regions.py`); the document-reading tests re-run
  after the last edits: 65 passed. `scripts/ui_check.js`: all checks passed, including the new regions check.
- Server (PIDs 50888, 69424) stopped; ports 8100 to 8199 free. No git, no Docker, nothing published.
- Not done: the NRHO landing cadence (NASA's "once every 6.5 days") is not applied; the availability is a
  share of 6-hourly landing times, not of real opportunities. The panel is precomputed for this rule, not
  live for other needs. The SunEarthYY columns are read but not cross-checked (their Earth rule is not
  stated closely enough to match ours). The clustered disagreements with SunDaysYY are not explained.

## Final fixes (from about 13:20)

1. **C1 in January.** Our model: C1 at 14 Jan 01:00 is Yes with 5 days, 13 of 13 points passing on days 0 to
   5. The Sun clearances per touchdown point show two knife edges: 0.076 degrees at touchdown (100 m at 90
   degrees) and 0.055 degrees on day 2 (100 m at 45 degrees). The reviewer's code puts the day-2 point 0.08
   degrees below the skyline and gets 1 day. So the earlier explanation (one point decides the margin) was
   incomplete: the 0.08-degree point decides whether 14 Jan is Yes at all, and the margin rests on a second
   point. Draft and DISCOVERIES now lead with the most robust option (map point 89.498 S, 137.663 W, 15 Jan
   13:00, 4 days, which the reviewer reproduces) and give C1's 14 Jan as "5 days in our model, 1 day in a
   separate calculation", fragile.
2. **Cross-check wording.** Page, slide 5 note, draft, README and DISCOVERIES now say: of 312 comparisons,
   about two in three agree within a day (206) and about three in ten differ by more than 3 days (92), nearly
   always with ours longer; our terrain model (80 m) is coarser than the paper's (60 m). The page computes the
   phrases from the data.
3. **Calendar.** Under the coverage table the page says the all-regions ceiling (44.1 %) is set by the
   illustrative 100-hour Earth-contact need, with sunlight only 92.0 %; the table has a sunlight-only column
   beside the main one; and the shares count landing times every 6 hours, not real launch opportunities.
   Slide 5 is retitled (it no longer calls measured results "what comes next") and trimmed.
4. **Jargon** removed from the page and documents: "site-years", "chosen greedily", "Speed-up check". The
   jargon test now also rejects those three.
5. **F2** marked: its order relative to the code and results cannot be checked from file times.
6. **Video re-recorded** (`demo/slipday_draft_29s.mp4`, 29.0 s, 8 steps, sha256 3717b1c5...). New step 6,
   18 to 23 s, the region calendar and coverage table, caption "NASA must keep several regions: on published
   sites the best one is open at 28.1% of landing times, three at 40.1% (sunlight only: 47.8%, 91.1%)"; all
   four numbers are in the filmed table. Other steps shortened: answer 4 s, windows 4 s, why 4 s, 3-D 2 s
   (caption shortened, no numbers), IM-1 4 s, map 3 s, closing 3 s. The previous video is kept as a scratch
   copy. A caption-3 change naming Malapert was tried and reverted, because "Malapert" is not on screen in
   that step.
7. **Checks.** Full suite 283 passed. `scripts/ui_check.js` all passed (the regions check now also asks for
   "not real launch opportunities" and "illustrative figure"); first screen #slip top 798 px; regions panel
   with no console errors and no horizontal scroll at 1280 and 390 px. Server (PIDs 65884, 67816) stopped;
   ports 8100 to 8199 free.

## Explainer (from 13:52)

- `demo/slipday_explainer.mp4`: 174.7 s (2 min 55 s), 17 scenes, a screen recording of the running app on
  port 8101 (`scripts/record_explainer.js`), captions in a band, synthetic voice (ElevenLabs, "Alice",
  eleven_multilingual_v2; `scripts/make_explainer_voice.py`, key read at run time only). No clip is sped up:
  each scene lasts its line plus 1.3 s (`scripts/make_explainer_video.py`).
- Lines were cut once: the first set ran 245 s of voice; rewritten to 153 s.
- Checks: the on-screen text of every scene is saved with the recording; a frame per scene was pulled from
  the finished video and read. Two captions were changed to match the screen: the typed site (No: 5 of 240
  sunlit hours, the Sun behind ground 88.4 km away) and the map (574 of 733 keep a margin; the "639 of 733"
  line of the 20 m check sits below the filmed area in this recording, so it is not quoted).
- `docs/EXPLAINER.html` with stills in `docs/explainer/` (16 images, 2.2 MB): same order and wording, light
  and dark, no horizontal scroll at 390 px, all images load. Footer and VOICEOVER.md say the voice is
  synthetic (ElevenLabs).
- Challenge resources section added to the README, the draft and the explainer page (QuickMap and Moon Trek
  are linked from every site, no data taken; JPL Horizons checks the Sun and Earth directions; the CSA page
  was background reading only).
- Tests reading the documents: 73 passed. My server on 8101 stopped; the orchestrator's server on 8100 left
  running.

## Add-on integration (14:18 to 14:42)

- Atlas: `"addons.atlas"` added to the optional-router loop in `api.py` (import path checked; the three
  endpoints answer, a year outside 2027 to 2035 gives 404); `<div id="addon-atlas">` after the regions panel;
  script after app.js.
- Listen and play: stylesheet link, `#addon-listen` and `#addon-game`, two scripts. The containers sit after the
  atlas, not right after the card as the note suggests, because the first screen must still show the slip grid
  (#slip top 798 px). Of the six suggested changes, made: `aria-live="off"` on `#missionOut` and `#ribbon`, and
  the map's label now says coordinates can be typed instead. Not made (changes inside app.js): roving tabindex,
  focus tooltips, a card-change event. Its check, run against my server: 25 passed on its own demo page. On the
  real page two of its steps fail for placement reasons only (700 Tab presses do not reach controls placed
  lower down; after a longer walk the live region has moved on from the first announcement); a direct check on
  the real page shows the card answer and the windows announced in order.
- Safety: `"addons.safety"` added to the loop; `#addon-safety` in its own panel after the slip grid (directly
  under the card it pushed #slip to 959 px). A note beside it gives NASA's slope uncertainty (about 2 degrees
  per point), says the opening example's 4.9 degrees is close to the 5-degree goal, and that 76 of the 78
  region sites have only 80 m terrain. The add-on itself already says the 8-degree limit is lander lean used as a
  ground-slope limit, and labels the map count as "48 of the 343 map points that keep at least 1 day of slip";
  343 + 390 = the map's 733 points that pass on the planned date, while the map's own 574 counts points keeping
  0 days or more.
- Full suite 332 passed; ui_check all passed; no console errors. README and explainer page describe the three
  add-ons in plain words. Server on 8101 stopped; 8100 (orchestrator) left running.

## Add-ons S5 (relay) and S4 (safe touchdown) (15:17 to 15:31)

- Relay: `"addons.relay"` in the router loop; `#addon-relay` just above the Deep Space Network panel; script after
  safety.js. On the page: the card still reads Yes, 8 days (Earth only); the relay panel shows 311 h with the
  Earth alone and 336 of 336 with the Earth or two relays, slip margin 8 days alone and 11 with relays, the
  "cannot be predicted from this model" line and "a representative relay orbit ... not a live service".
- Safe touchdown: `"addons.safetouch"` in the loop; `#addon-safetouch` inside `#safetyPanel` after `#slopeNote`;
  script after safety.js. The panel shows the three lander classes and the 2-degree lines (precision 5-degree
  figure 90 % falling to as low as 23 %). Its boulder and lander-class caveats sit in a fold-out, so a visible
  note was added after it (`#touchNote`): slope only, no boulder data; the lander classes are assumptions;
  the 90 % to 23 % example.
- README and explainer page: one plain paragraph each for both add-ons.
- Full suite 385 passed; ui_check all passed; #slip top 798 px; no console errors at 1280 and 390 px. Server on
  8101 stopped; 8100 left alone.

## UX pass (from 15:47; two reviews: reviews_final4/ux_judge and ux_public)

Page height, all folds closed (reviews' figures before): 1280 px 5,634 (18,071); 768 px 8,022 (26,473, and the
page scrolled sideways to 902 px; now 768); 390 px about 10,600 (22,702). No horizontal scroll at any of the three.

Done:
- First screen (1280 x 800): challenge name under the title, three plain intro sentences (from the game's
  intro), a sticky jump bar (Answer, Where else, 3-D view, Precision, Real missions, Artemis regions, Can you
  trust it?, Game), skip links and a `<main>` landmark; the input sentence; the verdict, the 20 m / 5 m line and
  a "Challenge objective" line with the Sun's and the Earth's azimuth, height above level and height above the
  skyline at touchdown (1.2 and 0.6 degrees for the example, matching the card's 0.64); the skyline chart with a
  legend (solid in view, faint hidden, compass degrees); what ends the margin; the next windows; "Other sites,
  other hours" and "Download this answer (CSV / JSON)". ui_check measures all of these above 800 px.
- Folded under "More about this answer": the Earth margin and mask (with "an Earth mask is the least height
  above the skyline a radio link is given"), the smooth-ball strip text (reworded), how sure, the answer in
  words. The station, shadow and 3-D buttons stay visible next to Download. No caveat was dropped.
- Download this answer: built in the browser from the card, the windows and (if asked) the other sites;
  the CSV header carries the need, scatter, verdict, margin and the illustrative-need note.
- Planner's own site and needs on the card: "Land at" lists the loaded sites, every curated site (picking one
  adds it) and "Your own coordinates…" (latitude in degrees south; a minus sign is read as south with a
  warning; far from the pole it warns that no terrain covers it). Days on the surface is a number (6.25 works).
  Landing scatter (50/100/200 m) is on the card, kept in step with the rules fold. Adding a fifth site replaces
  the fourth and says so, instead of refusing. The page still opens with the same four sites, so the published
  figures ("13 of 20 other sites") stay true; the public review asked for two.
- "Launch slipped by N days" on the card: the same as clicking day N on the strip; the plan and its monthly
  windows stay. A line under the windows says that typing a new date makes it the plan, with its own windows.
  A day banner under the strip answers a click: "Land on 27 Nov 2026 (launch slipped 9 days): No: only 95 hours
  of Earth contact of the 100 needed."
- Consistency: the map legend now reads "574 of the 733 ... (counting a margin of 0 days) keep a slip margin
  ...; 159 lose it. Of the 574, 343 survive at least one day of slip" (343 from the legend's own bins), and the
  draft and slide 6 say the same. The draft's "400 random polar points" is now "200 random polar points on each
  of the two maps". The regions panel says the atlas covers 2027 to 2035 and comes out about a point lower
  (27, 36, 39, 43 %), with 2027 to 2030 identical, and gives all three drift figures with their methods
  (18.4 Sun's path 2025 to 2032; 18.1 / 18.65 atlas landing times 2027 to 2035; 18.6 expected).
- Order: answer, where else (map and sites), 3-D, precision, flat ground, real missions, regions, atlas (folded),
  can you trust it (tables folded); then "More tools", each folded with a one-line summary: slip grid,
  compare over time, relay, not like Earth, listen, game. The safety panel has its own heading.
- Keyboard: the slip grid has one Tab stop per row with arrow keys, Home and End. Folded panels take no Tab
  stops. Tablet: the Sites panel stacks below 900 px. Phone: the card's day cells are 24 px in a strip that
  scrolls sideways, checkboxes 20 px; the verdict is still on the first phone screen (835 px of 844).
- Plain words: badge "Real Moon terrain: NASA LOLA laser heights, one every 80 m (80 m/px)"; panel titles
  shortened; the dead "Run a live Horizons cross-check" button is hidden when the server has it switched off.
- ui_check: the old "slip grid begins on the first screen" check became "the slip grid (4 x 60) is built, in
  its fold", and the phone "all 60 card days on screen" became "60 card days of at least 24 px in a scrolling
  strip" (the grid row still needs all 60 on screen). New checks: objective line in numbers, chart legend,
  windows, Other sites and Download on the first screen; jump bar, skip links, main. Two wording-only regex
  updates (smooth-ball strip; ride-through read from the whole fold). No number check was loosened.
- Video re-cut: 29 s, 8 steps (inputs and verdict, objective line and chart, day 9, 3-D, windows and buttons,
  map 639 of 733, IM-1, 2 s closing); a frame per step read. The voiceover version (29.5 s) was redone with
  `scripts/make_draft_voiceover.py`; no clip needed speeding up.
- Checks: full suite 385 passed; ui_check all passed; document tests re-run after the last edits, 73 passed.

Not done (with reasons):
- Opening with two sites: kept four so the published counts stay true.
- The public review's colour-blind point: the strip already differs by height and hatching, not colour alone.
- "Which of the best map points stay a clear yes?" (36 s) now shows a running clock and "about 40 s the first time"; no per-point count (the server answers once).
- The 12 px text floor everywhere, the lone ✕ swatch, hiding the whole-Moon chart, one dispersion convention
  across the precision panels (759 m against 820 ft), the 136.9 km label (only reworded to "at this moment"):
  not done.
- Add-on issues, for their owners: the atlas makes about 1,190 Tab stops when opened; the game keeps focus on
  "Start again" and scores an all-No round automatically; Listen's Escape works only inside its box.
- The explainer video and page were not re-recorded for the new layout.

## Add-on follow-ups (16:28 to 16:40)

- Atlas: each heat chart (the overview and the nine years) is one Tab stop with arrow keys (left/right by month,
  up/down by row, Home/End), the focused cell's value read into the live line, and each chart's label carries
  its year summary. Tab stops in the atlas: about 1,190 to 15.
- Game: focus moves to the round's question every round, including the first; the live line is for screen
  readers only (the same sentence was shown twice); a round where none of the three sites works gives no point
  and does not count ("You scored 3 of 4 (1 round had no working site and did not count)"). Its check now
  accepts that wording; `static/addons/demo.html` was refreshed from the current page with the Listen and Game
  folds open (the old snapshot no longer matched app.js). Listen/game check: 25 passed.
- Text size: every CSS font size under 12 px (41 places in the page, the 3-D and contrast scripts and the
  add-ons) is now 12 px, and the regions calendar labels too. SVG chart labels scale with their charts and
  were not changed. First screen still holds (Download at 762 px; phone verdict 835 px).
- Landing spread: one convention everywhere, the distance or oval that holds 99 % of touchdowns (3.035 standard
  deviations in two dimensions): "99 % within 100 m of the aim", "99 % within 759 m of the aim", "99 % within an
  oval about 4.1 km by 2.4 km", as the safe-touchdown panel already wrote it; IM-2's source is "250 m (820 ft)".
- Full suite 385 passed; add-on tests 102 passed; ui_check all passed. Server on 8101 stopped.

## Last fixes (from 17:01; reviews_final5)

- Stale claims: the draft no longer says the app does not model slopes or lander tilt (slope is checked where
  5 m or 20 m terrain covers the site; no power or temperature model); the explainer's IM-1 section and own-site
  text are corrected, and its video is labelled "recorded before the final page layout" (not re-recorded).
- 5 m slope at the opening example: ours 4.87 degrees at the south-west point, the reviewer's 5.06, NASA's slope
  map 5.0. Both fit a plane to 3 x 3 cells of the same Site07 model; moving the point by up to one 5 m cell
  gives 4.43 to 5.76 degrees, so the difference is which cell the point falls in. Page, README, draft, slide
  and explainer now say "about 5 degrees, right at NASA's 5-degree goal; one 5 m cell gives 4.4 to 5.8". The
  page never stated "13 of 13 under 5".
- Video: 29 s with the inputs and verdict, the objective line, day 9, 3-D, the slope line (an add-on), the
  regions calendar, the map and a 2 s closing; frame per step read; voiceover redone (29.5 s), no speed-up.
  Slide 7 has one line for the add-ons; the draft has one paragraph; the draft's long windows paragraph is split.
- Atlas fold summary says it uses the same 78 sites and check as the regions panel over 2027 to 2035 (about a
  point lower); the regions panel already said so from its side.
- "Other options:" now says it is for the next monthly windows of the planned date, not the day picked on the
  strip; "most robust" became "steadiest".
- Text: a 12 px floor for inherited sizes (`small`, em-sized notes). With every fold open, no visible text
  outside the charts is under 12 px.
- Full suite 385 passed; ui_check all passed.

## Explainer re-recorded on the final layout (from 17:16)

- `demo/slipday_explainer.mp4`: 173.9 s, 19 scenes, fresh recording on port 8101 (`scripts/record_explainer.js`,
  rewritten for the final page): question, card, challenge objective, launch slipped by 9 days, windows with
  other sites and Download, 3-D, own site on the card, map, 80/20/5 m, slope, safe touchdown, IM-1, regions,
  atlas, relay, listen, game, limits, closing. Voice "Alice", every clip at normal speed (each scene lasts its
  line plus 1.3 s). One frame per scene pulled from the finished video and read: every number in the captions
  is on screen. The recorder's site switch now sends a bubbling change event (the relay add-on listens on the
  document; with a non-bubbling event it kept showing the typed site; a real user's change bubbles).
- `docs/EXPLAINER.html`: 18 sections in the same order with new stills from this recording; the "earlier
  layout" note is gone. All 18 images load at 390 and 1280 px, light and dark. Old clips of dropped scenes
  were removed from `demo/voiceover/explainer/`.
