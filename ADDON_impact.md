# Add-on: upcoming missions, who this helps, open data (impact)

Sunday 15 Nov 2026, from 19:10 IST; hard stop 21:45 IST.

Order of work, from file times: the sources were fetched 19:12 to 19:16 IST; the rule was written into the
docstring of `slipday/addons/impact_build.py` (file created 19:17:52) before the one full run started
(19:18:08). Two edits were made to that file while the run was going (19:21:40): the wording of a label and
where the LPSC 2026 source file is found. Neither changes a site, a date or a need.

## 1. First principles

### What the official "impact" criterion rewards

The 2026 Judging and Awards Guide (fetched first-hand, `data/addons/impact/sources/jag.html`, sha256 in
`DOWNLOADS.tsv`):

> "This project makes an impact by addressing either a minor or major problem, which influences the quality
> and quantity of its overall effect. The extent to which it inspires or helps others varies, ranging from a
> broad audience to a select few."
>
> Score of 5: "addressing a significant problem with proposed solutions. Its reach is extensive, inspiring,
> benefits a large audience, or could change the world."

So two things are scored: **how big the problem is**, and **how many people it reaches or inspires**. A judge
can only score what the page shows. The reviewers' three reasons (narrow audience, illustrative needs, the page
does not say who it helps) are all "the page does not show it", not "the work is missing".

### Who is really helped, and how

1. **Planners of real landings in the next 18 months.** NASA's own launch schedule lists four south-pole
   landings with a published place: Griffin-1 (late 2026), IM-4 (2027, carrying ESA's PROSPECT drill),
   VIPER on Blue Moon MK1 (landing by late 2027) and Artemis IV (early 2028, crew). Three of the four go to
   the same place, Mons Mouton. The schedule gives seasons and years, not dates: these launches can and do
   move. IM-1 moved by a month (January to February 2024; DEEP_PASS.md). The question "if we slip, can we
   still land there, or must we move?" is a real one for each of them, and Slipday answers it with the
   card's own check.
2. **NASA keeping several regions open.** NASA writes that "individual regions typically provide limited
   viable opportunities when all constraints are simultaneously satisfied" and that "more than one landing
   regions must be maintained" (LPSC 2026 abstract, NTRS 20250011660; the saved .docx is checked by a test).
   The region calendar already measures that; the Artemis IV card on the board ties it to a date.
3. **Teachers and students.** The planner game exists (ages 12 and up).
4. **People who use screen readers.** The audio and text mode exists. It has not been tested with a real
   screen reader, and the page says so.
5. **Anyone building their own tool.** Every answer is an open endpoint with CSV or JSON downloads.

What I did not claim: that any mission uses Slipday; any money, jobs or "benefit to Earth" figure; any
mission's exact landing point or date. None of those are published or true.

### What evidence on the page would make a judge say "this matters to real missions"

- Real mission names, with the place and the period copied from NASA's own pages, each quote one click away.
- A number per mission, in plain words: "of the landing times that work, this share still works after a
  week's slip, and this share after a month's slip; when it is lost, another region is open this often".
- The same check as the card (13 touchdown points, two grids), and a per-month table re-run through the card's
  own code, so the numbers are not a separate model.
- Saying plainly what is left out and why (no site published), including that **Artemis III no longer lands**.
- A "who this helps" list where every line links to the part of the page that backs it.
- A download.

## 2. Sources (first-hand, plain `curl`, generic client name)

All saved under `data/addons/impact/sources/`; URL, HTTP code, bytes, sha256 and time in
`data/addons/impact/sources/DOWNLOADS.tsv`. The LPSC 2026 abstract was saved earlier for the entry
(`data/reference/sources/artemis3_update_lpsc2026.docx`, logged in `data/reference/DOWNLOADS.tsv`).
`tests/addons/test_impact.py` checks every quote below against the saved page text and every sha256 against
the file and the log.

| Mission | Place (published) | Launch (published) | Source |
|---|---|---|---|
| Griffin-1 (NASA TO20A) | "Voyager's Griffin-1 lander will deliver NASA's Lunar Retroreflector Array (LRA) to Mons Mouton (South Pole)." | "Late 2026 Moon Base: Voyager Griffin-1" | science.nasa.gov/lunar-science/clps-deliveries/to20a-astrobotic/ ; nasa.gov/event-type/launch-schedule/ |
| IM-4 (NASA CP-22) | "The Intuitive Machines Nova-C lander (IM-4) will deliver six NASA CLPS science payloads to Mons Mouton." Also: "PROSPECT , developed by the European Space Agency (ESA)" | "2027 Moon Base: Intuitive Machines IM-4" | science.nasa.gov/lunar-science/clps-deliveries/cp-22-science/ ; launch schedule |
| VIPER on Blue Moon MK1 (NASA CS-7) | "VIPER and its instruments will be delivered to Mons Mouton by a Blue Origin Blue Moon MK-1 lander as part of task order CS-7." | "The rover has a targeted science window for its 100-day mission that requires a landing by late 2027." | science.nasa.gov/mission/viper/ ; nasa.gov release of 19 Sep 2025 |
| Artemis IV | "the agency has identified nine candidate landing regions near the lunar South Pole"; "spend approximately a week near the South Pole" | "Mission Type Crewed Surface Landing LAUNCH Early 2028" | nasa.gov/mission/artemis-iv/ ; LPSC 2026 abstract for the 5.75 to 6.25-day stay |

Looked for and left out (no published site, or not readable first-hand):

| Mission | What the source says | Why no point |
|---|---|---|
| Artemis III | "On Artemis III, NASA will test one or both human landing systems in low Earth orbit, demonstrating rendezvous and docking operations." (nasa.gov/mission/artemis-iii/) | no landing |
| Blue Moon MK1 first flight (CT-3), 2027 | "will deliver two NASA science payloads to the lunar south pole" | no site |
| Blue Ghost Mission 4 (CS-6) | "to the lunar south pole" | no site, no date on NASA's schedule |
| Nova-D (CT-4) | "to the lunar south pole" (CLPS deliveries page) | no site, no date |
| LUPEX (JAXA with ISRO) | "Lunar Polar Exploration Mission No earlier than 2028" (JAXA) | no site |
| Chang'e-7 (CNSA) | nothing on CNSA's English home page | not found first-hand |
| CS-11 (Schrödinger Basin) | "A lunar lander to be determined will deliver three NASA CLPS payloads to Schrödinger Basin." | no lander, no date; on the far side, so the card's direct-to-Earth check would always say No |

Not reachable: blueorigin.com (HTTP 429), an ESA PROSPECT page and an Astrobotic Griffin page (404). The
failed fetches stay in the log; their files were deleted. One URL meant for IM-4 returned a 2021 IM-3 release;
it was not used and was deleted (noted in the log).

## 3. The rule (written before the run; the docstring of `impact_build.py`)

- **Places**: the published candidate landing sites of Wueller et al. 2026 (JGR Planets, CC BY 4.0) in NASA's
  nine regions, already in the entry. A mission whose published destination is "Mons Mouton" uses the ten
  sites of NASA's "Mons Mouton" region (MMO01 to MMO10). Artemis IV uses all nine regions (78 sites). No site
  was picked or moved by us; nothing was tuned.
- **Landing times**: every 6 hours inside the published launch period. "Late 2026" is read as 15 Nov (today)
  to 31 Dec 2026; "2027" as all of 2027; "late 2027" as 1 Sep to 31 Dec 2027 (as DEEP_PASS.md did); "early
  2028" as 1 Jan to 30 Apr 2028. The trip to the Moon is not modelled.
- **Needs**: Griffin-1, IM-4 and VIPER use the page's default need (240 sunlit hours and 100 hours of Earth
  contact in the 14 days after landing, the Sun and the Earth in view at touchdown). It is illustrative: NASA
  publishes no surface duration for Griffin-1 or IM-4. VIPER also gets totals over its published 100 days.
  Artemis IV uses the region calendar's rule (6.25-day stay, Sun up every hour, 100 hours of Earth contact,
  not fragile).
- **Check**: the card's own: 13 touchdown points within 100 m, the coarser grid, the near-field sampling,
  the Deep Space Network station rule on; Yes only when all agree.
- **Slip**: a week is 7 days; a month is 29.5 days (118 steps of 6 hours, one synodic month, as the "next
  windows" line on the card).
- **"Other regions still open"**: when the slip loses the home place, which of the other eight regions has
  at least one site that is a clear Yes at the slipped time, under the same need.
- **Per month**: the first Yes landing time at the home place in each calendar month is re-run through
  `robust.mission_card` (slip margin, and the answer 7 days later) and `windows.next_windows` (the answer one
  synodic month later). The board shows that table; a test re-runs one row from scratch on the 80 m grid.

## 4. Results (one run, 19:18:08 to 19:30:33 IST, 744.7 s; `data/addons/impact/missions.json`)

Every figure is approximate: NASA's published place and period, Wueller et al.'s published candidate sites,
landing times every 6 hours. Not any mission's own plan.

Terrain: the run used the page's live stack (`data/dem_live`, switched on by another agent at 19:12). At Mons
Mouton, Nobile, Malapert, Haworth and Peak near Cabeus B that is the 80 m grid; de Gerlache Rim 2 and Slater
Plain sites fall inside the 20 m square and use 20 m. **If the full 20 m mosaic is switched in later, re-run
`python -m slipday.addons.impact_build` (about 12 minutes) so the board matches the live card.**

**Headline, in plain words.** At Mons Mouton, where three of the four missions go, a landing time that works
mostly fails if it slips a week (20 % to 26 % still work), but mostly works again a month later (77 % to 86 %).
So after a slip, waiting for next month's window usually beats landing late in this one. When the slip does
lose Mons Mouton, the board names the other regions open at the slipped time.

| Mission | Landing times that work | Still work a week later | Still work a month later | When a week's slip loses it, another region is open | Most often |
|---|---|---|---|---|---|
| Griffin-1 (15 Nov to 31 Dec 2026) | 72 of 188 (38 %) | 16 of 72 (22 %) | 60 of 72 (83 %) | 16 of 56 | Peak near Cabeus B, Malapert Massif, Nobile Rim 1 |
| IM-4 (2027) | 253 of 1460 (17 %) | 50 of 253 (20 %) | 194 of 253 (77 %) | 99 of 203 | Peak near Cabeus B, Haworth, de Gerlache Rim 2 |
| VIPER (Sep to Dec 2027) | 152 of 488 (31 %) | 40 of 152 (26 %) | 131 of 152 (86 %) | 62 of 112 | Malapert Massif, Haworth, Peak near Cabeus B |
| Artemis IV (Jan to Apr 2028), any of nine regions | 211 of 484 (44 %) | 88 of 211 (42 %) | 147 of 211 (70 %) | (all nine are already "home") | |

Here "works" means at least one of the home sites is a clear Yes. The week and month columns ask the same of the
slipped time, at any home site.

Best Mons Mouton sites by share of landing times (IM-4, 2027): MMO02 10.8 %, MMO05 9.9 %, MMO03 7.7 %; MMO07
never works under this need. 11 of 12 months of 2027 have at least one good landing time; July has none.

**Per month: the first good landing time, re-run through the card's own code** (verdict, slip margin, the
same site 7 days later, the same site one synodic month later; "why" from the card's reasons):

| Mission | Landing (UTC) | Site | Card | Can slip | +7 days | +29.5 days |
|---|---|---|---|---|---|---|
| Griffin-1 | 2026-11-16 18:00 | MMO02 | Yes | 8 d | Yes | Yes |
| Griffin-1 | 2026-12-14 18:00 | MMO01 | Yes | 3 d | Not sure | Yes |
| IM-4 | 2027-01-11 00:00 | MMO01 | Yes | 4 d | Not sure | Not sure |
| IM-4 | 2027-02-14 00:00 | MMO02 | Yes | 2 d | Not sure (sunlight) | No (Sun at touchdown) |
| IM-4 | 2027-03-16 00:00 | MMO03 | Yes | 1 d | No (sunlight) | Not sure |
| IM-4 | 2027-04-14 18:00 | MMO03 | Yes | 0 d | No (Earth at touchdown, sunlight) | Yes |
| IM-4 | 2027-05-14 06:00 | MMO03 | Yes | 0 d | No (Earth at touchdown, sunlight) | Yes |
| IM-4 | 2027-06-12 18:00 | MMO03 | Yes | 0 d | No (sunlight) | No (Earth at touchdown) |
| IM-4 | 2027-08-11 06:00 | MMO03 | Yes | 1 d | No (sunlight) | Yes |
| IM-4 / VIPER | 2027-09-08 06:00 | MMO03 | Yes | 3 d | No (sunlight) | Yes |
| IM-4 / VIPER | 2027-10-07 18:00 | MMO03 | Yes | 4 d | No (sunlight) | Yes |
| IM-4 / VIPER | 2027-11-05 00:00 | MMO02 | Yes | 9 d | Yes | Yes |
| IM-4 / VIPER | 2027-12-02 18:00 | MMO02 | Yes | 0 d | Yes | Not sure |
| Artemis IV | 2028-01-01 00:00 | MMO01 | Yes | 7 d | Yes | No (sunlight) |
| Artemis IV | 2028-02-01 00:00 | NR102 | Yes | 5 d | No (Earth contact) | Not sure |
| Artemis IV | 2028-03-01 00:00 | NR105 | Yes | 3 d | No (sunlight, Earth contact) | Yes |
| Artemis IV | 2028-04-01 00:00 | NR203 | Yes | 0 d | No (Earth at touchdown, sunlight, Earth contact) | No (Earth contact) |

All 21 rows: the card's verdict is Yes where the board's vectorised check said Yes (agreement 21 of 21). A test
re-runs the IM-4 January row from scratch on the 80 m grid and gets the same verdict, margin, +7 and +29.5-day
answers. "Can slip 0 d" with "+7 days Yes" (2 Dec 2027) is not a contradiction: day 1 fails, day 7 passes again.
The Artemis IV rows start at 00:00 on the 1st because the regions are already open when each month begins.

**VIPER over its published 100 days**, from each month's first good landing (worst touchdown point; hours,
not a battery model): Sun 1,288 to 1,566 hours, Earth contact 1,455 to 2,080 hours, longest night met 338 to
384 hours, longest Earth outage 95 to 289 hours.

**A finding outside this add-on, for the participant:** NASA's Artemis III page now says Artemis III (2027) is
a test "in low Earth orbit" and the Artemis IV page says Artemis IV (early 2028) is the crewed landing near the
South Pole, with the same nine candidate regions. The rest of the entry (README, SUBMISSION_DRAFT, the region
panel) still says "Artemis III regions". Suggested wording: "NASA's nine Artemis candidate regions (first
crewed landing: Artemis IV, early 2028)". I did not edit those files.

## 5. What was built

| File | What |
|---|---|
| `slipday/addons/impact_build.py` | the precompute (`python -m slipday.addons.impact_build`, about 12 minutes on this laptop) and the rule |
| `slipday/addons/impact.py` | the router, `router = APIRouter(prefix="/api/addons/impact")` |
| `slipday/api.py` | one edit: `"addons.impact"` added to the optional-router loop |
| `data/addons/impact/missions.json` | the stored board (missions, months, left-out list, sources with sha256) |
| `data/addons/impact/sources/` | the saved pages and `DOWNLOADS.tsv` (URL, HTTP code, bytes, sha256, UTC time) |
| `static/addons/missions.js` | the front-end module (one container, styles scoped under `.msn`, uses the page's CSS variables) |
| `tests/addons/test_impact.py` | 14 tests |

Endpoints (router name `slipday.addons.impact.router`, tag "add-on: upcoming missions"):

- `GET /api/addons/impact`: the board, plus "who this helps" and "use the data"
- `GET /api/addons/impact/mission/{id}` (`griffin1`, `im4`, `viper`, `artemis4`)
- `GET /api/addons/impact/who`, `GET /api/addons/impact/open-data`
- `GET /api/addons/impact/missions.csv` and `/missions.json` (downloads)

The module draws, inside `#addon-missions`: the four mission cards (each tagged "Approximate, from NASA's
published place and period", with the quotes one click away), the "Looked for, but left out" list, **Who this
helps** (five lines, each linked to the part of the page that backs it), **Use the data** (`id="addon-missions-data"`:
endpoints and downloads), and the sources with sha256.

## 6. For the overhaul agent: where the container goes

1. Put `<div id="addon-missions"></div>` **high on the page, right after the first screen (the mission card)
   and before or beside the "Real missions" panel** (`#real` / `#realPanel`). It is the page's answer to "who
   is this for and does it matter", so it should not sit in a closed fold at the bottom. If a fold is used, a
   summary such as "Upcoming missions: Griffin-1, IM-4, VIPER, Artemis IV. What a week's or a month's slip
   would do." keeps it visible.
2. Add `<script src="/static/addons/missions.js"></script>` with the other add-on scripts.
3. A jump-bar entry "Upcoming missions" pointing at `#addon-missions` would help.
4. The "Who this helps" links point at these ids on the page: `h-mission`, `real`, `regions`, `foldGame`,
   `foldContrast`, `foldListen`. If the overhaul renames any of them, update `WHO` in
   `slipday/addons/impact.py`; `test_who_this_helps_points_at_real_places_on_the_page` will fail until then.
5. The module needs nothing from the page except those ids and, optionally, the CSS variables `--text`,
   `--text2`, `--surface`, `--page`, `--line`, `--accent`, `--ok-ink`, `--crit`, `--warn-ink`, `--warn-bg`.

Checked in the real page (headless Chrome, the container and script injected at run time on port 8160, no
file under `static/` other than the module touched): 4 cards, 21 month rows, no missing anchors, no console
errors, no horizontal page scroll at 1280 px and at 375 px (the month tables scroll inside their own box on a
phone).

## 7. Tests

`python -m pytest -q tests/addons/test_impact.py` (19:36): **14 passed**, none skipped, 7 s. They check: the
router is registered in `api.py`; the four missions; every quote is in the saved first-hand page (HTML text, or
the LPSC .docx); every sha256 matches the file and the download log; Artemis III is listed as "no landing";
counts and shares are consistent; the card agrees with the board on all 21 month rows; the mission endpoint and
its 404; the CSV has one row per mission and month; every "who this helps" link points at an id that exists;
every open-data endpoint exists in the app; no word about rivals or competition in the add-on's files; a
missing board is reported, not crashed; one month re-run from scratch on the 80 m grid matches.

Full suite, run once (19:33 to 19:44): **419 passed, 3 failed, 1 skipped** (662.8 s). The three failures are
not in this add-on's files and come from work by other agents during the run:

- `tests/addons/test_atlas.py::test_2027_to_2030_agree_with_the_existing_calendar_time_by_time` and
  `tests/test_regions.py::test_the_figures_quoted_in_the_documents`: `data/validation/region_availability.json`
  was rewritten at 19:32 and `data/addons/atlas/` at 19:40 for the new live terrain stack (DEEP_PASS_3.md, "Live
  finer terrain"); the stored figures and the documents now differ (for example all-nine 0.4362 against 0.4333).
- `tests/test_deep.py::test_follow_up_corrections_are_in_the_page_and_the_record`: a sentence in the slides
  document that the test forbids ("Earth contact there falls 311").

I did not touch any of those files.

## 8. What is left out, and why

- **Missions without a published site** (Blue Moon MK1 first flight, Blue Ghost 4, Nova-D, LUPEX) and
  **Chang'e-7** (nothing first-hand reachable) are listed with the reason, not placed. Artemis III is listed
  as "no landing".
- **Exact dates.** No mission publishes a landing date, so the board spreads landing times over the published
  period. Our readings of "late 2026", "late 2027" and "early 2028" are stated on each card. The trip to the
  Moon is not modelled.
- **Mission needs.** Griffin-1 and IM-4 publish no surface duration; they use the page's default need, marked
  illustrative. The 100-hour Earth-contact need is illustrative everywhere. VIPER's 100 days and Artemis's
  stay are published.
- **Mons Mouton is a large place.** "Mons Mouton" is read as NASA's region of that name (ten published
  sites). NASA's "Mons Mouton Plateau" region and the IM-2 landing point are not counted as home; the
  plateau is counted among the "other regions".
- **"Other regions"** means any published site in that region is a clear Yes at the slipped time; it does not
  check whether a lander could retarget that far.
- **No claims of use.** Nothing says any mission uses Slipday.
- **Not tested with a real screen reader** (the page and the "who" line say so).
- Not run: git, Docker, any deployment; nothing was published or sent to anyone.
