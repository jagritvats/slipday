# Add-on: Listen and play (sound, screen reader and keyboard help, and a game for students)

Written 15 Nov 2026 for the integrator. No existing file was changed.

## What it does, in plain words

**1. Listen to the landing window** (`static/addons/listen.js`, container `#addon-listen`)
- A **Play the sound** button turns the landing window on the main card into about 15 to 30 seconds of sound.
  - The 14-day window takes about 22 seconds.
  - The sound is made in the browser with the Web Audio API. There are no audio files and no library.
- The two tones:
  - The **high, clear tone is the Sun**. The **low, soft tone is the Earth**.
  - The higher the body stands above the skyline, the higher its tone.
  - A tone goes quiet while the ground hides that body.
  - A soft tick marks each new day.
- The controls:
  - Sound never starts by itself.
  - There is a visible **Stop** button, and Escape also stops the sound.
  - There is a **Volume** slider that works with the arrow keys.
- **Read it as text** gives the same window in words. So does a live text line, which screen readers read aloud as each day plays. Examples:
  - "Day 1, touchdown: Sun up, 1 degree above the skyline. Earth up, 0.5 degrees above the skyline."
  - "Day 12: Sun sets behind the ground to the south, then rises over the ground in the south. Earth stays up."
- "Day by day, in words" lists every day and ends with the hour counts and the card's need.
- A small strip shows, for each day, how much of the day the Sun and the Earth are up. Screen readers skip it, because the text says the same.
- **Where the data comes from:** the page's own `/api/why` answer for the site, date and day of slip on the card. That answer gives the Sun and Earth positions every hour (JPL DE421) and the skyline ray-cast from LOLA. Nothing is a new model.
  - **The Sun tone** uses the card's rule: half the disc above the skyline.
  - **The Earth tone** uses a second `/api/why` call with `earth_stations: false`, so "hidden" means hidden by the ground only.
  - The spoken summary also gives the card's own count with the radio-station rule. Example: "counting that, the card finds 311 hours of contact".
  - Pitch uses the height above the skyline, worked out in the browser from the `skyline` array. Between 0 and 6 degrees the pitch rises by up to 1.6 octaves for the Sun and 1.2 for the Earth; above 6 degrees it stays the same.

**2. Screen-reader and keyboard pass on the main card** (also in `listen.js`; it works on `#missionOut` whether or not `#addon-listen` exists)
- When the card changes, a hidden live region (`#sd-a11y-status`) says a short summary. Example: "Answer for Slip-robust ridge point …, landing 2026-11-18 at 00:00 UTC: Yes. It survives a slip of up to 8 days if it touches down within 100 m of the target." It also reads the finer-grid line when there is one.
- When the monthly windows arrive, it says them too. Example: "Next monthly launch windows: Landing on 2026-12-17 13:00 UTC: Yes, 6 days of margin. …"
- It turns off `aria-live` on `#missionOut` at run time. The card rewrites all of its HTML at each update, and a screen reader would read out the whole list of buttons.
- It adds labels:
  - on the verdict: `role="group"` and an `aria-label`, with `tabindex="-1"` so it can take focus;
  - on the day strip (`#vstrip`): `role="group"` and an `aria-label`;
  - on the window buttons and the "next good date" buttons: `aria-label` (for example "Make 17 Dec the planned landing date").
- **Arrow keys on the day strip:** the strip becomes one Tab stop instead of 60. Left, Right, Home and End move along it, and Enter opens "why" as before.
- Two buttons in the Listen panel: **Go to the answer on the main card** (moves focus to the verdict) and **Say the answer again**.

**3. Be the mission planner** (`static/addons/planner_game.js`, container `#addon-game`)
- A short intro for ages 12 and up explains a slip, sunlight for power and the Earth in view for radio. It uses no jargon.
- **Each round:**
  - The launch slips by a random 1 to 12 days.
  - Past 12 days the opening plan is in the lunar night almost everywhere, and every round would be "all No". That is why the range stops at 12.
  - The student picks one of three sites: the site on the card and two others from the page's own site list. The page's list is the sites the card was worked out for. If there are fewer than two others, the curated south-pole sites from `/api/sites` are used, without the "always dark" ones.
- **Then the real answer for all three:**
  - The verdict comes from `/api/mission`, with the card's plan and rules, `days[slip].verdict`.
  - Each answer has one plain sentence of reason, built from the server's numbers. Examples:
    - "The Sun goes behind the ground 2 km away to the west on day 7 of the 14 and stays hidden to the end, so it gets only 161 hours of sunlight for power; it needs 240."
    - "The Earth goes behind the ground 132 km away to the west-south-west (in Mons Mouton, on the rim of Malapert crater) on day 2 of the 14 …"
  - The ground, its direction and its distance come from `/api/why` for that day of slip, called with the radio-station rule off.
  - Hour counts come from `/api/mission`.
  - "Not sure" says how many of the 13 touchdown spots pass.
- **Scoring:** five rounds. A point when the pick is as good as the best of the three (Yes beats Not sure, and Not sure beats No). When all three are No, the game says a planner would have to wait for a later date.
- **Where the score lives:** the score is kept only in the browser. The best score is kept in `localStorage` when that is allowed.
- **Phones and keyboards:** it works at phone width, where the choices stack. All of it works with the keyboard, and the result is said in a live region.

**How the add-ons know the plan without touching `app.js`.**
- Both files install, once, a small read-only wrapper around `window.fetch` (`window.SlipdayAddonTap`).
- It notes the bodies and answers of the page's own `/api/mission` and `/api/why` calls.
- It never changes a request or a response, and it never sends one for the page.
- The add-ons' own calls carry an `X-Slipday-Addon: 1` header and are not recorded.
- The same block is in both files, so either file works alone.
- `static/addons/safety.js` (another add-on) also wraps `fetch`. Both only watch, so the two chain safely in either order.
- Before the page has asked for anything, the plan is the page's opening example: `robust_pick`, landing 18 Nov 2026 00:00 UTC, default need and rules.

## What to add to `static/index.html`

1. In `<head>`, after `<link rel="stylesheet" href="/static/view3d.css">`:
   ```html
   <link rel="stylesheet" href="/static/addons/addons.css">
   ```
   If it is left out, the scripts add this link themselves.
2. Right after the mission card section closes: the `</section>` that follows `<div class="mOut" id="missionOut" …>`, before `<section class="panel" aria-labelledby="h-slip">`:
   ```html
   <div id="addon-listen"></div>
   <div id="addon-game"></div>
   ```
   The game can go lower on the page if you prefer, for example just before `<footer>`. Each container is independent.
3. After `<script src="/static/app.js"></script>`:
   ```html
   <script src="/static/addons/listen.js"></script>
   <script src="/static/addons/planner_game.js"></script>
   ```
   Plain script tags: no `defer` and no `type="module"` are needed. They must load before the page's first API call. Placing them at the end of `<body>` (with app.js) does that, because app.js makes its first call on `DOMContentLoaded`.

`static/addons/demo.html` is a copy of today's `index.html` with exactly these three additions. Use it to see the placement.

## API

- **No new endpoint.** No router module is needed for the optional-router loop in `api.py`.
- `slipday/addons/play.py` was not written.
- `slipday/addons/__init__.py` was already there, empty; I left it unchanged.
- Endpoints used, all unchanged:
  - `GET /api/sites`;
  - `POST /api/mission`;
  - `POST /api/why`, with the page's body, and again with `earth_stations: false`.

## Changes to existing files I recommend but did not make

1. `static/index.html` line 50: `#missionOut` has `aria-live="polite"`. The whole card is re-rendered each time, so a screen reader reads out dozens of buttons. Set it to `aria-live="off"` and keep a short summary region; listen.js does both at run time today.
2. `static/app.js` `renderMission()`: the 60 day-strip buttons are 60 Tab stops. Use a roving `tabindex` (one stop, with arrow keys) in the app itself; listen.js adds it at run time. Do the same for `#vstrip2`. It is already `aria-hidden`, which is right.
3. `static/app.js`: the card tooltips (`showTip`) open on pointer only. A keyboard user gets the short `aria-label` but not the hour counts in the tooltip. Add focus and blur handlers that show the same tip, or put the counts in the label.
4. `static/index.html`: `#ribbon` (`aria-live="polite"`) has the same whole-block re-render problem as `#missionOut`.
5. `static/app.js`: dispatch an event when the plan or the card changes, for example `document.dispatchEvent(new CustomEvent('slipday:card', {detail: {...}}))`. Add-ons could then listen to it instead of wrapping `fetch`.
6. The south polar map (`#polar`) adds a site on click only. The coordinate inputs are a keyboard route, but the map does not say so. Add a line such as "or type the coordinates below".

## Test

```
cd D:\dev\projects\spaceapps26\spaceapps_handoff\mvps\slipday
node tests\addons\listen_game_check.mjs
```

- **How it runs:**
  - It starts its own server on port 8131 (`ADDON_PORT` changes it, within 8130 to 8139).
  - It opens `/static/addons/demo.html` in headless Chrome (Edge as a fallback), using puppeteer-core from `reviews_local\work\nodetools`.
  - At the end it stops the server by PID, with `taskkill /T`, because the venv `python.exe` starts a child process.
  - `ADDON_BASE=http://127.0.0.1:8130` points it at a server that is already running instead.
- **Result on 15 Nov 2026, fresh server: 25 passed, 0 failed** (about 2 minutes). It checks:
  - all 7 add-on controls exist, and each is reached with the Tab key;
  - the card answer and the next monthly windows are announced in the live region;
  - the verdict is labelled and `#missionOut` is no longer read out whole;
  - the day strip is one labelled group with one Tab stop, and the right-arrow key moves along it;
  - "Go to the answer" moves focus to the verdict;
  - "Read it as text" fills the live region and one line per day;
  - day 1 in words matches the API's touchdown flags;
  - the hour counts in words equal the API's (Sun 314 h, Earth 311 h of 336 for the opening example);
  - the volume slider works from the keyboard;
  - Play moves the live text from day to day: day 1, 2, 3 were heard;
  - Stop, Escape and the end of a full play each give the right text;
  - the game runs five rounds;
  - each round offers the planned site and two others;
  - **all 15 verdicts shown equal a separate `/api/mission` call** for that site and slip, landing date included;
  - **all 15 reason sentences use the API's hour counts**, and their direction word matches a hiding stretch in `/api/why`;
  - pressed at once after loading, Listen plays the site the card shows. A bug here was found and fixed: it used to take the first mission card to come back;
  - at 375 px nothing in the add-ons is wider than the screen, and the choices stack;
  - with reduced motion there are no transitions;
  - there are no script errors on the page.

There is no Python test, because no Python was written.

## What is not done

- **No test with a real screen reader** (NVDA, JAWS, VoiceOver, TalkBack). The checks are on the page's structure in headless Chrome. How a screen reader paces the day lines while the sound plays, and whether it skips some, needs a person.
- **No person has listened to the sound yet.** The test runs muted: it proves the audio clock runs and drives the text, not that the tones sound clear. The tone ranges and the 1.6 seconds per day are first choices.
- **No speed setting.** A "slow" option (about 40 seconds) would help screen-reader users keep up with the day lines.
- **The Earth tone ignores the radio-station rule** (on purpose: it follows the ground only). The summary sentence gives the card's count with the rule.
- **The game uses the card's plan.** Change the plan on the card, then press Start to play another one. Mid-game changes are ignored until the next Start. The "two other sites" come from the page's site list, not from the slower "Other sites, other hours" search (`/api/window-options`, a minute or more the first time).
- **`static/addons/addons.css` is shared** with the other add-on agents. My rules sit between the `listen / planner game` marker comments and are scoped to `.sd-addon` and `.sd-sr`. If another agent rewrites the file, put that block back. Without it the add-ons still work, unstyled.
- `demo.html` is a snapshot of today's `index.html`. It does not follow later changes.
