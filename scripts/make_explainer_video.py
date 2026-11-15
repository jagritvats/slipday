"""The explainer video: the screen recording of scripts/record_explainer.js, captions in a band under the picture,
and the synthetic voice of scripts/make_explainer_voice.py.

    python scripts/make_explainer_video.py RECORDING_DIR [--ffmpeg PATH] [--out demo/slipday_explainer.mp4]
                                           [--stills docs/explainer]

Each scene lasts its voice clip plus 1.3 s (the clip starts 0.4 s into the scene), played at normal speed.  The
closing scene is a card of text.  With --stills, the middle frame of each scene (without caption) is saved as
<scene>.jpg for the explainer page, and every scene's captioned middle frame as check_<scene>.jpg next to the
recording, so each number can be checked against the screen.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import make_draft_video as mdv  # noqa: E402

LEAD, TAIL = 0.4, 0.9


def closing(font: ImageFont.FreeTypeFont) -> Image.Image:
    img = Image.new("RGB", (1280, 800), (16, 24, 40))
    d = ImageDraw.Draw(img)
    big = ImageFont.truetype(font.path, 64)
    for text, f, y in (("Slipday", big, 280), ("by [TEAM NAME]", font, 390), ("NASA Space Apps 2026: Lunar Landing Site Navigator", font, 440)):
        w = d.textlength(text, font=f)
        d.text(((1280 - w) / 2, y), text, font=f, fill=(255, 255, 255))
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("recording")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--out", default=os.path.join(ROOT, "demo", "slipday_explainer.mp4"))
    ap.add_argument("--stills", default="")
    a = ap.parse_args()
    scenes = json.load(open(os.path.join(ROOT, "demo", "explainer", "scenes.json"), encoding="utf-8"))["scenes"]
    vdir = os.path.join(ROOT, "demo", "voiceover", "explainer")
    segs = {s["id"]: s for s in json.load(open(os.path.join(vdir, "segments.json"), encoding="utf-8"))}
    rec = json.load(open(os.path.join(a.recording, "frames.json"), encoding="utf-8"))
    frames, events = rec["frames"], {e["name"]: e["t"] for e in rec["events"]}
    order = [e["name"] for e in rec["events"]]
    nxt = {order[i]: events[order[i + 1]] for i in range(len(order) - 1)}      # a scene never shows the next one's frames
    font = next((ImageFont.truetype(p, 26) for p in mdv.FONTS if os.path.exists(p)), None)
    if a.stills:
        os.makedirs(a.stills, exist_ok=True)
    listing, starts, t = [], [], 0.0
    with tempfile.TemporaryDirectory(prefix="slipday_expl_") as tmp:
        for sc in scenes:
            secs = round(segs[sc["id"]]["dur"] + LEAD + TAIL, 2)
            starts.append((sc["id"], t, secs))
            if sc["id"] == "closing":
                out = os.path.join(tmp, "closing.png")
                mdv.caption(closing(font), sc["caption"], font).save(out)
                listing.append((out, secs))
                if a.stills:
                    mdv.caption(closing(font), sc["caption"], font).save(os.path.join(a.recording, "check_closing.jpg"))
                t += secs
                continue
            t0 = events[sc["id"]]
            inside = [f for f in frames if t0 <= f["t"] < min(t0 + secs, nxt.get(sc["id"], 1e18))]
            if not inside:
                sys.exit("no frames for " + sc["id"])
            if inside[-1]["t"] < t0 + secs - 1.5:
                print(f"warning: {sc['id']} recording ends {t0 + secs - inside[-1]['t']:.1f} s early; its last frame is held")
            for k, f in enumerate(inside):
                start = max(f["t"], t0) if k else t0
                end = inside[k + 1]["t"] if k + 1 < len(inside) else t0 + secs
                dur = max(0.0, min(end, t0 + secs) - start)
                if dur <= 0:
                    continue
                img = Image.open(os.path.join(a.recording, "frames", f["file"]))
                out = os.path.join(tmp, f"{sc['id']}_{k:04d}.png")
                mdv.caption(img, sc["caption"], font).save(out)
                listing.append((out, dur))
            mid = inside[len(inside) // 2]
            if a.stills:
                img = Image.open(os.path.join(a.recording, "frames", mid["file"])).convert("RGB")
                if img.width > 1600:
                    img = img.resize((1600, int(img.height * 1600 / img.width)), Image.LANCZOS)
                img.save(os.path.join(a.stills, sc["id"] + ".jpg"), quality=84)
                mdv.caption(Image.open(os.path.join(a.recording, "frames", mid["file"])), sc["caption"], font).save(
                    os.path.join(a.recording, "check_" + sc["id"] + ".jpg"))
            t += secs
        total = t
        concat = os.path.join(tmp, "list.txt")
        with open(concat, "w", encoding="utf-8") as fh:
            for p, d in listing:
                fh.write(f"file '{p.replace(os.sep, '/')}'\nduration {d:.4f}\n")
            fh.write(f"file '{listing[-1][0].replace(os.sep, '/')}'\n")
        silent = os.path.join(tmp, "video.mp4")
        subprocess.run([a.ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", concat, "-t", f"{total:.3f}",
                        "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "21", silent], check=True)
        cmd = [a.ffmpeg, "-y", "-loglevel", "error", "-i", silent]
        parts = []
        for i, (sid, st, _secs) in enumerate(starts):
            cmd += ["-i", os.path.join(vdir, sid + ".mp3")]
            ms = int(round((st + LEAD) * 1000))
            parts.append(f"[{i + 1}:a]adelay={ms}|{ms}[a{i}]")
        mix = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(starts))) + f"amix=inputs={len(starts)}:normalize=0[aout]"
        cmd += ["-filter_complex", mix, "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                "-t", f"{total:.3f}", "-movflags", "+faststart", a.out]
        subprocess.run(cmd, check=True)
    print(f"wrote {a.out}: {len(scenes)} scenes, {total:.1f} s")
    for sid, st, secs in starts:
        print(f"  {st:6.1f}-{st + secs:6.1f} s  {sid}")
    json.dump([{"id": sid, "start": round(st, 2), "secs": secs, "voice_start": round(st + LEAD, 2)} for sid, st, secs in starts],
              open(os.path.join(vdir, "timeline.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
