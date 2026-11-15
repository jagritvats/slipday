"""Draft of the 30-second video: the storyboard frames with their captions burnt in.

    python scripts/make_draft_video.py [--ffmpeg PATH] [--out demo/slipday_draft_29s.mp4]

Reads the frame table in demo/STORYBOARD.md (time span, image file, caption), draws each caption as an
English subtitle on a copy of its frame (real screenshots of the running app made by scripts/storyboard.js;
nothing here is generated imagery), and joins them with ffmpeg into one H.264 file of 1280x720 at 30
frames a second.  The length is the end of the last span in the table and must not exceed 29 seconds.
Where a frame has numbered follow-ups beside it (`04_terrain_3d_01.png`, `_02.png`, ...: further real
screenshots of the same view), they share that frame's time span in order, under the same caption.

It is a draft for the team to review and re-record or re-cut, not something to publish as it stands:
`[TEAM NAME]` in the last caption is still a placeholder.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile
import textwrap

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "demo")
FONTS = [r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/Library/Fonts/Arial Bold.ttf"]


def frames() -> list[dict]:
    rows = []
    with open(os.path.join(DEMO, "STORYBOARD.md"), encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"\|\s*(\d+)\s*\|\s*(\d+)-(\d+) s\s*\|\s*`([^`]+\.png)`[^|]*\|\s*\"(.+)\"\s*\|\s*$", line)
            if m:
                rows.append({"n": int(m.group(1)), "start": int(m.group(2)), "end": int(m.group(3)),
                             "file": m.group(4), "caption": m.group(5)})
    return rows


BAND = 118          # px at the bottom of the 1280x720 frame that hold the caption; the screenshot sits above it


def caption(img: Image.Image, text: str, font: ImageFont.FreeTypeFont) -> Image.Image:
    """The screenshot scaled into the area above a caption band, so that the caption covers nothing of it."""
    src = img.convert("RGB")
    area_h = 720 - BAND
    k = min(1280 / src.width, area_h / src.height)
    w, h = int(round(src.width * k)), int(round(src.height * k))
    out = Image.new("RGB", (1280, 720), (12, 12, 12))
    out.paste(src.resize((w, h), Image.LANCZOS), ((1280 - w) // 2, (area_h - h) // 2))
    d = ImageDraw.Draw(out)
    lines = textwrap.wrap(text, width=80)
    line_h = font.size + 8
    y = area_h + (BAND - line_h * len(lines)) // 2
    for ln in lines:
        lw = d.textlength(ln, font=font)
        d.text(((1280 - lw) / 2, y), ln, font=font, fill=(255, 255, 255))
        y += line_h
    return out


def closing_card(path: str, font: ImageFont.FreeTypeFont) -> None:
    """The closing frame: the name, the team placeholder and the public-link placeholder, as text."""
    img = Image.new("RGB", (1280, 800), (16, 24, 40))
    d = ImageDraw.Draw(img)
    big = ImageFont.truetype(font.path, 64)
    for text, f, y in (("Slipday", big, 280), ("https://slipday.synpse.app", font, 400), ("Lunar Landing Site Navigator", font, 450)):
        w = d.textlength(text, font=f)
        d.text(((1280 - w) / 2, y), text, font=f, fill=(255, 255, 255))
    img.save(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ffmpeg", default=os.environ.get("FFMPEG", "ffmpeg"))
    ap.add_argument("--out", default=os.path.join(DEMO, "slipday_draft_29s.mp4"))
    a = ap.parse_args()
    rows = frames()
    if not rows:
        sys.exit("no frame rows found in demo/STORYBOARD.md")
    total = rows[-1]["end"]
    if total > 29 or rows[0]["start"] != 0 or any(b["start"] != p["end"] for p, b in zip(rows, rows[1:])):
        sys.exit(f"the storyboard must run from 0 without gaps and end by 29 s (it ends at {total} s)")
    font = None
    for path in FONTS:
        if os.path.exists(path):
            font = ImageFont.truetype(path, 27)
            break
    if font is None:
        sys.exit("no caption font found; add one to FONTS")
    with tempfile.TemporaryDirectory(prefix="slipday_video_") as tmp:
        listing = []
        for r in rows:
            src = os.path.join(DEMO, r["file"])
            if r["file"] == "06_closing.png":
                closing_card(src, font)
            if not os.path.exists(src):
                sys.exit(f"missing frame {src}: run scripts/storyboard.js first")
            series = [src] + sorted(glob.glob(os.path.splitext(src)[0] + "_[0-9][0-9].png"))
            r["images"] = len(series)
            for k, path in enumerate(series):
                out = os.path.join(tmp, f"f{r['n']:02d}_{k:02d}.png")
                caption(Image.open(path), r["caption"], font).save(out)
                listing.append((out, (r["end"] - r["start"]) / len(series)))
        concat = os.path.join(tmp, "frames.txt")
        with open(concat, "w", encoding="utf-8") as fh:
            for path, dur in listing:
                fh.write(f"file '{path.replace(os.sep, '/')}'\nduration {dur:.4f}\n")
            fh.write(f"file '{listing[-1][0].replace(os.sep, '/')}'\n")       # the concat demuxer needs the last file twice
        cmd = [a.ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", concat, "-t", str(total),
               "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-movflags", "+faststart",
               a.out]
        subprocess.run(cmd, check=True)
    print(f"wrote {a.out}: {len(rows)} frames, {total} s, {os.path.getsize(a.out)} bytes")
    for r in rows:
        print(f"  {r['start']:>2}-{r['end']:<2} s  {r['file']}" + (f" and {r['images'] - 1} follow-ups" if r["images"] > 1 else "")
              + f": {r['caption']}")


if __name__ == "__main__":
    main()
