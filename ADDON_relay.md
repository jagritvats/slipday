# Add-on: Relay satellites, contact when the Earth is hidden

Status: the method section below was saved first, at 15:02:38 IST on 15 Nov 2026 (file time read at
15:04:57). The first site result was computed in a run started at 15:04:41 IST. The file has been edited
since (results and hand-over added), so its own modified time no longer shows this order; the two times
above were read from the file system and the run log when they happened. The geometry checks (orbit period,
distances, frames) were run between those two times; they use no site.

Corrections made after the first save are marked "Correction" and say why.

## Method (written before computing)

### The words

- **A relay**: a satellite circling the Moon that passes messages between a lander and Earth.
- **Skyline**: the edge of the terrain seen from the site, worked out from NASA's LOLA height maps, as
  everywhere else in Slipday.
- **Contact by Earth**: the hour counts when the Earth's centre is above the site's skyline. This is the
  rule the mission card already uses by default. It stays the default; this add-on never replaces it.
- **Contact by relay**: the hour counts when a relay is above the site's skyline and the Moon does not
  stand between the relay and the Earth.
- **Contact by either**: one or both of the above.

### The orbit (source)

NASA, "NASA Lunar Communications Relay and Navigation Systems (LCRNS) Reference Constellation 3.1",
G. Ryden and M. Volle, NASA Goddard, March 2025, NTRS record 20250002698.

- Record: https://ntrs.nasa.gov/citations/20250002698
- File: https://ntrs.nasa.gov/api/citations/20250002698/downloads/LCRNS_Reference_Constellation_White_Paper_03_2025.docx
- Copies and sha256 are in `data/addons/relay/` (see "Source files" below).

What it says, in its own words: "This document is provided to supply end-users with a set of states
representing the government reference Constellation design for these analyses. This reference design is
not final; the final design choice belongs to Intuitive Machines". It gives five satellites (SV-1 to SV-5)
in "Elliptical Lunar Frozen Orbits (ELFO) ... with apolune above the south pole", "approximately 30 hours
on average", as states at "March 01, 2027 00:00:00.000 UTC".

So the page labels it: **a representative relay orbit from NASA's LCRNS Reference Constellation 3.1, not a
live service.** (No relay is in service; the reference design is not final.)

### Which satellites

SV-1 and SV-2 share one orbit plane (inclination 59.37 and 58.95 degrees, node 321.02 and 321.00 degrees)
and start half an orbit apart (true anomaly 0 and 180 degrees). They are the only same-plane pair in the
source. The other three sit in two other planes.

- Headline: **two relays, SV-1 and SV-2**, the source's same-plane pair, phased as published.
- Extra line: **one relay, SV-1 alone.**
- SV-3, SV-4 and SV-5 are not used (other planes; the brief limits this add-on to one plane).

This choice comes from the source alone, before any site was computed.

### Moving the satellites

- Start from the source's Table 2: position and velocity of each satellite in the Moon-centred ICRF
  frame (a frame fixed to the stars), at 1 Mar 2027 00:00 UTC.
- Two-body motion: each satellite follows a fixed ellipse around a point-mass Moon (Kepler's laws). The
  Moon's gravity constant is the one in the DE421 ephemeris the app already uses.
- This ignores every other pull: the Moon's lumpy gravity, the Earth, the Sun, sunlight pressure. The
  source says plainly that its orbits stay stable only with a full model ("GRGM-900c, 25x25", point masses
  of the Sun, Earth and planets, solar pressure). **The source does not support two-body motion as an
  accurate prediction, over 14 days or any other span.** The landing window (from 18 Nov 2026) is also
  about 100 days before the source's start date, so the model is run backwards.
- What this means: the shape of the orbit (how high, how long over the south pole) is taken from the
  source and should be about right; where each satellite is at a given hour on 18 Nov 2026 is not a
  prediction. To show how much that matters, every count is also run for 144 other starting positions:
  12 positions along the orbit times 12 turns of the orbit plane about the Moon's pole (30 degrees apart),
  with SV-2 kept half an orbit from SV-1. The page reports the lowest, middle and highest of these
  beside the as-published count.
- Positions go into the Moon-fixed frame with the same DE421 lunar orientation the app uses for the Sun
  and the Earth.

### Seeing a relay from the site

For each hour of the window: the relay's direction (azimuth, elevation) from a point 2 m above the site,
compared with the site's skyline at that azimuth (the same terrain skyline the card uses, `sites.horizon_for`).
The relay counts when its elevation is above the skyline. The relay must also see the Earth: the straight
line from the relay to the Earth's centre must not pass through the Moon (a smooth ball of radius 1737.4 km).
No ground station rule is applied to either path, matching the card's default (the Deep Space Network rule
is an option on the card, off by default).
- Correction (about 15:07, after the first site results): that was wrong about the page. The API's default
  is off, but the page's box "Earth contact only while a Deep Space Network station sees the Moon" is ticked
  by default, so the page sends `earth_stations: true`. The module now takes a `stations` switch (on by
  default, and the page's own setting is passed through). When on, both paths need a Deep Space Network
  complex with the Moon at least 10 degrees up, the card's own station rule, because both links end at a
  ground station. Measured for all three sites and both relay counts: every number is the same with the
  rule on and off in this window (a complex always has the Moon in view), so no result changed.

### Sites and window (fixed before computing)

1. The opening example: 89.010 S, 122.764 E (`robust_pick`), landing 18 Nov 2026 00:00 UTC.
2. C1, the Shackleton connecting ridge (`shackleton`, 89.4398 S, 137.17 W), same landing.
3. One Artemis region site, by this rule: the first stored candidate site of Nobile Rim 1, the region the
   README names as the best single region. That is NR101 (85.295 S, 36.9168 E, Wueller et al. 2026).
   Same landing.

Window: 14 days (336 hours) from the landing hour, as on the card.

### Slip margin with and without relays

The card's slip margin needs all 13 touchdown points and two terrain grids to agree. This add-on uses
**the stated point only**, for both the Earth-only and the either-way count, so the two are like for like:

- For each day of slip d = 0, 1, 2, ... (up to 60): landing at the landing hour plus d days.
- The day passes when: at least 240 sunlit hours and at least 100 contact hours in the 14 days, Sun up at
  touchdown, contact at touchdown (the card's default need and rules).
- Contact = Earth for the default line; contact = Earth or relay for the relay line.
- Slip margin = the last day d such that every day 0..d passes (as on the card).

The 100-hour contact need is illustrative, as everywhere in Slipday.

### Checks (tests)

- The orbit period measured from the propagated positions (time between two closest approaches) against
  the source's "approximately 30 hours" and against Kepler's law for the source's semi-major axis.
- The highest and lowest distance from the Moon's centre against SMA x (1 + ECC) and SMA x (1 - ECC) from
  the source's Table 1; altitude at apolune = that distance minus 1737.4 km.
- The inclination of the Table 2 state measured against the Moon's pole at the epoch, against Table 1's
  59.37 degrees (shows the frames are read right).
  - Correction (found by the geometry check, run before any site result; written down at about 15:05): against the Moon's pole at the
    2027 epoch the inclination is 61.5 degrees, not 59.37. Table 1 says its frame is "referenced to the
    J2000 Epoch": with the Moon's principal-axis frame taken at 1 Jan 2000 (DE421 librations), Table 2
    gives inclination 59.373, node 321.019 and argument of perilune 92.494 degrees for SV-1, the same as
    Table 1 to three decimals (SV-2 too). The test checks that. The Moon's pole moves slowly against the
    stars (an 18.6-year wobble), which is why the two dates differ by about 2 degrees.
- Apolune lies over the south pole (the source says so).
  - Correction (found by the geometry check, run before any site result; written down at about 15:05):
    the source's "apolune above the south pole" is loose. With an inclination near 61 degrees to the
    Moon's equator, the high point of the orbit is over about 61 degrees south, not over the pole itself.
    From 17,400 km up it is still high in the sky seen from near the pole. The test checks that apolune
    is over about 61 S and perilune over about 61 N instead.
- The Earth-only hours this module counts equal the app's own slip-grid Earth hours for the same point.

## Results (measured 15 Nov 2026, from 15:04 IST)

Landing 18 Nov 2026 00:00 UTC, the 14 days (336 hours) after touchdown, LOLA 80 m terrain (240 m, 474 m and
1.90 km beyond its edge), 2 m above the ground. Station rule on (the page's default); every number is the
same with it off. Stored in full, with the hour codes, in `data/addons/relay/results_2026-11-18.json`
(sha256 1c229dccce0ea4878e3f561a2305755ec569b61ca236e9424b6eb1f32115970b).

"Spread" = the lowest and highest over 144 other starting positions of the relays (see Method).

### Hours of contact in the 14 days

| Site | Earth alone | One relay alone | Earth or one relay | Two relays alone | Earth or two relays |
|---|---|---|---|---|---|
| Opening example, 89.010 S 122.764 E | 311 | 292 (spread 277 to 292) | 333 (spread 331 to 336) | 336 | 336 (every run) |
| C1, Shackleton connecting ridge | 295 | 292 (spread 285 to 292) | 332 (spread 326 to 332) | 336 | 336 (every run) |
| Nobile Rim 1, site NR101 | 336 | 292 (spread 284 to 292) | 336 (every run) | 336 | 336 (every run) |

Plain sentence for the opening example: "With one relay of this design, contact covers 333 of 336 hours
instead of 311." With two relays (the headline): 336 of 336.

### Slip margin at the stated point (days)

| Site | Earth alone | Earth or one relay | Earth or two relays |
|---|---|---|---|
| Opening example | 8 (day 9: only 95 hours of Earth contact) | 11 (every run) | 11 (every run) |
| C1 | 8 (day 9: only 79 hours of Earth contact) | 12 (spread 12 to 59) | 59 or more (every run) |
| Nobile Rim 1, NR101 | 14 (day 15: Earth behind the skyline at touchdown) | 17 (spread 14 to 59) | 59 or more (every run) |

What these mean:
- **Opening example.** Relays would add 3 days of slip margin (8 to 11). Then sunlight ends it: on day 12 there
  are only 229 sunlit hours of the 240 needed. This does not depend on where the relays start.
- **C1 and NR101.** With two relays, contact never runs out, so the margin reaches the end of the check
  (59 is the last of the 60 days checked, so "59 or more"). With one relay the margin ends on a day when the
  landing hour falls in the relay's short gap while the Earth is hidden. That depends on where the relay
  is at that hour, which this model cannot predict, so the honest answer is the spread: 12 to 59 days at C1,
  14 to 59 at NR101.
- The Earth-alone margins are for the stated point only. The card's own margin needs 13 touchdown points
  and two grids to agree. It is 8 days for the opening example (the same; README) and 7 for C1 on the 80 m
  grid (one less than here; `data/validation/grids_5m.json`, asserted in `tests/test_deep2.py`).
- The Earth-alone hours by day equal the app's own slip-grid Earth hours exactly, with and without the
  station rule (tested). So the add-on does not change or re-derive the card's Earth answer.

### Orbit checks (from the propagated positions)

- Period: 30.0 hours between closest approaches (source: "approximately 30 hours on average"). Kepler's law
  for the source's semi-major axis gives 30.005 h (SV-1) and 30.013 h (SV-2).
- Highest point (apolune): 19,146 km from the Moon's centre, 17,409 km above the surface. Lowest (perilune):
  3,486 km from the centre, 1,748 km up. Both match Table 1's SMA x (1 +/- ECC) to 1 part in 10,000.
- Table 2's states give Table 1's inclination, node and argument of perilune to 0.01 degree in the Moon's
  principal-axis frame at J2000.
- Apolune is over about 61 S, perilune over about 61 N (see the correction in Method).
- The Moon's gravity constant from the DE421 header: 4902.800 km^3/s^2.

## Hand-over

### What it does (plain words)

When the Earth is behind the hills, a lander cannot talk to Earth directly. NASA plans relays: satellites
circling the Moon that pass messages between a lander and Earth. This panel takes NASA's own reference design
for those relays and sorts each hour of the 14 days, for the site and landing on the card, into contact by the
Earth, by a relay, by both, or by neither. It shows them as a grid of 14 rows of 24 coloured hours, one sentence
("With two relays of this design, contact covers 336 of 336 hours instead of 311 with the Earth alone"), and
how far the slip margin would stretch if relay contact counted. The card's own answer is never changed; this
is an extra line.

### Source

- NASA, "NASA Lunar Communications Relay and Navigation Systems (LCRNS) Reference Constellation 3.1",
  G. Ryden and M. Volle, NASA Goddard, March 2025.
- Record: https://ntrs.nasa.gov/citations/20250002698
- File: https://ntrs.nasa.gov/api/citations/20250002698/downloads/LCRNS_Reference_Constellation_White_Paper_03_2025.docx
- Text version: the same URL with `.txt` added (NTRS's own text extract).

Source files in `data/addons/relay/`, fetched 15 Nov 2026 with plain curl:

| File | sha256 |
|---|---|
| LCRNS_Reference_Constellation_White_Paper_03_2025.docx | a0812ed8405567125c3266c6cd0e7cbd7f115fff220f688bb978c4f7eccac0aa |
| LCRNS_Reference_Constellation_White_Paper_03_2025.docx.txt | a52bf9345f58ead9781e6f2dbdc267439f7858bc9b6b1a61a82be67d98160f3b |
| ntrs_record_20250002698.json (from https://ntrs.nasa.gov/api/citations/20250002698) | a821501a7547abb0c186910aebb1597d808befb2d01d7189949e061acbb2c0b6 |
| results_2026-11-18.json (our results, not a source) | 1c229dccce0ea4878e3f561a2305755ec569b61ca236e9424b6eb1f32115970b |

Label on the page: "a representative relay orbit from NASA's LCRNS Reference Constellation 3.1 (March 2025),
not a live service".

### Wiring it in (for the integrator)

1. **Router module: `addons.relay`** (file `slipday/addons/relay.py`, exposes `router`). Add it to the
   optional-router loop near the end of `slipday/api.py`:

   ```python
   for _extra in ("why", "scatterfield", "view3d", "contrast", "addons.atlas", "addons.safety", "addons.relay"):
   ```

   Routes: `GET /api/addons/relay` (source, model, satellites) and
   `GET /api/addons/relay/window?lat=&lon=&name=&landing=&stations=&config=two|one&spread=true|false`
   (or `site=<id>` instead of lat and lon). With the spread, one request took 0.63 s for C1 through the
   server (terrain already loaded).

2. **Container.** In `static/index.html`, just above the Deep Space Network panel (not on the first screen).
   Only the first line is new:

   ```html
   <div id="addon-relay"></div>
   <section class="panel" id="contactPanel" aria-labelledby="h-contact" hidden>
   ```

3. **Script tag.** After `/static/app.js`, with the other add-on scripts near the end of `static/index.html`:

   ```html
   <script src="/static/addons/relay.js"></script>
   ```

   No CSS file to add: the script injects its own styles, scoped to `#addon-relay`, using the page's colour
   tokens (light and dark). It follows the card the way the safety add-on does: it watches the page's
   `/api/mission` answers (cloned, never changed), picks the one for the site chosen in `#mSite`, and passes
   on the card's Deep Space Network box. Before the card loads it shows the opening example.

### Tests

```
cd mvps\slipday
.venv\Scripts\python.exe -m pytest tests\addons\test_relay.py -q
```

Result: **23 passed** (about 2 s). The whole `tests\addons` folder: **99 passed**. The four tests that use the
real 80 m terrain skip if it is not installed. The router is mounted in a small test app, so `api.py` is not
touched.

The tests cover: the stored source files and their sha256; every number used appears in the source text; the
period from the propagated positions (30.0 h) against the source and Kepler's law; distance and altitude at
apolune and perilune against Table 1; Table 2 against Table 1 in the Moon frame at J2000; apolune far south;
SV-1 and SV-2 in one plane, half an orbit apart; the Moon blocking the relay-to-Earth line; Earth hours equal
the app's own slip grid (station rule on and off); hour counts add up; bad input refused; the three sites'
numbers above on the 80 m terrain; what ends the opening example's margin.

Browser check (scratch script, not shipped): the real app plus this router on port 8150, the full
`index.html` with the container and script added in memory, Chrome at 375 px phone width through the
project's puppeteer-core. All 11 checks passed: sentence and counts match the API, 336 hour cells, the
one/two toggle works and its state is announced, nothing wider than the screen, buttons at least 44 px tall,
it follows the card when its site changes, no script errors. The server was stopped by PID afterwards.

Side effects to know about: running the app's own code (the scripts that made the numbers above, and the
full page in the browser check) let the app write skyline cache files to `data/horizon_cache/`, its normal
cache, and my first pytest run updated `.pytest_cache/`. Both are caches the app or pytest rebuilds. Another
agent was working in the same folder, so I did not delete any of them; none of the entry's own files was edited.

### What it cannot tell

- **No relay is in service.** NASA calls this design "not final"; Intuitive Machines makes the final choice.
  The number of satellites, their orbits and their start dates may all change.
- **Where a relay is at a given hour is not predicted.** The model is two-body (fixed ovals around the Moon,
  no other pulls). NASA's document says its orbits need a full force model to stay as designed, and the
  window here is about 100 days before the document's start date. So the hour colours show the kind of
  coverage, not a timetable. The spread over 144 starting positions shows how much that matters: not at all
  for two relays at these three sites, a lot for the one-relay slip margin at C1 and NR101.
- **Only one orbit plane.** The source has five satellites in three planes; this uses the one pair that
  shares a plane, and SV-1 alone. All five would cover at least as much.
- **In view is not a working link.** Nothing here models radio power, antennas, data rates, the relay's own
  link to Earth beyond "the Moon is not in the way", or who may use the service. Many landers have no relay
  radio at all.
- **Slip margin at the stated point only**, not the card's 13-point, two-grid check.
- **The 100-hour contact need is illustrative**, as everywhere in Slipday. With relays, sunlight or the
  landing hour becomes the limit instead.
- The station rule for the relay path uses the Deep Space Network's three complexes, as the card does. The
  source says the relay service is bought through NASA's Near Space Network, so other ground stations may
  carry it; they could only add hours. In this window the rule made no difference.
