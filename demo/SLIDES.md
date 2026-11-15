# Slipday: seven slides

Seven slides including the title, the limit in last year's submission guide. Each slide below is the text
that goes on it (the title, at most five lines, one picture), followed by a short speaker note in italics.
Every figure was measured on NASA's LOLA grids; the commands are in the project's results files. Pictures
are frames of the screen recording and the screenshots in `../screenshots/`.
`[TEAM NAME]` and `[MEMBER NAMES]` are placeholders for the participant.

## 1. Slipday: can this mission still land if the launch slips?

**A go / no-go check for lunar south-pole landing sites, on real LOLA terrain.**

- `[TEAM NAME]` · `[MEMBER NAMES]`
- Lunar Landing Site Navigator · NASA Space Apps Challenge 2026
- Live link: once the app is deployed

Picture: `../screenshots/desktop_1280x800_top.png` (the card: "Yes, it survives a slip of up to 8 days").

*Note: one sentence of what it is: you type a site, a landing date and what the mission needs; it says Yes,
Not sure or No, for every day and every launch window the date could move to.*

## 2. The problem: the date moves, and near the pole that changes everything

- "Hardware development challenges, launch delays, or other factors often force mission planners to
  reconsider their original landing date and location." (official challenge text)
- Its firm objective: "Display the positions of the Sun and Earth relative to the horizon at a selected
  landing site on a chosen date." Slipday's first screen draws exactly that.
- Near the pole the Sun and the Earth skim the horizon: a ridge 130 km away can end Earth contact for 13 days.
- NASA picks Artemis III sites only "after it identifies the mission's target launch dates", and keeps
  several regions "to increase flexibility in launch timing" (NASA 2024; LPSC 2026).

Picture: `../screenshots/desktop_1280x800_why_flip.png` (Sun and Earth against the terrain skyline).

*Note: the question a planner asks after a slip is not "where is the Sun", but "does our plan still work".*

## 3. Real slips step a month at a time, and the card follows them

- A lander gets a launch window of a few days each month, built around the landing: "each month has a window
  around three to six days" (Intuitive Machines on IM-1, Spaceflight Now, Oct 2023).
- A slip inside the window leaves the landing fixed (IM-1 launched on day 2 of three and still landed on
  22 Feb); a missed window moves it about 29.5 days (our inference from these sources, not a published rule).
- The card: "Dec 17 ✓ 6 d · Jan 16 ✕ sunlight · Feb 14 ✕ Sun down, sunlight" for the opening example
  (89.010 S, 122.764 E, landing 18 Nov 2026: Yes, 8 days of slip margin).
- Why January and February fail: sunlight, 217 and 151 hours against 240 needed: the polar season moves
  the light (Earth contact stays above its 100 hours). In January no hour within 3 days works there, but 13
  of 20 other sites have a Yes hour within 3 days, 11 of them fragile (Sun under 0.27 degrees above the
  skyline at a touchdown point). Steadiest: a map point at 89.498 S, 137.663 W, 15 Jan, 4 days.

Picture: the card's window line (recording, 0 to 5 s).

*Note: day-by-day slips measure how much of the lunar day is usable; monthly windows are how real dates move.*

## 4. Proof on a real landing: IM-1 Odysseus

- Planned about seven days on the surface (168 sunlit hours): the card says Yes, one day of slip margin, for
  the February window it flew (22 Feb 2024).
- The January window it missed: Yes at the same time of the lunar day (a modelled date); across the days of
  the window IM-1 published, Yes from 21 Jan, No on 17 to 20 Jan (before local sunrise).
- With the roughly ten days in NASA's press kit (240 hours) the answer is No: terrain leaves 208 sunlit hours.
- Chandrayaan-3's published 14 days would give No too. These are replays of published plans, not
  predictions and not a confirmation of the model.

Picture: `../screenshots/desktop_1280x800_real_missions.png` (IM-1 table).

*Note: Earth-contact hours are illustrative in every example; the page says so.*

## 5. How many of NASA's nine regions must stay open, and VIPER in late 2027

- NASA: "more than one landing regions must be maintained" (LPSC 2026 abstract).
- 78 published candidate sites (Wueller et al. 2026), landing times every 6 h, 2027 to 2030, 6.25-day stay:
  the best region is open at 28 % of them, the best three 40 %, all nine 44 %.
- That 44 % ceiling comes from the illustrative 100-hour Earth need; with sunlight only: 48 %, 91 %, 92 %.
- The season comes 18.4 days earlier each year; our ephemeris gives the paper's midsummer dates to the day.
- VIPER, on an illustrative point of Nobile's west rim at local sunrise: every window from September to December
  2027 is No (Earth behind the skyline at touchdown); next clear yes 31 Dec 2027.

Picture: `../screenshots/desktop_1280x800_regions.png` (calendar of the nine regions).

*Note: shares of landing times every 6 hours, not real launch opportunities; 80 m grid. Against the paper's own
sunlight figures, about two in three of 312 comparisons agree within a day and about three in ten differ by more
than 3 days (our terrain model is coarser than the paper's).*

## 6. The map only Slipday draws: slip margin with landing scatter, on two grids

- Each of 14,400 points 500 m apart, re-checked at 13 touchdown points: 574 of 733 passing points still pass at
  all 13 on the planned date (100 m scatter), 159 lose it; 343 survive at least one day of slip.
- Re-checked on NASA's 20 m grid: 87 % agree (86.6 % over 14 weekly dates); 452 of 454 disagreements are the
  80 m map being optimistic. Worked out for any date on request.
- Hours to ride through: slip 8 days and the night the lander meets grows from 20 to 179 hours (whole runs;
  not a battery model).
- 20 points survive a slip beside permanent shadow (dark ground, not proven ice).

Picture: `../screenshots/desktop_1280x800_map_scatter.png` (red crosses: where 20 m disagrees).

*Note: this is the part judges will not have seen elsewhere: how many slip days each spot survives, with scatter.*

## 7. What was checked, what it does not do, next

- Sun and Earth directions against JPL Horizons: 0.00001°; DSN station geometry: 0.0006°; sunlight against
  the LOLA team's maps: 0.8 points on ordinary terrain.
- Finer terrain: on the LOLA team's 5 m site models the opening example is still Yes with 8 days; the
  Shackleton ridge is Not sure, as on 20 m.
- Extra checks beside the answer: slope at the 13 touchdown points against NASA's 8° lean limit (opening example about
  5°, right at the 5° goal; IM-1 12.2°, too steep), the chance of a safe touchdown, relay satellites (311 h of contact
  with the Earth alone, 336 of 336 with two), a 2027 to 2035 region atlas, sound, and a student game.
- Limits: 80 m terrain by default (20 m and 5 m checked separately); no power or thermal model; the Earth margin of the opening
  Yes is 0.64° and no published lander-side mask exists; a Yes holds for the stated landing scatter only.
- Next: the 20 m grid as default, each mission's landing ellipse and window dates, a north-polar grid.

Picture: `../screenshots/desktop_1280x800_valid.png`.

*Note: open source (Apache-2.0), one Python process; the public link must serve the 80 m grid (badge says
"80 m/px").*
