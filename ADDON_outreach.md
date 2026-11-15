# Outreach add-ons: glossary, friendly site names, best spots this month (15 Nov 2026)

Three small pieces for visitors who are not mission planners. None changes an answer. The front-end agent owns
`static\`; only `static/addons/glossary.js` is new, and nothing else under `static\` was edited for this round.

## 1. Glossary (`static/addons/glossary.js`)

**Wire it in** with one tag, after the page's other scripts (the end of `static/index.html`):

```html
<script src="/static/addons/glossary.js" defer></script>
```

The module is self-contained, and the CSS is inside it (a `<style id="glossCss">`). On load it does three things:

- It finds the **first use** of each term in `<main>` (or the body) and turns that word into a small
  `<button class="gloss" data-gloss="<key>">` with a dotted underline. The button's text is unchanged.
- It watches the page. When a redraw removes a marked word, it marks the next first use again.
- Its pieces have fixed ids: one shared tooltip, `#glossTip` (`role="tooltip"`), and the definitions for screen
  readers in a visually hidden `#glossDefs` (one `#glossDef-<key>` each; each term button points to its definition
  with `aria-describedby`). These definitions sit outside the page's text, so `textContent` of the page's own
  elements does not change.
- **How it opens and closes:**
  - It opens on keyboard focus (Tab), on a tap or click, and on hover.
  - It closes with Escape, a second tap or a tap elsewhere.
- **What it never touches:** inputs, selects, buttons, links, labels, summaries, code, SVG and canvas, or anything
  inside `[data-no-gloss]`. Add that attribute to any block that should stay plain.
- **Theming:** it uses `var(--accent)` for the focus ring. Light and dark tooltips follow `prefers-color-scheme` and
  `:root[data-theme]`.
- **Script access:** `window.SlipdayGlossary.terms` (key and definition) and `window.SlipdayGlossary.rescan()`.

**Terms**, longest first:
- slip margin
- touchdown points
- Not sure
- 5 / 20 / 80 m terrain
- permanent shadow
- lunar day
- slip
- illustrative
- skyline
- azimuth
- elevation
- UTC
- LOLA
- CLPS
- LCRNS
- ephemeris
- libration

The definitions are in plain words, for example "Slip margin: how many days the launch can be late and the plan
still works."

**Checked in Chrome on the live page** (port 8102, script added by the test). Results:
- 16 of the 17 terms are found as the page opens; "lunar day" does not appear in the opening view's text.
- The verdict text is unchanged.
- Focus shows the definition, and Escape hides it.
- A click at 390 px shows it inside the screen (54 to 374 px).
- There is no sideways scroll at 390 px, and there are no page errors.

## 2. Friendly site names (`slipday/gazetteer.py`, `/api/sites`, `/api/mission`, `/api/why`)

Sites whose name is only a description plus coordinates now carry a short name built from the **IAU gazetteer
only**:
- The name starts with "Ridge" when the old name calls the place a ridge, otherwise "Spot".
- It then uses the gazetteer phrase when the point lies in or on the rim of a named feature (for example "Spot on
  the rim of Shackleton crater").
- Otherwise it says "near" the feature whose edge is closest.

No name is made up. Every site in `/api/sites`, and the `site` object of `/api/mission` and `/api/why`, now has
these new fields:

| Field | Example (the opening site) |
|---|---|
| `friendly_name` | `Ridge near Shackleton crater` |
| `subtitle` | `89.010 S, 122.764 E · 20 km from the centre of Shackleton crater` |
| `name_full` | `Slip-robust ridge point (89.010 S, 122.764 E)` (the old label) |
| `name_source` | `USGS / IAU Gazetteer of Planetary Nomenclature (nearest named feature)` |

Sites that already have a real name keep it as `friendly_name`, and their `subtitle` is the coordinates.
**`name` is unchanged**: the page, the tests, the stored data files and the recorded videos all reference it, so
nothing breaks. To show the new names, display `friendly_name` with `subtitle` under it, where the site name
appears: the site list and search, the verdict band, the comparison headers and the map labels.

## 3. Best spots this month (`slipday/addons/bestspots.py`)

The router is registered in the add-on loop in `slipday/api.py`.

`GET /api/addons/bestspots?month=YYYY-MM` returns the best 3 landing spots for that month. The default month is the
current UTC one. How it chooses them, from data the page already has:

- **Landing time.** The opening plan lands 18 Nov 2026 00:00 UTC. For another month the landing moves by whole
  synodic months, rounded to the hour, like the card's "next windows" line (our inference, as on the card). For
  example, December gives 2026-12-17 13:00.
- **Need.** The opening plan's: 240 sunlit hours and 100 hours of Earth contact in 14 days, landing within 100 m,
  with the Sun and the Earth in view at touchdown, and the station rule on. The 100 hours are illustrative.
- **Candidates:**
  - the site list's south-pole sites, except the always-dark ones;
  - the slip-margin map's best points, re-checked with the landing scatter, the coarser grid and the near-field
    sampling (the same list as "Which of the best map points stay a clear yes?").

  The 78 published region sites are judged by the regions panel instead, over 2027 to 2030; a mission card for each
  one would take minutes per month.
- **Rule:**
  - Each candidate gets the full mission card, and only a clear Yes counts.
  - Spots are ranked by slip margin, then by good dates in 60.
  - A spot is left out when its slope is known (5 m or 20 m terrain) and over NASA's 8° limit.
  - A map point within 1 km of a listed site is dropped, and the listed site is kept.
- **Speed.** The first call for a month takes about 7 to 40 s on a laptop. The answer is then kept in memory.

**Fields:**
- `available`, `month`, `landing_utc`
- `need` (`sunlit_h`, `earth_h`, `days`, `landing_within_m`, `illustrative`)
- `rule`, `landing_rule`, `candidates_from`, `candidates_checked`, `yes_found`, `seconds`
- `spots`, a list of at most 3, each with:
  - `friendly_name`, `subtitle`, `name_full`, `lat`, `lon`, `site_id` (null for a map point), `from`
  - `landing_utc`, `verdict`, `slip_margin_days`, `good_dates`, `points_passing`, `points`, `sunlit_h`, `earth_h`
  - `terrain_grid`
  - `slope`: `verdict`, `steepest_deg`, `grid_m`, `known`, `headline`. It is null where no slope grid covers the
    spot; `known` is false on 80 m terrain.
  - `map`: `lat`, `lon`, the `site` reference to pass to `/api/mission` or to the map's pick function, and `landing`

**Measured on the live terrain** (in-process):

| Month | # | Friendly name | Slip margin | Steepest slope |
|---|---|---|---|---|
| 2026-11 (landing 18 Nov 00:00) | 1 | Ridge near Shackleton crater | 8 days | 4.9° (5 m) |
| 2026-11 | 2 | Malapert massif summit | 5 days | 3.8° on 80 m (not "known") |
| 2026-11 | 3 | Spot near Shackleton crater (89.060 S, 123.551 E) | 3 days | 6.5° (5 m) |
| 2026-12 (landing 17 Dec 13:00) | 1 | Ridge near Shackleton crater | 6 days | |
| 2026-12 | 2 | Malapert massif summit | 5 days | |
| 2026-12 | 3 | Shackleton connecting ridge (C1) | 4 days | |

**Where it should go.** Put a small "Best spots this month" card near the top of "Where else could it land?", or
in the navigator's step 1 beside the map:
- three rows, each with the friendly name, the subtitle in small type, "Yes, slips up to N days" and the slope
  word;
- a "Show on map" button that calls the page's pick function with `map.site` and sets the date to `map.landing`.

State the rule in one line under the card, with "the 100 hours of Earth contact are illustrative".

## Tests

No new pytest files; the full suite was run once at the end of this round (see DEEP_PASS_3.md).
