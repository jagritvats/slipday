# Add-on: slip-tolerant atlas, 2027 to 2035

## What it does

It shows, year by year from 2027 to 2035, when each of NASA's nine Artemis III landing regions works for a landing.
It also shows how many regions must stay open to cover each year.

- Each region is judged on its published candidate landing sites: 78 sites from Wueller et al. 2026.
- The entry's 14 curated south-pole sites are shown too, each on its own.
- A landing "works" when the lander can stay 6.25 days with the Sun up the whole time and at least 100 hours with
  the Earth in view for radio contact.
- The check is the same as on the mission card: 13 touchdown points within 100 m, a coarser terrain grid and a
  finer sampling of the nearest ground must all pass.
- A region counts as open when at least one of its sites passes with room to spare (the Sun and the Earth do not
  graze the skyline). This is the rule of the existing 2027 to 2030 region calendar, unchanged.
- The entry's own code does the judging. `slipday.regions.members_of` and `slipday.regions.site_flags` are imported
  unchanged; nothing in the verdict was rewritten.

The page shows:

- one paragraph in plain words;
- a switch for "Sunlight + 100 h Earth contact" or "Sunlight only";
- a switch for NASA's nine regions or the entry's own south-pole sites;
- five key numbers;
- an overview: one row per year, one column per month, all nine regions together, where the drift of the season
  can be seen;
- one heat strip per year: one row per region and one column per month, coloured by the share of landing times
  that work (tap or point at a cell to read its value);
- a year-by-year table: all nine regions, the best one, two and three, and how many regions are needed to match
  all nine;
- a fold-out note on how it was worked out and what it cannot tell.

## Files (all new; no existing file was edited)

| File | What |
|---|---|
| `slipday/addons/__init__.py` | empty; created because it did not exist |
| `slipday/addons/atlas.py` | the API router (`router`) |
| `slipday/addons/atlas_build.py` | builds the data: `python -m slipday.addons.atlas_build --procs 4` |
| `static/addons/atlas.js` | the front-end module |
| `tests/addons/test_atlas.py` | 21 tests |
| `data/addons/atlas/atlas.json` | what the router serves (135 KB) |
| `data/addons/atlas/atlas_flags.npz` | every site at every landing time, four yes/no flags, bit-packed (60 KB) |
| `data/addons/atlas/build_1_full_run.log` | output of the full run |
| `data/addons/atlas/build_2_summary.log` | output of the summary rebuild after the drift measure was replaced (see below) |

## For the integrator

**Router.** Module `slipday.addons.atlas`, attribute `router`. The loop near the end of `api.py` imports
`"slipday." + name`, so add `"addons.atlas"` to its tuple:

```python
for _extra in ("why", "scatterfield", "view3d", "contrast", "addons.atlas"):
```

Or include it directly: `from slipday.addons.atlas import router as atlas_router; app.include_router(atlas_router)`.

Endpoints. Each one reads the stored file and computes nothing:

- `GET /api/addons/atlas`: the rule, the year-by-year table, the drift and the check against the 2027 to 2030
  calendar;
- `GET /api/addons/atlas/heat?variant=main|sun_only`: the monthly shares for the heat strips;
- `GET /api/addons/atlas/year/{year}`: one year in full, both variants. A year outside 2027 to 2035 gets 404.

If `atlas.json` is missing, every endpoint answers `{"available": false, "reason": ...}`.

**Page.** In `static/index.html`:

- Put `<div id="addon-atlas"></div>` straight after the regions panel. That is the `</section>` that closes
  `<section class="panel" id="regionsPanel" ...>` (line 108 today), before `contactPanel`. Put it between the
  sections, not inside one: the module draws its own card.
- Put `<script src="/static/addons/atlas.js"></script>` after `<script src="/static/app.js"></script>`, before
  `</body>`.

The module:

- adds one `<style id="atl-style">`;
- uses the page's colour variables (`--seq-lo`, `--seq-hi`, `--zero-cell`, `--surface`, ...), with fallbacks, so it
  follows light and dark mode;
- makes no outside requests.

It was checked in headless Chrome at 1280 px and inside a 390 px frame (a phone width): no sideways scroll, and the
12 month columns stay readable.

## Tests

```
.venv\Scripts\python.exe -m pytest -q tests/addons/test_atlas.py
21 passed, 1 warning in 4.2 s       (15 Nov 2026; the warning is the existing httpx deprecation notice)
```

With `tests/test_regions.py` as well: 29 passed. The router is mounted in a small test app, so `api.py` is not
needed. The tests check:

- the rule and the time grid;
- that 2027 to 2030 equal the existing calendar, landing time by landing time, worked out again from the flags;
- that the heat strip, the year table and the best sets follow from the flags;
- that the best pair is the best of all 36 pairs;
- one site (MMA_K2023) judged again from scratch for 40 days in October and November 2033 on the 80 m grid, which
  matches the stored flags;
- the drift measure on made-up signals with known answers;
- the endpoints, including the "not built" answer;
- that the front-end file makes no outside requests and states its limits.

## Time step and coverage

- **Every 6 hours, 2027-01-01 00:00 to 2035-12-31 18:00 UTC: 13,148 landing times.** All nine years at the same
  step as the existing calendar, so nothing was cut.
- 92 sites (78 published, 14 curated), each with 15 check members (13 touchdown points, the coarser grid, the
  near-field sampling).
- The full run took 120 s with 4 processes on this machine. Skylines went to a temporary folder, so the entry's
  `data/horizon_cache` was not written.
- **The shares count landing times every 6 hours, not real launch opportunities.**

## Measured results

### Check against the existing 2027 to 2030 calendar

The two agree completely. At every one of the 5,844 landing times from 2027 to 2030, in all nine regions, the count
of passing sites is the same. So is the count of sites that pass only narrowly. This holds with the Earth need and
with sunlight only.

For example, Nobile Rim 1 is open at 28.05 % of landing times in both. All nine together: 44.06 % in both.

### Best and worst years

The years differ, but not by a lot. These are shares of landing times, with all nine regions kept open:

| Year | All nine | Best 1 | Best 2 | Best 3 | Regions needed to match all nine | All nine, sunlight only |
|---|---|---|---|---|---|---|
| 2027 | 41.9 % | 27.7 % | 35.6 % | 38.3 % | 6 | 92.1 % |
| **2028 (best)** | **46.9 %** | 29.9 % | 38.9 % | 43.0 % | 6 | **92.4 % (best)** |
| 2029 | 44.3 % | 27.1 % | 36.4 % | 40.2 % | 7 | 91.8 % |
| 2030 | 43.2 % | 27.5 % | 36.2 % | 39.1 % | 8 | 91.9 % |
| 2031 | 41.3 % | 26.4 % | 34.3 % | 37.7 % | 7 | 92.1 % |
| **2032 (worst)** | **39.3 %** | 24.9 % | 32.3 % | 35.5 % | 8 | 91.0 % |
| 2033 | 41.9 % | 27.1 % | 34.4 % | 37.7 % | 8 | 92.4 % |
| 2034 | 45.6 % | 27.7 % | 36.9 % | 41.8 % | 8 | 91.8 % |
| 2035 | 44.7 % | 27.3 % | 37.1 % | 40.8 % | 6 | **90.3 % (worst)** |

- **Best year 2028 (46.9 %), worst 2032 (39.3 %): 7.6 points apart.** With sunlight only, the years lie within
  2.1 points of each other (90.3 % in 2035 to 92.4 % in 2028).
- The best single region is Nobile Rim 1 in every year. The best pair adds Peak near Cabeus B in every year. The
  best three add Malapert Massif in 8 of 9 years (Slater Plain in 2030). Each best set was found by trying every
  combination, separately for each year.
- Over the whole of 2027 to 2035:
  - best 1: 27.3 %; best 2: 35.8 %; best 3: 39.3 %; all nine: 43.2 %;
  - sunlight only: 47.5 %, 74.6 %, 90.7 % and 91.7 %.
- Three regions give about nine tenths of what all nine give. Matching all nine exactly takes 6 to 8 regions with the
  Earth need and 5 with sunlight only. The last regions add very little.
- The 100-hour Earth-contact need is illustrative. It is what holds the ceiling near 43 %.
- The years also differ because a calendar year (365 days) holds a little more than one season (346.6 days, see
  below). So each year gets an extra 19 days, and those days are good in some years and bad in others. These 9 years
  are about half of one 18.6-year cycle, so a slow trend over the whole cycle cannot be told apart from this.

The entry's curated sites, as the yearly share of landing times that work (lowest to highest year, with the Earth
need):

| Site | Share |
|---|---|
| Malapert summit | 16.1 to 19.1 % |
| Malapert Earth-facing shoulder | 16.2 to 18.0 % |
| IM-1 | 15.1 to 16.4 % |
| IM-2 | 14.1 to 16.6 % |
| Shackleton connecting ridge C1 | 11.8 to 14.0 % |
| Mons Mouton | 4.3 to 5.6 % |
| Slip-robust ridge point | 2.6 to 3.9 % |
| C2 | 1.5 to 2.1 % |
| Nobile crater centre | 0.3 to 1.5 % |

Five sites never pass:

- the Shackleton rim point fails the full 13-point check;
- the Haworth, de Gerlache and Shackleton crater floors and the LCROSS site are always dark.

### Does the season come about 18.4 days earlier each year?

Yes, about 18 to 19 days, measured from the atlas itself:

- **All nine regions, Earth need: 18.05 days a year** (season length 347.2 days).
- **Sunlight only: 18.65 days a year** (season length 346.6 days).
- Each region alone: 18.45 to 18.95 days a year with the Earth need, and 18.55 to 18.85 with sunlight only.
- The same fit on the Sun's path alone (the latitude of the point under the Sun, from the ephemeris) gives 346.6
  days, so 18.65 days a year. The expected value is 365.25 − 346.62 = 18.63.
- For comparison, the existing calendar's method (the day of the Sun's lowest point in each calendar year, then a
  straight line) gives 18.4 days for 2025 to 2032. Over 2027 to 2035 it gives 19.3 days. Its year-to-year steps
  jump between 10 and 35 days, because the lowest point can fall in a different month from year to year.

How the atlas measure works:

- The landing times are cut into whole lunar months of 29.53 days, one cycle of sunlight at the pole.
- In each month, the share of open landing times is taken. Because each piece holds one full month, the
  month-to-month pattern drops out.
- A wave is fitted for every season length from 300 to 400 days, in 0.1-day steps, and the best fit gives the
  season's length.
- On made-up signals it finds the true season length to within 0.6 days. When a 27.2-day pattern is added (the
  Earth's nodding in the sky, which whole lunar months do not cancel), it is within 2 days.
- The fit explains 54 % of the month-to-month variation for all nine regions with the Earth need, and 89 % with
  sunlight only.

**A first try was replaced, and it is kept on record.**

- The first measure averaged daily shares over 31 days and lined each year up with the next. It ran in the full
  build and gave 15.0 days (Earth need) and 11.5 days (sunlight only); see `build_1_full_run.log`.
- On made-up signals it read the right answer for a season alone. With a monthly pattern added, it read about 12
  days. The reason: a 31-day average does not cancel the monthly pattern, which itself comes about 11 days earlier
  each calendar year (365.25 days minus 12 lunar months). So the first try followed the Moon's phases, not the
  season.
- A second idea, a sliding 29.5-day average, was tried on made-up signals only. It read about 13 days there, so it
  was never run on the atlas.
- The whole-month fit above replaced both. It was checked on made-up signals before it was run on the atlas.
- The first try's numbers are still in `atlas.json` (`first_try_drift`, marked `"measures_the_season": false`).

## What it cannot tell

- **Shares count landing times every 6 hours, not launch opportunities.** A real mission gets a launch window of a
  few days a month, set by the rocket and the orbit. None of that is modelled.
- **The 100-hour Earth-contact need is illustrative**, not a NASA requirement. The sunlight-only figures stand
  beside it everywhere.
- **Terrain is the 80 m LOLA grid.** Finer terrain would most likely give fewer working landing times. The existing
  cross-check against the paper's sunlight figures found ours often longer; LIMITATIONS.md and the existing
  calendar's notes cover this.
- A region is only as good as its published sites. A region could have better ground that the paper did not list.
- "Open" is about sunlight and Earth contact at touchdown and through the stay. It says nothing about slopes, rocks,
  hazards, the descent path, communications relays or the crew timeline.
- Nine years are about half of one 18.6-year cycle. The atlas cannot say how the years after 2035 compare.
- Earth contact includes the existing check that a Deep Space Network station can see the Moon (`stations=True`, as
  in the calendar). No link budget is modelled.
