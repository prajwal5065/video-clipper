"""Cut a segment, crop to 9:16, burn captions, encode with FFmpeg."""
import re
import subprocess
from pathlib import Path

from .captions import build_ass


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "clip"


def render_clip(video, clip, segments, out_dir, index, captions=True):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    start, end = float(clip["start"]), float(clip["end"])
    name = f"{index:02d}-{_slug(clip.get('title', 'clip'))}"
    out_file = out_dir / f"{name}.mp4"

    vf = "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920"
    ass_name = None
    if captions:
        words = [w for s in segments for w in s.words if w.start >= start - 0.05 and w.end <= end + 0.05]
        if words:
            ass_name = f"{name}.ass"
            build_ass(words, start, out_dir / ass_name)
            vf += f",ass={ass_name}"

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-i", str(Path(video).resolve()),
        "-t", f"{end - start:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        out_file.name,
    ]
    subprocess.run(cmd, cwd=out_dir, check=True)  # cwd lets the ass= path stay simple
    if ass_name:
        (out_dir / ass_name).unlink(missing_ok=True)
    return out_file
