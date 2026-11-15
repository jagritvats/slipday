# Add-on: planner checks (`planner-1`)

Three small checks a lunar mission planner asked for. Each reuses code the entry already has; no other
computation was changed. Files:

- back end `slipday/addons/planner.py` (router `router`, registered by adding `"addons.planner"` to the
  optional-router loop in `slipday/api.py`; that is the only edit outside the new files)
- front end `static/addons/planner.js` (one container `<div id="addon-planner"></div>`)
- tests `tests/addons/test_planner.py`

## What each part does

1. **Descent lighting.** For the site and touchdown time (landing date + slip days):
   - Sun elevation and azimuth at touchdown, and its clearance above the local terrain skyline
     (`geometry.track_at`, JPL DE421, the same call the 3-D view uses).
   - Sun direction relative to an approach heading the visitor enters ("coming in from", degrees, default 0 =
     from the north). 0° = Sun straight behind the lander, 90° = beside, 180° = ahead (into the camera).
     ILLUSTRATIVE limits, no published figure was read: "behind" within 60°, "good for a descent camera" when
     within 90° of behind AND above the skyline. A 5° minimum Sun elevation is shown for reference only;
     south-pole sites do not reach it (the Sun stays within a few degrees of the horizon there), and the
     text says so.
   - Share of the landing-scatter ellipse in shadow at touchdown, per lander class: 1,500 Gaussian touchdown
     points per class (the entry's three ASSUMED classes from `robust.LANDER_CLASSES`; the long axis of the
     non-round class is laid along the approach heading, ILLUSTRATIVE). Each point is ray-cast toward the Sun
     with the 3-D view's own `view3d.cell_horizon` / `sun_from_cells` on the installed terrain stack (finest
     grid first: 5 m LOLA site model at the opening example and C1). In shadow = centre of the Sun's disc at or
     below the skyline, seen from 2 m above the ground (`observer_m`).
2. **Joint chance per lander class.** It uses the same Gaussian touchdown draws as the safe-touchdown add-on
   (`safetouch.draws()`, same seed, 20,000 per class). For each draw:
   - flat enough = the safetouch 5 m slope at that cell is 8° or less;
   - plan holds = the entry's own pass rule (`robust._passes`: sunlit hours, Earth-contact hours, Sun and Earth
     up at touchdown) at the nearest of the lander-class ring points (target + `RING_LAYOUT` + `OUTER_RINGS`,
     141 points out to 2.5 km), judged at the touchdown date.
   - Reported: plan-holds %, flat %, **both %**, the 95 % Wilson range of "both", and the product you would get
     if the two were independent (for comparison). Only where a 5 m LOLA site model covers the spread, as for
     safetouch; elsewhere it says why.
3. **Alternatives at the slipped date.** The 14 curated "South pole" sites and the 18 scatter-checked map
   candidates (`windows.map_candidates()`) are judged with the entry's own `robust.mission_card` (13-point
   "how sure" check, default need) at the slipped landing date itself, followed for 15 days (as the existing
   window-options check does). The plan's own site is left out. Ranking: clear yes first, then not sure, then
   no; within each, the longest slip margin, then the most touchdown points passing, then the most sunlit hours.

## Endpoints (all GET)

| Path | Parameters | Main fields |
|---|---|---|
| `/api/addons/planner/lighting` | `id` or `lat`+`lon`, `name`, `landing` (default 2026-11-18T00:00:00Z), `slip_days` (0-120), `heading_from_deg` (0-360, default 0), `observer_m` (default 2), `shadow` (default true) | `touchdown_utc`, `sun{az_deg, el_deg, clear_of_skyline_deg, above_skyline, disc_fraction}`, `approach{from_deg, sun_from_behind_deg, sun_side: behind/beside/ahead, illustrative}`, `camera{good, max_from_behind_deg, behind_within_deg, min_el_deg, meets_min_el, illustrative}`, `text`, `shadow{classes[{id,label,in_shadow_pct,in_shadow_count,points,grid_m}], terrain, observer_m, rule}`, `assumptions` |
| `/api/addons/planner/joint` | `id` or `lat`+`lon`, `name`, `landing`, `slip_days`, `need_sun_h` (240), `need_earth_h` (100), `window_days` (14) | `available` (or `reason`), `touchdown_utc`, `grid`, `plan_points`, `plan_points_passing`, `classes[{id,label,plan_holds_pct,flat_pct,joint_pct,joint_count,joint_range,if_independent_pct,draws_used,median_distance_to_plan_point_m}]`, `how` |
| `/api/addons/planner/alternatives` | `landing`, `slip_days`, the plan's site (`id` or `lat`+`lon`, left out of the list), `need_sun_h`, `need_earth_h`, `window_days`, `scatter_m` (100) | `touchdown_utc`, `sites_checked`, `sites_yes`, `rank_rule`, `rows[{rank,name,kind: curated/map,lat,lon,verdict,slip_margin_days (-1 = not a yes on the day itself),points_passing,points,sunlit_h,earth_h,grid_m,why}]` |
| `/api/addons/planner/about` | none | assumptions and limits |

Lighting takes about 1 s. Joint takes under 1 s with warm skylines and about 40 s cold. Alternatives take 10 to 20 s
with warm skylines and about 2 min cold; answers are cached (16 entries).

## Where the container should go

- Put `<div id="addon-planner"></div>` in the **"How sure"** step of the decision path, just after the lander-class
  chances. The joint chance and the shadowed share answer "how sure" per lander. Then add
  `<script src="/static/addons/planner.js"></script>` after `/static/app.js`.
- The alternatives table belongs to **"What to do"**. If the page wants it there, the simplest option is to place the
  container in "What to do" instead: the module draws all three cards in one container. It cannot be split
  without editing the module.
- The module watches the page's own `/api/mission` answers (cloned, never changed) to follow the site and
  landing on the card. Until then it shows the opening example. It has its own inputs for approach heading and
  slip days. It is styled with `--text --muted --line --surface --accent --ok-bg --ok-ink` and works at phone
  width (tables scroll sideways inside their card).

## Results (measured 15 Nov 2026, app's own terrain stack, landing 18 Nov 2026 00:00 UTC, default need)

**Opening example (89.010 S, 122.764 E)**, 5 m LOLA site model under the site:
- Sun 2.25° up, azimuth 315.1°, 0.99° clear of the skyline. Coming in from the north it is 45° from straight
  behind: "behind", so good under the illustrative rule. It is below the illustrative 5°.
- Landing spread in shadow: precision 0.0 %, CLPS-class 18.8 %, unguided 27.1 %.
- Joint (plan holds / flat / both / if independent): precision 100.0 / 100.0 / **100.0** (99.9-100.0) / 100.0;
  CLPS-class 79.0 / 93.7 / **73.0** (72.3-73.6) / 74.0; unguided 73.7 / 82.9 / **59.6** (58.9-60.2) / 61.2.
  88 of 141 plan points pass.
- At a 10-day slip (28 Nov) the Sun is 0.53° up, azimuth 193.7°, ahead of a north approach. Plan holds is 0 %
  for every class because the site itself is a "no" that day, so joint = 0 %.
- Alternatives at a 3-day slip (21 Nov): 19 of 30 sites are a clear yes. Top: map point 89.005 S, 124.875 E
  (yes, margin 5 d), C1 (yes, 4 d), map point 89.019 S, 125.426 E (yes, 4 d), Malapert summit (yes, 2 d),
  map point 88.849 S, 121.527 E (yes, 2 d).
- Alternatives at a 10-day slip (28 Nov): 0 of 30 are a clear yes. Malapert summit is "not sure" (2 of 13 points,
  214 of 240 sunlit hours); all others are "no", mostly on Earth-contact hours.

**C1, Shackleton connecting ridge (89.4398 S, 137.17 W)**, 5 m LOLA site model:
- Sun 1.09° up, azimuth 215.1°, 2.88° clear of the skyline. Coming in from the north it is 145° from behind:
  "ahead", so poor under the illustrative rule.
- Landing spread in shadow: precision 0.3 %, CLPS-class 47.3 %, unguided 55.9 %.
- Joint: precision 99.1 / 99.9 / **99.1** (98.9-99.2) / 99.1; CLPS-class 28.7 / 80.7 / **28.2** (27.6-28.8) / 23.1;
  unguided 14.9 / 50.8 / **12.6** (12.1-13.0) / 7.6. 34 of 141 plan points pass.
  The two are not independent here: where the plan holds, the ground is flatter than average, so "both" is
  above the product.
- Alternatives at a 10-day slip (C1 left out): 0 of 31 are a clear yes. Top is Malapert summit, "not sure".

## Tests

`tests/addons/test_planner.py` has 10 tests: the relative-angle maths; lighting at the opening example (the Sun
near the horizon, shadow shares in 0-100 % that grow with the spread); a heading changes only the relative
angle; a slip moves the touchdown; joint ≤ min(plan, flat) and ≥ plan + flat − 100 at the opening example and
C1; joint refused off the 5 m grids (IM-1); 422/404 validation; lighting by site id; alternatives ranked by
verdict with the plan's own site left out. Module run: 10 passed (about 3 min cold; the alternatives test is
about 2 min of that, and `PLANNER_FAST=1` skips it).

Full suite, run once at the end (`.venv\Scripts\python.exe -m pytest tests`): **435 passed, 0 failed** in 8 min 13 s.
A live check on port 8143 (stopped afterwards) found the router registered through `api.py`: the opening example's
lighting and C1's joint chance matched the figures below, and `/static/addons/planner.js` was served (it passes
`node --check`).

## What is not done

- No published descent-camera Sun limits were found and read; the 60°/90°/5° limits are illustrative.
- The approach heading is entered by the visitor; no real trajectory is modelled. The shadow ellipse lays the
  unguided class's long axis along that heading; the joint chance uses safetouch's 12 directions instead.
- "Plan holds" for a draw comes from the nearest of 141 ring points (median 17 to 87 m away), not from a skyline
  at the draw itself. The 95 % range covers sampling only, not this nearest-point step.
- Shadow points use the 3-D view's coarser far-ray step (`STEP_FRAC` 0.01), not the site-skyline step. The terrain
  under the shadow points is the installed stack. In the test run that stack may be 80 m only, so the module
  test checks consistency, not the 5 m figures above.
- The joint chance is judged at the touchdown date only (no per-day slip curve).
- Alternatives use the default need unless passed. They do not include the page's own comparison sites or the
  Artemis regions, and do not run the ±72 h best-hour search.
- Not placed in `index.html` (by instruction); no browser check of the page with the container in place.
