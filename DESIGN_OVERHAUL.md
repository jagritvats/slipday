# Slipday design overhaul (15 Nov 2026)

The plan was written first, from 18:45 IST; edits began once the front end was free. The safety copy of the old front end
is in `_static_before_overhaul/` (not referenced by the page). Every number on screen still comes from the API, and no
computation, verdict or caveat was changed.

## 1. What needed fixing

The answer was trusted, but the page read as a dense lab page. The one firm objective of the challenge (the Sun and the
Earth against the horizon at a chosen site and date) was a run-on sentence. The site and date controls were a
9-input sentence, and picking a site was nine screens down. Chart labels collided, and buttons and cards followed no
common style. Three colours failed WCAG AA, and the add-on panels looked pasted in.

## 2. Design decisions

1. **The core navigator flow comes first.** The first screen follows the challenge's own steps:
   - choose a site;
   - choose a date and time;
   - read the Sun and the Earth against the real skyline;
   - decide what to do if the launch slips.
2. **Map first.** The south polar map (click to pick) heads the site column on the first screen, beside the verdict band and the skyline.
3. **One decision path.** Four steps: Answer, How sure, Why, What to do. "What to do" ranks real options (wait for a later
   good date, or move to another south-pole site) with their verdicts, slip margins and distances.
4. **Data-forward.**
   - A "Built on" strip near the top links to the evidence.
   - Source tags next to the verdict show:
     - the terrain grid;
     - the 13 touchdown points;
     - the 20 m and 5 m check;
     - the need (illustrative unless a published plan is named).
   - The proof tiles keep their headline figure in view and fold the method text under it.
   - The terrain grid each answer used (`terrain_grid` from `/api/mission`) shows as a chip in both verdicts, for example "on 5 m terrain".
5. **Side by side.** The comparison table holds up to four sites, each with its number (the same as its marker on the map) and the best value in each row shaded. Its rows:
   - verdict, slip margin, hours, darkness and Earth gaps;
   - sunset and Earthset with UTC times, and slope;
   - next good dates;
   - a per-day answer strip, a small skyline, and one sentence on what hides the Sun or the Earth.

   A single "Launch slipped by N days" control applies to every column at once.
6. **A plain path in.**
   - A dismissible "start here" strip with four steps; it never blocks the tool and is never a splash screen.
   - Ready-made comparisons: Worked example, Ridge or crater floor, Apollo 11 or the pole, IM-1 as flown, Slip a week.
   - The comparison is never empty.
7. **The slip question is the planner's view on top of the core.** The existing mission card is kept whole under "Launch slipped?".
8. **The section bar marks the section in view.**
9. **Sky view.** The same data as the skyline chart, drawn as what you would see standing at the site:
   - a black sky, the real skyline, and the Sun and Earth discs;
   - heights stretched 4 times, and the page says so.

   It follows the time slider.

### Visual system (`static/overhaul.css`, loaded last)

- **Colour (light / dark):**
  - page `#eef0f3` / `#0f1218`;
  - surface `#ffffff` / `#171b22`;
  - ink `#141820` / `#e9ecf1`;
  - secondary ink `#454d5a` / `#b9c1cc`;
  - muted `#59626f` / `#9ba5b3`;
  - accent (horizon navy) `#1d3f8f` / `#9dbcff`;
  - Sun `#c2560f` / `#f08a4b`;
  - Earth `#2364c4` / `#6aa6ff`;
  - three verdict tints (yes, not sure, no), each with its own ink.
- **Type:** the system UI family (no web fonts, no CDN). The scale is 12 / 13 / 15 / 18 / 24 / 30 px, with tabular numbers and no all-caps labels.
- **Spacing:** 4 / 8 / 12 / 16 / 24 / 32 px.
- **One card:** surface, 1 px line, 12 px radius.
- **One button:** 36 px high, 8 px radius, weight 600. The primary button is filled in the accent colour; date chips are rounded.
- **Charts:**
  - drawn at their real pixel width, so text stays 12 to 13 px at every screen size;
  - labels have a halo and switch sides at the edges;
  - every chart has a legend with units.
- **Add-ons share the system:**
  - the same buttons;
  - fold markers on their own folds;
  - no card inside a card;
  - capitalised lander class names.

### Accessibility

Checked by script at 1280 px with every fold open, in light and dark mode:

- WCAG AA contrast: 0 failures;
- text under 12 px: none;
- buttons and stand-alone links under 24 px: none, apart from the data cells of the atlas grid, which are 18 x 32 px as before.

Also in place:

- skip links, landmarks (`header`, `nav`, `main`, `footer`) and a visible 3 px focus ring;
- the time slider works with the arrow keys, and reports the time as text;
- `prefers-reduced-motion`: Play takes larger, slower steps, and there are no transitions;
- no autoplay audio (Listen is unchanged);
- no sideways scroll at 1920, 1280, 768 and 390 px in light and dark mode. Wide tables scroll inside their own box.

## 3. What changed, file by file

| File | Change |
|---|---|
| `static/index.html` | New order and grouping; the navigator, decision path and comparison sections; the "Built on" strip; the polar map moved into step 1; precision panel and two long safety notes folded; new section bar |
| `static/navigator.js` (new) | Site search and grouped list, own coordinates with North/South and East/West buttons, date and quick steps, skyline chart and sky view with the slider, speeds and Play, Sun and Earth table, hourly strip, summary sentence, verdict band and source tags, comparison table, decision path, presets, folded proof tiles |
| `static/overhaul.css` (new) | The visual system above, applied to the page and the add-ons |
| `static/app.js` | A small bridge `window.SlipdayApp` that reads and sets the site list and the plan, with an update event. Map fixes from `BUGFIX_MAP_SLOPE.md`: the first-visit layer is saved to the address, slip layers say "(close-up only)", and one plain note says why the map moved or what a slip layer covers. `FULL_SLIP` is the switch for a future full-area slip layer |
| `static/addons/safety.js` | The slope line reads the shown site directly, clears while loading, names its site and shows an error state, so it never keeps an old answer. New "slope only" map mode (the default when the slope layer is on): every close-up point coloured Flat (5° or less, NASA's goal), Flat enough (up to 8°, NASA's limit) or Too steep, from `GET /api/addons/slopemap` (fetched once and kept). The address is one constant, `SLOPE_SOURCE`. "Slip and slope together" keeps the earlier layer |
| `static/addons/planner_game.js`, `game.css` (new) | The mission-planner campaign (section 5) |
| `tests/navigator_check.mjs` (new) | Browser check of the navigator against independent API calls |
| `tests/addons/game_check.mjs` (new), `tests/addons/listen_game_check.mjs` | Game checks (only the game parts of the second file changed) |


## 4. Every feature that was on the page, and where it is now

| Feature before | Where it is now |
|---|---|
| Header, terrain badge, challenge name | Header (same) |
| Intro paragraph | Navigator lede (`#intro` kept) |
| Section bar | Section bar: Sun and Earth · Decide · Compare · Launch slipped? · Where else · Is it safe? · Talking to Earth · Plan ahead · Proof · Play |
| Skip links | Kept, plus "Skip to the Sun and the Earth" and "Skip to Launch slipped?" |
| Mission card: sentence inputs, scatter, launch-slipped input, real-landing buttons, "What am I looking at?", year ribbon, verdict, 20 m line, challenge objective line, day strip, smooth-sphere strip, skyline chart, what ends the margin, ride-through, next days, monthly windows, other sites and hours, Download CSV and JSON, links to other tools, "More about this answer" | "Launch slipped?" section, unchanged |
| Polar map, area and layer menus, scatter re-check, permanent shadow, legend | Navigator step 1 (moved, same controls and ids) |
| Map note, "Which of the best map points stay a clear yes?", "Where can you land beside permanent shadow?", curated site menu, coordinates, site chips, whole-Moon grid, rules for "usable" | "Where else" |
| 3-D view | "Where else" (and "Open the 3-D view" in the navigator) |
| Real missions | "Where else" (opened from the card) |
| Slope (flat enough?) and safe-touchdown chance, with their notes | "Is it safe?" (notes folded under plain summaries); slope also in the comparison and the decision path |
| How precise must the landing be? | "Is it safe?", in a fold |
| Relay satellites, DSN hour by hour | "Talking to Earth" |
| NASA landing regions calendar (formerly called the Artemis III regions), 2027 to 2035 atlas | "Plan ahead" |
| Slip grid (CSV, copy link), Compare over time (Play, CSVs) | "Plan ahead", folds |
| Can you trust it? tiles and tables, live Horizons check | "Proof" (tiles fold their method text) |
| Game, Listen, Not like Earth | "Play, listen and compare with home" |
| Footer (ephemeris and terrain sources) | Footer (same) |
| (new) Upcoming missions board (`static/addons/missions.js`, built separately) | "Real missions ahead", between "Launch slipped?" and "Where else", with its own section-bar link "Missions" |

Nothing was removed.

Wording: NASA now says Artemis III will not land, so the page no longer says "Artemis III regions". It says "NASA's nine south-pole landing regions (for the first crewed landing, Artemis IV, early 2028)" in full, or "NASA landing regions" for short. This applies to the regions heading, the "Built on" link, the missed-window table heading, a source note, the atlas text and one game briefing. Text that comes from the API keeps the API's own words.

## 5. The game

It is a five-scenario campaign, harder each time:

1. a small slip;
2. a slip past the 8-day margin;
3. the IM-1 replay, with its 168 h need from the published plan;
4. a south-pole site choice;
5. a low-Sun January.

Each scenario runs the same way:

- a briefing (the needs, the plan and the slip; the 100 h of Earth contact is labelled illustrative);
- 3 or 4 options, each with an inspect panel:
  - the skyline and tracks;
  - hours against the need;
  - slope and safe-touchdown chance;
  - the next window;
  - relay hours;
- the real outcome with its reason;
- a 14-day Sun and Earth timeline;
- the best of the options offered.

The scoring rule is stated on the page: Yes 100, Not sure 40, No 0, plus 5 points per day of margin (at most 50), minus 1 point per day waited. Scores are kept in this browser only.

## 6. Screenshots

`screenshots/overhaul/`:

- `before_*`: the first screen before the overhaul, from the final visual review;
- `after_*`: the first screen now, at 1280 x 800 and 390 x 844, in light and dark mode.

## 7. Tests (final run about 20:55 IST, own server on port 8180)

| Check | Result |
|---|---|
| Python suite, `.venv`, `pytest tests` (final run, integration round) | **425 passed, 0 failed** (6 min 10 s). The two earlier failures, on the slides file and the atlas agreement, are gone |
| `tests/navigator_check.mjs` (new): the Sun and Earth table, the slider, the verdict, search, own coordinates, the comparison and the decision path, each against an independent API call; no sideways scroll at four widths in two modes | 14 passed, 0 failed |
| `tests/addons/game_check.mjs` (new): one scenario played end to end by keyboard; the outcome equals an independent `/api/mission` call | 17 passed, 0 failed |
| `tests/addons/listen_game_check.mjs` (game parts updated) | 25 passed, 0 failed (one earlier run timed out on its first 30 s wait while the Python suite was loading the machine; the re-run passed) |
| Contrast, text size and tap-target audit (script, every fold open, light and dark) | 0 failures |

Run the browser checks with `node tests/navigator_check.mjs` (own server on 8184; `NAV_BASE` for a running one), `node tests/addons/game_check.mjs` (8182; `GAME_BASE`) and `node tests/addons/listen_game_check.mjs` (`ADDON_BASE`).

## 8. Not done, and what would come next

- **Whole-map slip layer: done and checked (integration round, about 20:55).** The wide view now shows `/api/addons/fullmap` (92,416 points, one every 2 km, complete), with the close-up's 500 m layer drawn on top in its 60 km square. The close-up view keeps the 500 m layer with its 13-point check.
  - The legend says, in plain words: one point every 2 km, each checked at its own spot only, and the close-up checks 13 touchdown points.
  - It also gives the overlap figures from the API's `agreement_with_close_up`. At 41 shared points that pass, the 13-point check keeps the margin at 27, shortens it at 4 and loses it at 10, so the whole-map layer is optimistic.
  - For any plan other than the opening one, the API answers `available: false`. The legend then shows its reason and a "Show the close-up" button, not an empty map.
  - Map screenshots are in `screenshots/overhaul/`: `map_wide_1280_*`, `map_closeup_1280_*` and `map_wide_otherplan_1280_light`.
- The `/api/map` extent problem noted earlier (30 km instead of 608 km) was fixed on the server; the wide view and its "published average sunlight" layer are back.
- The time slider moves the navigator's chart, sky view, table and strip, and the 3-D view's slider when no slip is picked. The "Compare over time" cards keep their own time control.
- The relay add-on keeps its own two extra colours (teal and purple) for "relay only" and "both".
- The game briefing always says "landing in sunlight with the Earth in view", even if those checkboxes are off.

## 9. Fixes after the post-overhaul review (21:10 to 21:25 IST)

1. **Proof tiles follow the live answer.**
   - The two stored 80 m / 20 m tiles are now titled as stored checks. They no longer claim "the page computes on 80 m".
   - Two new tiles read `/api/mission` now and show the live verdict, the touchdown points that pass and the terrain grid used (`terrain_grid`). They cover the opening example and the Shackleton connecting ridge (C1).
2. **The comparison follows the slip.**
   - With "Launch slipped by N days" set, every row moves to the slipped landing: Sun and Earth, sunset, Earthset, darkness, Earth gaps and the small skyline.
   - The rows say "at the slipped landing".
3. **The slip drives "4 What to do".** The same control reworks the decision path for the slipped landing: "What to do after a slip of N days", with the options ranked again.
4. **Real missions in "What to do".** One line, read from `/api/addons/impact`, names the upcoming missions that plan to land at Mons Mouton, with the distance from the shown site. It links to the board.
5. **Phone order.** Step 1 (the site) now comes before steps 2 and 3.
6. **Shorter page.** Height with folds closed, measured:
   - 6,627 px at 1280 (it was 12,241);
   - 11,717 px at 390 (it was 22,514).

   Newly folded, each with a one-line summary:
   - the missions board;
   - the map notes and site list;
   - the 3-D view;
   - "Is the ground flat enough?";
   - the regions calendar.

   Links into a fold open it. Nothing was removed.
7. **The slip-day map up front.** Buttons above the first-screen map switch between "Days of slip it survives" (the default), "Slope" and "Plain relief", with one line saying what the colours mean.
8. **Lunar against Earth.** "Not like Earth" now sits straight after the Sun and Earth view.
9. **Libration explained.** Under the skyline chart: "The Earth's path makes a small loop: the Earth wobbles slightly in the sky because the Moon's tilt and orbit make it rock (this is called libration)."

Feature map changes:
- "Not like Earth" moved from "Play, listen and compare with home" to just after the navigator.
- The missions board, the map notes and site list, the 3-D view, slope and safe touchdown, and the regions calendar are now folds in the same sections.

Tests after these fixes (21:15 to 21:24 IST, own server on 8180):

| Check | Result |
|---|---|
| Browser checks | `navigator_check` 14 of 14, `game_check` 17 of 17, `listen_game_check` 25 of 25 |
| Contrast, text-size and tap-target audit | 0 failures |
| Python suite | 423 passed, 2 failed. Neither involves the front end |

The two Python failures:
- `test_regions.py::test_the_figures_quoted_in_the_documents` was failing on documents being edited for the 20 m numbers; it passes on re-run.
- `test_impact.py::test_one_month_rejudged_from_scratch_matches` fails because the stored mission board gives a margin of 4 days, while a re-run on today's finer live terrain gives 2. Its stored results need rebuilding on the live grid.

## 10. Planner, outreach and comparison round (21:58 to 22:16 IST)

### Fixes
- **Two-part verdict.**
  - The band says "Power and contact: Yes, …" and then "Ground: flat enough / too steep (steepest of 13 points X°, limit Y°)", read from `/api/addons/safety/site`.
  - When light and contact pass but the ground fails, the band turns amber with "Light and contact work, but the ground is too steep here."
  - A plain line says what Yes means.
- **Instant map clicks.**
  - A clicked point answers at once from the precomputed grids: `/api/slipmap` 500 m in the close-up, `/api/addons/fullmap` 2 km elsewhere, `/api/addons/slopemap` for the ground. It names the nearest grid point's distance.
  - About 13 s later the full check replaces it, marked "full check on N m terrain".
- **The headline follows the slip.**
  - With a slip set, the slipped answer is the big headline on both the navigator band and the "Launch slipped?" card, for example "Slipped 10 days, landing Nov 28: No, only 56 sunlit hours of the 240 needed".
  - The planned answer becomes the small line.
  - The comparison's slip control and the card's "Launch slipped by" are now one value.
- **Bigger map.** It takes about half the width at 1280 and 1920. On a phone the verdict comes first, then the map.
- **Trade table.**
  - New row: safe-touchdown chance per lander class (assumed accuracies). The best cell is shaded for the CLPS class.
  - "Download this table (CSV)" exports every row of the comparison with the plan and the slip in its header.
- **Stand here.** Buttons under the verdict open the sky view, or the 3-D view of the chosen spot.
- **Outreach fixes.**
  - Listen follows the main card: the navigator's own requests now carry the add-on header, so they no longer look like the card's.
  - The game's inspect panel and its "wait" option now read the same field: the plan's first monthly window after the slipped date.
  - The section bar highlights the clicked link and watches headings.
  - Enter in the search picks a single match, and the wait reads "Working it out (about 10 s)…".
  - A "Play the mission game" button sits in the start strip.
  - The map legend now reads "Blue = a good place to land even if the launch slips…".
- **Hook line.** One line at the top is built from `/api/addons/impact` and `/api/region-availability`: one region against three for Artemis IV, and VIPER after a week's slip. It links to the missions board.

### Not done in this round
- The hour-by-day heatmap.
- The plan-holds, joint-chance and permanent-shadow-distance rows of the trade table. Their endpoints, and the `addon-planner` hand-over note, had not arrived.
- A low-resolution first image for the relief map on phones.

### Tests (22:06 to 22:16)
- `navigator_check`: 16 of 16. It now also checks the slipped headline, an instant map-click answer and zero page errors.
- `game_check`: 17 of 17.
- `listen_game_check`: 25 of 25.
- Contrast and tap-target audit: 0 failures.
- Python suite: 434 passed, 1 failed. `tests/addons/test_planner.py::test_lighting_opening` is the new planner add-on's own back-end test, still being built by another agent; it involves no front-end file.

## 11. Last additions (22:16 to 22:21 IST)
- **VIPER preset.** "VIPER at Mons Mouton" in the preset row loads VIPER's first good landing time, in its published period, at the published candidate site the missions board names. All of it comes from `/api/addons/impact`.
- **Map computation chip.** A line under the map reads, for example: "Behind this map: 106,816 terrain skylines (92,416 every 2 km, 14,400 every 500 m near the pole), 720 directions each, reaching at least 301 km, on NASA LOLA heights". The counts come from `/api/addons/fullmap/about` and `/api/map`; the directions and reach come from the site's `/api/why` skyline.
- **Planner add-on.**
  - `addon-planner` sits in a fold under the decision path, the "how sure, in more depth" part.
  - `planner.js` loads only when that fold opens, so the first load and the main interactions never wait on it. The page then repeats one cached mission request, so the add-on starts on the shown site.
  - "Other sites at the slipped date" runs only after a slip is set and Check is pressed. A plain note says it checks 30 sites and can take up to 2 minutes the first time.
- **Trade table.** A new row, "Plan holds / flat / both, per lander class", shows the joint chance from `/api/addons/planner/joint` for each compared site, loaded without blocking. The best CLPS-class value is shaded. Distance to permanent shadow is still not shown: no endpoint gives it.
- **Browser checks, run once at the end.** `navigator_check` 16 of 16, `game_check` 17 of 17, `listen_game_check` 25 of 25, and the contrast and tap-target audit has 0 failures.

## 12. Deploy batch (22:27 to 22:37 IST): findings, outreach, brief, thermal
- **What we found:** its own section near Proof, with a "Findings" link in the section bar. `findings.js` loads only when the fold opens or comes near the screen.
- **Glossary:** `glossary.js` is loaded deferred. No focus, phone or contrast clash was found in the audit.
- **Friendly names:** shown wherever a site is named, with the subtitle as the smaller line. This covers the card title, the site list (search also matches the friendly name), the comparison columns and the decision path. The internal `name` is unchanged.
- **Best 3 spots this month:** at the top of "Where else", and only on demand. A note says the first look at a month takes 7 to 40 s. Each spot has a "Show on map" button.
- **Review-board brief:** its button sits under the decision path.
- **Diviner temperature card:** beside the slope check in "Is it safe?". It was checked at 1280 and 390 px in light and dark: it renders with no console errors.
- **Integration fixes:**
  - `brief.js` and `thermal.js` now skip `/api/mission` requests that carry the add-on header.
  - The navigator re-asks the shown site's mission once, without that header and answered from the server's cache, so the brief, the thermal card and the planner follow the shown site.
  - The brief button uses the accent colours in dark mode; it was 1.9:1 and now passes.
- **Learned estimate:** wired, but used only when `/openapi.json` lists `/api/addons/estimate`, so an unregistered endpoint never shows a 404. Its label is "Learned estimate (right N % of the time in testing); the full check on the finest terrain follows", with N read from the endpoint's own `measured_accuracy`. It falls back to the nearest grid point, and the full check still replaces it.
- **Checks:** `navigator_check` 16 of 16, `game_check` 17 of 17, `listen_game_check` 25 of 25, and the contrast and tap-target audit has 0 failures in both modes.

## 13. The skyline as "you are here" (22:38 to 22:42 IST)
- **Title:** the chart is now headed "The skyline all around you, standing at <friendly name>". Above it, a small figure line reads "You are here, at the centre of this panorama. Left to right: every compass direction around you. Up: height above level ground."
- **Compass inset:** a small circle in the top-right corner of the chart shows the same view from above:
  - you in the middle;
  - arrows to the Sun (orange) and the Earth (blue) at their azimuths for the shown hour;
  - the ground that hides one of them as a grey arc at its direction.

  A line under the chart gives that ground's direction and distance from `/api/why`, for example "to the WSW, 131 km away". Below 520 px the inset is left out and the same line also says where the Sun and the Earth are.
- **Plain labels:** for example "Sun: 2.3° up, just 1.0° above the ground in that direction", or "Earth: 1.0° up, but the ground in that direction rises to 5.9°, so it is hidden". The numbers come from the API's track and skyline. A long label sits above or below its dot when neither side fits.
- **Play the stay:**
  - Play, plus a "Step +6 h" button. Under reduced motion Play is hidden and only the step button is offered.
  - The time and date update live, with "So far: the Sun up X of Y hours, the Earth in view Z of Y hours", and whether each is up or hidden now.
- **Instant approximate skyline:** wired for `/api/addons/skyfast` and switched on only if `/openapi.json` lists it. Its skyline is drawn at once, labelled "Approximate: the nearest precomputed point, N m away", and the exact `/api/why` replaces it.
- **Checks:** `navigator_check` 16 of 16, `game_check` 17 of 17, `listen_game_check` 25 of 25. The contrast and tap-target audit has 0 failures, and there are no console errors at 1280 or 390.

## 14. Final polish pass (22:57 to 23:25 IST)
The first screen's layout and the skyline chart were not moved or restructured. Every number still comes from the API, and nothing was removed.

**Bugs fixed**
- **Learned estimate now shows.** The API gives its plan as words ("landing 18 Nov 2026, … 240 sunlit hours and 100 hours of Earth contact in the first 14 days"). The page reads the date, the hours and the days from that text and compares them with its own plan (`estPlanMatches`). The label now gives the measured accuracy from `measured_accuracy.verdict_accuracy`, for example "right 97.5 % of the time in testing".
- **Instant approximate skyline now shows.** `/api/addons/skyfast` returns a skyline only. The chart draws that ground line at once, with no Sun or Earth tracks, labelled "Approximate: the skyline of the nearest precomputed point, N m away" (`distance_m`). The exact `/api/why` replaces it.
- **Battery, darkness and launch windows are on the page.** `power.js` and `trajwindows.js` are loaded. `#addon-power` and `#addon-darkness` sit in "Is it safe?" next to slope and temperature. `#addon-trajwindows` is a new fold, "Launch windows from orbital mechanics", right after the real-missions panel. A rocks line (`#rocksLine`, from `/api/addons/rocks`) sits under the slope note in the API's own words: no rock value is shown, and why.
- **Findings chart.** The stacked bars set each part's height from its own value, so there are no more negative `<rect>` heights (that was 9 console errors).
- **Brief follows the shown site.** `brief.js` ignores `/api/mission` answers for any site other than the one shown (`SlipdayApp.selected()[current()]`).
- **Temperature outside Diviner's map.** When nothing is measured, the card says "Not measured here: <the API's note>" instead of four "no data" boxes.

**Navigation**
- Section-bar links open the section's first fold (they never close one), move focus to the section heading, and add `at=<section>` to the address beside the plan (`s=…&d=…`, unchanged). Opening any fold does the same. A reload with `at=` opens and scrolls to that section. The bar's highlight of the section on screen was already in place.
- A "Back to top" button (44 px high) appears after 1.5 screens. It respects reduced motion and moves focus to the page title.
- The closed "Is the ground flat enough?" fold shows its key number, for example "Here: steepest 4.9°, flat enough (limit 8°)".

**3-D view**
- "The ground in 3-D" is open by default. `SlipdayView3D.show` waits for an IntersectionObserver (300 px ahead of the screen) before building the scene and keeps the latest options until then. Checked: the scene is not built at first load, and it is built after scrolling, at 1280 and 390.

**Polish**
- The header now lines up with the content at 1920. It had `margin: 0`, which cancelled the centring.
- Glossary words no longer take a button's 36 px height, so their sentences keep even line spacing. This uses the inline-text exception of WCAG 2.5.8.
- **Decision path.** The cards no longer stretch beside a tall "What to do" card. Above 1100 px, "Answer", "How sure" and "Why" sit in one row, and "What to do" takes a full row below them, with its options in two columns.
- Multi-line tags (relay caveat, need, tiles) and the "Behind this map" line use an 8 px radius instead of a pill shape.
- **Comparison table.** The long "not known here" reason for the joint chance is now under a "Why not" fold in its cell. The reason is kept in full.
- The time strip leaves out the tick next to "day 0", so the two labels no longer touch.
- The card's "Stations hour by hour", "Beside permanent shadow?" and "See this place in 3-D" buttons have gaps between them.
- The 3-D controls are at least 36 x 36 px.
- **Duplicate headings.**
  - The findings fold is now titled "Open the findings", under the "What we found" heading.
  - The proof card is now headed "The checks behind every answer", under "Proof: can you trust it?".

**Not done:** a scroll hint at the edge of the wide tables on phones; a redesign of the "Launch slipped?" sentence form, which is a kept feature; the phone order of steps 2, 3 and 1, which is part of the first-screen layout recorded in the video.

**Checks (23:08 to 23:10 IST, own servers on 8181, 8182 and 8184):**

| Check | Result |
|---|---|
| `navigator_check` | 16 of 16 |
| `game_check` | 17 of 17 |
| `listen_game_check` | 25 of 25 |
| Console errors, page load and full scroll, 1280 x 800, 1920 x 1080 and 390 x 844, light and dark | 0, with no sideways scroll |
| Section-bar walk through all sections, findings fold included | 0 console errors |

The `screenshots/overhaul/after_*` files were retaken at all three sizes, in light and dark mode.

