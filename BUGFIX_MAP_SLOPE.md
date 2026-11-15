# Map and slope bugs: causes, evidence, fixes

Debug pass, Sunday 15 November 2026. Own server on port 8195 (stopped afterwards, by PID). Headless Chrome
(puppeteer-core from the npx cache, scratch scripts only, not shipped) drove the real page on that server.
The participant's copy on port 8100 was not touched. Nothing under `static/` was edited.

Short version:

| # | what the participant saw | cause | where the fix goes |
|---|---|---|---|
| 1 | choosing "days of slip..." changes the map area by itself | **deliberate**: the slip-margin layers exist only for the 60 km square round the pole, so the page jumps to **Close-up of the pole**. The page never says why. **Plus a real bug:** the page's first-visit switch is never written to the address, so a reload (or a link copied then) comes back on **"South pole to 80°S" with no layer**. | front end (`static/app.js`): say it; save the address |
| 2 | "too steep at all 13 points" wherever they click | **front-end bug** in `static/addons/safety.js`: after a click the slope line keeps showing the **previous site's** answer (often IM-1: "Too steep at 13 of 13, steepest 14.8°") until the new site's mission card arrives, and for ever if that request fails or is busy. The line does not name its site, so it looks like the clicked point's answer. The server's slopes are right (checked against my own slope code). Also real: much of the close-up is steep. | front end (`static/addons/safety.js`) |
| 3 | wants a slope guide or filter on the map | the existing `POST /api/addons/safety/map-layer` already returns the steepest slope of the 13 points for 2,407 map points, and a combined "slip-tolerant and flat enough" filter that the page already offers behind a checkbox | front end first (no server change); a new endpoint only if full coverage is wanted |

**Back end: no bug found, nothing changed.** One regression test was added (below).

---

## Bug 1. The map area changes when "days of slip the planned landing survives" is chosen

### What happens (reproduced in headless Chrome on port 8195)

| step | Map area afterwards | Colour the map by |
|---|---|---|
| page opens (first visit) | Close-up of the pole | days of slip... |
| choose "South pole to 80°S" | South pole to 80°S | days of slip... |
| choose "nothing (shaded relief)" | South pole to 80°S | nothing |
| choose "days of slip..." | **Close-up of the pole** (switched by the page) | days of slip... |
| choose "South pole to 80°S" again, layer still on | South pole to 80°S (allowed) | days of slip... |
| choose "sunlit hours on the worst landing date" | **Close-up of the pole** (switched again) | worst sunlit hours |

So choosing a slip layer switches the map **to the close-up**. Within one page visit, no order of menu choices
made it switch to "South pole to 80°S" by itself; the only such path is a reload (next section). The same code is
in `_static_before_overhaul/app.js` (line 2498), so the overhaul did not introduce either behaviour.

### Cause: a deliberate limit, not a bug

`static/app.js`, the `mapLayer` change handler (line 2534 to 2538):

```js
if (SLIP_LAYERS[state.layer] && state.zoom !== 'pole') { state.zoom = 'pole'; $('mapZoom').value = 'pole'; loadMap(); }
```

The five slip-margin layers (`SLIP_LAYERS`: days of slip, good dates, sunlit hours, usable hours) come from
`/api/slipmap`, which is worked out on one grid only: 120 x 120 points, one every 500 m, **60 km across round the
pole** (`/api/map` reports `slip_field: n 120, half_km 30, step_m 500`). The "South pole to 80°S" view is 608 km
across, so the layer there is a 60 km square in the middle, about a tenth of the map's width. The page jumps to the
close-up so the layer can be seen. That is reasonable, but the page says nothing about it, and it lets the user go
back to the 80°S view with the layer on, where the tiny square is easy to miss.

### A real bug next to it: the page drops back to "South pole to 80°S" on reload

This is the one path I found where the map goes to "South pole to 80°S" without the user choosing it, and it is
probably what the participant saw. On first visit the page itself sets the layer to "days of slip" and the area to
the close-up (`app.js` line 439, in `loadMap()`), but does not call `saveHash()`. The address bar keeps
`...&z=&l=` while the page shows the close-up with the layer. Reproduced in headless Chrome:

| step | Map area | Colour the map by | address ends |
|---|---|---|---|
| first visit | Close-up of the pole | days of slip... | `z=&l=` |
| reload (F5), or open a link copied now | **South pole to 80°S** | **nothing** | `z=&l=` |
| choose "days of slip..." | Close-up of the pole (switched by the page) | days of slip... | `z=pole&l=margin` |

So after any reload, or from a link copied before the first change, the map comes back on the 80°S view with no
layer; choosing the layer then jumps to the close-up. That looks like the area changing by itself. Cause: the
missing `saveHash()` (and `applyHash()` at line 2074 only ever sets the close-up, never the 80°S view, so the
hash's empty `z=` is read as "leave the default", which is 80°S).

### Front-end fix (for the front-end owner; `static/app.js`)

1. **Say it in the menu.** In `loadMap()`, where the slip layers are added to `#mapLayer` (line 440), add
   "(close-up only)" to each label:

   ```js
   Object.keys(SLIP_LAYERS).forEach(function (k) { html += '<option value="' + k + '">' + esc(SLIP_LAYERS[k].label) + ' (close-up only)</option>'; });
   ```

2. **Say it when the page switches.** In the `mapLayer` change handler, remember that the page moved the map:

   ```js
   if (SLIP_LAYERS[state.layer] && state.zoom !== 'pole') { state.zoom = 'pole'; $('mapZoom').value = 'pole'; state.zoomMoved = true; loadMap(); }
   ```

   and in `renderPolar()`, at the start of the note (`var note = ...`, line 411), add one sentence when
   `state.zoomMoved && slipLayer`:

   > "The map moved to the close-up because this layer is worked out only for the 60 km square around the pole,
   > one point every 500 m."

   Clear `state.zoomMoved` in the `mapZoom` change handler (the user chose an area).

3. **Say it on the 80°S view.** In `renderPolar()`, when `slipLayer && sm && sm.available && half > 2 * sm.half_km`
   (a slip layer on the 80°S view), add to the legend:

   > "This layer covers only the small square in the middle (60 km across). Choose Close-up of the pole to see it."

4. **Fix the reload bug:** in `loadMap()`, line 439, save the address after the page's own switch:

   ```js
   if (state.firstVisit && !state.layer) { state.layer = 'margin'; state.zoom = 'pole'; $('mapZoom').value = 'pole'; saveHash(); }
   ```

   (`saveHash()` returns early if `state.lastCfg` is not set yet; if so, call it again in `loadMissions()` once
   the first card arrives, which already calls `emitUpdate()`. A reload must then come back on the close-up with
   "days of slip" on.)

---

## Bug 2. "Too steep at all 13 touchdown points" for every clicked point

### Step 1: is the server's slope right for clicked points? Yes.

I copied the page's click maths (`renderPolar().where()` in `app.js`: click in km, snapped to the 500 m cell when a
slip layer is on, then inverse polar stereographic) into a script, made 10 clicks across the close-up, sent each
to `GET /api/addons/safety/site?lat=&lon=&scatter_m=100` on port 8195, and measured the same 13 points with my
own code: my own reader of the `.npy` files and `dems.json`, my own projection, my own 13 points (great-circle steps
from the layout in `robust.SCATTER_LAYOUT`), and a different slope method (central differences of a bilinear
surface over 10 m on 5 m terrain, 20 m on 20 m terrain, instead of the add-on's plane fit).

| click (km: right, up) | lat, lon | grid | points under 8° (app) | steepest: app / mine | flattest: app / mine |
|---|---|---|---|---|---|
| -20, 15 | 89.1871 S, 53.246 W | 20 m | 5 of 13 | 10.7 / 11.1 | 5.6 / 6.3 |
| 5, -8 | 89.6775 S, 147.529 E | 20 m | 0 of 13 | 22.4 / 21.8 | 12.0 / 10.5 |
| 12, 12 | 89.4402 S, 46.193 E | 20 m | 8 of 13 | 10.6 / 10.4 | 3.4 / 3.6 |
| -3, -22 | 89.2607 S, 172.954 W | 20 m | **13 of 13** | 7.1 / 7.2 | 3.2 / 4.0 |
| 25, -5 | 89.1495 S, 101.746 E | 20 m | **13 of 13** | 6.4 / 6.0 | 3.5 / 3.5 |
| -10, -10 | 89.5335 S, 136.432 W | 5 m | 0 of 13 | 24.4 / 25.6 | 13.9 / 13.6 |
| 2, 2 | 89.906 S, 52.125 E | 20 m | 2 of 13 | 26.5 / 25.9 | 1.3 / 0.5 |
| -27, 27 | 88.7525 S, 45.0 W | 20 m | 11 of 13 | 8.7 / 8.2 | 3.3 / 2.5 |
| 18, -24 | 88.9991 S, 143.036 E | 20 m | 1 of 13 | 14.5 / 15.2 | 4.8 / 9.0 |
| 0.4, -6.5 | 89.7772 S, 177.879 E | 20 m | 0 of 13 | 34.8 / 34.7 | 30.7 / 30.7 |

Over all 130 points: median difference 0.36°, 90 % within 1.12°, largest 5.4° (one point on very rough ground,
where the two methods sample slightly different cells), correlation 0.995; pass or fail agrees at 122 of 130
(the other 8 are within about 1° of 8°). The 13 point positions agree with mine exactly (to 5 decimals).

Each suspected cause, checked:

| suspect | finding |
|---|---|
| wrong grid (80 m instead of 20 or 5 m) | no: every clicked point in the close-up uses 20 m, or 5 m on the two site models. The 20 m crop reaches about 88.4 S, beyond the close-up's corners (42 km from the pole). Over all 14,400 close-up cells, the 13 points use 5 m (19,968 points) or 20 m (167,232), never 80 m. |
| units (radians against degrees, metres against pixels) | no: the plane fit divides by the cell size in metres and returns degrees; it reads a tilted test plane back within 0.05° (`test_safety.py`), and agrees with my independent code (table above). |
| touchdown pattern in the wrong projection | no: the card's 13 points match my own great-circle points exactly; the map layer's stored points match the card's layout within 0.3 m (all 2,407 stored map points sampled). |
| sign or index error | no: x0/y0 in `dems.json` are cell centres and the code treats them so (`dem.py`); rows and columns agree with my reader. |
| wrong threshold | no: `LIMIT_DEG = 8.0`, `GOAL_DEG = 5.0`, pass is `slope <= 8`. |
| map click coordinates passed wrongly | no: the request carries the clicked lat/lon (seen in Chrome: e.g. `GET /api/addons/safety/site?lat=-89.277&lon=-172.794&scatter_m=100`). The close-up picture is drawn in the same frame as the click maths: its brightness correlates with the elevation gradient of the 80 m grid at +0.58 as drawn, and at -0.16 to +0.16 when flipped or transposed. |
| opening example | 4.9° at the steepest of 13 points, 5 m terrain over 10 m, flat enough at all 13. Unchanged. |

### Step 2: the cause: the slope line shows the previous site's answer

`static/addons/safety.js` does not ask for the slope of the selected site directly. It waits for the page's
`/api/mission` answer for that site, finds it by name (`currentMission()`), and only then asks the slope. In
`updateCard()`:

```js
var m = currentMission();
if (!m) { if (!cardData) { ui.card.innerHTML = '...Waiting for the site card…'; } return; }
```

When the newly clicked site's mission answer has not arrived, `m` is null, `cardData` still holds **the previous
site's answer**, and the line is left as it was. The line never shows the site's name, so the old answer reads as
the clicked point's. It stays until the mission answer arrives; if that request fails, or the server says it is busy
(the page retries up to 6 times), it stays for good.

Reproduced in headless Chrome (port 8195; the clicked site's `/api/mission` held back 6 s, as on a busy server):

| time after the click | site menu says | slope line says |
|---|---|---|
| before (IM-1 selected) | IM-1 Odysseus (Malapert A) | No. Too steep at 13 of 13 touchdown points: the steepest is 14.8° |
| 1 s to 6 s | Map pick 89.277 S, 172.794 W | **No. Too steep at 13 of 13 touchdown points: the steepest is 14.8°** (IM-1's answer) |
| 7 s on | Map pick 89.277 S, 172.794 W | Yes. Flat enough at all 13 touchdown points: the steepest is 5.05° (the real answer) |

IM-1 is the only default site that is too steep at all 13 points (14.8°, true: it tipped over). A click on the
map replaces site 4, which is IM-1 by default, so a user who looked at IM-1 and then clicked the map sees "too steep
at all 13" for every click, at least for as long as the mission card takes. On a loaded server (the participant's,
with other visitors or agents asking for skylines) that can be a long time, or for ever.

### Step 3: what is real: the close-up is mostly steep

This is not hiding a result: much of the ground near the pole really is too steep. Every one of the 14,400
clickable cells of the close-up (60 km square, one per 500 m), with the server's own slope function, 100 m
scatter:

| cells | count | all 13 under 8° | all 13 too steep | median of the steepest of 13 |
|---|---|---|---|---|
| every clickable cell | 14,400 | 2,108 (14.6 %) | 6,146 (42.7 %) | 14.3° |
| coloured on "days of slip" (planned date 18 Nov 2026 meets the default need) | 733 | 98 (13.4 %) | 291 (39.7 %) | 14.2° |
| 1 day of slip or more at that single point | 462 | 66 (14.3 %) | 184 (39.8 %) | 14.4° |

So about 2 clicks in 5 really are too steep at all 13 points, and only about 1 in 7 is flat enough at all 13. Points
with the most light are on ridges and crater rims, so clicking the coloured cells does not help. The close-up is
on 20 m terrain (slope over 20 m, wider than a lander), and 5 m in two small squares; this smooths slopes, so if
anything the real ground is steeper. No clicked point on the close-up uses 80 m terrain. (Clicks on the 80°S view
outside about 88.4 S do use 80 m terrain; the line already says "80 m terrain" there.)

### Front-end fix (for the front-end owner; `static/addons/safety.js`)

1. **Ask for the selected site directly, not through the mission answer.** The page exposes the selected sites
   (`window.SlipdayApp.selected()`, `.current()`, `.cfg()` in `app.js` line 2294). Add a `currentSite()` and use
   it in `updateCard()`; keep the mission answer only for a widened scatter:

   ```js
   function currentSite() {
     var A = window.SlipdayApp, s = A && A.selected ? A.selected()[A.current()] : null;
     if (s && isFinite(s.lat) && isFinite(s.lon)) {
       var m = currentMission(), c = A.cfg ? A.cfg() : null;
       var sc = (m && m.resp.site.name === s.name && m.resp.sure && m.resp.sure.points > 1) ? m.resp.sure.scatter_m : ((c && c.scatter) || 100);
       return { name: s.name, lat: s.lat, lon: s.lon, sc: sc };
     }
     var mm = currentMission();
     if (!mm) { return null; }
     return { name: mm.resp.site.name, lat: mm.resp.site.lat, lon: mm.resp.site.lon,
              sc: (mm.resp.sure && mm.resp.sure.points > 1) ? mm.resp.sure.scatter_m : ((mm.body && mm.body.scatter_m) || 100) };
   }
   ```

   and in `updateCard()` replace the first lines with:

   ```js
   var s = currentSite();
   if (!s) { cardKey = ''; cardData = null; ui.card.innerHTML = '<p class="sdS-sub">Flat enough to land? Waiting for the site card…</p>'; return; }
   var key = s.lat + ',' + s.lon + ',' + s.sc;
   ```

   (and use `s.name`, `s.lat`, `s.lon`, `s.sc` in the request). Also listen for the page's own
   `slipday:update` event (`document.addEventListener('slipday:update', updateCard)`), which `app.js` fires after
   each change, so the line follows a click at once.

2. **Never leave an old answer up.** Whatever the source, when the key changes, the line must first say
   "Measuring the slope at 13 touchdown points…" (it already does this when it does ask), and the "no mission
   yet" branch must not return with the previous card on screen (the `if (!cardData)` guard is the bug).

3. **Name the site in the line,** so a mix-up can be seen: in `renderCard()`, after "Flat enough to land?", add
   `' <span class="sdS-sub">(' + esc(r.site.name) + ')</span>'`.

4. **Say what is true near the pole.** When the verdict is "steep" and the grid is 20 m, add one plain sentence
   under the headline: "Much of the ground near the pole is too steep: about 2 in 5 points on the close-up are too
   steep at all 13 touchdown points, and only about 1 in 7 is flat enough at all 13." When a point uses 80 m terrain,
   keep the existing words and add: "80 m terrain is too coarse to judge slope at lander scale; treat this as a
   rough guide."

---

## Item 3. A slope guide or filter on the map

### What the existing map-layer endpoint offers

`POST /api/addons/safety/map-layer`, body: the same JSON the page sends to `/api/robust-map`, plus optional
`min_slip_days` (default 1). Measured on port 8195 for the page's default plan (18 Nov 2026, 60 dates): 3.3 s.

It returns, for each of the 120 x 120 cells of the close-up (500 m apart):

- `layer`: 2 = slip-tolerant and flat enough, 1 = slip-tolerant but too steep, 0 = not slip-tolerant, -1 = the
  planned date already fails here, -2 = not checked. Default plan: 48 / 295 / 390 / 13,667 / 0.
- `steepest_deg`: the steepest of the cell's 13 touchdown points (100 m scatter, finest grid: 5 m over 10 m or
  20 m over 20 m), **for the 2,407 map points whose extra touchdown points are stored** (17 % of the cells:
  those that pass on at least one landing date from 14 Nov 2026 to 16 Jan 2027 for the default need); `null`
  elsewhere. Of the 2,407: 48 at 5° or less, 236 between 5° and 8°, 2,123 over 8°.
- `limit_deg` (8), `grids_used`, `counts`, `summary`, `source`, `limits`. (`goal_deg`, 5, is in
  `GET /api/addons/safety/about`, not here.)

The page already exposes the **filter** half: `static/addons/safety.js` mounts a checkbox under the map legend,
"Flat enough to land? Show the slope layer on the map", which draws codes 2/1/0. It only works once "days of slip"
is chosen and the scatter check has loaded, and it mixes slip and slope in one colour scheme.

### Smallest correct design (front end only, no server change)

Add a second choice next to the existing checkbox in `safety.js`, drawn from the same response:

- control: a two-way choice under "Flat enough to land?": **"slip and slope together"** (today's layer) and
  **"slope only"** (new);
- "slope only" colours each cell by `steepest_deg`, the steepest of its 13 touchdown points:

| colour | rule | legend words |
|---|---|---|
| green `#1b7837`, filled | `steepest_deg <= 5` | **Flat**: all 13 touchdown points are 5° or less (NASA's goal) |
| amber `#e8a33d`, filled | `5 < steepest_deg <= 8` | **Flat enough**: the steepest of the 13 is between 5° and 8° (under NASA's 8° limit) |
| red `#d03b3b` with a white diagonal stripe (so it does not rely on colour alone) | `steepest_deg > 8` | **Too steep**: at least one of the 13 is over 8° |
| no fill | `steepest_deg === null` | not drawn: "Slope is shown only where the page has stored the 13 touchdown points (2,407 of 14,400 points: those that can meet the default need at some date this season)." |

- legend footer, plain words: "Slope over 10 m on 5 m terrain (two squares near Shackleton) and over 20 m on 20 m
  terrain elsewhere; 20 m is wider than a lander, so it can read low. No boulders or small craters are shown. One
  point every 500 m; a flat patch smaller than that can be missed."
- hover (already in `describe()`): "Steepest of its 13 touchdown points: 6.3°".
- the same thresholds as the site card (`<= 8` passes, `<= 5` meets the goal), read from the response
  (`limit_deg`) and from `/about` (`goal_deg`), not typed again.

This needs no change on the server and shows only numbers the server already computes and tests.

### Built afterwards, at the coordinator's request: `GET /api/addons/slopemap`

`slipday/addons/slopemap.py` (new router), registered in `api.py`'s optional-router loop (`"addons.slopemap"`
added to the tuple; nothing else in `api.py` changed). `dem.py`, `demstore.py`, `terrain.py` were not touched;
`safety.py` was not changed (the new module calls its `slope_finest`, `grids`, limits and texts).

- **Points:** every point of the slip-margin map, 120 x 120 = **14,400**, one every 500 m, 60 km across: the same
  points and the same order as `/api/slipmap`'s layers (read from `data/field/pole_points.npz`; a test checks
  that point `i = row * 120 + col` is the centre of the page's cell, within 1 m).
- **Slope:** at the card's 13 touchdown points of each map point (`robust.scatter_points`, 100 m), each on the
  finest grid that covers it, 5 m (over 10 m), then 20 m (over 20 m), then 80 m (over 80 m), by
  `safety.slope_finest`: exactly the card's numbers (test: 25 random points, steepest within 0.01°, the same
  passing count and grids).
- **Stored:** `python -m slipday.addons.slopemap` writes `data/addons/safety/slopemap.npz` (sha256
  d1f06acacc51c760f2d226b7006ed39651020a6f967bdcb3856d3374658a2a01) and `slopemap.json` (an inputs key from the
  map points, the grids on disk, the scatter, the limits and a version). Build time 1 s. If the stored file is
  missing or its key does not match (for example after the terrain changes), the server works it out on first
  request and keeps it in memory; it never writes at run time. Served from the stored file: 1.2 s for the first
  request including start-up, 396 kB of JSON.

Fields (arrays have 14,400 entries, row by row, row 0 at the top):

| field | meaning |
|---|---|
| `class` | 2 flat (all 13 at 5° or less), 1 flat enough (all 13 at 8° or less), 0 too steep (one or more over 8°), -1 not known (off every grid) |
| `steepest_deg` | steepest of the 13 touchdown points (0.01°) |
| `target_deg` | slope at the map point itself |
| `points_passing`, `points_meeting_goal` | how many of the 13 are at 8° or less, at 5° or less |
| `grid_m` | grid under the map point itself (5, 20 or 80) |
| `coarsest_grid_m` | coarsest grid used among its 13 points |
| also | `available`, `stored`, `n`, `half_km`, `step_m`, `points`, `points_known`, `order`, `scatter_m`, `limit_deg`, `goal_deg`, `classes`, `counts`, `points_by_coarsest_grid_m`, `grids`, `summary`, `how`, `source`, `limits` |

**Coverage and result (15 Nov 2026):** all 14,400 points known. Grid: all 13 points on 5 m at 1,536 map points,
20 m (with 5 m at some points) at 12,864, 80 m at none (the close-up is inside the 20 m crop; the 80 m fallback
is tested at 85° S, and "not known" at 70° S). Classes: **457 flat, 1,677 flat enough, 12,266 too steep**.

Against the existing map layer, at its 2,407 stored points: median difference 0.003°, 2,355 within 0.011°, pass or
fail differs at 3 points. The rest differ because the stored touchdown points (in `data/scatterfield`) sit up
to about 0.3 m from `robust.scatter_points`, which on rough ground can move a point into the next 2 x 2 cells.
The new endpoint matches the site card; the old layer's numbers were left unchanged.

Tests: `tests/addons/test_slopemap.py` (8 tests: coverage, page order, class rule, agreement with the card and with
the old layer, stored file equals a fresh run, 80 m fallback and "not known", mounted in the real app).

### The design note written before it was built

The existing response covers only stored points and needs a slip-map run. A guide for the whole close-up, any
date, would be one small read-only endpoint in `slipday/addons/safety.py`:

- `GET /api/addons/safety/slope-map` returning `{n: 120, half_km: 30, step_m: 500, limit_deg: 8, goal_deg: 5,
  steepest_deg: [14,400 values], grids_used, limits}`: the steepest of the 13 touchdown points at every cell,
  using the same `robust.scatter_points` and `slope_finest` as the card; date-independent, computed once and
  cached (the per-cell figures in Bug 2, step 3 were made exactly this way in one pass).
- The page draws it with the colours above, available on the close-up only, the same note as Bug 1.

(Built as above, at `/api/addons/slopemap` rather than `/api/addons/safety/slope-map`, as a separate router.) For
the page, the "slope only" colours and legend above apply unchanged, but use `class` from this endpoint, which
covers all 14,400 points, so the "not drawn" row is needed only for class -1.

---

## Back end: what changed, and tests

- **No back-end bug fix was needed.** `safety.py`, `safetouch.py` and `scatterfield.py` were checked and are
  correct for clicked points (evidence above); none was changed.
- **Added afterwards (feature, on request):** `slipday/addons/slopemap.py`, its stored data in
  `data/addons/safety/`, one entry in `api.py`'s optional-router loop, and `tests/addons/test_slopemap.py`. No
  existing number changed.
- **Added** `tests/addons/test_map_slope_clicks.py` (3 tests): the page's click maths (copied) feeds the server's
  slope, which must agree with an independent slope from the LOLA files (median difference under 0.6°, 90 %
  under 1.6°, correlation over 0.98, same grid chosen at every point); the close-up uses 5 m and 20 m only; and
  some clicked points are flat enough at all 13 while others are too steep at all 13.
- Results: `tests/addons/test_map_slope_clicks.py`, `test_safety.py` and `test_safetouch.py` together:
  **61 passed** (1 warning from the test client's library). Full suite: see the line below.

Full suite (`pytest tests -q`, with the new file): **388 passed**, 1 warning (the same test-client library
warning), 6 min 2 s.

Full suite after the slope-map endpoint (19:15 IST): **395 passed, 1 failed**, 7 min 34 s. The failure is
`tests/test_pass2_text.py::test_readme_states_what_is_and_is_not_matched_elsewhere`: it looks for the line
"Slip-margin map | not matched" in `README.md`, and `README.md` was rewritten by someone else at 19:10 IST. It
passed in the run before that edit. Not related to this work, and `README.md` was not touched here.

## Evidence scripts (scratch folder, not shipped)

`clicks.py` (simulated clicks, app against independent slope), `reg.py` (picture registration), `stats.py` (all
14,400 close-up cells), `layer.py` (map-layer response and stored touchdown points), `ui.js`, `ui2.js` and
`ui3.js` (headless Chrome: the map-area switch, the stale slope line, the reload).
