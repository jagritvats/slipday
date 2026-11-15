"""Synthetic voice for the explainer video: one clip per scene of demo/explainer/scenes.json.

    python scripts/make_explainer_voice.py --key-file PATH [--ffprobe PATH]

Text-to-speech by ElevenLabs (voice "Alice", Xb7hH8MSUJpSbSDYk0k2, model eleven_multilingual_v2).  The API key is
read from --key-file at run time and only sent in the request header; it is never printed, logged or written.
A clip is fetched again only when its line changed.  Writes demo/voiceover/explainer/<scene>.mp3 and
segments.json (line, duration in seconds).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES = os.path.join(ROOT, "demo", "explainer", "scenes.json")
OUT = os.path.join(ROOT, "demo", "voiceover", "explainer")
VOICE = "Xb7hH8MSUJpSbSDYk0k2"
MODEL = "eleven_multilingual_v2"


def tts(text: str, key: str) -> bytes:
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_128",
        data=json.dumps({"text": text, "model_id": MODEL}).encode("utf-8"),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg",
                 "User-Agent": "tts-client/1.0"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def duration(path: str, ffprobe: str) -> float:
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return round(float(out.strip()), 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-file", required=True)
    ap.add_argument("--ffprobe", default="ffprobe")
    a = ap.parse_args()
    scenes = json.load(open(SCENES, encoding="utf-8"))["scenes"]
    os.makedirs(OUT, exist_ok=True)
    seg_path = os.path.join(OUT, "segments.json")
    old = {s["id"]: s for s in json.load(open(seg_path, encoding="utf-8"))} if os.path.exists(seg_path) else {}
    key = None
    segs = []
    for sc in scenes:
        h = hashlib.sha256(sc["voice"].encode("utf-8")).hexdigest()[:16]
        mp3 = os.path.join(OUT, sc["id"] + ".mp3")
        if not (os.path.exists(mp3) and old.get(sc["id"], {}).get("text_hash") == h):
            if key is None:
                key = open(a.key_file, encoding="utf-8").read().strip()
            open(mp3, "wb").write(tts(sc["voice"], key))
            print("fetched", sc["id"])
        segs.append({"id": sc["id"], "text": sc["voice"], "text_hash": h, "dur": duration(mp3, a.ffprobe)})
        print(f"  {sc['id']:<9} {segs[-1]['dur']:6.2f} s")
    key = None
    json.dump(segs, open(seg_path, "w", encoding="utf-8"), indent=1)
    print("total voice", round(sum(s["dur"] for s in segs), 1), "s")


if __name__ == "__main__":
    main()
