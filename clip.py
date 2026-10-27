#!/usr/bin/env python3
"""video-clipper: long video -> short vertical subtitled clips.

Usage:  python clip.py my_video.mp4 --clips 5
"""
import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from clipper import transcribe as tr
from clipper.select import pick_clips
from clipper.render import render_clip


def main():
    p = argparse.ArgumentParser(description="Turn a long video into short vertical clips.")
    p.add_argument("video")
    p.add_argument("--clips", type=int, default=5, help="how many clips to make")
    p.add_argument("--min", type=int, default=20, dest="min_len", help="min clip seconds")
    p.add_argument("--max", type=int, default=60, dest="max_len", help="max clip seconds")
    p.add_argument("--whisper", default="small", help="tiny/base/small/medium/large-v3")
    p.add_argument("--device", default="auto", help="auto/cpu/cuda")
    p.add_argument("--compute-type", default="int8", help="int8 (CPU) or float16 (GPU)")
    p.add_argument("--out", default="output")
    p.add_argument("--crop", choices=["face", "center"], default="face", help="9:16 crop mode")
    p.add_argument("--no-captions", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="only pick clips, do not render")
    a = p.parse_args()

    load_dotenv()
    video = Path(a.video)
    if not video.exists():
        sys.exit(f"File not found: {video}")

    out_dir = Path(a.out) / video.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_file = out_dir / "transcript.json"

    if transcript_file.exists():
        print("Using cached transcript.")
        segments = tr.load(transcript_file)
    else:
        print(f"Transcribing with Whisper '{a.whisper}' (this is the slow step)...")
        segments = tr.transcribe(video, a.whisper, a.device, a.compute_type)
        tr.save(segments, transcript_file)
    if not segments:
        sys.exit("No speech found in this video.")

    print("Asking the LLM for the best moments...")
    clips = pick_clips(segments, a.clips, a.min_len, a.max_len)
    (out_dir / "clips.json").write_text(json.dumps(clips, indent=1), encoding="utf-8")
    for i, c in enumerate(clips, 1):
        print(f"  {i}. {c['start']:.0f}s-{c['end']:.0f}s  [{c.get('score', '?')}]  {c.get('title', '')}")
    if a.dry_run:
        return

    for i, c in enumerate(clips, 1):
        print(f"Rendering clip {i}/{len(clips)}...")
        f = render_clip(video, c, segments, out_dir, i, captions=not a.no_captions, crop=a.crop)
        print(f"  -> {f}")
    print(f"Done. Clips are in {out_dir}")


if __name__ == "__main__":
    main()
