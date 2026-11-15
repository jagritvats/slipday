"""The voiceover version of the 29 s video: one synthetic spoken line per storyboard step, laid over
demo/slipday_draft_29s.mp4.

    python scripts/make_draft_voiceover.py --key-file PATH [--ffmpeg PATH] [--ffprobe PATH]

Lines: demo/voiceover/lines.json (one per storyboard step, in order).  Text-to-speech by ElevenLabs, voice "Alice"
(Xb7hH8MSUJpSbSDYk0k2), model eleven_multilingual_v2; the key is read from --key-file at run time and only sent in
the request header.  Each clip starts 0.15 s into its step; a clip longer than its step is played faster, at most
1.1x; a line that would need more must be rewritten (the script stops).  The closing frame is held 0.5 s longer.
Writes demo/voiceover/seg<n>.mp3, segments.json and demo/slipday_draft_voiceover.mp4.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from make_explainer_voice import duration, tts  # noqa: E402
from make_recorded_video import segments  # noqa: E402

VDIR = os.path.join(ROOT, "demo", "voiceover")
LEAD, GAP, MAX_TEMPO, HOLD = 0.15, 0.1, 1.1, 0.5


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-file", required=True)
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--ffprobe", default="ffprobe")
    a = ap.parse_args()
    steps = segments()
    lines = json.load(open(os.path.join(VDIR, "lines.json"), encoding="utf-8"))
    if len(lines) != len(steps):
        sys.exit(f"{len(lines)} lines for {len(steps)} steps")
    old_p = os.path.join(VDIR, "segments.json")
    old = {s.get("text_hash"): s for s in json.load(open(old_p, encoding="utf-8"))} if os.path.exists(old_p) else {}
    key, t, segs = None, 0.0, []
    for n, ((name, secs, _cap), text) in enumerate(zip(steps, lines), 1):
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        mp3 = os.path.join(VDIR, f"seg{n}.mp3")
        prev = old.get(h)
        if not (os.path.exists(mp3) and prev and prev.get("seg") == n):
            if key is None:
                key = open(a.key_file, encoding="utf-8").read().strip()
            open(mp3, "wb").write(tts(text, key))
        dur = duration(mp3, a.ffprobe)
        slot = secs - LEAD - GAP + (HOLD if n == len(steps) else 0.0)
        tempo = round(max(1.0, dur / slot), 3)
        segs.append({"seg": n, "step": name, "start": round(t + LEAD, 2), "slot": round(slot, 2), "dur": dur, "tempo": tempo,
                     "text": text, "text_hash": h})
        print(f"  {n} {name:<9} slot {slot:4.2f} s  clip {dur:5.2f} s  tempo {tempo:5.3f}  {text}")
        t += secs
    key = None
    json.dump(segs, open(old_p, "w", encoding="utf-8"), indent=1)
    long = [s for s in segs if s["tempo"] > MAX_TEMPO]
    if long:
        sys.exit("rewrite these lines, they need more than 1.1x: " + ", ".join(str(s["seg"]) for s in long))
    video = os.path.join(ROOT, "demo", "slipday_draft_29s.mp4")
    out = os.path.join(ROOT, "demo", "slipday_draft_voiceover.mp4")
    total = t + HOLD
    cmd = [a.ffmpeg, "-y", "-loglevel", "error", "-i", video]
    parts = []
    for i, s in enumerate(segs):
        cmd += ["-i", os.path.join(VDIR, f"seg{s['seg']}.mp3")]
        ms = int(round(s["start"] * 1000))
        tempo = f"atempo={s['tempo']}," if s["tempo"] > 1.0 else ""
        parts.append(f"[{i + 1}:a]{tempo}adelay={ms}|{ms}[a{i}]")
    mix = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(segs))) + f"amix=inputs={len(segs)}:normalize=0[aout]"
    cmd += ["-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration={HOLD}[v];" + mix, "-map", "[v]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-t", f"{total:.3f}", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    print(f"wrote {out}: {total:.1f} s")


if __name__ == "__main__":
    main()
