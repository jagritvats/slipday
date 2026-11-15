# Slipday: seven slides

Seven slides including the title, the limit in last year's submission guide. Each slide below is the text
that goes on it (the title, at most five lines, one picture), followed by a short speaker note in italics.
Every figure was measured on NASA's LOLA terrain, on the finest grid that covers each place (5 m site
models, the 20 m mosaic out to 80° S, 80 m beyond), on 15 Nov 2026. Pictures are frames of the screen
recording (`slipday_draft_voiceover.mp4`) and the screenshots in `../screenshots/`.
`[TEAM NAME]` and `[MEMBER NAMES]` are placeholders for the participant.

## 1. Slipday: if the launch slips, can we still land here?

**Pick a south-pole site on the map, pick a date: see the Sun and the Earth over the real skyline, and how many days the launch can slip.**

- `[TEAM NAME]` · `[MEMBER NAMES]`
- Lunar Landing Site Navigator · NASA Space Apps Challenge 2026
- Live link: https://slipday.synpse.app

Picture: `../screenshots/overhaul/after_1280_light.png` (the first screen: map, date, sky chart, "Yes, and the
launch can slip up to 8 days").

*Note: one sentence: you choose a site and a landing date; it says Yes, Not sure or No, and for how many days of
launch delay that stays true.*

## 2. Map first: the Sun and the Earth over the real skyline

- "Hardware development challenges, launch delays, or other factors often force mission planners to
  reconsider their original landing date and location." (official challenge text)
- Its objective: "Display the positions of the Sun and Earth relative to the horizon at a selected landing site on
  a chosen date." Slipday's first screen: click the south-polar map or search, pick a date and time, read the chart.
- At the opening example (89.010 S, 122.764 E, 18 Nov 2026), on NASA's 5 m terrain: "Sun 2.3° high, 1.0° over the
  skyline; Earth -0.2° high, 0.6° over the skyline".
- A time slider, a sky view (what you would see standing there) and a 3-D view of the ground with its shadows.
- Near the pole the Sun and the Earth skim the horizon, so ground 131 km away can decide the answer.

Picture: the sky chart (recording, 5 to 10 s).

*Note: the page says which terrain grid each answer used: "on 5 m terrain", "on 20 m terrain" or "on 80 m terrain".*

## 3. One decision path: Answer, How sure, Why, What to do

- **Answer**: landing 18 Nov works, and the launch can slip up to **8 days**.
- **How sure**: 13 of 13 touchdown points within 100 m pass on 5 m terrain; the 20 m grid and a finer sampling agree; slope 4.9°.
- **Why**: a slip of 9 days fails: only 95 of the 100 hours of Earth contact needed, because the Earth goes behind
  ground 131.4 km away (the 100 hours are an illustrative need, and the page says so).
- **What to do**: wait for a later good date or move to another south-pole site, ranked, with verdicts and distances;
  and the real missions facing this choice: VIPER lands at Mons Mouton by late 2027, 167 km from this site.
- Next monthly windows: "Dec 17 ✓ 6 d · Jan 16 ✕ sunlight · Feb 14 ✕ Sun down, sunlight": January and
  February fail on sunlight, 217 and 148 hours against 240 needed (the polar season).

Picture: the decision path (recording, 14 to 17 s).

*Note: "Compare sites side by side" puts up to four sites in one table, the same "launch slipped by N days" applied to all.*

## 4. Is it safe to land there? Slope and the chance of a safe touchdown

- Slope at the 13 touchdown points against NASA's limit for its crewed lander (8° from upright; 5° is the goal):
  4.9° at the opening example, on 5 m terrain.
- Chance the ground under the lander is under 8°, for three assumed lander accuracies: 100 % (precision lander),
  93.7 % (CLPS-class) and 82.9 % (unguided) at the opening example.
- Real landing replayed: IM-1 Odysseus planned about seven days (168 sunlit hours): Yes, 1 day of slip margin, on
  NASA's 20 m terrain. With the roughly ten days in NASA's press kit (240 hours): No, terrain leaves 207 hours.
- Chandrayaan-3's published 14 days would give No too. These are replays of published plans, not a confirmation of the model.

Picture: "Flat enough to land?" (recording, 17 to 20 s).

*Note: slope only; no boulder data. The three lander accuracies are assumptions sized from one published figure each.*

## 5. The slip-day map: whole map and close-up

- **Whole map**, 80° S to the pole, a point every 2 km (92,416 points): for the opening plan 95.4 % cannot land on
  the planned date; 84 points survive 5 days of slip or more; the largest margin is 8 days.
- **Close-up**, 14,400 points 500 m apart, each re-checked at 13 touchdown points: 574 of 733 passing points keep a
  margin at all 13; 159 lose it; 343 survive at least one day of slip.
- Re-checked on NASA's 20 m grid: 639 of 733 points agree (87.2 %); the 94 that differ are marked with a red cross.
- **Our finding: coarse terrain is optimistic, not noisy.** Over 14 weekly dates, 452 of the 454 points where 80 m
  and 20 m disagree are called landable on 80 m and rejected on 20 m. Shackleton ridge, longest darkness: 194 h on
  80 m, 110 h on 20 m, 112 h published. (5 m covers only two sites.)

Picture: the close-up slip-day map with its legend (recording, 24 to 27 s).

*Note: the whole map is checked at each point only; the close-up adds the landing scatter.*

## 6. Plan ahead: regions, missions, relay, years

- NASA keeps several of its nine south-pole landing regions "to increase flexibility in launch timing". On 78
  published candidate sites, 2027 to 2030, with sunlight alone the best single region allows a 6.25-day stay at 45 %
  of landing times, the best three at 89 %; with the illustrative 100 hours of Earth contact added, 26 % and 37 %.
- **Missions board**: Griffin-1 (late 2026), IM-4 (2027), VIPER (late 2027), Artemis IV (early 2028): what a week
  or a month of slip does to each. VIPER: a week's slip keeps 14 of its 124 good landing times, a month keeps 102.
- **Relay**: with the Earth alone, 311 hours of contact in 14 days; with two relay satellites, 336 of 336.
- **Atlas**: which years from 2027 to 2035 suit a landing in each region.

Picture: the nine-region calendar (recording, 20 to 24 s).

*Note: shares of landing times every 6 hours, not real launch opportunities; the Earth need is illustrative; the
relay orbit is NASA's reference design, not a live service.*

## 7. Can you trust it, what it does not do, and play

- Every answer names the NASA terrain grid it used, and is checked against the LOLA team's own maps: sunlight within
  0.8 points, Earth view within 0.97. Sun and Earth directions match JPL Horizons to 0.00001°.
- 92,416 terrain skylines, 720 rays each out to 300 km, on four LOLA grids (80 m to 1.9 km); a worked-out answer
  comes back in 0.04 s.
- Computes on the finest LOLA grid at each place: 5 m at two sites near Shackleton, 20 m out to 80° S, 80 m beyond.
- Limits: no power or thermal model; no boulder data; the Earth margin of the opening Yes is 0.64° and no published
  link mask exists; a Yes holds for the stated landing scatter only.
- **Be the mission planner**: a five-scenario game for students, from a small slip to a low-Sun January.

Picture: `../screenshots/desktop_1280x800_valid.png`.

*Note: open source (Apache-2.0), one Python process.*
