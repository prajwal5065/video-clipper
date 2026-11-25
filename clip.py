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
from clipper.captions import STYLES
from clipper.download import describe, download, is_url
from clipper.render import QUALITY, render_clip


def main():
    p = argparse.ArgumentParser(description="Turn a long video into short vertical clips.")
    p.add_argument("video", help="path to a video file, or a link (YouTube etc.)")
    p.add_argument("--clips", type=int, default=5, help="how many clips to make")
    p.add_argument("--min", type=int, default=20, dest="min_len", help="min clip seconds")
    p.add_argument("--max", type=int, default=60, dest="max_len", help="max clip seconds")
    p.add_argument("--model", default=None, help="Gemini model (e.g. gemini-2.5-flash, gemini-3.8-flash)")
    p.add_argument("--whisper", default="small", help="tiny/base/small/medium/large-v3")
    p.add_argument("--device", default="auto", help="auto/cpu/cuda")
    p.add_argument("--compute-type", default="int8", help="int8 (CPU) or float16 (GPU)")
    p.add_argument("--out", default="output")
    p.add_argument("--crop", choices=["face", "center", "fit", "fit-black"], default="face",
                   help="face/center = crop to 9:16; fit = whole frame on a blurred background; fit-black = whole frame with black bars")
    p.add_argument("--style", choices=list(STYLES), default="classic", help="caption style")
    p.add_argument("--quality", choices=list(QUALITY), default="standard",
                   help="draft = 720p fast; standard = 1080p; high = sharper, slower; max = best, slowest")
    p.add_argument("--no-captions", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="only pick clips, do not render")
    a = p.parse_args()

    load_dotenv()
    if is_url(a.video):
        print("Downloading video...")
        def show(info):
            head, detail = describe(info)
            print(f"\r{head}  {detail}".ljust(100), end="", flush=True)

        video = download(a.video, Path(a.out) / "_downloads", max_height=QUALITY[a.quality]["max_height"],
                         on_progress=show)
        print()
    else:
        video = Path(a.video)
    if not video.exists():
        sys.exit(f"File not found: {video}")

    out_dir = Path(a.out) / video.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_file = out_dir / "transcript.json"
    source_id_file = out_dir / "transcript.source"
    source_id = tr.fingerprint(video)

    if transcript_file.exists() and source_id_file.exists() and source_id_file.read_text().strip() == source_id:
        print("Using cached transcript.")
        segments = tr.load(transcript_file)
    else:
        print(f"Transcribing with Whisper '{a.whisper}' (this is the slow step)...")
        segments = tr.transcribe(video, a.whisper, a.device, a.compute_type)
        tr.save(segments, transcript_file)
        source_id_file.write_text(source_id)
    if not segments:
        sys.exit("No speech found in this video.")

    print("Asking the LLM for the best moments...")
    clips = pick_clips(segments, a.clips, a.min_len, a.max_len, model=a.model)
    (out_dir / "clips.json").write_text(json.dumps(clips, indent=1), encoding="utf-8")
    for i, c in enumerate(clips, 1):
        print(f"  {i}. {c['start']:.0f}s-{c['end']:.0f}s  [{c.get('score', '?')}]  {c.get('title', '')}")
    if a.dry_run:
        return

    for i, c in enumerate(clips, 1):
        print(f"Rendering clip {i}/{len(clips)}...")
        f = render_clip(video, c, segments, out_dir, i, captions=not a.no_captions, crop=a.crop, style=a.style, quality=a.quality)
        print(f"  -> {f}")
    print(f"Done. Clips are in {out_dir}")


if __name__ == "__main__":
    main()
