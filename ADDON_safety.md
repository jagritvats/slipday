# Add-on: "Flat enough to land?"

Hand-over from the safety add-on, Sunday 15 November 2026 (built 14:04 to 14:35 IST).

## What it does

Slipday already asks: will a lander at this site have sunlight and Earth contact, and how many days of launch slip
can it take? This add-on asks the other question every landing site must answer: **is the ground flat enough where
the lander may come down?**

- **On the site card**, one new line: "Flat enough to land? Yes / No", with the steepest slope among the card's 13
  touchdown points (the target, 8 points 100 m away and 4 points 50 m away). A "Show the 13 points" toggle lists the
  slope at each point, whether it is under the limit, which terrain grid was used and over how wide a square.
- **On the south-polar map**, a switch "Flat enough to land? Show the slope layer on the map". It recolours the
  scatter-checked slip-margin map into three kinds of point:
  - green: **slip-tolerant and flat enough** (keeps at least 1 day of slip at all 13 touchdown points, and all 13
    are under 8 degrees);
  - red with a white stripe: **slip-tolerant but too steep** (at least one of the 13 is 8 degrees or more);
  - grey outline: **not slip-tolerant** (passes on the planned date but keeps less than 1 day of slip at all 13).
  Points where the planned date already fails stay blank, as on the page's own map.

**The limit.** NASA's requirement for the crewed Artemis lander: it must stand within **8 degrees of upright**
(5 degrees is the goal). Strictly this limits how far the lander may lean, not the ground. Published site studies
(Wueller et al. 2026, which the entry already uses; Kring et al. 2023) apply it to the ground slope, and so do we.
The page says this in one sentence next to the answer.

**The slope.** At each touchdown point a flat plane is fitted to the terrain heights around it; the slope is how
much that plane tilts. The finest grid on disk that covers the point is used:

| grid | where | the square the slope is measured over |
|---|---|---|
| LOLA 5 m site models (Site01 connecting ridge, Site07 peak near Shackleton) | two 16 km squares near Shackleton | 10 m (3 x 3 cells): about the width of a crewed lander on its legs |
| LOLA 20 m mosaic (crop) | pole to about 88.4 S | 20 m (the 2 x 2 cells around the point) |
| LOLA 80 m mosaic | pole to 80 S | 80 m (the 2 x 2 cells around the point) |

The 10 m figure is the one NASA's own 2019 white paper for the lander solicitation uses for slopes seen in LOLA 5 m
data ("a slope of about 6 degrees over a 10 m baseline"). 20 m and 80 m squares are wider than a lander, so they
average the ground and usually read lower than the slope under the lander's feet. All grids are read in place,
read-only.

## What we found (all measured today on this machine)

### The named sites (13 touchdown points, 100 m scatter)

| site | grid used | steepest of 13 | points under 8 degrees | points under 5 degrees (goal) | answer |
|---|---|---|---|---|---|
| Opening example, 89.010 S, 122.764 E | 5 m (Site07), over 10 m | **4.9 degrees** (100 m to the south-west) | 13 of 13 | 13 of 13 | **Yes, flat enough** |
| C1, Shackleton connecting ridge, 89.440 S, 137.170 W | 5 m (Site01), over 10 m | **3.9 degrees** | 13 of 13 | 13 of 13 | **Yes, flat enough** |
| IM-1 Odysseus, 80.13 S, 1.44 E | 80 m, over 80 m | 14.8 degrees | 0 of 13 | 0 of 13 | **No, too steep** |

- The opening example is **not** too steep. It is flat enough at all 13 points, but its steepest point (4.9
  degrees; NASA's own slope map gives 5.0 at that point) sits right at NASA's 5 degree goal, so it meets the goal
  only just. NASA's map gives its own uncertainty there as 1.5 to 2.2 degrees per point; even the steepest point
  is about 3 degrees under the 8 degree limit, more than the largest of those uncertainties.
- At the target of the opening example the three grids read 4.6 (5 m), 3.6 (20 m) and 3.3 degrees (80 m); at C1's
  target 1.5, 2.2 and 0.4 degrees. Coarser grids smooth the ground, as expected.
- **IM-1 is a check against the real world.** LROC (26 February 2024) gives IM-1's local slope as 12 degrees; the
  lander came down on a slope and tipped over. Our 80 m figure at its target is **12.2 degrees**. All 13 of its
  touchdown points read 10.0 to 14.8 degrees.

### The Artemis III region sites (Wueller et al. 2026, the 78 published sites in NASA's nine current regions)

All 78 are flat enough at all 13 touchdown points. **76 of the 78 are outside the 20 m crop, so their slope comes
from 80 m terrain only**, which smooths slopes; only 2 use 20 m. So this result agrees with the paper (which picked
these sites under 8 degrees on the 20 m grid and at least 100 m from steeper ground) but adds little evidence of
its own. Steepest of the 13 points, per region:

| region | sites | flat at all 13 | median of the steepest | largest |
|---|---|---|---|---|
| Peak near Cabeus B | 5 | 5 | 5.5 | 6.3 |
| Haworth | 11 | 11 | 4.0 | 6.3 |
| Malapert Massif | 5 | 5 | 5.2 | 5.9 |
| Mons Mouton Plateau | 11 | 11 | 2.9 | 4.3 |
| Mons Mouton | 10 | 10 | 5.6 | 6.8 |
| Nobile Rim 1 | 9 | 9 | 4.7 | 6.8 |
| Nobile Rim 2 | 9 | 9 | 5.1 | 6.5 |
| de Gerlache Rim 2 | 7 | 7 | 3.1 | 6.8 |
| Slater Plain | 11 | 11 | 4.5 | 6.4 |

(degrees; the site centres alone are at most 5.3 degrees)

### The map layer (slip-margin map for landing on 18 Nov 2026, 60 dates, the page's default need)

- 343 map points keep at least 1 day of slip at all 13 touchdown points. Of these, **48 are also flat enough at
  all 13**, and **295 are too steep at one or more**. 390 more pass on the planned date but are not slip-tolerant.
- With "slip-tolerant" set to 0 days instead of 1 (any point that keeps its margin at all), it is 78 of 574.
- Why so few: the map points that keep their light longest sit on ridge crests and crater rims, which are steep.
  For 386 of the 2,407 stored map points all 13 touchdown points are on the 5 m site models; for the other 2,021
  all 13 are on the 20 m crop; none needs 80 m.
- The 1-day rule for "slip-tolerant" was set when the module was written, before the layer was first run, but the
  file times do not show that (the module was edited after the first run), so read it as stated, not as shown to
  come first. The API takes `min_slip_days` if another rule is wanted. The 8 degree limit was never changed.

### Check against NASA's own slope maps

NASA publishes a slope map with each 5 m site model. We downloaded the Site01 and Site07 slope maps and their
uncertainty maps and compared them with our slope at 400 random cells per site:

| site | median difference | 90 % of cells within | correlation |
|---|---|---|---|
| Site01 | 0.12 degrees | 0.54 degrees | 0.997 |
| Site07 | 0.10 degrees | 0.63 degrees | 0.996 |

At the 13 points of the opening example and C1 the two agree within 0.4 degrees at every point; NASA's map also
puts all 26 under 8 degrees. A sample of those NASA values is kept in `tests/addons/safety_nasa_slope_sample.json`
so the tests repeat this check.

## How to add it (for the integrator)

1. **API.** In `slipday/api.py`, add `"addons.safety"` to the optional-router loop near the end:

   ```python
   for _extra in ("why", "scatterfield", "view3d", "contrast", "addons.safety"):
   ```

   The loop calls `importlib.util.find_spec("slipday." + _extra)`, so the import path that works is
   **`slipday.addons.safety`** (checked: `find_spec` finds it and the module has `router`). It needs
   `slipday/addons/__init__.py`, which already exists (another add-on created it at 14:06; this add-on did not
   overwrite it). Routes:
   - `GET /api/addons/safety/site?id=robust_pick` or `?lat=-89.0098&lon=122.76389&scatter_m=100&name=...`:
     the slope at each of the 13 touchdown points, the grid used, pass or fail, the verdict and a plain headline.
   - `POST /api/addons/safety/map-layer`: send the same JSON body the page sends to `/api/robust-map`
     (optional extra field `min_slip_days`, default 1). Returns one code per map point (2, 1, 0, -1, -2), the
     steepest slope of each point's 13 touchdown points, counts and a one-sentence summary.
   - `GET /api/addons/safety/about`: the limit, its source, the grids on this machine, what it cannot tell.
2. **Page.** In `static/index.html`:
   - the container, **directly after the site card** (`<div class="mOut" id="missionOut" ...>...</div>`, inside
     `<section class="panel mission">`):

     ```html
     <div id="addon-safety"></div>
     ```

     The add-on's own CSS places it under the card in the card's column (desktop) and right after the card on a
     phone (it adds a grid row to `.mission` through `:has()`; without `:has()` support the line goes after the
     settings instead).
   - the script, **after** `<script src="/static/app.js"></script>`:

     ```html
     <script src="/static/addons/safety.js"></script>
     ```

   The map switch needs no container: the script puts it under the map legend (`#mapLegend`) by itself, and
   while the slope layer is on it hides the page's own map colours and legend and shows its own.
   The script brings its own small stylesheet (no change to `style.css` or `addons/addons.css` is needed). It
   watches the page's own requests to `/api/mission`, `/api/robust-map` and `/api/map`, chaining onto any other
   add-on's watcher; it never changes them. Its own requests carry `X-Slipday-Addon: 1`.

## Tests

```
cd mvps\slipday
.venv\Scripts\python.exe -m pytest tests\addons\test_safety.py -q
```

Result (14:32 IST, last run after the final edits): **28 passed** (1 warning from the test client's library, not
from this add-on). The router is mounted in a small test app; `api.py` is not touched. The tests check: a tilted
plane of known slope is read back within 0.05 degrees on 5, 20 and 80 m grids; NASA's 5 m slope maps match; the
opening example, C1 and IM-1 numbers above; all 78 published Artemis sites read under 8 degrees at the centre;
the endpoints and their errors; and that the map layer's "slip-tolerant" is exactly the page's own scatter-checked
margin of 1 day or more.

Browser check (scratch script, Chrome, not shipped): desktop 1280 x 900 and phone 390 x 844, on the real app with
the add-on's container and script added to the page in memory (port 8113, stopped afterwards). All checks passed:
the line appears under the card and follows the card's site menu (opening example 4.9 degrees, C1 3.9 degrees),
13 rows, the slope layer draws and comes off, no horizontal scroll at 390 px, no console errors from this add-on.

## Sources (fetched with curl, generic client name, 15 Nov 2026; kept outside the entry, in the scratch folder)

| file | bytes | sha256 | URL |
|---|---|---|---|
| Attachment_F_-_Requirements.zip (holds `HLS-RQMT-001 SRD Rev R 20190927.pdf`) | 11945218 | c31995ca3f22c3cecb9272154bf7e99c72acfbc6495d129f63f56d8f74a369e2 | https://sam.gov/api/prod/opps/v3/opportunities/resources/files/f2d5fc850fef29d71e20080d6c4c9d3a/download (public attachment of https://sam.gov/opp/f3f8689858d6fc2c7f91e6533235f6e7/view, NASA NextSTEP-2 Appendix H, Human Landing System, 2019) |
| HLS-RQMT-001 SRD Rev R 20190927.pdf (from the zip) | 5739744 | 9909a14441c6e4931e69f80dba858523368ef76aff05f945a58b7db3d39ad790 | as above. HLS-R-0071 on page 37 of 315, HLS-R-0021 on page 32 |
| Attachment_A20 Lunar Landing Site Characterization White Paper (pdf) | 743461 | 77889315e0e4693d3192ebcd11c9b6351fa85451363cfce3157e9ca658138ff7 | https://sam.gov/api/prod/opps/v3/opportunities/resources/files/8a973f39d9363729d99e5e7480f1386b/download |
| SAM.gov attachment list (json) | 32040 | 10b107655f353738c8d1a35c287599a84f2985e1b6696922de7fbd3201d73cc1 | https://sam.gov/api/prod/opps/v3/opportunities/f3f8689858d6fc2c7f91e6533235f6e7/resources |
| Site01_final_adj_5mpp_slp.tif | 40980776 | 3a90035a4946b4a04b7332c52f0b2b1cff71648bd8c105e14d8a7e15c6bcfe8e | https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_final_adj_5mpp_slp.tif |
| Site01_final_adj_5mpp_slperr.tif | 40980810 | 52bc3b239f61605e6bb98bab6d6b17acd22389c59e57336862157f2fbd643a33 | https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_final_adj_5mpp_slperr.tif |
| Site07_final_adj_5mpp_slp.tif | 40980774 | febfe1bf19087f537bba2f7854d40ac83adadba5003f2585b1685cbd90d02219 | https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site07/Site07_final_adj_5mpp_slp.tif |
| Site07_final_adj_5mpp_slperr.tif | 40980808 | a7cca9566b91e12da4b0f5d31547a122afe859d3ccf81b1379e094bdd85d6488 | https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site07/Site07_final_adj_5mpp_slperr.tif |
| hls-qanda-log-1a_2019-10-16.pdf (searched, no slope figure) | 167588 | 197ecf8dfad71caff1c54cb185c4a9a822643c39dc9550512e04dd9302dcf71c | https://www.nasa.gov/wp-content/uploads/2019/04/hls-qanda-log-1a_2019-10-16.pdf |
| hls_nextstep-h_baa_virtual-industry-forum_10-3-19.pdf (searched, no slope figure) | 3829901 | fe6c4cae3adfa2267ceabbe445fe5b637f5f0b8e37cf9d0108852d1be6ff7fb2 | https://www.nasa.gov/wp-content/uploads/2019/04/hls_nextstep-h_baa_virtual-industry-forum_10-3-19.pdf |
| 2025-HuLC-QA-Summary-Document.pdf (pointed to the SAM.gov copy of HLS-RQMT-001) | 499370 | 502b52491807120446f6438108dac6b9ccc66fbc37045dc120de0e731c19561b | https://hulc.nianet.org/wp-content/uploads/2025-HuLC-QA-Summary-Document.pdf |

Quoted first-hand from HLS-RQMT-001 (NASA Marshall, initial release, 27 September 2019):
- HLS-R-0071 Landing Site Vertical Orientation: "The HLS shall provide vertical orientation of 0 to 8 deg
  (threshold) and 0 to 5 deg (goal) from local vertical for surface operations." Its rationale adds that the
  lander's slope tolerance is expected to exceed the tilt the crew can work at, "As a result, some means of tilt
  mitigation may be required."
- HLS-R-0021 HLS Landing Accuracy: "The HLS shall be capable of landing within 100m (3-sigma) of target landing
  site."

Already in the entry and used here: Wueller et al. 2026 (`data/reference/wueller2026/wueller2026_jgr_eth.pdf.txt`,
section 2.2, which quotes HLS-R-0071 and cites it as "NASA (2019) HLS-RQMT-001"); the LPSC 2026 NASA abstract
(`data/reference/sources/artemis3_update_lpsc2026.docx`), which says terrain safety is "a primary consideration"
and that regions with "sufficient low-slope area" were prioritised, but gives no number; the 2024 NASA regions
release, which gives no slope number either; the LOLA 5 m README (`data/reference/sources/pgda_lola5mpp_README.txt`)
for the slope and slope-uncertainty files; LROC's IM-1 note in `slipday/sites.py` (12 degrees).

No CLPS document was needed: the crewed-lander requirement is first-hand NASA. CLPS landers have their own,
smaller limits that this add-on does not use.

## What it cannot tell

- **Boulders and small craters.** 5 m terrain shows nothing smaller than about 10 m, 20 m terrain nothing smaller
  than about 40 m, and 80 m terrain is far too coarse to see boulders at all. NASA's white paper says the best
  orbital data show rocks and craters of 1 m and up; this add-on does not use them.
- **Coarse grids read low.** Outside the two 5 m site models the slope is measured over 20 m or 80 m, wider than a
  lander, so a "Yes" there is weaker than a "Yes" on 5 m. Every Artemis region site except two is on 80 m only.
- **Lander tilt is not ground slope.** NASA's 8 degrees is how far the lander may lean. A lander that can level
  itself may cope with steeper ground; a footpad on a rock or in a small crater can lean it more than the slope.
- **13 points are a sample**, not the whole landing ellipse. The published site studies also ask for 100 m of
  clearance from steeper ground; the 13 points within 100 m are a coarse version of that.
- **Uncertainty is not shown on the page.** NASA's 5 m uncertainty maps give about 1.5 to 2.4 degrees per point
  near the opening example and C1; the add-on reports the slope itself, not a range.
- **The map layer** is for the stored map points only (one per 500 m, 2,407 with stored touchdown points), and
  "slip-tolerant" uses the page's 80 m skylines; only the slope uses the finer grids.

## Files

- `slipday/addons/safety.py`: the slope and the router (`router`).
- `static/addons/safety.js`: the card line and the map switch.
- `tests/addons/test_safety.py`, `tests/addons/safety_nasa_slope_sample.json`: tests and the NASA slope sample.
- `ADDON_safety.md`: this file.

No existing file was edited. Nothing was published or uploaded. No server is left running.
