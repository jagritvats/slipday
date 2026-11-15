# Add-on: "Chance of a safe touchdown"

## Part 1. The method, written down before any chance was computed (15 Nov 2026)

This part was written before the code that computes the chances existed. The file times show the order: this
file was created at 15:01:27 IST; `slipday/addons/safetouch.py` and the first computed chances (a scratch run
at 15:04:23, then `data/addons/safetouch/sites.json` at 15:04:49) came after. (The heading first said "15:15
IST", a wrong guess at the clock; it was corrected at 15:05. Only that stamp was changed.) Nothing below may be changed after the first numbers come out; if
something has to change, it is added as a dated note under Part 2, with the reason.

### The question

The "flat enough to land?" add-on checks the slope at 13 fixed touchdown points. A real lander comes down
somewhere in a spread of points around its aim point. This add-on turns that into a chance: aim here with a
lander of this accuracy, and there is an X % chance that the ground under the lander is within 8 degrees of
level (NASA's limit, HLS-R-0071), and a Y % chance it is within 5 degrees (NASA's goal).

### Where it runs

Only where NASA's 5 m terrain (the LOLA team's 5 m site models, Site01 and Site07, in `data/dem5/`) covers
the whole spread of touchdown points. That includes the opening example (89.010 S, 122.764 E, on Site07) and
C1 (the Shackleton connecting ridge, 89.440 S, 137.170 W, on Site01). Everywhere else the add-on says that 80 m
terrain is too coarse for this and shows no number. The 20 m grid is not used either: a 20 m cell is wider
than a lander.

A lander class is left out at a site if more than 1 % of its touchdown points fall outside the 5 m grid. The
share outside is reported for every class.

### The lander classes (the entry's own, not new ones)

Taken unchanged from `slipday/robust.py`, `LANDER_CLASSES`, read in code so the two can never drift apart:

| class | spread (one standard deviation) | the public figure behind it |
|---|---|---|
| precision lander | 33 m, round | JAXA, SLIM, "pinpoint landing within an accuracy of 100m" (25 Jan 2024) |
| CLPS-class lander | 250 m, round | NASA, IM-2 came down "about 820 feet" (250 m) from its target (7 Mar 2025) |
| unguided lander | 670 m by 400 m | ISRO, Chandrayaan-3 "Landing Site (Prime) 4 km x 2.4 km" |

These sizes are the entry's assumptions, each tied to one public figure, not a model of any named lander. The
add-on says so next to the numbers. For the unguided lander the direction of the long axis is not known, so
12 directions are tried (0 to 165 degrees in steps of 15, the same as the entry); the chance is the average
over them, and the lowest and highest direction are reported.

### The touchdown points

For each class, touchdown points are drawn at random from a bell-shaped (Gaussian) spread of the size above,
centred on the aim point: 20,000 points for each round class, 2,000 for each of the 12 directions of the
unguided class (24,000 in all). The random numbers come from a fixed seed (20261115), so every run gives the
same answer. Offsets are drawn in metres on the map grid of the 5 m model (polar stereographic; its scale
differs from true ground distance by less than 0.01 % here).

### The slope under the lander

The same slope as the safety add-on: a flat plane fitted to the 3 x 3 cells of 5 m terrain around the
touchdown point, a 10 m square, about the width of a crewed lander on its legs. The slope is how much that
plane tilts. To make this fast the slope is worked out once for every 5 m cell of a patch around the site and
each touchdown point takes the slope of the cell it falls in, which is what the safety add-on's own function
does (it centres on the nearest cell). A test checks that the two agree.

### The answer and its range

- The chance within 8 degrees is the share of touchdown points whose slope is 8 degrees or less; the same for
  5 degrees.
- The range is the 95 % range from the random sampling (Wilson's formula for a share). With 20,000 points it is
  under 1 percentage point either way. It says only how much the number would move with other random draws,
  not how good the terrain or the lander sizes are.
- For the unguided class the range also covers the lowest and highest of the 12 directions.

### NASA's slope uncertainty

NASA's 5 m slope maps give about 2 degrees of uncertainty per point. The chance is computed again with every
slope 2 degrees higher (a worse case) and 2 degrees lower (a better case, never below 0). Both are shown next to
the main number. This is a simple bound, not a model of how errors are shared between neighbouring cells.

### A better aim point (a suggestion, not a site study)

- Candidate aim points: every point of a 10 m grid within **200 m** of the planned site.
- For each class and each candidate, the chance within 8 degrees is computed with the same random offsets
  (only the aim point moves), so candidates are compared fairly.
- The best candidate is the one with the highest chance within 8 degrees; ties go to the higher chance within 5
  degrees, then to the candidate nearest the planned site.
- It is offered only if it beats the planned site by more than the sampling range of both (their 95 % ranges do
  not overlap) and by at least 1 percentage point.
- It must keep the slip-margin verdict: the entry's own mission card (the page's 80 m skylines, the page's
  default need: landing 18 Nov 2026, 240 sunlit hours and 100 hours of Earth contact in 14 days, 100 m
  scatter, 60 days of slip) is run at the candidate. It is kept only if the verdict is the same as at the
  planned site and the slip margin is at least as long. If it fails, the next best candidate at least 20 m away
  from every rejected one is tried, up to 5 candidates in all. If none passes, the add-on says so.
- The page calls it a suggestion, not a site study: it looks only at slope over 10 m and the slip margin, not
  at boulders, lighting during descent, or anything else a site study checks.

### What is decided now and will not be tuned

The 8 and 5 degree limits, the 10 m square, the lander sizes, the seed, the number of draws, the 200 m radius,
the 1 % coverage rule and the rules for the suggestion. None of these is changed to make a site look safer.

### What it cannot see (to be repeated on the page)

- Boulders and small craters: 5 m terrain shows nothing smaller than about 10 m. A lander can still come down
  on a rock or in a small crater the terrain does not show.
- The lander sizes are the entry's assumptions.
- Ground slope is not lander tilt: NASA's 8 degrees is how far the lander may lean.
- Only two 16 km squares near Shackleton have 5 m terrain here.

## Part 2. Hand-over (written after the numbers, 15 Nov 2026)

### What it does, in plain words

Slipday's "flat enough to land?" check looks at the slope at 13 fixed points. A real lander does not come down
exactly where it aims. It lands somewhere in a spread around the aim point, and a less accurate lander has a
wider spread. This add-on asks: **if you aim here, what is the chance that the ground under the lander is flat
enough?** It gives that chance for three lander accuracies, against NASA's 8 degree limit and its 5 degree
goal. It shows the ground around the aim point coloured by slope, with the landing spread drawn over it. It
also looks for a better aim point within 200 m, and offers one only if it is clearly better and the site keeps
its slip margin. It works only where NASA's 5 m terrain exists. Anywhere else it says that 80 m terrain is too
coarse and shows no number.

Words used on the page, explained once: **slope** is how much the ground tilts, measured over a 10 m square
(about a lander's width). **Within 8 degrees** means that tilt is 8 degrees or less. **The range** is how much
the number could move if the random touchdown points were drawn again. **Slip margin** is how many days the
landing can slip and still get the sunlight and Earth contact the mission needs (Slipday's main answer).

### How to add it (for the integrator)

1. **API.** In `slipday/api.py`, add `"addons.safetouch"` to the optional-router loop near the end:

   ```python
   for _extra in ("why", "scatterfield", "view3d", "contrast", "addons.atlas", "addons.safety", "addons.safetouch"):
   ```

   The loop calls `importlib.util.find_spec("slipday." + _extra)`, so the module name is
   **`slipday.addons.safetouch`**. It exposes `router`. Routes:
   - `GET /api/addons/safetouch/site?id=robust_pick` (or `id=shackleton`, any id from `/api/sites`, or
     `?lat=-89.0098&lon=122.76389&name=...`): the chances per lander class, the pictures and the suggestion.
     The opening example and C1 come at once from `data/addons/safetouch/sites.json`. Another point on the 5 m
     site models is worked out live: under a second for the chances, plus a few seconds per slip check (the
     planned site, and any candidate aim point), through the entry's own job lanes. Anywhere else the answer
     is `available: false` with the plain "too coarse" sentence.
   - `GET /api/addons/safetouch/about`: the method, the lander classes, the 5 m grids on this machine, the limits.
2. **Page.** In `static/index.html`:
   - the container goes **inside the existing "Flat enough to land?" panel** (`<section class="panel"
     id="safetyPanel">`, which already sits after the slip grid), directly after its
     `<p class="note" id="slopeNote">...</p>`. That way the first screen does not grow:

     ```html
     <div id="addon-safetouch"></div>
     ```
   - the script goes **after** `<script src="/static/addons/safety.js"></script>` (it must come after
     `/static/app.js`):

     ```html
     <script src="/static/addons/safetouch.js"></script>
     ```

   The script brings its own small stylesheet and uses the page's colour names, so it follows light and dark
   mode. It follows the card's site menu (`#mSite`) by watching the page's own requests to `/api/mission`
   (answers are copied, never changed; it chains onto the safety add-on's watcher). Its own requests carry
   `X-Slipday-Addon: 1`. The picture and the method sit behind two "show" toggles, so until opened the panel
   adds a heading and three short boxes.
3. **Data.** `data/addons/safetouch/sites.json` (about 210 kB) is made by
   `.venv\Scripts\python.exe -m slipday.addons.safetouch` (2 to 20 s, mostly the slip checks). Without it, the
   two named sites are worked out live instead.

### Tests

```
cd mvps\slipday
.venv\Scripts\python.exe -m pytest tests\addons\test_safetouch.py -q
```

Result (15:17 IST, after the last code change): **30 passed** (1 warning from the test client's library, not
from this add-on). Run together with the safety add-on's tests: 58 passed. `find_spec("slipday.addons.safetouch")`
finds the module and it has `router`. The router is mounted in a small test app; `api.py` is not touched. The tests check:
- the lander classes are the entry's own (the same object, not a copy);
- the random draws have the right spread, and the right direction for the unguided oval, and repeat exactly;
- a tilted plane of known slope reads back within 0.01 degrees;
- the patch slope equals the safety add-on's own slope at 400 random cells per site (difference under 1e-9 degrees);
- **an independent route gives the same chances**: touchdown points placed with the entry's own great-circle
  step and the safety add-on's own slope function, another seed, agree within 1.5 points (measured: opening
  example 100.0 / 90.5 % and 93.6 / 70.8 %; C1 99.9 / 98.5 % and 81.1 / 54.2 %, for precision and CLPS-class,
  within 8 / within 5 degrees);
- an 80 m place gets no number; a class whose spread runs off the 5 m grid (more than 1 % of draws) is left out;
- the opening example and C1 numbers below; "100 %" is never claimed from rounding;
- the plus-or-minus-2-degree figures bracket the main one; the stored file equals a fresh run;
- every rejected aim point really lost the slip verdict, and nothing is offered without the slip check;
- the endpoints and their errors, and a live point 500 m from C1.

Browser check (scratch script, headless Chrome, not shipped): desktop 1280 x 900 and phone 390 x 844, on the
real app with the container and script added to the page in memory (port 8141, stopped by PID afterwards). All
passed: the panel follows the card's site menu (opening example, then C1, then IM-2, which shows the "too
coarse" sentence), the picture and lander buttons work, no horizontal scroll at 390 px (page 390 px wide,
picture 311 px), no console errors.

### What we found (measured today on this machine)

20,000 touchdown points per round class, 24,000 for the unguided oval (2,000 in each of 12 directions). Slope
over a 10 m square of LOLA 5 m terrain. "Range" is the 95 % range from the random draws. For the unguided
lander it is widened to the lowest and highest of the 12 directions, which is much the larger effect. "2
degrees steeper / flatter" is the same count with every slope shifted by 2 degrees, for NASA's stated slope
uncertainty. No touchdown point of any class fell off the 5 m terrain at either site.

**Opening example, 89.010 S, 122.764 E (LOLA 5 m Site07)**

| lander (spread: the entry's assumption) | within 8 degrees | range | 2 degrees steeper / flatter | within 5 degrees | range | 2 degrees steeper / flatter |
|---|---|---|---|---|---|---|
| precision (99 % within 100 m) | **over 99.9 %** (19,993 of 20,000) | 99.9 to 100 | 97.2 / over 99.9 % | **90.0 %** | 89.5 to 90.4 | 22.8 / 99.0 % |
| CLPS-class (99 % within 759 m) | **93.7 %** | 93.3 to 94.0 | 81.3 / 98.4 % | **70.9 %** | 70.3 to 71.5 | 35.3 / 88.7 % |
| unguided (oval, 99 % within about 4.1 by 2.4 km) | **82.9 %** | 78.1 to 87.4 | 67.7 / 92.0 % | **57.6 %** | 54.2 to 61.1 | 28.7 / 76.1 % |

**C1, Shackleton connecting ridge, 89.440 S, 137.170 W (LOLA 5 m Site01)**

| lander | within 8 degrees | range | 2 degrees steeper / flatter | within 5 degrees | range | 2 degrees steeper / flatter |
|---|---|---|---|---|---|---|
| precision | **99.9 %** (19,984 of 20,000) | 99.9 to 100 | 99.4 / 100 % | **98.4 %** | 98.2 to 98.5 | 67.1 / 99.8 % |
| CLPS-class | **80.7 %** | 80.1 to 81.2 | 65.8 / 90.7 % | **53.8 %** | 53.1 to 54.5 | 22.6 / 74.5 % |
| unguided | **50.8 %** | 45.4 to 55.8 | 35.3 / 64.9 % | **27.0 %** | 22.6 to 30.6 | 10.4 / 43.1 % |

What this says:
- With a precision lander, both sites are almost certainly within NASA's 8 degree limit. The 5 degree goal is
  another matter at the opening example: 90 %, and only **23 %** if NASA's slopes are 2 degrees too low. About
  two-thirds of the precision lander's touchdown points land on ground of 3 to 5 degrees (22.8 % at 3 or less,
  90.0 % at 5 or less), which fits the safety add-on (steepest of its 13 points there: 4.9 degrees). C1 is flatter close in (98 % within 5 degrees).
- With wider landers the order flips. C1 has steep ground within a few hundred metres, so a CLPS-class lander
  has about a **1 in 5** chance of coming down on ground steeper than 8 degrees, and an unguided one about
  **1 in 2**. The opening example sits on a broader flat patch: about 1 in 16 for a CLPS-class lander and 1
  in 6 for an unguided one.
- NASA's 2 degree uncertainty moves the 8 degree figures by up to about 15 points for the wider landers, and
  the 5 degree figures by much more. So the 5 degree chances are weak; the 8 degree chances for the precision
  lander are firm.

**A better aim point: none is suggested, at either site, for any lander.**
- Searched: 1,257 aim points on a 10 m grid within 200 m of each site.
- Opening example, CLPS-class lander: aim points at the 200 m edge do better for slope (best 97.8 % within 8
  degrees, against 93.7 %). But all 5 tried lose the slip margin on the page's own check. The planned site
  reads Yes with 8 days of slip; of the five, four read "Not sure" on the planned date and one reads Yes with
  0 days. So none is offered, by the rule set in Part 1.
- Every other case: no aim point within 200 m does clearly better (by at least 1 point, with the ranges
  apart). For the precision lander there is little left to gain. For the unguided lander the spread is
  kilometres wide, so moving the aim by 200 m changes little, and its range over 12 directions is wide.
- The slip check: the entry's own mission card, 80 m skylines, landing 18 Nov 2026, 240 sunlit hours and 100
  hours of Earth contact in 14 days, 100 m scatter, 60 days of slip. The planned sites read Yes with 8 days
  (opening example) and Yes with 7 days (C1), the same as the page.

### Notes added after the first numbers

- 15:13 IST: the answer now also carries the raw counts behind each share (for example 19,993 of 20,000), and
  the page says "over 99.9 %" instead of "100 %" when a share only rounds to 100. No number changed.
- Nothing in Part 1 was changed after the numbers came out, except the clock stamp in its heading (see there).
  No limit, size, seed, radius or rule was tuned.

### What it cannot tell

- **Boulders and small craters.** 5 m terrain shows nothing smaller than about 10 m. A lander can still come
  down on a rock or in a small crater this terrain does not show. So the real chance of a safe touchdown is
  lower than the chance of flat-enough ground given here.
- **The lander sizes are the entry's assumptions**, each tied to one public figure (JAXA's SLIM, NASA's IM-2
  report, ISRO's Chandrayaan-3 landing area). They are not a model of any real lander. A lander that dodges
  hazards on the way down would do better; that is not modelled.
- **Ground slope is not lander tilt.** NASA's 8 degrees is how far the lander may lean.
- **The plus-or-minus-2-degree figures** shift every slope the same way at once. Real errors vary from place to
  place, so the truth most likely lies between the two. It is a simple bound, not a full error model.
- **Only two 16 km squares near Shackleton have 5 m terrain here.** The 78 Artemis region sites, IM-1, IM-2
  and every other site get no chance at all, on purpose: an 80 m (or 20 m) cell is wider than a lander.
- **The suggestion** looks only at slope over 10 m and at the slip margin for the page's default need. It does
  not look at boulders, light during descent, approach paths or anything else a site study checks. For a
  place worked out live, the slip check also uses the default need, not the need typed on the page.
- **The slip check uses 80 m skylines**, like the page; only the slope uses 5 m terrain.

### Sources

Nothing was downloaded for this add-on. It reads, in place and read-only:
- the LOLA 5 m site models `data/dem5/site01/ldem_site01_5m_f32.npy` and `data/dem5/site07/ldem_site07_5m_f32.npy`
  (provenance and hashes in their `dems.json`; Barker et al. 2021, https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/);
- the lander classes in `slipday/robust.py` (`LANDER_CLASSES`) and their sources: JAXA press release, 25 Jan
  2024 (https://global.jaxa.jp/press/2024/01/20240125-1_e.html); NASA news release, 7 Mar 2025
  (https://www.nasa.gov/news-release/nasa-receives-some-data-before-intuitive-machines-ends-lunar-mission/); ISRO
  Chandrayaan-3 details page (https://www.isro.gov.in/Chandrayaan3_Details.html);
- the 8 and 5 degree limits, their source (NASA HLS-RQMT-001, HLS-R-0071) and the slope function, from
  `slipday/addons/safety.py`. The 2 degree uncertainty is the figure in `ADDON_safety.md` (NASA's 5 m
  slope-uncertainty maps: 1.5 to 2.4 degrees near these sites);
- the entry's mission card (`slipday/robust.py`) and its skylines, for the slip check.

Made here: `data/addons/safetouch/sites.json`, sha256
8475914a270f94a762eec19cb8732efe447d7e6627c58f9f5a0eb249e69b2a87 (built 15:13 IST).

### Files

- `slipday/addons/safetouch.py`: the method, the builder (`python -m slipday.addons.safetouch`) and the router (`router`).
- `static/addons/safetouch.js`: the panel.
- `tests/addons/test_safetouch.py`: the tests.
- `data/addons/safetouch/sites.json`: the stored answers for the opening example and C1.
- `ADDON_safetouch.md`: this file.

No existing file was edited. Nothing was published or uploaded. No server is left running.
