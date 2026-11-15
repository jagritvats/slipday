# Voiceover draft

`../slipday_draft_voiceover.mp4` is the 29 s screen recording (hook first: NASA's need to keep several regions open, in numbers) (`../slipday_draft_29s.mp4`) with a spoken
track added; the original is unchanged. The closing frame is held 0.5 s longer, so it runs 29.5 s (limit 30 s).

The voice is synthetic: ElevenLabs text-to-speech, premade voice "Alice", model eleven_multilingual_v2,
15 Nov 2026. Mention it in the project's AI-use statement.

| Start (s) | Line |
|---|---|
| 0.15 | One region is not enough: NASA must keep several. |
| 4.15 | Launch slipped. Can we still land here? Yes, eight days to spare. |
| 9.15 | Sun and Earth against the real horizon, in numbers. |
| 13.15 | On day nine, the Earth sets behind distant ground. |
| 17.15 | VIPER lands at Mons Mouton by late 2027. |
| 21.15 | Flat enough to land? Only just. |
| 24.15 | The slip-day map, checked on finer terrain. |
| 27.15 | Slipday: know your margin. |

Re-cut in the UX pass and again in the last fixes (15 Nov 2026): the inputs and the objective line come first, then the slope line and the regions calendar; the closing frame is 2 s. Re-recorded on the overhauled page with the live terrain (15 Nov 2026, evening): step 4 is now the decision path's line on real missions (VIPER at Mons Mouton by late 2027), step 7 the close-up slip-day map. Re-cut with the hook first (regions), the same recording: one clip is sped up slightly, the slip-day map line at 1.064x (limit 1.1x); the rest play at normal speed. Made with `scripts/make_draft_voiceover.py` (lines in `lines.json`, clips `seg1.mp3` to `seg8.mp3`).

Every spoken number is on screen in its step and matches its caption.

## Explainer video (`../slipday_explainer.mp4`, 3 min 4 s; re-recorded on the overhauled page with the live terrain, 15 Nov 2026, evening)

The voice in the explainer is synthetic too: ElevenLabs text-to-speech, premade voice "Alice"
(Xb7hH8MSUJpSbSDYk0k2), model eleven_multilingual_v2, 15 Nov 2026. One clip per scene, in `explainer/`
(`<scene>.mp3`, lines and lengths in `explainer/segments.json`, start times in `explainer/timeline.json`). The
lines are in `../explainer/scenes.json`. Every clip plays at normal speed: each scene is made as long as its
line plus 1.3 s, so nothing is sped up. Every spoken number is on screen in its scene and in its caption.

How it is made: `scripts/make_explainer_voice.py --key-file <file>` (the key is read at run time and only sent
in the request header), `scripts/record_explainer.js <url> <dir> <durations.json>` (the screen recording) and
`scripts/make_explainer_video.py <dir>` (captions, voice, and the stills for `docs/EXPLAINER.html`).
