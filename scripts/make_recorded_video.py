"""Draft video from a screen recording of the running page (scripts/record_demo.js), captions in a band.

    python scripts/make_recorded_video.py RECORDING_DIR [--ffmpeg PATH] [--out demo/slipday_draft_29s.mp4]

Reads RECORDING_DIR/frames.json (the screencast frames with their times, and the time each step began), takes
the first seconds of each step as the table in demo/STORYBOARD.md gives them, scales every frame into the area
above a caption band (the band covers nothing of the page), adds a closing frame of text, and joins them at 30
frames a second with ffmpeg.  Every number in a caption must be on screen in its segment; the script prints the
page text it found so that this can be checked.
"""
from __future__ import annotations

import argparse
import json
import re
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import make_draft_video as mdv  # noqa: E402

def segments() -> list:
    """The table in demo/STORYBOARD.md: rows "| n | a-b s | step `name`: ... | "caption" |"."""
    rows = []
    with open(os.path.join(ROOT, "demo", "STORYBOARD.md"), encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"\|\s*(\d+)\s*\|\s*(\d+)-(\d+) s\s*\|\s*step `(\w+)`[^|]*\|\s*\"(.+)\"\s*\|\s*$", line)
            if m:
                rows.append((m.group(4), float(int(m.group(3)) - int(m.group(2))), m.group(5)))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("recording")
    ap.add_argument("--ffmpeg", default=os.environ.get("FFMPEG", "ffmpeg"))
    ap.add_argument("--out", default=os.path.join(ROOT, "demo", "slipday_draft_29s.mp4"))
    a = ap.parse_args()
    rec = json.load(open(os.path.join(a.recording, "frames.json"), encoding="utf-8"))
    frames, events = rec["frames"], {e["name"]: e["t"] for e in rec["events"]}
    crops = {e["name"]: e.get("crop") for e in rec["events"]}
    dpr = float(rec.get("dpr", 1))

    def load(fname, name):
        img = Image.open(os.path.join(a.recording, "frames", fname))
        c = crops.get(name)
        if c:                                   # zoom into the region the step shows, so its text stays readable
            k = img.width / 1280.0                # frames may come at the viewport's size or at its pixel density
            img = img.crop((int(c["x"] * k), int(c["y"] * k), int((c["x"] + c["w"]) * k), int((c["y"] + c["h"]) * k)))
        return img

    SEGMENTS = segments()
    if not SEGMENTS:
        sys.exit("no step rows in demo/STORYBOARD.md")
    total = sum(s[1] for s in SEGMENTS)
    if total > 29.0:
        sys.exit(f"the video must not exceed 29 s (it would be {total} s)")
    font = next((ImageFont.truetype(p, 27) for p in mdv.FONTS if os.path.exists(p)), None)
    if font is None:
        sys.exit("no caption font found")
    with tempfile.TemporaryDirectory(prefix="slipday_rec_") as tmp:
        listing = []
        for name, secs, cap in SEGMENTS:
            if name == "closing":
                src = os.path.join(tmp, "closing.png")
                mdv.closing_card(src, font)
                out = os.path.join(tmp, "closing_c.png")
                mdv.caption(Image.open(src), cap, font).save(out)
                listing.append((out, secs))
                continue
            t0 = events[name]
            t1 = t0 + secs
            inside = [f for f in frames if t0 <= f["t"] < t1]
            before = [f for f in frames if f["t"] < t0]
            seq = ([before[-1]] if before else []) + inside
            if not seq:
                sys.exit(f"no frames for step {name}")
            times = [t0] + [f["t"] for f in inside] if before else [f["t"] for f in inside]
            for k, f in enumerate(seq):
                start = max(times[k], t0)
                end = times[k + 1] if k + 1 < len(seq) else t1
                dur = max(0.0, min(end, t1) - start)
                if dur <= 0:
                    continue
                out = os.path.join(tmp, f"{name}_{k:04d}.png")
                mdv.caption(load(f["file"], name), cap, font).save(out)
                listing.append((out, dur))
        concat = os.path.join(tmp, "list.txt")
        with open(concat, "w", encoding="utf-8") as fh:
            for p, d in listing:
                fh.write(f"file '{p.replace(os.sep, '/')}'\nduration {d:.4f}\n")
            fh.write(f"file '{listing[-1][0].replace(os.sep, '/')}'\n")
        subprocess.run([a.ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", concat, "-t", f"{total:.3f}",
                        "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-movflags", "+faststart",
                        a.out], check=True)
    print(f"wrote {a.out}: {len(SEGMENTS)} segments, {total} s, {len(listing)} pictures, {os.path.getsize(a.out)} bytes")
    t = 0.0
    for name, secs, cap in SEGMENTS:
        print(f"  {t:5.1f}-{t + secs:5.1f} s  {name}: {cap}")
        t += secs
    print("page text at the end of the recording:", json.dumps(rec.get("text", {}))[:1500])


if __name__ == "__main__":
    main()
