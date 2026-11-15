# Add-on: days of slip for the whole map

Hand-over, Sunday 15 November 2026 (19:15 to 20:55 IST).

## What it does

The map layer "days of slip the planned landing survives" existed only for the 60 km square around the pole
(14,400 points, one every 500 m). That is why the page jumps to the close-up when the layer is chosen. This add-on
works out the same layer for the **whole "South pole to 80°S" map**: the square of the LOLA 80 m mosaic, 608 km
across, **one point every 2 km** (304 x 304 = 92,416 points).

- **Same method as the close-up.** Each point's skyline is made by the close-up's own builder
  (`scripts/build_field.py`'s worker, imported, not copied): same ray-march, observer 2 m above the ground,
  720 directions, 300 km reach. Same terrain stack (`data/dem`: LOLA 80 m, then 240 m, 474 m and 1.9 km beyond
  its edge, for the far part of each skyline; fingerprint `76de51d5e9+35bc39a609+cdb14f87ee+feb25e8376`, identical to the close-up's). Same
  evaluation code (`slipday.field.per_date` and `field.statistics`, unchanged).
- **Same plan as the close-up's default:** landing 18 Nov 2026 00:00 UTC, 60 landing dates one day apart,
  240 sunlit hours and 100 hours of Earth contact in the first 14 days, Sun and Earth up at touchdown, half the
  Sun's disc, no extra mask. Both Earth rules are stored: "a Deep Space Network station must see the Moon" (the
  page's default) and "Earth above the skyline is enough".
- **Checked at one position only.** Each coarse point is checked at its own position, not at the 13 touchdown
  points that the close-up's scatter check and the site card use. The 13-point check was not run for the coarse
  layer (no time). The close-up stays the detailed layer inside its 60 km square, unchanged.
- **Placed on the close-up's points.** The 2 km grid is laid out so that each of its points inside the 60 km
  square is exactly one of the close-up's 500 m points. That makes the agreement check exact (below).

The terrain under every point is the 80 m mosaic (it has data to the corners of its square).
The other agent's change to `dem.py`, `demstore.py` and `terrain.py` (finer live terrain, `data/dem_live`) did not
affect this run: the scripts pin `SLIPDAY_DEM_DIR` to `data/dem`, the 80 m stack the close-up was built from, and
none of those three files was edited.

## Spacing chosen, and why

Timing test (19:18, 6 worker processes at below-normal priority, 384 points at the map's top edge): 24.7 s,
**0.36 to 0.38 s per point per process, 0.064 s per point** for the machine (6 processes). All 384 used 80 m
terrain, as the whole map does.

| spacing | points | time at 0.064 s per point | fits by about 21:15? |
|---|---|---|---|
| 1 km | 369,664 | 6.6 h | no |
| 1.5 km | 164,025 | 2.9 h | no |
| **2 km** | **92,416** | **1.6 h** | **yes, just** |
| 4 km | 23,104 | 25 min | yes |

2 km is the finest spacing that fits. The full run (started 19:19, restarted at 19:23 with one maths thread per
worker, which cut each worker's private memory from about 830 MB to about 85 MB; finished chunks were kept) ran at
0.052 s per point for the machine (0.24 to 0.49 s per point per process as the machine's load changed; 0.316 s
on average, 29,205 process-seconds in all). It **finished at 20:40**, 81 minutes after the start, well inside the
21:15 limit. 1.5 km would have needed about 2.4 h even at that faster rate, so it would not have fitted either.

Run order: first every 2nd point each way (a complete map at 4 km), then the points in between. So a run cut short
still covers the whole map, at 4 km. Results are written in chunks of 64 points as they finish
(`data/addons/fullmap/chunks_2000m/`); a re-run skips chunks already on disk.

## Coverage achieved

**Complete: 92,416 of 92,416 points (100 %), one every 2 km**, over the whole 608 km square, including all
72,583 points south of 80°S and the corners beyond it. No point lacks terrain, and every point has 80 m terrain under it.
(At 19:46, with only the first pass done, 23,424 points (the full map at 4 km) were already served and tested.)

What it shows, for the opening plan (the same with either Earth rule):

| at the point itself | points | share |
|---|---|---|
| the planned date (18 Nov 2026) does not meet the need | 88,122 | 95.4 % |
| meets it, but a 1-day slip does not | 1,791 | 1.9 % |
| survives 1 to 4 days of slip | 2,419 | 2.6 % |
| survives 5 days or more | 84 | 0.1 % |
| largest margin | 8 days | |

The Earth rule does work in the stored data (with the station rule, the usable hours differ at 2,610 points and the
number of good dates at 3), but it never changes the slip margin for this plan: sunlight is what limits it.

## Agreement with the 500 m layer where they overlap

The 2 km grid shares **900 points** (30 x 30) with the close-up's 500 m grid, at exactly the same positions
(largest difference 0.0°).

| check at the 900 shared points | result |
|---|---|
| skylines (720 values each) identical to the close-up's stored skylines | **900 of 900** (largest difference 0.000°) |
| slip margin identical to `POST /api/slipmap` (same plan), station rule | **900 of 900** |
| the same, no station rule | **900 of 900** |
| number of good dates identical (both rules) | 900 of 900 |
| verdict on the planned date identical | 900 of 900 |

So where they overlap, the coarse layer and the close-up's single-point layer give the same numbers, as they
should: same skyline code, same terrain, same evaluation.

**What the coarse layer leaves out**, measured at the same points: the close-up also offers a check at 13 touchdown
points (`POST /api/robust-map`). Of the 41 shared points where the planned date meets the need, the 13-point check
keeps the same margin at 27, gives a shorter margin at 4, and loses the margin at 10. So about 1 in 3 coloured
points would read better on the coarse layer than after the landing-scatter check. The layer's `how` and
`limits` say so in plain words.

## Endpoint and field names

Router `slipday/addons/fullmap.py` (`router`), registered in `api.py`'s optional-router loop (`"addons.fullmap"`
added to the tuple; nothing else in `api.py` changed). The server only reads the stored files; it never computes
or writes at request time.

**`GET /api/addons/fullmap`** — the layer as grids (for drawing).

Query (all optional): `earth_stations` (default `true`, the page's default), and `start`, `n_dates`,
`need_sun_h`, `need_earth_h`, `window_days`. If the plan differs from the stored one, the answer is
`{"available": false, "reason": ..., "plan": ...}`: the layer exists for the opening plan only. The front end
should pass its current plan and hide the layer outside the close-up when it gets `available: false`.

| field | meaning |
|---|---|
| `layers.slip_margin_days` | n x n values, row by row: days of slip the planned landing survives at the point; -1 = the planned date itself fails; `null` = not worked out |
| `layers.verdict` | 1 = the planned date meets the need at the point, 0 = it does not, `null` = not worked out |
| `layers.good_dates` | how many of the 60 landing dates meet the need at the point |
| `layers.terrain_m` | spacing of the terrain grid under the point (80) |
| `grid_spacing_m` (= `step_m`), `n` | 2000, 304 |
| `first_centre_km` | {x, y} of the centre of row 0, column 0, km from the pole (polar stereographic; row 0 at the top, longitude 0 up, like `/api/slipmap`). Cell (row, col): x = x0 + col * 2, y = y0 - row * 2 |
| `label`, `how`, `limits`, `layer_words`, `verdicts`, `coverage_words` | plain words for a visitor |
| `coverage` | `grid_points`, `done`, `share_done`, `complete`, `complete_at_m` (the finest spacing at which the whole map is covered), `half_spacing_lattice_done`, `points_south_of_80S(_done)`, timings |
| `plan`, `dates`, `earth_rule`, `earth_rule_words`, `counts`, `terrain`, `terrain_under_points_m` | what it was worked out for and the totals |
| `agreement_with_close_up` | the overlap check below, for the chosen Earth rule |
| `close_up` | where the detailed layer is (`POST /api/slipmap`, 60 km, 500 m) and a note to draw it on top |

**`GET /api/addons/fullmap/points`** — the worked-out points as rows. Query: `earth_stations`, a box
`x_min_km`, `x_max_km`, `y_min_km`, `y_max_km`, and `limit` (default 5,000, at most 100,000). Each row:
`lat`, `lon`, `x_km`, `y_km`, `slip_margin_days`, `verdict` ("yes" / "no" for the planned date at that point),
`good_dates`, `grid_spacing_m`, `terrain_m`. Plus `matched`, `returned`, `truncated` and the same description
fields.

**`GET /api/addons/fullmap/about`** — the description, coverage, counts for both Earth rules and the agreement,
without the arrays.

**Served and measured** on my own server (port 8171, started and stopped by PID; nothing left running; port 8100
not touched): the grid answer is 905 kB of JSON, or **28 kB gzipped** (the router gzips it itself when the browser
accepts gzip, since `api.py` has no compression), 110 ms plain and 19 ms gzipped once loaded. `/points` with no box
returns all 92,416 rows. `?start=2026-12-01` returns `available: false` with the reason.

Stored data: `data/addons/fullmap/fullmap_2000m.npz` (sha256 87efca3708a5f1d09f03677e974ecd72e3e38d65e6ddf1375b8fd65c028e540a)
and `fullmap_2000m.json` (coverage, counts, agreement, plan, terrain). The skyline chunks take 134 MB in all.

Suggested words for the page (plain): "Whole map: one point every 2 km, each checked at its own position only. In
the 60 km square round the pole, the close-up (one point every 500 m, checked at 13 touchdown points) is shown
instead."

## Files

- `slipday/addons/fullmap.py` — the router.
- `scripts/addons/build_fullmap.py` — skylines in resumable chunks (at most 6 processes, below-normal priority,
  one maths thread each, terrain memory-mapped, never copied).
- `scripts/addons/finish_fullmap.py` — the slip margin for the opening plan, the coverage and the overlap check;
  writes `data/addons/fullmap/fullmap_2000m.npz` and `fullmap_2000m.json`.
- `data/addons/fullmap/chunks_2000m/` — the skylines (int16, 720 per point) and `grid.json`; logs
  `timing.log`, `build_2000m_part1.log`, `build_2000m.log`.
- `tests/addons/test_fullmap.py` — the tests.

To finish or redo: run the two scripts again; the build skips done chunks.

## Tests

`tests/addons/test_fullmap.py`, 11 tests, all passing on the complete layer:

1. the layers cover the full grid, and the reported coverage matches the data (no assumption that it is complete);
2. the verdict follows the margin (1 exactly where the margin is 0 or more), and good dates are at least margin + 1;
3. the label names the spacing and `how` says "own position only", not the 13 touchdown points;
4. every coarse point inside the 60 km square is exactly a close-up point (900 points, same latitude);
5. stored positions match the grid formula;
6. **agreement with the real app's `POST /api/slipmap`** for the same plan, both Earth rules: margin and good
   dates identical at every shared point;
7. **three random points recomputed from the LOLA files** (`data/dem`, built in the test, fingerprint checked)
   with the close-up's skyline code (`terrain.horizon_profile`) and counting code (`scatterfield._passes`):
   margin identical for both rules;
8. `/points` rows have the promised fields, verdict words and spacing;
9. other plans are refused, not guessed;
10. the gzipped and plain answers are identical;
11. `/about`, and the router mounted in the real app.

**Full suite** (`pytest tests -q`, run once at the end, 20:43 to 20:50): **425 passed**, 1 warning (the test
client library's deprecation warning, as before), 7 min 13 s.

## Not done

- **No 13-point (landing-scatter) check on the coarse layer.** It would need 12 more skylines for each of the
  4,294 points that pass on the planned date, about 45 minutes more on this machine. Each coarse point is checked
  at its own position only, and the overlap shows this matters (10 of 41 lose their margin at 13 points).
- **One plan only** (the opening plan, both Earth rules). Other dates, needs or rules get `available: false`.
  The skylines are stored, so another plan takes about 70 s off line with `finish_fullmap.py` (after changing
  `PLAN`); it is not worked out at request time, to keep the server light.
- **2 km, not finer.** Features smaller than 2 km (crater rims, small ridges, where the light is) fall between
  points. The close-up stays the detailed layer inside its 60 km square.
- **80 m terrain, as stated.** The finer live terrain (`data/dem_live`, being added by another agent) is not used,
  on purpose, so that the layer matches the close-up exactly.
- **No front-end change** (`static/` not touched). The page still jumps to the close-up when a slip layer is
  chosen. With this endpoint, the front end can draw the whole map at 2 km on the 80°S view and the 500 m close-up on
  top inside its square.
