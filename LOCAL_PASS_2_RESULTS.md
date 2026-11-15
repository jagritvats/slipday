# Local pass 2 results

Run on Saturday 14 Nov 2026 from 22:25 local time (UTC+5:30) by the builder of this entry, on the same
Windows 11 laptop as the first local pass (24 cores, 31 GB; Python 3.12 in `.venv`; Node 22 with
`puppeteer-core` and Chrome). Two other build jobs were using the machine throughout, so every timing is an
upper figure for this hardware. Two helpers worked in parallel on parts of the list (the 3-D view; the
validation panel and the document fixes); their numbers are marked and were looked at on the running page.

Every number below was measured on this machine in this pass, with the command given beside it (`py` is
`.venv\Scripts\python.exe`, run from `mvps/slipday`). What was not run is in section D.

**Docker's engine was down for the whole pass and was not started. Every container figure in the earlier
documents (image size, memory inside 512 MB) is from the first pass, belongs to the code as it was then,
and was not re-measured after this pass's changes.**

## 0. Summary

| Item | Outcome |
|---|---|
| A1 stored answers behind slow work | done. Default card with 2 slow requests in flight: 25.87 s before, 0.04 to 0.05 s after; with 12: 142.44 s before, 0.04 to 0.06 s after (5 of the 12 answered, 7 refused at once) |
| A2 IM-1 and Chandrayaan-3, the other figure | done (helper): storyboard caption, draft, README, slides and replay note give both; tests pin it |
| A3 slide 2 quotes | done (helper): the official words; the paraphrase is marked as one |
| A4 "could not be obtained" | done (helper), and in REALDATA.md (here) |
| A5 README comparison text | later removed: the README describes Slipday on its own terms |
| A6 which Earth rule | done: the Earth tile names its rule and the card's stricter one (3.5 points lower, measured); the card names the rule beside each number |
| A7 both Earth figures; ridge range | done (helper): 0.97 and 1.31 (53 points); 0.69 and 1.11 (76 points); ridge Sun 3.77 to 5.25 over ten seeds, correlation 0.41 to 0.75 |
| A8 landing-circle range | done: 62.1 % (54.2 to 70.0), 26.9 % (19.4 to 36.3), 12.9 % (7.3 to 19.4) |
| A9 note for the team; AI statement | done (helper): fenced "NOT FOR PASTING" section; the AI statement is a marked placeholder in the draft and the README, not written |
| A10 smooth sphere "20 against 20" | done: the card counts the dates on which the two answers differ (4 of 60, and 6 more where terrain is not sure) and outlines them |
| B1 why it flips | done, on the first screen (chart bottom at 412 px of 800) |
| B2 scatter-checked slip-margin map | done: 574 of 733 coloured points keep a margin, 159 lose it |
| B3 3-D view | done (helper): Canvas 2-D, no library, real grid, shadows, slider |
| B4 chance by lander class | done: 100 %, 34.8 % (28.6 to 42.6), 17.1 % (11.6 to 23.5) at the default example; labelled as assumptions |
| B5 permanent shadow, links out, lunar against terrestrial | done (links and the comparison view by the helper) |
| B6 year ribbon | done: 62 clear yes, 54 not sure, 249 no; none in February to June 2027 |
| B7 20 m mosaic | partly: the 71.7 km square around the pole fetched by range request (30 MB of 2.7 GB); the default example repeated on it. **It changes the headline: "Not sure" on the planned date (11 of 13).** Shown on the page. The map, the validation and the tests stay on 80 m |
| B8 cheaper ideas from the possibilities report | not done |
| C judged surface | done: draft, README, LIMITATIONS, storyboard (29 s, five frames), slides (7), 27 screenshots, draft video (29.0 s) |
| Tests | 204 passed, 0 failed (152 before); browser checks 61 pass, 0 fail (43 before). After the follow-up: 207 passed; 65 checks |
| Follow-up (section H, 23:52 to 00:20) | done: the page and the video open on an example chosen by a rule fixed in advance, 89.010 S 122.764 E, "Yes" with 8 days of margin on the 80 m and on the 20 m grid (1 candidate tried, 1 passed); the old example stays as site 2, the case where the grids disagree; the card names the need that ends the margin (Earth contact, 95 of an illustrative 100 h); the three lander-class figures read first-hand and cited; `validate_terrain.py` re-run, all tables unchanged; peak working set 498 MB on Windows |

## A1. Stored answers must not wait behind slow work (review bug 1)

`py -I scripts\local_pass_tools\measure_blocking.py http://127.0.0.1:8100 0 1 2 12`. The script starts k
landing-circle requests for points nobody has asked for (seeded from the clock, so a second run does not
find them stored), waits two seconds, then times the default mission card three times, the page, the
health check and the default landing circles. The server ran with `SLIPDAY_HORIZON_CACHE` pointing at a
scratch copy of the skyline cache.

Before (the code as the reviewer tested it):

| Slow requests in flight | Default card, first call | Second and third | Page | Slow requests answered in |
|---|---|---|---|---|
| 0 | 0.04 s | 0.04, 0.04 s | 0.06 s | - |
| 1 | 0.05 s | 0.04, 0.04 s | 0.00 s | 25.6 s |
| 2 | **25.87 s** | 0.04, 0.05 s | 0.01 s | 27.8 to 28.0 s |
| 12 | **142.44 s** | 0.04, 0.04 s | 0.01 s | 25.8 to 144.5 s |

This reproduces the review (23.5 s and 153 s): the stored card waited for one of two slots that the slow
requests held.

Fix (`slipday/load.py`, used by every endpoint in `slipday/api.py`). A request starts in a light lane
(4 at a time) that only reads stored skylines. The moment it needs a new skyline
(`terrain.cached_profile`) or a new evaluation of the map (`field.per_date`, `scatterfield`,
`view3d`), it leaves that lane and queues for one of two slow slots, the same two as before, so the memory
bound of the slow work is unchanged. A big job (landing circles, lander classes, the slip-robust list) is
refused at once with HTTP 503, a Retry-After header and a plain sentence when three are already waiting;
a small job (a card for a new site) when twelve are, so one visitor's own page is not refused by itself.
The page asks again by itself (4, 8 and 12 seconds later) and then shows the sentence. `/api/health`
reports the lane counters. Environment: `SLIPDAY_MAX_LIGHT` 4, `SLIPDAY_MAX_HEAVY` 2,
`SLIPDAY_MAX_COLD_QUEUE` 3, `SLIPDAY_MAX_COLD_QUEUE_SMALL` 12.

After, final lane code (same script, 23:23):

| Slow requests in flight | Default card, three calls | Page | Default circles | Slow requests |
|---|---|---|---|---|
| 0 | 0.02, 0.03, 0.04 s | 0.01 s | 0.13 s | - |
| 1 | 0.05, 0.04, 0.04 s | 0.01 s | 0.16 s | 1 answered in 20.0 s |
| 2 | **0.05, 0.04, 0.05 s** | 0.00 s | 0.21 s | 2 answered in 22.2 and 22.4 s |
| 12 | **0.06, 0.04, 0.04 s** | 0.00 s | 0.20 s | 5 answered in 22.0 to 62.6 s, 7 refused at once (503) |

Two earlier runs of the same script on intermediate code gave the same picture: with one slow slot and a
queue of three, 0.03 to 0.05 s and 4 of 12 answered (21.4 to 113.8 s); with two slots, 0.03 to 0.05 s
except one row (0.22 to 0.44 s with one slow request) that was taken while two page loads of mine were
also running on the server. One browser-check run on the three-deep queue failed with a 503 on
`/api/compare` when the page itself fired six slow requests at once (switching the mast height); that
is why small jobs got the longer queue. The final browser-check run has no failed request.

What it costs: a visitor whose landing-circle request arrives behind five others is told to try again
in 20 seconds instead of waiting. Not measured: a host with a fraction of a CPU, and memory.

## A2 to A9 (helper; checked on the page and in the files)

- **A4**: the stale sentence is gone from `data/validation/terrain_validation.json` and from
  `scripts/validate_terrain.py` (which wrote it); `REALDATA.md` carries a dated correction in its place.
- **A6, A7** (`PROCS=1 py scripts\validate_more.py data\reference --only e,s`, 238.7 s): Earth in view on
  the 60 m map, 200 points: 0.97 points, r 0.9946; without the 53 points where map and model are both
  exactly zero: 1.31, r 0.9898. On the 120 m map: 0.69, r 0.9984; without 76 points (64 both 0, 12 both
  1): 1.11, r 0.9957. The card's rule (Earth's centre) reads 3.52 points lower on the 60 m map (4.79
  without the 53) and 4.09 lower on the 120 m map (6.42). Ridge-pixel Sun check on ten seeds, 20261115 to
  20261124 (the first is the original; +1 and +2 were run first, +3 to +9 were added before their
  results were seen): 4.02, 4.42, 4.25, 5.04, 3.99, 4.26, 4.25, 5.25, 3.77, 4.77, so 3.77 to 5.25, with
  correlation 0.41 to 0.75. Ridge-pixel Earth check on the same draws: 1.30 to 1.98. The tile now reads
  "±3.77 to 5.25 pts"; the Earth tile gives both figures and both rules.
- **A2**: IM-1's caption reads "Its seven-day plan fits with one day to spare; the ten days in the press
  kit would not"; README, draft, slides and the replay note give both figures for IM-1 and Chandrayaan-3
  and say the replays are not a confirmation of the model.
- **A3**: slide 2 quotes "Hardware development challenges, launch delays, or other factors often force
  mission planners to reconsider their original landing date and location." and the firm objective, and
  marks "respond quickly when the schedule changes" as a paraphrase.
- **A5**: the comparison table was later removed from the README.
- **A9**: `SUBMISSION_DRAFT.md` ends the form text with `END OF TEXT FOR THE FORM`; the notes for the
  team sit below, in a fenced section headed "NOT FOR PASTING". The AI statement is
  `[PARTICIPANT TO WRITE: statement of AI use]` in the draft and in the README.

## A8. Sampling range of the landing circles

`slipday/robust.py`: beside every share, the 5th to 95th percentile of the same count over 400
resamplings of the touchdown points (with replacement, ring by ring, fixed seed 20261114).
`py scripts\local_pass_tools\measure_pass2.py` (in-process, the app's own endpoints):

| Site, landing, sunlit need | Within 100 m | 250 m | 500 m | 1 km |
|---|---|---|---|---|
| C1, 18 Nov 2026, 240 h | 100 % | 62.1 % (54.2 to 70.0) | 26.9 % (19.4 to 36.3) | 12.9 % (7.3 to 19.4) |
| Malapert shoulder, same | 94.5 % (89.1 to 100) | 76.2 % (61.5 to 88.3) | 65.9 % (53.3 to 78.2) | 61.0 % (50.2 to 71.1) |
| Ridge C2, same | 78.1 % (67.2 to 89.1) | 51.5 % (34.8 to 66.5) | 32.0 % (21.7 to 42.7) | 20.3 % (11.9 to 28.7) |
| IM-2, 6 Mar 2025 17:00, 240 h | 100 % | 100 % | 100 % | 95.6 % (91.2 to 98.5) |
| IM-1, 22 Feb 2024 23:00, 168 h | 100 % | 100 % | 98.0 % (94.1 to 100) | 88.4 % (80.0 to 95.3) |

The shares are unchanged from the first pass. The reviewer's denser count at C1 (55.4, 24.1, 11.7 %) lies
inside each range.

## A10. Where terrain changes the answer

Same script. The legend under the verdict strip now counts the dates on which a smooth-sphere tool
would answer differently, and outlines them in the thin strip:

| Example | Terrain yes / not sure | Smooth sphere yes | Dates where the answers differ |
|---|---|---|---|
| C1, 18 Nov 2026 | 20 / 6 | 20 | 4 of 60 (2 smooth yes where terrain is not, 2 smooth no where terrain is yes) |
| Malapert shoulder | 11 / 9 | 16 | 9 (7 and 2) |
| Ridge C2 | 0 / 21 | 21 | 21 (21 and 0) |
| IM-2 | 6 / 2 | 8 | 2 (2 and 0) |
| IM-1, 168 h | 9 / 2 | 17 | 8 (8 and 0) |

So "20 against 20" at C1 hid four dates on which the two disagree. In the chosen landing window itself
the skyline view prints both sets of hours: at C1, 336 sunlit and 295 Earth-contact hours on terrain,
336 and 281 on a smooth sphere (the ridge is high ground and sees below the level horizon); at IM-1,
208 and 336 against 225 and 336.

## B1. Why it flips, on the first screen

`slipday/why.py`, `POST /api/why` (the mission card's body plus `day`). For the landing date of the chosen
cell: the 720-point skyline with the distance of the ground that sets it, the hourly positions of the Sun
and the Earth through the window with the flags the card counts, the height of each at touchdown, the time
to the next sunset and Earthset (refined to the second), each stretch in which a body is hidden with the
ground it goes behind, and, for the first day of slip that is not a clear yes, which member of the check
fails, why, and the ground responsible. Clicking a cell of the strip now selects that day (it used to
re-plan); "Plan for this date" is a button in the panel. The chart's bottom edge is at 412 px on a
1280x800 screen.

Measured (same script; first call, repeat call):

| Example | Time | What ends the margin, as the page words it |
|---|---|---|
| C1 | 0.18 s, 0.01 s | "A slip of 8 days (landing 26 Nov) is no longer a clear yes: 100 m north-west of the target the Earth is hidden for 239 of the 336 hours (from 30 Nov 01:00 UTC), leaving 97 hours of Earth contact of the 100 needed. The Earth goes behind the crest it stands on: ground 80 m away (one cell of the elevation grid) towards azimuth 144 deg (south-east)." |
| IM-1, 168 h | 0.10 s, 0.01 s | "A slip of 2 days (landing 24 Feb 23:00 UTC) fails: at the target itself the Sun is hidden for 176 of the 336 hours (from 2 Mar 15:00 UTC), leaving 160 sunlit hours of the 168 needed. The Sun goes behind ground 4.72 km away towards azimuth 273 deg (west), at 80.121 S, 0.534 E (130 m above the site)." |
| IM-2 | 0.12 s, 0.01 s | day 3: 100 m east of the target the Sun is hidden for 107 of the 336 hours, leaving 229 of the 240 needed; it goes behind the crest it stands on, 80 m away |
| Malapert shoulder | 0.07 s, 0.01 s | the planned date is not a clear yes: 100 m south-west of the target the Sun is behind the skyline at touchdown for 13 h; the crest it stands on |
| Ridge C2 | 3.88 s (new skylines), 0.01 s | the planned date is not a clear yes: 100 m north-west of the target 239 sunlit hours of 240 |

At touchdown at C1: Sun 1.09 degrees up and 2.69 above the skyline, no sunset in the window (next one
2,189 h away); Earth 0.07 degrees up and 2.20 above the skyline, Earthset 294.4 h later (30 Nov 06:22
UTC). What this view showed that changes a claim: **at the default example the margin is ended by Earth
contact, not sunlight, at one touchdown point, by 3 hours of an illustrative 100-hour need**; and at
three of five examples the "ridge" is ground one grid cell away, which is the limit of the 80 m grid and
is worded so.

## B2. Scatter-checked slip-margin map

`py scripts\build_scatter_field.py --procs 6` stored 12 landing-scatter skylines (8 on a 100 m circle, 4
at 50 m) for 2,407 map points: every point that passes at the point itself on at least one landing date
of 18 Nov 2026 to 16 Jan 2027 or 14 Nov 2026 to 12 Jan 2027 for the default need (733 that pass on 18
Nov, then 1,673, then 1). 28,884 skylines in 1,711 s with six processes. Files:
`data/field/scatter_el_i16.npy` (41,593,088 bytes, sha256 b64133724c93ae76...), `scatter_points.npz`
(sha256 dab418f4c8c1da73...), `scatter_field.json`.

`slipday/scatterfield.py`, `POST /api/robust-map`: for the dates and need on the card, every map point
that passes at the point is evaluated at its 12 scatter points and coloured by the days of slip that all
13 survive (five steps of one colour; a hollow amber cell where the margin is lost; a hollow grey cell
where no scatter skylines are stored). The single-point map is one switch away.

`py scripts\local_pass_tools\measure_pass2.py`:

| Landing, sunlit need | Pass at the point | Re-checked | Keep a margin (same / shorter) | Lose it | Largest margin | 5 days or more | Time, new / repeat |
|---|---|---|---|---|---|---|---|
| 18 Nov 2026, 240 h (the default) | 733 | 733 | **574** (454 / 120) | **159** | 9 -> 8 d | 74 -> 18 | 10.56 s / 0.03 s |
| 15 Dec 2026, 240 h | 678 | 678 | 517 (403 / 114) | 161 | 8 -> 5 d | 55 -> 14 | 10.56 s / 0.03 s |
| 18 Nov 2026, 168 h | 1,733 | 1,140 | 991 (765 / 226) | 149 | 9 -> 8 d | 266 -> 170 | 6.19 s / 0.03 s |
| 14 Nov 2026, 240 h | 0 | 0 | 0 | 0 | none | 0 | 7.07 s / 0.03 s |
| 1 Mar 2027, 240 h | 0 | 0 | 0 | 0 | none | 0 | 5.62 s / 0.03 s |

Default example, surviving margin: 0 days at 231 points, 1 at 174, 2 at 88, 3 at 30, 4 at 33, 5 at 12,
6 at 2, 7 at 1, 8 at 3. At the 159 points that lose their margin, 3 to 12 of the 13 touchdown points
pass on the planned date (37 points with 12 of 13). For the 168-hour need 593 coloured points are
outside the stored set and are drawn "not re-checked". Like for like against the mission card's
13-point count (float skylines) at 12 map points drawn at random, four from each class: identical at 12
of 12, in margin and in points passing. So the re-check removes 22 % of the coloured points and three
quarters of the points with five or more days of margin; the page prints the counts in the legend.

## B3. 3-D view (helper)

`slipday/view3d.py` (`GET /api/terrain3d`), `static/view3d.js`, `static/view3d.css`: a Canvas 2-D surface
of the real grid around the card's site (8, 16 or 32 km across), true scale by default with 2x and 3x
labelled, the directions to the Sun and the Earth with their height and whether the skyline hides them,
cells in shadow at the chosen time, the ground the Sun or the Earth goes behind (from B1), a slider and a
Play button over the landing window. No library and no request to any other host. A cell is in shadow
when the centre of the Sun's disc is behind terrain along a ray from 2 m above it; the far part of the
ray uses a step fraction of 0.01 where the skylines use 0.002. Measured by the helper on port 8130: a new
frame 0.95 s (81 x 81 cells; 0.46 s at 57 x 57, the phone size), a stored frame 0.015 s, 18 kB gzipped;
centre cell against the app's own skyline, hourly: IM-1 337 of 337 hours, Malapert shoulder 1,441 of
1,441 over 60 days (both printed again by the final test run), largest clearance difference 0.055
degrees (at C1 the Sun never comes within 1.67 degrees of the skyline in the default window, so that
window tests nothing). I checked it on the page (browser check "3-D view of the real LOLA grid ...": 80
distinct tones on the canvas, labels present) and in the screenshots. Not done: pinch zoom; a real phone.

## B4. Chance by lander class

`slipday/robust.py` (`lander_classes`), `POST /api/lander-classes`: the 93 landing-circle points plus
three rings to 2.5 km (141 points), each weighted by the mass of a two-dimensional Gaussian in the cell
it stands for (midpoint quadrature, checked against the analytic mass in a test); for the elliptical
class the long axis is tried in twelve directions. The range is the lowest and highest of the twelve
directions and of the 5th to 95th percentile over 400 resamplings of the points.

The three dispersions are **assumptions**, labelled so on the page ("assumed dispersions", and a caption
naming the one public figure behind each): precision lander, 99 % within 100 m (the goal JAXA set for
SLIM); CLPS-class lander, one standard deviation 250 m (the one reported miss, IM-2); unguided lander,
670 m by 400 m (a third of the 4 km by 2.4 km area ISRO specified for Chandrayaan-3). Those three figures
are from memory of public statements and were not re-read in this pass.

`py scripts\local_pass_tools\measure_pass2.py` (planned date; range in brackets):

| Site | Precision | CLPS-class | Unguided | Days of slip with 90 % or more (precision) |
|---|---|---|---|---|
| C1, 18 Nov 2026 | 100 % | **34.8 % (28.6 to 42.6)** | **17.1 % (11.6 to 23.5)** | 8 |
| Malapert shoulder | 99.1 % (98.1 to 100) | 68.7 % (57.8 to 78.6) | 61.1 % (51.4 to 70.1) | 7 |
| Ridge C2 | 96.2 % (94.4 to 98.1) | 36.8 % (26.5 to 46.7) | 21.9 % (14.6 to 29.7) | 8 |
| IM-2 | 100 % | 100 % (99.9 to 100) | 93.6 % (89.2 to 97.5) | 3 |
| IM-1, 168 h | 100 % | 97.8 % (95.1 to 99.7) | 91.0 % (84.8 to 96.3) | 1 |

At C1 the chance for the CLPS-class dispersion rises with slip (34.8 % as planned, 72.2 % on days 6 and 7,
0 % on day 9): later landing dates suit the surroundings better than the planned one. For the unguided
class the direction of the long axis alone moves the figure from 13.3 to 22.1 %. A site not in the stored
cache: 16.7 s here for the 48 extra skylines (35.9 s for all 141 at ridge C2); stored: 0.4 to 0.5 s.

## B5. Permanent shadow, links out, lunar against terrestrial

- **Permanent shadow** (`slipday/moonmap.py`, `/api/map/shadow`, a switch under the map): every 480 m cell
  of the average-illumination layer that reads zero (the layer is the LOLA team's 120 m map
  AVGVISIB_75S_120M_201608 averaged 4 by 4, already shipped). 527.3 km2 of such cells in the 60 km
  close-up. `/api/why` gives the nearest shadowed cell: 5.14 km from C1, 1.84 km from ridge C2, 7.5 km
  from the IM-2 site; the floor of Shackleton is inside one.
- **Links out** (helper, `static/links.js`): each site links to the same place in LROC QuickMap and NASA
  Moon Trek, in their south-polar views south of 80 S and their equirectangular views elsewhere. Each
  format was confirmed on a screenshot (seven page loads in all, generic client).
- **Not like Earth** (helper, `slipday/contrast.py`, `static/contrast.js`): the Sun's height over the same
  60 days at the site (the app's own series), at a place on Earth at the same latitude and at a town at
  45 N (textbook solar-position formula, labelled as such and as not NASA data), with a table. At C1 from
  18 Nov 2026: the Sun stays between +0.2 and +2.0 degrees and has no sunrise in the 60 days; the town
  has 60.

## B6. Year ribbon

`POST /api/year-ribbon`: the card's three-state verdict for each of 365 landing dates from the planned
one, drawn as one ribbon under the inputs; click a date to plan for it. `measure_pass2.py`: C1 from 18 Nov
2026: 62 clear yes, 54 not sure, 249 no; no clear-yes date in February, March, April, May or June 2027;
eight runs of yes, the longest 10 days; a smooth sphere says yes on 59 dates. IM-2's site from 6 Mar
2025: 27 / 10 / 328. IM-1's site (168 h): 51 / 10 / 304. 0.18 s each, then stored. The first 60 cells
equal the card's strip (tested).

## B7. The 20 m mosaic: fetched in part, and what it says about the headline

The whole file (`LDEM_80S_20MPP_ADJ.TIF`, 2,696,082,051 bytes) was started and stopped: it came at about
0.5 MB/s, which would have taken 90 minutes and competed with the other jobs. Its tile table sits at the
start of the file, so `py -I scripts\fetch_ldem20_crop.py` read the 49 tiles around the pole by HTTP range
request instead (236 s): a 3,584 x 3,584 crop at 20 m, 71.7 km across, no empty cells, heights -4,048 to
+1,959 m. Fetched twice; both times the received bytes had the same sha256. Checked against the 80 m
grid at 20,000 random points: mean absolute height difference 0.72 m as placed (RMS 1.03 m), 2.8 m when
shifted by one 20 m pixel in any of four directions, 10.7 m when shifted by 80 m.

The crop is **not** in the default terrain stack. `py scripts\ridge_20m.py --save` works the same example
out with the app's own functions on a stack whose finest grid is the crop (the 80 m grid and the coarser
ones beyond its edge), and stores the comparison in `data/validation/finer_grid_check.json`:

| C1, landing 18 Nov 2026, 240 h / 100 h / 14 days | 80 m grid (the page) | 20 m grid |
|---|---|---|
| Verdict on the planned date | Yes, 13 of 13, 7 days of margin | **Not sure, 11 of 13** |
| Touchdown points passing, days 0 to 9 | 13 13 13 13 13 13 13 13 12 0 | 11 13 13 13 13 13 13 13 10 0 |
| Clear-yes dates of 60 / of 365 | 20 / 62 | 13 / 35 |
| Landing circles 100 m / 250 m / 500 m / 1 km | 100 / 62.1 / 26.9 / 12.9 % | 88.3 / 49.4 / 21.7 / 10.4 % |
| Lander classes | 100 / 34.8 / 17.1 % | 90.6 / 28.1 / 13.9 % |
| Time with any Sun, 365 days, at the point | 92.51 % | 92.36 % (published: 92.1 %) |
| Same, range within 100 m | 74.0 to 92.95 % | 64.24 to 92.36 % |
| Longest darkness at the point | 194 h | 110 h (published: 112 h) |

On the 20 m grid two of the 13 touchdown points lose the Earth at touchdown on the planned date (hidden
for 11 h); slips of 1 to 7 days pass at all 13; day 8 fails on both grids. At ridge C2 both grids say
"Not sure" (9 of 13 on 80 m, 6 of 13 on 20 m), and one touchdown point there has Sun for 4 % of the year.

**This weakens the headline example**: "Yes, 7 days" is the 80 m grid's answer. The page now says so in an
amber line directly under the verdict of that example ("On the 20 m grid (off-line check): Not sure as
planned (11 of 13 touchdown points); slips of 1 to 7 days pass.") and in a validation tile, and the first
caption of the storyboard says "on the 80 m grid". It also settles an old mismatch in the other
direction: the longest darkness at the published point is 110 h on 20 m against a published 112 h.

Not done on 20 m: the slip-margin map and its scatter skylines, the ridge-pixel check against the LOLA
maps, every other site, and the tests (pinned to 80 m values). The page computes on 80 m.

## B8. Not done

Nothing from the "possibilities" report (ground-station calendar, shadow-adjacent sites, power network).

## C. Judged surface

- `SUBMISSION_DRAFT.md`: the new features with their numbers, the 20 m finding under "How we know how far
  to trust it" and "What it does not do", the 20 m mosaic and QuickMap / Moon Trek in the data lists; the
  container figures in the team notes are marked as belonging to the earlier code.
- `README.md`: what the second pass added, the page description, data sizes, test counts, the lanes, the
  architecture list. `LIMITATIONS.md`: a new first section on what the new views are and what they found.
- `demo/STORYBOARD.md`: five frames, 0-7, 7-13, 13-19, 19-24, 24-29 s; the challenge name opens caption 1
  and `[TEAM NAME]` closes caption 5; the old validation caption (three numbers) is gone from the video.
  `demo/SLIDES.md`: seven slides; slide 1 has `[TEAM NAME]` and `[MEMBER NAMES]`.
- Screenshots (`screenshots/`, 27 files, retaken 23:35 to 23:45 at 1280x800 and 390x844) and five
  storyboard frames at 1280x720 (`node scripts\storyboard.js http://127.0.0.1:8100/ demo`).
- Draft video: `py scripts\make_draft_video.py --ffmpeg D:\softwares\ffmpeg-8.1-full_build\bin\ffmpeg.exe`
  wrote `demo/slipday_draft_29s.mp4`; ffprobe: h264, 1280x720, 30 frames a second, 870 frames, duration
  29.000 s, 1.4 MB. Real screenshots with the storyboard's captions burnt in: one each for frames 1, 2, 3
  and 5, and ten for frame 4 (the 3-D view with the time slider stepped through the first 60 % of the
  landing window and the view turned 15 degrees each time, so the shadows move). A draft for the
  participant.
- Page length (browser check, `scripts\shot.js` and `node <scratch>\measure.js`): phone 12,408 px at the
  last measurement (21,303 at the review); every site card but the first, and the validation tables, are
  folded on a phone. Desktop 12,499 px (10,043 at the review): longer, because of the 3-D panel (688 px)
  and the comparison panel. A late bug found on the way: the tag of the new 20 m validation tile did not
  wrap and pushed the phone page to 461 px wide; fixed, and a browser check now measures the width again
  after every panel has loaded. First
  screen at 1280x800: verdict bottom 155 px, skyline chart bottom 412 px, the mission card ends at
  659 px, the slip grid starts at 783 px.
- Page load to network idle: 2.9 s desktop and 3.6 s phone on a warm server (browser-check run); 12.3 to
  12.8 s on the first visit after a restart, while the map and its re-check are worked out.

## Tests

```
> py -m pytest -q -p no:cacheprovider -rs        (SLIPDAY_REALDATA_DIR = data\reference)
204 passed, 1 warning in 195.75s                  last run 23:42 to 23:45, after the document changes
> node scripts\ui_check.js http://127.0.0.1:8100/ <folder>          (NODE_PATH and CHROME set; last run 23:43 to 23:45)
61 PASS, 0 FAIL, "ALL UI CHECKS PASSED"
> py -m pytest tests\test_pass2_text.py -q        (the document rules once more, after the last caption change, 23:46)
16 passed
```

152 tests before this pass; 52 new: `tests/test_pass2.py` (14: the lanes, a stored card while a slow
request runs, why it flips at C1 and IM-1, lander classes and ranges, the fallback grid, the year ribbon,
the scatter-checked map against the mission card, permanent shadow, the 20 m note and its reproduction on
the crop), `tests/test_view3d.py` (22, helper), `tests/test_pass2_text.py` (16, helper: the validation
panel, the document rules, the comparison view). No existing test was changed or removed.
`tests/test_round3.py::test_heavy_lets_two_computations_run_at_a_time` is why the slow lane keeps two
slots and `load.heavy()` keeps its old meaning. Browser checks: 43 before, 18 added, none changed. One
behaviour the old checks did not cover did change: a click on a cell of the verdict strip now draws the
skyline view for that day instead of re-planning (re-planning is a button in the panel).

Fresh-clone state (`SLIPDAY_DEM_DIR` pointing at a copy of `data/dem` without the 80 m file,
`SLIPDAY_REALDATA_DIR` at an empty folder; 23:48): `169 passed, 35 skipped, 1 warning in 50.12s`, no
failure. The 35 skips say why: 30 need the 80 m grid, 5 the reference maps (it was 130 and 22 before
this pass).

## New downloads

| What | Bytes | sha256 | From |
|---|---|---|---|
| `data/reference/LDEM_80S_20MPP_ADJ_tiles_r26-32_c26-32.bin`: 49 tiles of the 20 m mosaic as received | 30,148,202 | 43766eff358e612b1d2b13bceec9d8ba7c5d61ddf29037a3eef0aa9594a64d02 | https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF, HTTP range requests; byte ranges in the `.json` beside it; the first 1,048,576 bytes were also read for the tile table |
| `data/dem20/ldem_pole_20m_f32.npy`: those tiles decoded, values unchanged | 51,380,352 | 554c3532d842d97103a1bfb68ebbe2caabd33b0a23cd86dc5c3b0745dbc8200c | derived |

Both are recorded in `data/reference/DOWNLOADS.tsv` (23 rows, all present with the recorded sizes). The
aborted full download (23.5 MB of 2.7 GB) was deleted. Client name `slipday-data-fetch/1.0`; no other
outside request by me. The helper loaded QuickMap and Moon Trek pages seven times to confirm the link
formats. The 80 m source file still hashes to 82030dcb... and the working array to 1c1e4ac6....

Shipped data grew: `data/field` 21 MB to 62 MB (the scatter skylines), `data/horizon_cache` 9 MB to 19 MB
(1,545 files: the lander-class rings of the default and replay sites on both grid configurations, by
`py scripts\warm_cache.py` and `py scripts\warm_cache.py --no-80m`), `data/validation` one more file.

## D. What was not run

- Docker: nothing. Image size and every memory figure are from the first pass and the earlier code.
- No deployment, no public link, nothing pushed or posted. No git work; one `git status` was typed by
  mistake inside a shell line (read-only, nothing changed).
- Memory of the server after this pass's changes, on any system.
- `scripts/validate_terrain.py` (18 minutes) and the 240 m Earth map check.
- The 20 m grid for anything but the two ridge sites' cards, circles, classes and year statistics.
- A real phone; a screen reader.
- The 240 m fallback beyond one screenshot and the tests that cover it (the first screen there still
  reads "Not sure" for the default example).
- The JAXA and ISRO figures behind two of the three lander classes were not re-read at their sources.

## E. What a judge would still see that is wrong or weak

(Written before the follow-up of section H. Items 1 and 3 are answered there: the page now opens on an
example both grids support, and the card says which need ends its margin.)

1. The headline "Yes, 7 days" is the 80 m grid's answer; NASA's 20 m grid says "Not sure" for the
   planned date. The page says so under the verdict, but the example and the video still open on a Yes.
2. Nothing is deployed; no public link; the container figures are stale.
3. The slip margin of the headline example is set by an illustrative Earth-contact need (97 of 100 h).
4. At three of five examples "the ground that ends the margin" is one grid cell away: the tool can only
   say "the crest it stands on".
5. The lander classes are assumptions; the map's re-check leaves out the coarser grid and the near
   field; for a need other than the default, a third of the coloured points can be "not re-checked".
6. The first screen is dense: the skyline chart is 104 px tall on a desktop.
7. The desktop page is longer than before (12,499 px).
8. The draft video is five still frames; the 3-D view does not move in it.
9. The 3-D view has no pinch zoom and its sunlit shading is illustrative.

## F. Needs the participant

- Write the statement of AI use (draft and README placeholders) and fill `[TEAM NAME]`, `[MEMBER NAMES]`
  and both links.
- Decide whether the headline example should stay on 18 Nov 2026 now that the 20 m grid reads "Not sure"
  there, or move to a date both grids agree on; any change means new frames and captions.
- Re-measure memory in a container before choosing a host (Docker was down); deploy with the 80 m grid and
  `data/field/scatter_el_i16.npy`.
- Check the three lander-class figures at their sources, or reword them.
- Review the draft video; record the live page if the 3-D view should be seen turning.

## G. Files changed in this pass

New: `slipday/why.py`, `slipday/scatterfield.py`, `slipday/view3d.py`, `slipday/contrast.py`,
`static/view3d.js`, `static/view3d.css`, `static/contrast.js`, `static/links.js`,
`scripts/build_scatter_field.py`, `scripts/fetch_ldem20_crop.py`, `scripts/ridge_20m.py`,
`scripts/make_draft_video.py`, `scripts/local_pass_tools/measure_blocking.py`,
`scripts/local_pass_tools/measure_pass2.py`, `tests/test_pass2.py`, `tests/test_view3d.py`,
`tests/test_pass2_text.py`, `data/field/scatter_*`, `data/validation/finer_grid_check.json`,
`data/dem20/` (git-ignored array, `dems.json`), `demo/02_why_it_flips.png`, `demo/04_terrain_3d.png` and
`demo/04_terrain_3d_01.png` to `_09.png`, `demo/05_slip_margin_map.png`, `demo/slipday_draft_29s.mp4`,
this file.

Changed: `slipday/load.py`, `slipday/api.py`, `slipday/robust.py`, `slipday/field.py`, `slipday/terrain.py`,
`slipday/moonmap.py`, `slipday/replay.py` (the note only), `static/app.js`, `static/index.html`,
`static/style.css`, `scripts/ui_check.js`, `scripts/storyboard.js`, `scripts/warm_cache.py`,
`scripts/validate_more.py`, `scripts/validate_terrain.py`, `data/validation/*.json`,
`data/horizon_cache/` (576 more files), `data/reference/DOWNLOADS.tsv`, `README.md`, `LIMITATIONS.md`,
`REALDATA.md` (one sentence), `DISCOVERIES.md` (a new first section), `TEST_REPORT.md` (a note at the
top), `SUBMISSION_DRAFT.md`, `demo/STORYBOARD.md`, `demo/SLIDES.md`, `scripts/local_pass_tools/README.md`,
`demo/01_answer.png`, `demo/03_real_landing_im1.png`, `screenshots/*`, `.gitignore`, `.dockerignore`.

Removed: `demo/02_real_landing_im1.png`, `demo/03_validation.png`, `demo/04_slip_margin_map.png` (the
old frames, replaced by the five new ones).

## H. Follow-up (started 23:52): an opening example that the finer grid also supports

### H.1 The rule, written at 23:53 before any 20 m answer for any candidate was computed

The page and the video must not open on a verdict that finer data contradicts. The opening example is
chosen by this rule and by nothing else:

1. Scenario: unchanged. Landing 18 Nov 2026 00:00 UTC, 240 sunlit hours and 100 hours of Earth contact
   in 14 days, landing in sunlight with the Earth in view, 100 m landing scatter, 2 m observer, default
   rules (half the Sun's disc, the Earth's centre).
2. Candidates: the map points of the scatter-checked slip-margin map (section B2) that keep 5 or more
   days of margin at all 13 touchdown points on the 80 m grid for that scenario (18 points).
3. Order, the one the app already uses for its slip-robust list: largest surviving margin first; ties by
   the larger number of good landing dates of the single-point map; remaining ties by the lower map
   index (row by row from the top-left of the map). No other filter.
4. Test, for each candidate in that order: the full mission card (13 touchdown points, the coarser grid,
   the finer near-field sampling) on the 80 m stack the page serves, and the same full card on the stack
   whose finest grid is the 20 m mosaic (the coarser grid of that card is then the 80 m grid). The 20 m
   tiles within 10.3 km of the candidate (the distance out to which a 20 m skyline is sampled at full
   resolution) must be on disk first; any that are missing are fetched by range request from the NASA
   host and recorded.
5. The first candidate whose 20 m card is a clear "Yes" with at least one day of slip margin, and whose
   80 m card is a clear "Yes" with at least one day as well (the page computes on 80 m), becomes the
   opening example.
6. Stop after six candidates or at 00:23, whichever comes first. Every candidate tried is reported with
   both verdicts, failures included.
7. If none passes: the default stays where it is and the first screen shows the verdict the finest grid
   supports ("Not sure"), with the 80 m answer beside it.

### H.2 Candidates tried (`py scripts\pick_opening_example.py --max 6 --until 00:23 --save`, 23:55)

The 18 candidates in rule order, as the script lists them before any card is computed, start: 1. map
point 11150, 89.010 S 122.764 E (8 days at all 13 points; 16 good dates); 2. 11388, 89.019 S 125.426 E
(8; 16); 3. 11389, 89.005 S 124.875 E (8; 16); 4. 9998, 89.475 S 137.545 W (7; 26); 5. 11151, 88.996 S
122.255 E (6; 16); 6. 11517, 88.886 S 121.691 E (6; 15). Candidates 1, 2, 3, 5 and 6 need 20 m tiles of
column 33 (rows 30 to 32) that the first crop did not hold; those three tiles were fetched by range
request first (`py scripts\fetch_ldem20_tiles.py --rows 30 32 --cols 33 33`, 19.3 s; see "New downloads,
follow-up" below).

| Rank | Map point | 80 m grid, full card | 20 m grid, full card | Result |
|---|---|---|---|---|
| 1 | 89.010 S, 122.764 E | Yes, 8 days of margin; 13 13 13 13 13 13 13 13 13 0 touchdown points pass on days 0 to 9; coarser grid (240 m) yes, near field yes; 314 sunlit h, 311 Earth h | Yes, 8 days of margin; 13 13 13 13 13 13 13 13 13 0; coarser grid (80 m) yes, near field yes; 308 sunlit h, 311 Earth h | **passes** (5.3 s for both cards) |

The first candidate passed, so the search stopped there under the rule: **one candidate tried, one
passed, none failed; the other 17 were not tried**, and nothing is claimed about them. (The earlier
off-line result for the Shackleton connecting ridge, 80 m Yes and 20 m Not sure, is not one of these
candidates: that site is a literature point, not a map point.) All tried candidates are stored with both
cards in `data/validation/finer_grid_check.json` under `opening_example`.

### H.3 What the first screen opens on now

A first visit opens on the fixed example **"Slip-robust ridge point (89.010 S, 122.764 E)", landing 18 Nov
2026 00:00 UTC** (curated site `robust_pick`; a first visit no longer starts from today's date). On
screen: "Yes, it survives a slip of up to 8 days if it touches down within 100 m of the target", and
directly under it "Both grids agree. On the 20 m grid (off-line check): Yes as planned (13 of 13 touchdown
points), 8 days of margin." A line under the inputs says the page opens on a worked example that both
grids support and that site 2 shows a case where they disagree. Site 2 is the old example, the
Shackleton connecting ridge: selected, the card reads "Yes ... 7 days" with the amber line "On the 20 m
grid (off-line check): Not sure as planned (11 of 13 touchdown points); slips of 1 to 7 days pass."

Figures of the opening example on the 80 m grid (in-process calls to the app's endpoints, 23:59): 16
clear-yes dates of 60 and none unsure; next good dates 17, 18 and 19 Dec 2026; a smooth sphere says yes on
15 dates and the two answers differ on 5 (2 and 3). At touchdown the Sun is 2.25 degrees up, 1.16 above
the skyline, sunset 269.6 h later; the Earth is 0.19 degrees below the level horizon and 0.64 above the
skyline (the site is high ground), Earthset 310.6 h later. In the window: 314 sunlit hours (a smooth
sphere: 336) and 311 hours of Earth contact (277). Chance by lander class: 100 %, 86.6 % (79.5 to 94.0),
77.2 % (70.1 to 84.9). Landing circles: 100 %, 97.0 % (91.0 to 100), 82.8 % (73.5 to 93.0), 80.8 % (73.1 to
88.7). A year from 18 Nov 2026: 42 clear yes, 2 not sure, 321 no; no clear-yes date from January to
August 2027. On the 20 m grid: 15 clear-yes dates of 60 and 1 not sure; next good dates 18 to 20 Dec.

### H.4 Which need ends the margin

The card now says it, in bold at the end of "What ends the margin", for whichever example is shown.
Opening example: "A slip of 9 days (landing 27 Nov) fails: at the target itself the Earth is hidden for
241 of the 336 hours (from 30 Nov 23:00 UTC), leaving 95 hours of Earth contact of the 100 needed. The
Earth goes behind ground 131.59 km away towards azimuth 244 deg (west-south-west), at 85.996 S, 19.485 E
(488 m above the site). **Ended by the Earth-contact need (95 of 100 h), an illustrative figure, not a
published requirement.**" The 20 m card gives the same reason (131.63 km, 489 m). So the opening example's
margin is still set by an illustrative need; no published Earth-contact requirement was found for any
mission, and the card now says so instead of leaving it to be inferred. For a replay whose sunlit need
comes from a published plan (IM-1) the line reads "Ended by the sunlit-hours need (160 of 168 h), a
figure from the mission's published plan."

### H.5 Lander classes: each figure read first-hand (plain `curl`, client name `slipday-source-check/1.0`, 00:01)

| Class | Figure, as read | Page | sha256 of the page as fetched (bytes) |
|---|---|---|---|
| precision | "pinpoint landing within an accuracy of 100m, which has been declared to be the main mission of SLIM"; touchdown "approximately 55m east of the original target landing site" | JAXA press release, 25 Jan 2024, https://global.jaxa.jp/press/2024/01/20240125-1_e.html | ff55c374acc9908540d84a740665fab63e64a9321c411f2d9630f9e31b4e8a58 (30,472) |
| CLPS-class | "The lunar lander is on its side about 820 feet from the intended landing site, Mons Mouton" (820 feet is 250 m) | NASA news release, 7 Mar 2025, https://www.nasa.gov/news-release/nasa-receives-some-data-before-intuitive-machines-ends-lunar-mission/ | e3ded4636df4627022fbdb8d86e4ce5ff3306401b8e2a0ea1f79e59b6faa7433 (285,535) |
| unguided | "Landing Site (Prime) 4 km x 2.4 km 69.367621 S, 32.348126 E" | ISRO, Chandrayaan-3 details page, https://www.isro.gov.in/Chandrayaan3_Details.html | 1cd93453d0c774e35ed58b52a2d9a87eba81be65433f30ae421e8f6add92eded (33,528) |

Two other pages were fetched and did not carry the figure (https://global.jaxa.jp/projects/sas/slim/,
35,453 bytes; https://www.isas.jaxa.jp/en/missions/spacecraft/current/slim.html, 384 bytes). All three
figures are now cited in the code (`slipday/robust.py`: figure, source, address, date read) and on the
page: the caption under the lander-class rows links each figure to its page, and each row's tooltip
quotes it. What stays an assumption, and is labelled so: turning each figure into a Gaussian of that
size (100 m as the 99 % radius; one landing's miss as one standard deviation; a third of a landing
area's half-axes as one standard deviation), and calling the third class "unguided" although
Chandrayaan-3 itself was guided.

### H.6 Validation re-run, and memory on Windows

- `py scripts\validate_terrain.py data\reference` (23:52 to 00:02, 9 min 53 s, exit 0) followed by
  `py scripts\validate_more.py data\reference` (2 min 1 s; the first script rewrites the stored file
  without the second one's tables): **all 11 tables of the validation panel are identical, row for row,
  to the ones stored before, and so are the four headline tiles.** Sunlit share against the LOLA maps:
  0.80 points, correlation 0.9916 (60 m map) and 0.76, 0.9949 (120 m map); ridge pixels 3.77 to 5.25 over
  ten seeds; Earth in view 0.97 (1.31 without 53 points); connecting ridge 92.1 %.
- Peak memory of the plain Python server **on Windows** (`Get-Process` on the process listening on port
  8100; the glibc arena setting does nothing here, and these are not comparable with a Linux memory
  group): 59 MB working set after start; 199 MB (peak 334 MB) after the first page load with every new
  view drawn (card, skyline view, ribbon, lander classes, map with its 13-point re-check, 3-D view,
  comparison view); the same after a phone page load; **peak working set 498 MB, peak commit 1,107 MB**
  after 15 cold requests fired at once (4 landing circles and 2 lander classes for new points, the
  slip-robust list, 2 new map dates with their re-check, 6 new 3-D frames: 10 answered in 0.8 to 43.8 s,
  5 big ones refused at once with 503) followed by four big cold jobs two at a time (22.6 to 47.4 s
  each). The stored opening card answered in under 0.05 s afterwards. The review measured 553 MB in
  normal use and 764 MB after its burst of twelve on the earlier code; the queue now bounds the burst.
  Not measured: Linux, a container, a small host.

### H.7 Judged surface and tests after the change

- Storyboard: captions 1 and 2 changed ("Yes, with 8 days of slip margin, and NASA's finer grid agrees.";
  "On day 9 the Earth sets behind high ground far away."); notes rewritten for the new numbers on screen.
  Slides 3 and 4, the draft, README, LIMITATIONS (new first point) and DISCOVERIES (finding 7) updated.
  The storyboard frames, the draft video and the screenshots were retaken on the new opening example.
- New downloads, follow-up: `data/reference/LDEM_80S_20MPP_ADJ_tiles_r30-32_c33-33.bin`, 1,903,731 bytes,
  sha256 fd7006d95713b38adfb12157462899f5f5460c3577d150b530defb5a16b63087, three tiles of
  https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF by range request (byte ranges in the
  `.json` beside it), merged into `data/dem20/ldem_pole_20m_f32.npy`, which is now 3,584 x 4,096 cells,
  58,720,384 bytes, sha256 24d627521a0fa6701bec914c493edeb2c9ca888782ca848c8828e729248e6ec2 (this
  replaces the hash given under "New downloads"; 1,048,576 cells of the added column are empty and fall
  back to the 80 m grid). Recorded in `data/reference/DOWNLOADS.tsv`. The three source pages of H.5 are
  not kept in the entry; their addresses and hashes are above.
- `data/horizon_cache` now holds 1,827 files (the opening example's skylines on both grid
  configurations, by `py scripts\warm_cache.py` and `--no-80m`).

### H.8 Tests and checks after the follow-up (last runs 00:13 to 00:19)

```
> py -m pytest -q -p no:cacheprovider -rs        (SLIPDAY_REALDATA_DIR = data\reference; 00:13 to 00:16)
207 passed, 1 warning in 189.32s
> the same as a fresh clone has it (no 80 m grid, no reference maps; 00:16)
170 passed, 37 skipped, 1 warning in 48.42s
> node scripts\ui_check.js http://127.0.0.1:8100/ <folder>          (00:12 to 00:14)
65 PASS, 0 FAIL, "ALL UI CHECKS PASSED"
> py -I scripts\local_pass_tools\measure_blocking.py http://127.0.0.1:8100 0 2 12        (00:17)
default card 0.04 to 0.06 s with 2 and with 12 slow requests in flight; of the 12, 5 answered (21.8 to 62.9 s), 7 refused at once
```

Three tests added in the follow-up (`tests/test_pass2.py`, now 17): the page opens on an example both
grids support and the rule's bookkeeping holds (every candidate stored in order, the chosen one is the
first that passes, the curated site is that point, the card carries the 20 m answer and names the need
that ends the margin, the connecting ridge stays as the disagreeing case); the stored 20 m card of the
opening example reproduces on the crop; each lander class cites its page. Two of my own earlier tests
were changed to look the connecting ridge up by its id instead of by position in the stored file. Four
browser checks added (opening example and its "both grids agree" line; the need that ends the margin;
the three source links; the old example as the disagreeing case); none of the earlier ones changed.

One more defect found and fixed on the way: a browser-check run failed with 503 on `/api/landing-circles`
and `/api/lander-classes` when the page changed the mast height, because the big-job queue limit counted
small waiting jobs too. Now only big jobs count towards it (`slipday/load.py`); the run after the fix has
no failed request, and the blocking measurement above was repeated on that code.

Page figures after the follow-up: first screen at 1280x800: verdict bottom 146 px, skyline chart bottom
399 px, slip grid top 790 px; phone page 12,908 px; page load to network idle 12.8 s on the first visit
after a restart, 2.1 to 2.3 s after. Draft video: 29.000 s, 870 frames, 1.4 MB, on the new example.
Screenshots: 28 files (one new: `desktop_1280x800_grids_disagree.png`, the connecting ridge with its
amber line).

### H.9 What this follow-up changes in the sections above, and what it could not do

- Section E, items 1 and 3, and section F, second item: superseded. The page and the video now open on
  an example that both grids give a clear "Yes" for. Its margin is still ended by an illustrative need
  (Earth contact, 95 of 100 hours), and the card now says so in bold.
- Section B4 and LIMITATIONS: the lander-class figures are no longer "from memory"; each was read
  first-hand and is cited beside the number.
- Section D: `validate_terrain.py` has now been run (all tables unchanged) and a Windows memory figure
  taken (peak working set 498 MB). Docker is still not run; no Linux or container figure exists for the
  current code.
- Could not do: try more than one candidate (the rule stops at the first that passes, and it was the
  first); look up what the feature at the opening example or at the blocking ground is called; find a
  published Earth-contact requirement, so the margin of the opening example is still set by an
  illustrative figure; measure memory on Linux.
- Files added in the follow-up: `scripts/pick_opening_example.py`, `scripts/fetch_ldem20_tiles.py`,
  `data/reference/LDEM_80S_20MPP_ADJ_tiles_r30-32_c33-33.bin` and `.json`,
  `screenshots/desktop_1280x800_grids_disagree.png`. Changed: `slipday/load.py`, `slipday/api.py`,
  `slipday/why.py`, `slipday/robust.py`, `slipday/sites.py` (the curated site `robust_pick`),
  `static/app.js`, `static/style.css`, `scripts/ui_check.js`, `scripts/storyboard.js`,
  `scripts/ridge_20m.py`, `scripts/warm_cache.py`, `tests/test_pass2.py`,
  `data/validation/*.json` (regenerated, same figures; the opening-example search added),
  `data/dem20/` (three more tiles), `data/horizon_cache/` (1,827 files), `data/reference/DOWNLOADS.tsv`,
  the storyboard frames, the draft video, the screenshots, and the documents.

# Pass 3 (started Sunday 15 Nov 2026, 01:00 local time; time box 3.5 hours)

Same machine, same rules. This section is written as the work goes. The four rules below were written at
01:05, before any of the answers they govern was computed or looked at.

## P3.0 Rules R1 to R4 (stated as written first; not verifiable from file times, see DEEP_PASS.md G1)

**R1. Earth mask on the card.** For the example on the card, the Earth rule is swept from a mask of 0
degrees (the Earth's centre just above the skyline, the rule used so far) upwards in steps of 0.05
degrees, with everything else unchanged, and the card reports three numbers for the planned date: the
largest mask at which it is still a clear "Yes", the smallest at which it is "Not sure", the smallest at
which it is "No". The opening example is not changed whatever the sweep says. If a published mask for a
direct-to-Earth link from the lunar surface can be cited first-hand, the verdict at that mask is shown
beside the zero-mask verdict; if not, every non-zero mask is labelled illustrative. Separately, and
without changing the default, the first candidate in the fixed order of section H.1 whose full card is a
clear "Yes" with at least one day of margin on the 80 m grid and on the 20 m grid at that mask (or, with
no citable mask, at 1 degree, labelled illustrative) is reported; at most six candidates are tried.

**R2. Slip-robust sites beside permanent shadow.** Permanent shadow: the pixels of the LOLA team's 60 m
average Sun-visibility map (AVGVISIB_85S_060M_201608) that read zero. For every point of the
scatter-checked slip-margin map: A = area of such pixels whose centre lies within 1.0 km of the point
(0.36 hectares each), D = distance to the nearest one. A point is "beside permanent shadow" when A is at
least 10 hectares (the depth check's thresholds, kept). It "survives a slip" when all 13 touchdown points
pass on the planned date and for at least one day of slip (surviving margin of 1 day or more). A point is
flagged "on shadow itself", listed apart and not ranked, when its own pixel, or the pixel under any of its
13 touchdown points, is a zero pixel. Ranking of the rest: larger surviving margin first, then larger A,
then lower map index; the list shows the first 12 that are at least 1 km apart (the separation the
slip-robust list uses). Counts are reported for surviving margins of 0 or more, 1 or more and 5 or more
days, whatever they turn out to be. Permanent shadow is where it is dark, not where ice is.

**R3. Earth contact as station visibility.** An hour counts as Earth contact when the Earth's centre is
above the terrain skyline at the site (the rule used so far) and the Moon's centre is at or above the
elevation mask at one or more of NASA's three Deep Space Network complexes (Goldstone, Madrid, Canberra),
using coordinates and a mask read first-hand and cited; if no mask can be cited, 10 degrees is used and
labelled illustrative. The hour is credited to the complex at which the Moon stands highest. The station
geometry is checked against JPL Horizons before it is used. The opening example's card is then worked
out under this rule on both grids, and its verdict and margin are reported and shown whether or not they
change. The hours a mission needs (100 by default) remain a figure typed on the card.

**R4. A 20 m mark on the slip-margin map (last, if time allows).** For the default scenario, each
coloured map point is re-checked on the stack whose finest grid is the 20 m mosaic: 13 skylines (the
point and its 12 scatter points). A point is marked "20 m agrees" when the 20 m grid gives the same
answer as the 80 m grid to the question "do all 13 touchdown points pass on the planned date", and "20 m
disagrees" otherwise; the share that agrees is printed whatever it is, together with how many surviving
margins are equal. If the run cannot finish, the layer is shown for the part done and the share done is
stated.

## P3.1 Earth-mask sweep (rule R1), measured 01:05 to 01:10

`robust.earth_mask_sweep` and `POST /api/earth-mask` (0.13 s in process, stored skylines). Everything on
the card is held fixed (240 h of sunlight in 14 days [corrected in pass 4: this line said 100 h; the runs used the card's 240 h], 100 h of Earth contact, Sun and Earth at
touchdown, 2 m mast, 100 m scatter) and only the Earth mask moves, in steps of 0.05 degrees.

| example | landing | Yes up to | Not sure from | No from | Earth's centre above the skyline at touchdown | least of the 13 touchdown points |
|---|---|---|---|---|---|---|
| opening example (robust_pick, 89.010 S 122.764 E) | 18 Nov 2026 00:00 UTC | 0.60 deg | 0.65 deg | 0.70 deg | 0.64 deg | 0.63 deg |
| old example (shackleton, C1) | its stored date | 0.50 deg | 0.55 deg | 2.25 deg | 2.20 deg | 0.53 deg |
| IM-2 (6 Mar 2025 17:00 UTC) | as flown | 10 deg (end of sweep) | - | - | 12.3 deg | - |

In plain words: on the planned date the Earth's centre stands only 0.64 degrees above the skyline at the
opening site (about one and a quarter Earth diameters as seen from the Moon). The planned date is the
thinnest of its nine "Yes" days: least clearance of the 13 touchdown points by landing day 0.63, 1.88,
3.18, 4.39, 5.48, 6.48, 7.23, 7.46, 6.97 degrees. At masks of 1, 2, 3, 5 and 10 degrees the planned date
is "No" (0 of 13 touchdown points pass). The opening example was not changed (rule R1).

Published mask: no published elevation mask for a direct-to-Earth link from the lunar surface was found
first-hand in this pass (the helper sent to look was stopped by a usage limit before it reported). Every
non-zero lander-side mask on the page is therefore labelled illustrative. The DSN handbook's 10-degree
figure (P3.3) is a mask at the ground station, not at the lander, and is used only for the station rule.

## P3.2 Slip-robust sites beside permanent shadow (rule R2), measured 01:10

`scripts/prepare_psr.py` cut the mask from AVGVISIB_85S_060M_201608.TIF (sha256 ccf67d4f39e0a970...):
1068 x 1068 pixels of 60 m round the pole, 178,727 zero pixels = 643.42 km2;
`data/field/psr_pole_60m.npz` 32,330 bytes, `data/field/psr_points.npz` 322,225 bytes (9.3 s). Of the
14,400 map points, 5,405 have 10 ha or more of permanent shadow within 1 km, 2,368 sit on a zero pixel
themselves and 2,662 have the point or one of its touchdown points on one.

Default scenario (start 18 Nov 2026, the map's own defaults), `POST /api/shadow-sites`, 10.0 s first
call, 0.06 s repeat:

| surviving margin | all points | beside shadow | beside, not on it (ranked) | beside but on shadow itself |
|---|---|---|---|---|
| passes at the point (single) | 733 | 67 | 48 | 19 |
| 0 days or more (all 13) | 574 | 39 | 28 | 11 |
| 1 day or more ("survives a slip") | 343 | 27 | **20** | 7 |
| 5 days or more | 18 | 0 | 0 | 0 |

So 20 points survive a slip of at least a day and have at least 10 ha of permanent shadow within 1 km
without standing on it; none of them keeps 5 days. Best: 89.572 S, 19.134 E, surviving margin 4 days
(4 at the point alone), 10.4 ha within 1 km, nearest shadowed pixel 221 m at bearing 166 deg. Next:
89.374 S 110.821 W (3 days, 10.1 ha, 439 m); 89.543 S 140.856 W (2 days, 18.7 ha, 172 m); 89.413 S
114.044 W (2 days, 16.2 ha, 128 m); 89.016 S 85.675 W (2 days, 14.0 ha, 665 m). Permanent shadow is
where it is dark in the LOLA team's 18.6-year model, not where ice is; no ice data is used.

## P3.3 Station geometry (rule R3), checked 02:10

`slipday/stations.py` (written by a helper before the usage limit stopped it; read, run and checked
here). Coordinates of DSS 14, DSS 63 and DSS 43 and the elevation limits were read first-hand from the
DSN Telecommunications Link Design Handbook 810-005, module 301 Rev. P (2,745,535 bytes, sha256
53d8c28e...; Table 5 and section 2.2.3: "6.0 degrees for receive, 10.0 degrees for low-power transmit,
and 13.5 degrees for high-power transmit"). The 10.0-degree transmit limit is used, as one flat angle.
So the station mask is cited, not illustrative. Against six JPL Horizons tables (294 hourly rows, 20 to
22 Nov 2026 and 10 to 12 Jun 2034, airless): largest difference in the Moon's elevation 0.00060 deg,
mean 0.00023 to 0.00044 deg per complex (`scripts/check_stations_horizons.py`). `tests/test_stations.py`
and `tests/test_view3d.py`: 48 passed. URLs and sha256 in `fixtures/stations/SOURCES.md` and
`DOWNLOADS.tsv`.

## P3.4 Station rule on the card (rule R3), measured 02:15 to 02:20

`slipday/contact.py`, `POST /api/stations`; the card's Earth need uses it when `earth_stations` is set (the
page sets it by default and has a box to turn it off, under "Rules"). Opening example, landing 18 Nov 2026,
first 14 days, Earth's centre above the target's skyline for 311 of 336 hours:

| complex | hours carried (Moon highest there and at least 10 deg up) |
|---|---|
| Goldstone (DSS 14) | 104 |
| Madrid (DSS 63) | 122 |
| Canberra (DSS 43) | 85 |
| Earth up, no complex in view | 0 |

Over one 18.6-year cycle (2026 to 2044, 2-hour steps), of the hours with the Earth above this site's
skyline: Goldstone 26 to 34 %, Madrid 33 to 41 %, Canberra 26 to 39 % (largest 2033 to 2035, smallest
2044), no complex in view 0.3 to 1.5 %. The old example (Shackleton ridge C1) is within a point of these.

Card under the station rule: **verdict and margin unchanged**. Opening example: "Yes, 8 days" on the 80 m
grid and "Yes, 8 days" on the 20 m stack, with and without the station rule; Earth-mask sweep unchanged
(Yes up to 0.60 deg). Shackleton C1: "Yes, 7 days" on 80 m and "Not sure" on 20 m, with and without it.
The slip-margin map and the shadow-site list for the default scenario are also unchanged by it (574 map
points keep a margin; 20 shadow sites). That the rule is live: with the station limit raised to 40 deg in
a test the opening card turns to "No". The 20 m runs used the 9 x 9 tile crop (rows and columns 25 to 33,
fetched in pass 3), larger than the 7 x 7 crop of the stored finer-grid check, and agree with it.

## P3.5 Other measured items, 02:20 to 02:45

- **240 m fallback** (`SLIPDAY_SKIP_DEMS=ldem_80s_80m`): the opening example reads "Yes, 7 days" with the
  scatter widened to 240 m, both Earth rules; no 20 m line is shown (correct: the stored check is for the
  80 m grid). The draft, team notes, storyboard notes, slides, README, LIMITATIONS and DISCOVERIES said
  "Not sure"; corrected. The old example's season sentence (February to June) is gone from the draft.
- **Ground that ends the margin, named** (`slipday/gazetteer.py`, the USGS / IAU gazetteer cut to 509
  features south of 80 S with diameters): a name is given only when the point lies within half the
  feature's diameter of its centre (smallest such feature). Opening example: the Earth goes behind ground
  131.6 km west-south-west, inside Malapert (crater, 72.4 km). C1: inside Mons Malapert (67 km). IM-2:
  Mons Mouton. Points that no feature contains keep direction and distance only. The map marks the point
  when it lies on the map.
- **Another observer height**: `/api/robust-map` and `/api/shadow-sites` now refuse a request for any
  observer other than the stored 2 m ("not available for 10 m") instead of answering with 2 m skylines.
- **The opening map stays in memory**: the slip-map and scatter-map caches never evict the opening
  map's entry (the review's 62 s first visit under load came from that map dropping out of memory).
- **3-D view**: the helper's WebGL renderer was left complete (syntax check, 22 Python tests and the
  browser check pass; played in headless Chrome the time moved 30.2 h in 4.5 s). It draws smooth per-vertex
  shading from the real grid, the server's ray-cast shadow as a texture, 100 m contour lines, the Sun and
  Earth arrows, the landing point and its 100 m scatter ring, a "Heights exaggerated 2x" label, and merges
  labels that would fall on the same ground ("ground the Earth goes behind; ground that ends the margin").
  No library is used, so nothing is loaded from a CDN; a 2-D canvas renderer takes over without WebGL.
- **First screen** (1280 x 800): larger type on the card (13.5 px), the skyline chart 152 px tall (was
  104) with labels placed so that none overlaps (0 overlaps of 14 labels, checked in the browser), the
  hour-by-hour numbers folded under one line, the lander classes and landing circles moved to their own
  panel under the slip grid; the slip grid still begins on the first screen (793 px).

## P3.6 Rule R1, the separate report at 1 degree (illustrative), 02:48

`scripts/pick_opening_example.py --earth-margin 1 --max 6` (new option; it refuses `--save`, so it cannot
change the opening example), the same 18 candidates in the same order, full card on the 80 m grid and
on the 20 m stack (9 x 9 tiles), Earth's centre required 1 degree above the skyline:

| rank | point | 80 m | 20 m | passes |
|---|---|---|---|---|
| 1 (the opening example) | 89.010 S, 122.764 E | No (0 of 13 on the planned date; 13 of 13 on days 1 to 8) | No, same pattern | no |
| 2 | 89.019 S, 125.426 E | No | No | no |
| 3 | 89.005 S, 124.875 E | No | No | no |
| 4 | 89.475 S, 137.545 W | Not sure (9 of 13) | Not sure (9 of 13) | no |
| 5 | 88.996 S, 122.255 E | No | No | no |
| 6 | 88.886 S, 121.691 E | **Yes, 6 days** | **Yes, 5 days** | **yes** |

So at an illustrative 1-degree mask the first candidate that stays a clear Yes on both grids is rank 6,
88.886 S, 121.691 E (Yes, 6 days on 80 m and 5 days on 20 m). It is not made the default: the rule for
the opening example was written for mask 0 and is unchanged. Under a 1-degree mask the opening example
fails its planned date (at 1 degree the Earth counts as hidden at touchdown, for 8 hours on both grids) but a landing one
to eight days later passes at all 13 touchdown points.

## P3.7 Memory and load, Windows, 02:35 to 02:53

One server (port 8140, a scratch copy of the skyline cache) through: the browser checks twice (70
checks each), the storyboard script, four first-screen measurements, three bursts of the review's load
(10 cold requests at once, landing circles for i % 3 != 0 and lander classes otherwise, random points
89.2 S to 89.9 S; each burst: 5 answered, 5 refused with 503 and Retry-After, done after 82, 86 and 104
s), a mixed burst of 15 (4 landing circles, 2 lander classes, the slip-robust list, two new map dates
with their scatter check, six 3-D frames; all done after 84 s), two rounds of two big cold jobs, the
shadow-site list for three more dates and the station panel for two sites, then a fourth burst of the
review's load with a first visit in a browser 4 s into it.

- **Peak working set of the server process (Windows): 579 MiB** (607,453,184 bytes); peak commit
  (paged) 1,214 MiB. The review measured 627 MB and 1,173 MB in its own session; mine is a Windows
  figure under a comparable load, not a container figure.
- **First visit during a burst of 10 cold requests: network idle after 2.8 s** (1280 x 800), slip grid
  top at 793 px. The review's one 62 s first visit came from the opening map dropping out of memory; that
  entry is now never evicted (P3.5).
- Container figures: none. The Docker engine was not started; `scripts/container_check.sh` is written and
  has never run.

## P3.8 Rule R4, the 20 m mark on the slip-margin map, 02:32 to 02:58

`scripts/finer_map_check.py --procs 2`: every map point re-checked at 13 touchdown points on the 80 m
stack for the default scenario (733 points), re-checked again on the 20 m stack (81 tiles, rows and
columns 25 to 33, 92 km around the pole; beyond it the 80 m stack): 13 new skylines per point with the
app's own ray-march, counted as the scatter map counts. Self-check first: 4 points re-computed on the
80 m stack reproduce their stored margins exactly. Run: 1,571 s, complete (733 of 733).

- **639 of 733 points agree (87.2 %)** on whether all 13 touchdown points pass on the planned date;
  **94 disagree**, and every one of them the same way: the 80 m grid keeps a margin and the 20 m grid
  loses it (94 of the 574 margin-keeping points, 16 %). No point fails on 80 m and passes on 20 m.
- Surviving margins equal on both grids: 573 of 733. Of the 480 points that keep a margin on both, 414
  have the same margin, 60 one day less on 20 m, 5 two days less, 1 one day more.
- The opening example's point (map index 11150): 8 days on both.
- So the 80 m map is optimistic where it disagrees. The page marks each disagreeing cell with a red cross
  and prints the share in the legend, for this scenario only (`data/validation/finer_map_check.json`,
  13,163 bytes); any other date or rule gets no mark. The mark was computed with the skyline-only Earth
  rule; the station rule changes no point of this map (test), so the page shows it under either.
- The 20 shadow sites of P3.2 against the 20 m mark: 15 still survive a slip of a day or more on 20 m,
  1 keeps the planned date with no slip margin, 4 lose the planned date. The best, 89.572 S, 19.134 E,
  keeps 4 days on both grids; the second, 89.374 S, 110.821 W (3 days on 80 m), loses the planned date on
  20 m. The list on the page now shows the 20 m figure beside each row for this scenario.

## P3.9 Tests, state at the end, what was not run (03:08)

- `pytest` with everything installed: **248 passed** (205 s); as a fresh clone: **205 passed, 43
  skipped**; `node scripts/ui_check.js`: **70 of 70** (5 new checks; the 65 earlier ones unchanged).
  41 new tests (`tests/test_stations.py` 26, `tests/test_pass3.py` 15).
- The 80 m source file still hashes to 82030dcbdd7c4bb0... and the working array to 1c1e4ac62224f786...
  The shipped skyline cache still holds 1,827 files (every server and test of this pass used a scratch
  copy). No server is running; ports 8100 to 8199 are free.
- Draft video rebuilt (`demo/slipday_draft_29s.mp4`, 29 s, 1,081,498 bytes) from screenshots retaken
  this pass: captions in a 118 px band under the picture, so nothing on screen is covered; six frames,
  the last a closing frame of text with `[PUBLIC LINK]` (3 s); `[TEAM NAME]` is the only other
  placeholder. It is a sequence of real screenshots, not a screen recording (the 3-D view's ten frames
  are the view stepped through the landing window).
- A disclosure: an earlier patch script of this pass emptied `slipday/api.py` (a bad argument to Python's
  `open`, which truncates before it fails). The file was restored byte for byte from the last commit by
  reading the repository's loose object with Python's zlib, read-only; git itself was not run. All later
  changes to it were made on that restored copy.
- **Not run:** the container check (Docker engine not started), any deployment, a screen recording of
  the page (the video is screenshots), a search beyond the first pass for a published lander-side link
  mask (the helper sent to look stopped at a usage limit; masks stay illustrative), the 20 m check for
  any map date but the default one, and the per-antenna DSN horizon masks.

### Pass 3 items, status

| item | status |
|---|---|
| 1 Earth rule: sweep on the card, clearance in plain words, cited mask | done; no lander-side mask could be cited, so non-zero masks are labelled illustrative; separate report at 1 degree done (P3.6) |
| 2 How it looks: 3-D view, first screen, skyline chart | done (P3.5) |
| 3 Name the ground that ends the margin | done (P3.5) |
| 4 20 m layer on the slip-margin map | done, complete (P3.8) |
| 5 Bug rows 3, 4, 6, 8 to 12 | done: docs corrected, season sentence removed, MANIFEST lists the tiles, 2 m-only refusal, opening map pinned in memory, fixed-date note, 20 m-only-for-stored-examples said |
| 6 Draft video | done as corrected stills with a caption band, not a screen recording |
| 7 Deployment readiness | done: README host needs, repository contents (248 MB, largest file 88.5 MB), render.yaml reason, container script written and not run, Windows memory measured (P3.7) |
| 8 Docs, screenshots, tests | done |
| Deep feature, part 1 (shadow sites) | done (P3.2, P3.8) |
| Deep feature, part 2 (station contact) | done (P3.3, P3.4) |
| Deep feature, part 3 (first screen, tests, docs) | done: one click from the card |

# Pass 4 (started Sunday 15 Nov 2026, 03:42 local time; time box 3 hours)

Same machine, same rules. Written as the work goes. The rules below were written at 03:50, before any
answer they govern was computed.

## P4.0 Rules R5 to R7 (stated as written first; not verifiable from file times, see DEEP_PASS.md G1)

**R5. Survival across slip days.** For a landing on slip day d (d = 0 is the planned date) the mission
window is the window on the card (14 days by default), hours [24 d, 24 d + window). Within it:
- *longest night* = the longest run of consecutive hours in which the Sun does not count as up under the
  card's own Sun rule (half the disc above the terrain skyline by default);
- *longest Earth outage* = the longest run of hours without Earth contact under the card's own Earth rule
  (Earth's centre above the skyline by the card's mask, and, when the station rule is on, a Deep Space
  Network complex with the Moon at least 10 degrees up).
A run that is still going at the end of the window is cut at the window's end and flagged "runs past the
window"; one going on at touchdown is counted from touchdown. These are hours a lander must ride through on
stored energy; no battery model is used, and no battery size is shown.
- Card: for each slip day, the largest value over the 13 touchdown points (the worst point), and one
  sentence for the last slip day that still passes: "slip N days and the longest night grows from X to Y
  hours" (and the same for the Earth outage); if it shrinks or stays, the sentence says so.
- Map: for each point of the scatter-checked map that keeps a margin (all 13 points pass on the planned
  date), the worst longest night over its 13 touchdown points and over the slip days 0 to its surviving
  margin (the slip days that still pass). Colour classes, fixed now: under 24 h, 24 to 48 h, 48 to 72 h,
  72 to 120 h, 120 h or more.
- Check: the same run-length code on the "no part of the disc visible" flags over the span of the
  existing longest-darkness figure at C1 must give that figure (194 h on 80 m, 110 h on 20 m).

**R6. The 20 m layer for more dates.** Map start dates 18 Nov 2026 and each 7th day after it up to 13
weeks (14 start dates, 18 Nov 2026 to 17 Feb 2027), page default need and rules. For each, every point of
the stored scatter skylines that the 80 m scatter check colours (keeps or loses a margin) is re-checked on
the 20 m stack exactly as in R4, with 20 m skylines computed once per point (they do not depend on the
date). Printed per date whatever it is: points, agreeing share, equal margins, and the direction of the
disagreements.

**R7. Naming.** A gazetteer feature names the ground only when the point lies within 90 % of its radius
("inside"); between 90 % and 110 % it is "on the rim of" (craters only; other kinds keep "near"); beyond,
no name. A crater is written "<name> crater" so that it cannot be read as a mountain of the same name.

## P4.1 Corrections, 03:44 to 03:50

- **Naming (rule R7).** The ground that ends the opening margin (85.996 S, 19.485 E) lies at 98.6 % of
  Malapert crater's radius (its rim line) and at 78 % of Mons Mouton's (130 km across in the gazetteer).
  Under R7 it is now "inside Mons Mouton"; pass 3's "inside Malapert" overstated it, as the review found.
  Craters are written "<name> crater" ("inside Shackleton crater"), so a crater cannot be read as the
  mountain of the same name. C1's own point has no name under R7.
- **Year ribbon.** Measured: 41 clear-yes dates and 3 not sure with the station rule on (the page's default),
  42 and 2 without it. Draft, slide 3, storyboard notes and LIMITATIONS now say 41 / 3 and give 42 / 2 as the
  no-station figure.
- **P3.1's "100 h of sunlight"** was a slip in the text: the runs used the card's 240 h (the review's
  r03b reproduces the results with 240 h). Corrected in place, marked as corrected.
- **3-D time label.** While playing, the label and the time under the picture now show the time of the frame
  whose shadow and words are drawn (the nearest step), not the in-between position. Browser check: 6 of 6
  samples equal while playing.
- **render.yaml** no longer cites the first pass's 512 MB container run; it says 1 GB or more and gives the
  Windows figure.
- **Lander-side Earth mask, looked for first-hand (about 15 minutes).** The LunaNet Interoperability
  Specification v5 (NASA, 29 Jan 2025; 2,778,937 bytes, sha256 f2158da7...) states no elevation mask for a
  surface user's direct-to-Earth link (its only "elevation" hits are the digital elevation map). JPL IPN
  Progress Report 42-243 (15 Nov 2025, "Antenna Separation for Multipath Diversity on Direct-with-Earth
  Links ..."; 1,195,161 bytes, sha256 affdf8c8...) describes fading from reflections off the lunar surface
  at low elevation and calls angles under about 2 degrees "extremely low"; it gives no mask either. So no
  mask is cited and the default stays 0. The card now says in one line: "A real link would want more than
  0.6° (ground reflections fade signals at grazing angles; JPL IPN 42-243)". Both files are in
  data/reference with DOWNLOADS.tsv lines.

## P4.2 Survival across slip days (rule R5), 03:50 to 04:00

`slipday/survival.py`, `POST /api/survival`, `POST /api/survival-map`.

- **Check first.** The new run-length code on the "no part of the disc visible" flags, 365 days from 18 Nov
  2026 at C1: **194 h on 80 m and 110 h on 20 m**, equal to `span_stats`' longest darkness (and the 20 m
  figure against the published 112 h). On the card's own Sun rule the same span gives 253 h (80 m) and
  226 h (20 m).
- **Opening example** (station rule on, 13 touchdown points, worst point per slip day): longest night
  20 h on slip days 0 to 7, 21 h on day 8 (the last day that passes), then 45, 69, 93 ... h as the window
  slides into the lunar night; longest Earth outage 27, 51, 75 ... 219 h on days 0 to 8. Both day-8 runs
  are still going when the 14-day window ends: the card says "slip 8 days and the longest night grows
  from 20 to 21 hours*, the longest Earth outage from 27 to 219 h* (*still going when the window ends)".
  So within the window the night barely changes over the slip margin, but the Earth outage that closes the
  window grows by 24 h per day of slip: that is what a late slip costs here.
- **C1** (station rule on): longest night 0 h on every passing day (0 to 7); Earth outage 47 to 215 h.
- **Map layer** (default scenario, 574 points that keep a margin): worst longest night over 13 touchdown
  points and the passing slip days ranges 10 to 96 h; classes fixed in R5: under 24 h 2 points, 24 to 48 h
  2, 48 to 72 h 24, 72 to 120 h 546, 120 h or more 0. At 331 of the 574 the worst night on some passing
  slip day is longer than on the planned date. The opening point: 21 h (20 h on the planned date). First
  computation 18 s, then cached. Refused for a 10 m observer like the other stored-skyline views.
- No battery model and no battery size are shown; the page says "hours, not a battery model".

## P4.3 Rule R6, the 20 m mark for 14 map dates, 03:44 to 04:25

`scripts/finer_map_store.py --procs 6`: 20 m skylines for all 2,407 points that have stored 80 m scatter
skylines, 13 each (31,291 skylines), 2,314 s; they do not depend on the date (git-ignored,
`data/dem20/scatter20_el_i16.npy`). `scripts/finer_map_dates.py`: page default need and rules with the station
rule on, start dates every 7 days from 18 Nov 2026; `data/validation/finer_map_dates.json`, 67,617 bytes.

| map start date | points re-checked | agree | share | 80 m keeps, 20 m loses | 80 m loses, 20 m keeps | equal margins |
|---|---|---|---|---|---|---|
| 18 Nov 2026 | 733 | 639 | 87.2 % | 94 | 0 | 573 |
| 25 Nov 2026 | 218 | 177 | 81.2 % | 41 | 0 | 170 |
| 2 Dec 2026 | 0 | - | - | - | - | - |
| 9 Dec 2026 | 0 | - | - | - | - | - |
| 16 Dec 2026 | 1,368 | 1,203 | 87.9 % | 165 | 0 | 1,053 |
| 23 Dec 2026 | 260 | 224 | 86.2 % | 35 | 1 | 224 |
| 30 Dec 2026 | 0 | - | - | - | - | - |
| 6 Jan 2027 | 0 | - | - | - | - | - |
| 13 Jan 2027 | 724 | 625 | 86.3 % | 99 | 0 | 536 |
| 20 Jan 2027 | 9 | 8 | 88.9 % | 1 | 0 | 8 |
| 27 Jan 2027 | 0 | - | - | - | - | - |
| 3 Feb 2027 | 0 | - | - | - | - | - |
| 10 Feb 2027 | 64 | 46 | 71.9 % | 17 | 1 | 42 |
| 17 Feb 2027 | 0 | - | - | - | - | - |

On 7 of the 14 dates no map point passes on the planned date under this need, so there is nothing to
re-check (the season: compare the ribbon's "none in Jan to Aug 2027" at the opening site). Over the 7 dates
with points: 2,922 of 3,376 agree (86.6 %); of the 454 disagreements, 452 are "80 m keeps a margin, 20 m loses
it" and 2 the other way. So the pass-3 finding holds across the season: where the 80 m map is wrong it is
almost always optimistic. 18 Nov reproduces pass 3's run exactly (639 / 733, 573 equal margins) with skylines
computed by a different script, which is a consistency check of both. The page marks the cells and prints the
share for whichever of the 14 dates is on the map (with the station rule on), and nothing for others.

## P4.4 Screen recording for the draft video, 04:15 to 04:30

`scripts/record_demo.js`: a headless-Chrome screencast through the DevTools protocol (WebGL by SwiftShader),
1280 x 800, of the running page clicking through six steps; 824 frames with their times.
`scripts/make_recorded_video.py` takes the first seconds of each step from the table in `demo/STORYBOARD.md`,
puts the caption in a band under the picture and adds a text closing frame: `demo/slipday_draft_29s.mp4`,
29.0 s, 1280 x 720, 30 fps, 870 frames, 1,071,740 bytes. Steps: the first screen (5 s), why it flips with
the ride-through line opened (5 s), the ride-through chart (4 s), the 3-D view playing (6 s), the shadow-site
list (3 s), the map with the 20 m crosses and a tooltip (3 s), closing (3 s). I looked at a frame from every
step: each caption number (8 days; day 9, 131.6 km, Mons Mouton; 8 days, 20 to 21 hours; 20 map points; 639
of 733) is on screen in its step. `[TEAM NAME]` and `[PUBLIC LINK]` are the only placeholders. The 3-D step
shows a "Working out the shadow" note for a moment while frames load: that is the page as it plays.

## P4.5 Tests, state at the end, what was not run (04:35)

- `pytest` with everything installed: **258 passed** (236 s); as a fresh clone (no 80 m grid, no reference
  maps; the 20 m crop still present, as the review noted): **210 passed, 48 skipped**. `node
  scripts/ui_check.js`: **74 of 74** (4 new: the ride-through line and chart, the link-margin note, the night
  layer, the 3-D time label while playing). New: `tests/test_pass4.py` (10). Two pass-3 tests that encoded
  "inside Malapert" were changed to rule R7; no test was removed or loosened otherwise.
- First screen at 1280 x 800: the slip grid still begins on it (795 px); phone: no horizontal overflow
  (a long layer name had pushed it to 526 px; fixed).
- Shipped skyline cache unchanged (1,827 files); the 80 m grid and its source file were not touched. No
  server is running; ports 8100 to 8199 are free.
- **Not run:** a container, any deployment, a search for a lander-side link mask beyond the two documents
  above, a battery model (by design), the 20 m check for the 2,407 points' neighbours that have no stored
  scatter skylines (the 80 m check does not colour them either), memory under load for this pass.

### Pass 4 items, status

| item | status |
|---|---|
| 1 Corrections (Malapert, 41 / 3, 100 h note, 3-D label, render.yaml, link-margin line) | done; no lander-side mask found to cite |
| 2 Survival across slip days (card sentence and chart, map layer, check against 194 / 110 h) | done |
| 3 20 m layer for more dates | done: 14 weekly dates, rate printed per date |
| 4 Screen recording | done: headless screencast, 29 s, captions in a band |
| 5 Tests, browser checks, screenshots, draft, slides, storyboard | done |
