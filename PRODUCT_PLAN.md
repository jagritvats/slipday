# Product plan, round 3

## Who uses it, for what decision

A CLPS payload or mission planner who has just been told the launch moved. The decision: does our landing
site still work if we land N days late, how many days can we slip before it stops working, when is the next
good date, and how sure is that answer. Second audience: an educator or a curious reader who wants the
same answer in one sentence for a real mission ("what if IM-2 had landed five days later?").

## One-sentence pitch

Slipday tells you what a launch slip costs at a lunar south-pole landing site: a plain yes or no for your
site, date and power and radio needs, the number of days you can slip, the next good dates, and how sure
the answer is.

## The view a judge sees first

A mission card at the top of the page, written as a sentence with four inputs (site, landing date, sunlit
hours needed, Earth-contact hours needed). Beside it the verdict in large type (Yes / Not sure / No), the
slip margin in days, one strip with a cell per day of slip, the next three good dates as buttons, and a
"how sure" line. The slip grid for four sites sits directly under it.

Competing public entries compete on terrain resolution and 3-D views (two ray-cast 20 m and 5 m grids).
Slipday does not try to match that. It competes on the decision: slip cost, and confidence.

## One list, fixes and features together, ordered by value per hour

| # | Item | Kind | Why it raises the win chance |
|---|---|---|---|
| 1 | Mission card: yes / not sure / no, slip margin, next three good dates, plain sentence | feature (own idea) | Turns a heat map into an answer; the 30-second demo opens on it. No public entry read gives a slip margin. |
| 2 | "How sure" ensemble on every verdict, slip-grid cell and year-table figure: 13 points within 100 m, the same point on the 240 m grid, and a finer near-field sampling | feature + fixes | One mechanism that also retires three review findings: the fragile exact match at C1, longest darkness on ridges shown without a caveat, and the undisclosed near-field sampling convention. |
| 3 | Headline numbers made true: the 0.8-point agreement qualified by a ridge-pixel figure measured in this build; C1 shown as a range; the "distant peak" explanation corrected | fix | These cap the validity score and are what a LOLA specialist would object to first. |
| 4 | Slip-robustness map: slip margin, number of good dates, worst and median landing date for every 500 m point within 30 km of the pole | feature (reviewer's item 3) | "Where does a slip hurt least" in one picture; computed live for the dates and need on the card. |
| 5 | Memory under burst load brought under a measured figure, with the host requirement restated | fix | The live link is a judged surface; the free host has 512 MB. |
| 6 | Earth-visibility check against the LOLA team's Earth maps: our side computed at the same 400 points, loader and comparison ready, download in the local pass | feature (reviewer's item 1) | Closes the one admitted validation hole once the files are fetched. |
| 7 | Default slip measure changed to total usable hours; zero cells explain themselves | fix | The first screen no longer reads as "no power" when only the Earth is down at touchdown. |
| 8 | Shareable URL for every scenario; four real missions (IM-1, IM-2, Chandrayaan-3, Blue Ghost 1) as one-click worked examples | feature (own idea) | A judge can open the exact scenario from the video; real missions make the story concrete. |
| 9 | Resolution ladder on each site card: 80 m, 240 m, 474 m, 1.9 km, smooth sphere | feature (reviewer's item 4) | Cheap; shows with the app's own data why terrain resolution matters. |
| 10 | "Not validated" note on coarse-grid and north-polar sites; validation tiles say which grid they were run on | fix | Removes two places where a label claimed more than was tested. |
| 11 | Site pairs: joint sunlight and longest joint darkness | feature (reviewer's item 5) | Cheap once the masks exist; shown as model output with its caveat. |

## Deliberately not built

- Finer terrain (20 m, 5 m): catch-up, and the files are not reachable from the sandbox.
- 3-D globe, first-person sky, slope maps, power or thermal models, an AI assistant: other entries have
  them; they do not sharpen the slip answer.
- Cosmetic fixes a judge would not notice.

Status at the end of the round: all eleven items are built; item 6 runs its comparison once the Earth maps are
downloaded (LOCAL_PASS.md).

## Local pass, 14 Nov 2026 (one more list, same ordering; results in LOCAL_PASS_RESULTS.md)

| # | Item | Kind | Status |
|---|---|---|---|
| 1 | Official downloads of every LOLA file; hashes compared; arrays, field and validation rebuilt from them | provenance | done; all recorded hashes matched |
| 2 | Earth check run against the LOLA team's Earth maps, reported for the rule in the label | validation (item 6 above) | done: 0.97 and 0.69 points, correlation 0.995 and 0.998 |
| 3 | 240 m fallback no longer overconfident: scatter never smaller than a grid cell, said on the card | fix | done; the default example reads "Not sure" on the fallback |
| 4 | The headline says which landing scatter the Yes assumes | fix | done |
| 5 | Arena limit in every start command and in code; measured in a 512 MB container | fix | done |
| 6 | Each real-landing replay carries its mission's own need | fix | done for three of four; Earth-contact hours stay illustrative |
| 7 | Storyboard cut from eight frames to four | fix | done |
| 8 | Landing circles: share of a 100 m to 1 km circle where the plan holds, per day of slip | feature | done; an area count, not a dispersion model |
| 9 | Slip-robust site list from the map | feature | done, on demand |
| 10 | Live Horizons cross-check | check | run once: 1.4e-05 degrees |

Lead with what the round-3 review found in no other public description: a slip margin in days, a
three-state verdict that needs an ensemble to agree, a slip-margin map, the same site on several grids.
The "no public entry read gives a slip margin" in item 1 of the first table dates from an earlier reading
of five entries; the round-3 reviewer read 63 and found nine with slip or re-plan features, none with
those four. Not built: the 20 m mosaic, a deployment, a video.
