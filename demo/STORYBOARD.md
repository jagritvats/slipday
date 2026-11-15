# Storyboard for the 30-second video

Total running time: 29 seconds (the limit is 30; one second is left spare). The inputs and the objective line come first, then the slope line and the regions calendar; the closing frame is 2 s. The draft video
is a **screen recording of the running page** (recorded in a headless browser,
1280x800 at twice the pixel density, on the real LOLA 80 m grid, 15 Nov 2026; each step is zoomed into the part of the page it shows, so the text is readable): `node scripts/record_demo.js http://127.0.0.1:8100/ <dir>`
clicks through the steps below and writes the frames with their times; `python scripts/make_recorded_video.py
<dir> --ffmpeg <path>` takes the first seconds of each step as this table gives them, puts each caption in a
band under the picture (the band covers nothing of the page) and adds a closing frame of text. Nothing is
drawn into the page. Captions are the English subtitles; no narration is needed. Every number in a caption
is on the screen in its step. The challenge name opens the first caption and the team name closes the last
one; `[TEAM NAME]` and `[PUBLIC LINK]` (on the closing frame) are the only placeholders. Older stills
(`scripts/storyboard.js`, `scripts/make_draft_video.py`) are kept as a fallback.

| # | Time | Step | Caption (one or two lines, on screen) |
|---|---|---|---|
| 1 | 0-5 s | step `answer` (zoomed on the input sentence and the verdict): "Land at Slip-robust ridge point ... on 18-11-2026 ... It needs 240 sunlit hours and 100 hours of Earth contact"; "Yes, it survives a slip of up to 8 days" | "Lunar Landing Site Navigator. Land here on 18 Nov 2026. If the launch slips, can we still land? Yes, with 8 days of slip margin." |
| 2 | 5-10 s | step `objective` (zoomed on the objective line and the skyline chart): "Challenge objective ... Sun azimuth 315° (NW), 2.3° above level, 1.2° above the skyline · Earth azimuth 231° (SW), -0.2° above level, 0.6° above the skyline" | "The challenge objective: at touchdown the Sun is 1.2° and the Earth 0.6° above the real skyline." |
| 3 | 10-14 s | step `why` (zoomed on the day banner and the chart): a click on the first day that fails; "Land on 27 Nov 2026 (launch slipped 9 days): No"; "The Earth goes behind ground inside Mons Mouton, 131.6 km WSW" | "Click the day that fails: on day 9 the Earth sets behind ground 131.6 km away." |
| 4 | 14-17 s | step `view3d` (zoomed on the 3-D view): WebGL view playing through the landing window | "The real ground in 3-D, from NASA's LOLA laser altimeter: the shadows move." |
| 5 | 17-20 s | step `safety` (zoomed on "Is the ground flat enough?"): "Flat enough to land? Yes"; "the steepest is 4.9°, under NASA's 8° limit"; "8° of upright (5° is the goal)" | "Flat enough to land? The steepest touchdown point is 4.9°: inside NASA's 8° limit, right at its 5° goal." |
| 6 | 20-24 s | step `regions` (zoomed on the calendar and the coverage table): nine rows of open times, 2027 to 2030; "Nobile Rim 1 ... 28.1%"; "Malapert Massif ... 40.1%" | "NASA must keep several regions: the best one is open at 28.1% of landing times, three at 40.1%." |
| 7 | 24-27 s | step `map` (zoomed on the map and its legend): red 20 m crosses; "639 of 733 re-checked points agree" | "The slip-margin map, re-checked on NASA's 20 m grid: 639 of 733 points agree." |
| 8 | 27-29 s | step `closing`: closing frame (text only: the name, `[PUBLIC LINK]` and the challenge) | "Slipday, by [TEAM NAME]." |

Notes for whoever records it:

- The recording follows the table above. The frame notes below were written for an earlier set of stills and
  still describe what each view shows; where they disagree with the table, the table holds. The ground that
  ends the margin is named "inside Mons Mouton"; the year ribbon reads 41 clear yes (3 not sure) with the
  station rule on.

- Frames 1, 2, 4 and 5 are one page (link in `scripts/storyboard.js`, constant `C1`); frame 3 is the link
  `IM1` in the same script, or one click on "IM-1 Odysseus" under "Try a real landing". A screen recording
  of that page scrolled down, with two clicks, gives the same sequence live.
- The opening example is the first of the map's scatter-robust points whose card is a clear Yes on the 80 m
  grid and on NASA's 20 m grid. It is not a published site.
- Frame 1: the headline reads "Yes, it survives a slip of up to 8 days if it touches down within 100 m of
  the target". Directly under it, on a blue band: "Both grids agree. On the 20 m grid:
  Yes as planned (13 of 13 touchdown points), 8 days of margin." Keep that band in shot; it is what the
  subtitle's "NASA's finer grid agrees" refers to. Under it, the Earth margin: "the Earth's centre is
  0.64° above the skyline at touchdown ... Yes up to an Earth mask of 0.60°; Not sure from 0.65°, No from
  0.70°" with the tag "masks illustrative", and "Contact also needs a DSN station". Under the inputs, "A
  year of landing dates: 41 clear yes of 365 (3 not sure); none in Jan to Aug 2027" (with the station rule
  on, as the page opens; 42 and 2 without it). The
  lander classes and landing circles are in their own panel under the slip grid, not in this frame. The
  subtitle reads none of these out: it carries the challenge name and one number.
- Frame 2: the head of the skyline view reads "landing Nov 27 (slip of 9 days)". The text under the chart
  reads "A slip of 9 days (landing 27 Nov) fails: at the target itself the Earth is hidden for 241 of the
  336 hours (from 30 Nov 23:00 UTC), leaving 95 hours of Earth contact of the 100 needed. The Earth goes
  behind ground 131.59 km away towards azimuth 244 deg (west-south-west), at 85.996 S, 19.485 E (488 m
  above the site), inside Mons Mouton (130 km across; IAU name). Ended by the Earth-contact need
  (95 of 100 h), an illustrative figure, not a published requirement." The first line under
  the chart is the need that ends the margin and "The Earth goes behind ground inside Mons Mouton,
  131.6 km west-south-west"; the full sentence is one click away. The name comes from the IAU gazetteer: the point is at 78 % of Mons Mouton's radius and on the rim
  line of Malapert crater (98.6 % of its radius); the full sentence names both. If the video is narrated, say that
  the need that ends the margin is an illustrative one.
- Frame 3: the headline reads "Yes, it survives a slip of up to 1 day"; the text gives 208 sunlit hours.
  The note under the card says where the 168 hours come from (IM-1 was planned for about seven days of
  surface operations; NASA's press kit says approximately 10 days, and with 240 hours the answer is No)
  and that the 100 hours of Earth contact are illustrative. The subtitle gives both figures (seven days
  fits, ten would not); keep the note in shot so the viewer can read where each comes from. Do not say
  the tool "predicted" or "confirmed" the landing: it is a replay with the mission's published plan, and
  with the other published figure the card says No.
- Frame 4: real LOLA heights drawn twice as tall (the view says "Heights exaggerated 2x"; 1x is one click
  away), smooth shading with light from the Sun's true direction, contour lines every 100 m, the landing
  point and its 100 m scatter ring; the dark ground is in shadow at the time shown, ray-cast on the same
  grid. The script takes nine more screenshots of the same
  view (`04_terrain_3d_01.png` to `04_terrain_3d_09.png`), each with the time slider moved on through the
  first 60 % of the landing window and the view turned by 15 degrees; the draft video plays the ten in
  this frame's five seconds, so the shadows are seen to move. They are screenshots of the app, one after
  another, not an animation made elsewhere. The brightness of the sunlit slopes is illustrative
  (the view's folded caption says so). In a screen recording, drag to turn it and press Play to step the
  shadows through the landing window.
- Frame 5: the legend reads "574 of the 733 map points that pass on the planned date keep a slip margin at
  all 13 touchdown points; 159 lose it. Largest margin: 9 days at a single point, 8 days with the
  scatter." Red crosses mark the points where NASA's 20 m grid disagrees (one of 14 weekly map dates;
  the legend gives the share that agrees).
- Frame 6: the closing frame, text only. Replace `[PUBLIC LINK]` with the deployed address and
  `[TEAM NAME]` in the caption with the team's registered name; these are the only two placeholders. The tooltip is on the point with the largest surviving margin, which is the opening example
  (89.010 S, 122.764 E; the orange marker 1 sits on it). The map checks the 13
  touchdown points only; the coarser grid and the finer near-field sampling of the card are not part of
  it (the note under the map says so).
- The validation tiles are no longer a video frame; they are on slide 6. If a validation line is wanted
  in a longer cut, read one number only (sunlight agrees with the LOLA team's maps within 0.8 points on
  ordinary terrain) and say that it is worse on ridges.
- The 29 seconds show the inputs and the verdict, the objective line, day 9, 3-D, the slope line (an add-on),
  the regions calendar and the map. The windows step and IM-1 are on slides 3 and 4 and in the explainer.
- The frames were taken on the 80 m grid. On a 240 m deployment frame 1 reads "Yes, 7 days" for a landing
  within 240 m, not "Yes, 8 days" within 100 m, and has no 20 m line: record
  against a server that has the 80 m grid, and make sure the public link serves it too (the badge at the
  top right of the page says "Real Moon terrain: NASA LOLA laser heights, one every 80 m (80 m/px)").
- If any image in the video is AI-generated it needs a visible "AI-generated" watermark under last year's
  rules; these frames are screenshots of the app and are not.
