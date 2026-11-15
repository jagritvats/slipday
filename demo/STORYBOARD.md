# Storyboard for the 30-second video

Recorded on the overhauled page with the live terrain (5 m at the opening example, 20 m near the pole, 80 m beyond), 15 Nov 2026, evening.

Total running time: 29 seconds, 29.5 s with the voice (the limit is 30). It opens on the hook (NASA's need to keep several regions open, in numbers), then the tool: the answer, the objective line, day 9, the decision path's real missions, the slope line and the slip-day map; the closing frame is 2 s. The draft video
is a **screen recording of the running page** (recorded in a headless browser,
1280x800 at twice the pixel density, on the live LOLA terrain (5 m, 20 m and 80 m), 15 Nov 2026; each step is zoomed into the part of the page it shows, so the text is readable): `node scripts/record_demo.js http://127.0.0.1:8101/ <dir>`
clicks through the steps below and writes the frames with their times; `python scripts/make_recorded_video.py
<dir> --ffmpeg <path>` takes the first seconds of each step as this table gives them, puts each caption in a
band under the picture (the band covers nothing of the page) and adds a closing frame of text. Nothing is
drawn into the page. Captions are the English subtitles; no narration is needed. Every number in a caption
is on the screen in its step. The challenge name opens the first caption and the team name closes the last
one; `[TEAM NAME]` and `[PUBLIC LINK]` (on the closing frame) are the only placeholders. Older stills
(`scripts/storyboard.js`, `scripts/make_draft_video.py`) are kept as a fallback.

| # | Time | Step | Caption (one or two lines, on screen) |
|---|---|---|---|
| 1 | 0-4 s | step `regions` (zoomed on the calendar and the coverage table of NASA's nine south-pole landing regions): "26%" and "37%" in the first and third rows | "Lunar Landing Site Navigator. NASA must keep several south-pole regions open for Artemis IV: one works at 26% of landing times, three at 37%." |
| 2 | 4-9 s | step `answer` (zoomed on the page's question, the date and time, the site and the verdict): "Yes and the launch can slip up to 8 days" | "Land here on 18 Nov 2026. If the launch slips, can we still land? Yes, with 8 days of slip margin." |
| 3 | 9-13 s | step `objective` (zoomed on the sky chart): "Sun 2.3° high, 1.0° over the skyline"; "Earth -0.2° high, 0.6° over the skyline"; "On 5 m terrain" | "The challenge objective: at touchdown the Sun is 1.0° and the Earth 0.6° above the real skyline, on NASA's 5 m terrain." |
| 4 | 13-17 s | step `why` (zoomed on the day banner and the chart): "Land on Nov 27 (launch slipped 9 days): No"; "The Earth goes behind ground inside Mons Mouton, 131.4 km WSW" | "Launch slipped 9 days: No. The Earth sets behind ground 131.4 km away." |
| 5 | 17-21 s | step `missions` (zoomed on the four-step decision path): "VIPER on Blue Moon MK1 (landing by late 2027) plan to land at Mons Mouton, 167 km from this site" | "A real mission faces this: VIPER lands at Mons Mouton by late 2027, 167 km from here." |
| 6 | 21-24 s | step `safety` (zoomed on "Is the ground flat enough?"): "the steepest is 4.9°, under NASA's 8° limit" | "Flat enough to land? The steepest touchdown point is 4.9°: inside NASA's 8° limit and just inside its 5° goal." |
| 7 | 24-27 s | step `map` (zoomed on the close-up slip-day map and its legend): "Days of slip that all 13 touchdown points survive"; red 20 m crosses; "639 of 733 re-checked points agree" | "The slip-day map: how many days of slip each point survives. On NASA's 20 m grid, 639 of 733 agree." |
| 8 | 27-29 s | step `closing`: closing frame (text only: the name, `[PUBLIC LINK]` and the challenge) | "Slipday, by [TEAM NAME]." |

Notes for whoever records it:

- The recording follows the table above, on the overhauled page with the live terrain stack. Each step is
  zoomed on the part of the page it shows; the recorder opens the folded sections it films.
- Step 1: the verdict reads "Yes and the launch can slip up to 8 days, if it touches down within 100 m of
  the target", with the chip "on 5 m terrain". The year ribbon on the card reads 39 clear yes of 365
  (4 not sure); none in Jan to Aug 2027. The subtitle reads none of these out except the 8 days.
- Step 3: the day banner reads "Land on Nov 27 (launch slipped 9 days): No: only 95 hours of Earth contact
  of the 100 needed"; the ground that ends the margin is named "inside Mons Mouton, 131.4 km WSW".
- Step 4: the decision path ("If the launch slips: the answer, how sure it is, why, and what to do"); its
  line on real missions names VIPER on Blue Moon MK1, landing by late 2027 at Mons Mouton, 167 km away.
- Step 7: the close-up slip-day map (map area "Close-up of the pole", colour "days of slip the planned
  landing survives"), with its legend and the 20 m check line.
- The opening example is the first of the map's scatter-robust points whose card is a clear Yes on the 80 m
  grid and on NASA's 20 m grid; it is not a published site. The page now computes it on the 5 m site model.
- The validation tiles, the next windows and IM-1 are on the slides and in the explainer, not in the 29 s.
- Record against a server with the live terrain stack (`data/dem_live`): the verdict chip must read "on 5 m
  terrain". On a server with only the 80 m grid the opening answer is the same but other figures differ; on
  a 240 m deployment frame 1 reads "Yes, 7 days" for a landing within 240 m.
- If any image in the video is AI-generated it needs a visible "AI-generated" watermark under last year's
  rules; these frames are screenshots of the app and are not.
