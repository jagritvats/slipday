# Add-on: "What we found" (science panel)

Every number below was worked out again by `scripts/addons/build_findings.py` (127 s on this machine) from Slipday's
stored data and its own code. None was copied from the other documents. The output is
`data/addons/findings/findings.json`.

## Wiring

- Endpoint: `GET /api/addons/findings`, served by the router in `slipday/addons/findings.py` (`router`). The
  orchestrator needs to register it: `app.include_router(findings.router)`. If the JSON file is missing, the endpoint
  returns `{"available": false, "reason": ...}`.
- Front end: `static/addons/findings.js`. Put `<div id="addon-findings"></div>` on the page and load the script. It
  draws plain SVG charts (no libraries, no CDN), takes its colours from the page's CSS variables (`--text`, `--crit`,
  `--accent`, `--sun`, `--earth`, ...), and redraws when the light/dark theme changes. Each finding has a headline
  sentence, its charts, a table of numbers and its caveats.
- Tests: `tests/addons/test_findings.py` (8 tests, all pass). They compare the results with the earlier stored
  20 m run and the region calendar, and recount the best region straight from the atlas flags.
- Rebuild: `.venv\Scripts\python scripts\addons\build_findings.py` (add `--no-ridge` to skip the ridge runs).

## Finding 1: coarse terrain is optimistic, not noisy

- **20 m check, 14 weekly start dates from 18 Nov 2026.** Recounted with `slipday.finer20.cells` on the stored 20 m
  skylines. The rule is the page default: 240 sunlit hours and 100 hours of Earth contact in 14 days, with a ground
  station required and 13 touchdown points.
  - 3,376 points were re-checked, and 2,922 agree (86.6 %).
  - Of the **454** disagreements, **452** are "landable on 80 m, rejected on 20 m" and 2 are the other way
    (one on 23 Dec, one on 10 Feb).
  - Only 7 of the 14 dates have any point that passes.
  - Every date matches the stored `finer_map_dates.json`. The documents' figures are confirmed.
- **Map:** a polar view of every re-checked point, with each disagreement marked by direction
  (`map_points`, in km from the pole).
- **Shackleton ridge C1, longest darkness** (365 days from 18 Nov 2026, any part of the Sun's disc counts as light,
  computed with `span_stats`):
  - **194 h on 80 m** and **110 h on 20 m**, against **112 h** published. This confirms the documents.
  - New: the 5 m site model gives 111 h.
  - The 112 h is the literature value we check against, so it was not recomputed.
- **5 m terrain covers only two sites:** Site07 (the peak near Shackleton) and Site01 (the connecting ridge), read
  from `data/dem_live/dems.json`.

## Finding 2: how many NASA landing regions must stay open

The data are the 78 published sites in the atlas flags. For each number of regions, every combination was tried to
find the best set. Shares are of landing times every 6 hours.

| Coverage by the best 1 / 2 / 3 / 9 regions | 2027 to 2030 | 2027 to 2035 |
|---|---|---|
| With the Earth need (100 h, **illustrative**) | 26.0 / 34.8 / 37.0 / 39.9 % | 25.2 / 33.7 / 35.9 / 38.9 % |
| Sunlight only | 44.8 / 73.0 / 89.4 / 91.1 % | 44.5 / 72.9 / 89.0 / 90.9 % |

- The best three regions are Peak near Cabeus B, Nobile Rim 1 and Slater Plain.
- With sunlight only, 5 regions reach the ceiling.
- For 2027 to 2030 the figures match `region_availability.json` exactly. The documents round them to 26 / 37 / 40 %
  and 45 / 89 / 91 %.
- The chart is a coverage curve for 1 to 9 regions, both variants, with solid lines for 2027 to 2030 and dashed
  lines for 2027 to 2035.

## Checks (shown as validation, not as findings)

- **Season drift.** A sine wave fitted to Slipday's own daily sub-solar latitude over 2025 to 2035 gives a period of
  346.65 days, so the season comes **18.6 days earlier each year**. Expected: 18.63 days (365.25 minus the eclipse
  year).
  - A straight line through each year's lowest-Sun date gives 18.4 days for 2025 to 2032, which matches the
    documents' 18.4.
  - The same straight line over 2025 to 2035 gives 19.15 days. **This differs:** the yearly date wobbles by a few
    days, so this method depends on which years are used. The panel says so and leads with the sine fit.
- **LOLA team's Earth-visibility maps.** The published values were read from the map files in `data/reference` at
  the 200 stored points per map, using the "any part of the Earth's disc" rule.
  - 60 m map: 0.97 points mean difference, correlation 0.9946.
  - 120 m map: 0.69 points mean difference, correlation 0.9984.
  - These are the same as the documents.
- **JPL Horizons.** Six stored tables (Sun and Earth at IM-1, Blue Ghost 1 and Chandrayaan-3), 218 rows in all. The
  largest difference is 1.3e-5 degrees in elevation and in azimuth.
  - The documents' "0.0006 degrees" is a different check (ground-station geometry) and was not recomputed here.

## Limits

- The 20 m map check covers only the 2,407 map points with stored 20 m skylines, under one mission rule.
- The 100-hour Earth need is illustrative, and it is what keeps the region ceiling near 40 %.
- The polar map's frame is set by the points that were re-checked; it is not the full map.
