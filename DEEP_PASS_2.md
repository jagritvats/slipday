# Slipday deep pass 2 (Sunday 15 Nov 2026, from 11:06 local time; time box 3.5 hours)

Written as the work goes. No rule here is described as written before computing: the scripts and their
outputs carry their own file times (listed with each result), and the rules were written into the scripts
themselves.

## E0. Jargon removed from what a judge sees (participant's request)

Process words ("a written rule", "not verifiable", "rule fixed before computing", "R1 to R14", "pass 3",
"deep pass") are gone from the page, README, SUBMISSION_DRAFT (the text for the form), the slides and the
storyboard. The method is stated plainly instead, e.g. "A site counts as Yes only if all 13 touchdown points
within the landing scatter get enough sunlight and Earth contact, on two terrain grids." The real caveats stay
(illustrative, inference, modelled date). Process notes and the timing corrections stay in DEEP_PASS.md and
here. README's history of passes was replaced by a short list of what the page does.

## E1. A finer-terrain check: the LOLA team's 5 m site models (11:08 to 11:16)

Read first-hand (data/reference/sources/, URL and sha256 in DOWNLOADS.tsv): the PGDA product page
(products/78), the data directory index and its README. The README lists 5 m/pix models for: Site01
Connecting ridge, Site04 Shackleton rim, Site06 Nobile rim 1, Site07 Peak near Shackleton, Site11 de Gerlache
rim, Site20 Leibnitz beta plateau, Site23 Malapert massif, Haworth, Shoemaker, DM2 Nobile rim 2. The index
links surface files for Site01, 04, 07, 11, 20 and 23. Their extents (read from the GeoTIFF headers by a 64 KB
range request each) show that **Site07 covers the opening example** (x 22 to 38 km, y -28 to -12 km) and
**Site01 covers C1** (x -19 to -3 km, y -20 to -4 km).

Both files were fetched by HTTP range requests (4 ranges each, 40,980,808 and 40,980,810 bytes; sha256
38aaee10... and 3ba7b97c...). `scripts/prepare_dem5.py` (11:14:38) puts each 5 m model on top of the 20 m crop
and the 80 m and coarser grids (16 km square; beyond it 20 m, then 80 m). `scripts/compare_grids.py`
(11:15:20) runs the page's card on each stack in its own process; output `data/validation/grids_5m.json`
(11:15:56). Landing 18 Nov 2026, 240 sunlit and 100 Earth hours in 14 days, station rule on:

| site | grid | height at the site | verdict | margin | touchdown points passing, days 0 to 9 | sunlit / Earth h |
|---|---|---|---|---|---|---|
| opening example | 80 m | 1,173.7 m | Yes | 8 d | 13 on days 0 to 8, 0 on day 9 | 314 / 311 |
| opening example | 20 m | 1,173.9 m | Yes | 8 d | 13 on days 0 to 8, 0 on day 9 | 308 / 311 |
| opening example | **5 m** (Site07) | 1,173.9 m | **Yes** | **8 d** | 13 on days 0 to 8, 0 on day 9 | 306 / 311 |
| C1 | 80 m | 1,957.6 m | Yes | 7 d | 13, 13 ... 13, 12 (day 8), 0 | 336 / 295 |
| C1 | 20 m | 1,958.7 m | Not sure | - | 11, 13 ... 13, 10, 0 | 336 / 295 |
| C1 | **5 m** (Site01) | 1,958.5 m | **Not sure** | - | 12, 13 ... 13, 10, 0 | 336 / 295 |

The heights agree to 1 m across the three grids, so the 5 m models are placed right. The opening example
holds on all three grids. C1 is "Not sure" on the planned date on both finer grids (12 of 13 points on 5 m,
11 of 13 on 20 m); slips of 1 to 7 days pass at all 13 on every grid. The card's 20 m line now adds the 5 m
answer for these two examples.

## E2. Artemis III regions as options in missed windows (11:16 to 11:19)

NASA's list (news release of 28 Oct 2024, read first-hand, `sources/artemis3_regions_2024.html`): Peak near
Cabeus B, Haworth, Malapert Massif, Mons Mouton Plateau, Mons Mouton, Nobile Rim 1, Nobile Rim 2, de Gerlache
Rim 2, Slater Plain. NASA gives names, not points, and "will select sites within the regions after it
identifies the mission's target launch dates".

**The anchor points are my choice, illustrative, not NASA's landing sites.** For each region: the best-lit
point (LOLA average Sun visibility, AVGVISIB_75S_120M_201608) in a search area tied to its name (the rule is in
the header of `scripts/artemis_regions.py`; for Malapert Massif and Mons Mouton Plateau the area is the LOLA
team's 5 m site model of that name). A first run (11:17) put Mons Mouton's and Nobile Rim 1's anchors on the
same point, where the mountain's circle overlaps the crater's rim; I then added "no anchor within 10 km of an
earlier one" and re-ran (script 11:17:49, output 11:18:07). That change came after seeing the first run.

| region | anchor (illustrative) | average Sun visibility |
|---|---|---|
| Peak near Cabeus B | 82.207 S, 47.285 W | 0.58 |
| Haworth | 86.866 S, 19.941 W | 0.46 |
| Malapert Massif | 86.038 S, 3.196 E | 0.70 |
| Mons Mouton Plateau | 85.414 S, 31.691 E | 0.80 |
| Mons Mouton | 85.297 S, 37.063 E | 0.69 |
| Nobile Rim 1 | 86.678 S, 49.254 E | 0.64 |
| Nobile Rim 2 | 84.368 S, 44.376 E | 0.61 |
| de Gerlache Rim 2 | 88.456 S, 67.785 W | 0.77 |
| Slater Plain | 87.453 S, 113.736 E | 0.52 |

Each anchor judged with the card's rules (13 touchdown points within 100 m, station rule on) in each missed
window, at the window's landing and over landings every 6 hours within 72 hours of it:

| plan | window | regions with a Yes hour within 72 h | Yes at the window's own hour | which |
|---|---|---|---|---|
| opening example (240 / 100 h) | 17 Dec 2026 | 7 of 9 | 4 | Cabeus B peak, Malapert Massif, Mons Mouton Plateau, Mons Mouton, Nobile Rim 2, de Gerlache Rim 2, Slater Plain |
| | 16 Jan 2027 | 5 of 9 | 1 | Cabeus B peak, Malapert Massif, Mons Mouton, Nobile Rim 2, de Gerlache Rim 2 |
| | 14 Feb 2027 | **0 of 9** | 0 | none: the season closes every region for this need |
| IM-1 (168 / 100 h) | Jan 2024 (modelled date) | 8 of 9 | 6 | all but Nobile Rim 1 |
| | 22 Feb 2024 (flown) | 7 of 9 | 5 | all but the two Nobile rims |
| | Mar 2024 | 4 of 9 | 0 | Cabeus B peak, Malapert Massif, Mons Mouton, de Gerlache Rim 2 |

Several of these best margins are fragile (a touchdown point within 0.27 degrees of the skyline); the JSON
marks each. Read plainly: keeping several regions buys real flexibility in December and January (as NASA
says), but not in February for a 240-hour sunlight need.

## E3. Hours to watt-hours: skipped

No battery capacity and night-time load for a real lander class could be found first-hand in the time given
(one search: press coverage of IM-1's remaining battery hours, and a NASA study of a generic small lander with a
night load of about 40 W, which is not a lander's published capacity). Following the brief, the card keeps
hours and does not say "survives / does not survive".

## E4. Page, documents, tests (11:20 to 11:35)

- The card's 20 m line adds the 5 m answer: "Both grids agree. On the 20 m grid (off-line check): Yes as planned
  (13 of 13 touchdown points), 8 days of margin. 5 m: the same." For C1: "... 5 m: Not sure (12 of 13)."
- The real-missions panel has a table of the nine Artemis III regions for the opening plan's windows and for
  IM-1's windows (✓ with the margin of the best landing within 72 hours, * fragile), saying each region is one
  illustrative point of ours, not a NASA landing site. `GET /api/artemis-regions`.
- The draft and slides carry the 5 m result and the Artemis counts; README's pass history was replaced by a plain
  list; process words are gone from what a judge reads (a test checks the form text, slides, storyboard captions,
  page strings and README).
- The five new files are in `realdata/lunar/MANIFEST.md` and DOWNLOADS.tsv.

## E5. State at the end (11:40)

- `pytest`: 274 passed and 1 failed on the first full run (a pass-3 test looks for "fixed example" on the
  page, which the plain-wording edit had dropped); the wording was restored ("It is a fixed example, so the page
  keeps opening on it after that date has passed") and that test and the jargon test pass: **275 passed**.
  `node scripts/ui_check.js`: **78 of 78** (one new: the Artemis region table; the real-missions check now
  expects its four tables). New: `tests/test_deep2.py` (4).
- First screen: the slip grid still begins on it (798 px). Screenshots refreshed. The video was not
  re-recorded: no caption number changed (frame 1's band now also says "5 m: the same", which the caption
  "NASA's finer grid agrees" still covers).
- Shipped skyline cache unchanged (1,827 files); no server running; ports 8100 to 8199 free.
- Not done: watt-hours (no first-hand figures); 5 m checks for the Artemis anchors (only Site20 and Site23
  have 5 m models among them, and they were not run); the Artemis table is precomputed for two plans, not
  live for any plan.

## Final fixes (wording fixes; file times 12:08 to 12:25)

1. **Slide 7**: the line saying the headline numbers were reproduced by a reviewer is removed.
2. **Artemis January, 5 of 9 (ours) against 3 of 9 (the reviewer's code).** Two causes. (a) The cells that
   differ were the knife-edge ones: margins of 0 d and 1 d with a fragile flag, which flip with any small
   change. (b) Malapert's anchor came from a lat/lon round trip that rounded to a neighbouring map pixel
   (0.70 average visibility picked where a 0.79 pixel existed). Both show that one best-lit pixel on the
   120 m map is a poor anchor. Fix: each anchor is now the centre of the best-lit 9 x 9-pixel (1.1 km) area,
   evaluated at every map pixel centre with an integral image (no lat/lon round trip), still at least 10 km
   apart in list order (the spacing was added after the first run put two regions on one point).
   Anchors moved by: Peak near Cabeus B 8.2 km, Haworth 41.9, Malapert Massif 3.1, Mons Mouton Plateau 5.9,
   Mons Mouton 19.9, Nobile Rim 1 49.1, Nobile Rim 2 0.7, de Gerlache Rim 2 6.4, Slater Plain 37.3.
   New counts (Yes within 72 h / of them not fragile / Yes at the window hour):

   | Plan, window | pixel anchors (old) | area anchors (now) |
   |---|---|---|
   | opening, Dec 2026 | 7 / 1 / 4 | 7 / 3 / 4 |
   | opening, Jan 2027 | 5 / 2 / 1 | 7 / 1 / 2 |
   | opening, Feb 2027 | 0 / 0 / 0 | 5 / 2 / 0 |
   | IM-1, Jan 2024 | 8 / 8 / 6 | 6 / 5 / 6 |
   | IM-1, Feb 2024 | 7 / 5 / 5 | 6 / 6 / 5 |
   | IM-1, Mar 2024 | 4 / 2 / 0 | 5 / 5 / 3 |

   What holds: the counts are sensitive to the point chosen. Between the two anchor choices, 3 to 5 of the 9
   regions change Yes/No in every window. Regions that are Yes and not fragile under both: opening Dec none,
   Jan Nobile Rim 2, Feb none; IM-1 Jan Peak near Cabeus B, Malapert Massif, Mons Mouton Plateau,
   de Gerlache Rim 2; Feb Peak near Cabeus B, Haworth, Malapert Massif; Mar Malapert Massif. "None in
   February" (the old slide) is false with area anchors and is removed. The page, draft and slides now say
   the points are rough, "Rim 1"/"Rim 2" are our labels, points are kept 10 km apart, and give fragile counts.
3. **Options card, C1 in January (ours 14 Jan 01:00, 5 d; the reviewer's 16 Jan, 2 d).** At 14 Jan 01:00 the
   smallest Sun clearance over the 13 touchdown points is 0.05 degrees; at 16 Jan 19:00 it is 0.12 degrees.
   Both are fragile. The reviewer's code loses the 0.05-degree point, so its best hour is 16 Jan with 2 d.
   What holds: C1 has January Yes hours, margin about 2 days, all fragile. The card now leads with the most
   robust option (not fragile first, then largest clearance, then margin) and gives the fragile count: January
   "most robust: map point 89.498 S, 137.663 W at 15 Jan 13:00, 4 d; 13 of 20 other sites have a Yes hour
   within 3 days, 11 of them fragile"; February "most robust: IM-2 Athena at 13 Feb 02:00, 2 d; 5 of 20,
   2 fragile". Slide 3 and DISCOVERIES item 1 match.
4. **Jargon**: "off-line check" -> "On the 20 m grid:" / "checked separately"; "web-fetch tool" -> "copied
   from the web page"; storyboard process notes (DevTools, "passes 2 and 3") reworded; the README comparison
   table is kept (a test pins it) with plain framing and without the withdrawn-claim note. ui_check.js and
   test_pass2.py match the new wording with the same strictness; test_deep2.py's jargon list adds
   off-line, web-fetch, independent review, DevTools; its Artemis expectations are updated to the new counts.
5. **Checks**: ui_check all passed; first screen #slip top 798 px (< 800); options line and Artemis panel read
   in the browser, no console errors. No video caption number changed, so the video is not re-recorded.
   Full suite: 275 passed. Server (PIDs 11452, 32900) stopped; ports 8100 to 8199 free.
