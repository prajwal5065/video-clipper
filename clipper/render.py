"""Cut a segment, crop to 9:16, burn captions, encode with FFmpeg."""
import re
import subprocess
from pathlib import Path

from .captions import build_ass
from .framing import face_center


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "clip"


def render_clip(video, clip, segments, out_dir, index, captions=True, crop="face", style="classic",
                on_progress=None):
    """on_progress(fraction 0..1) is called while FFmpeg encodes this clip."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    start, end = float(clip["start"]), float(clip["end"])
    name = f"{index:02d}-{_slug(clip.get('title', 'clip'))}"
    out_file = out_dir / f"{name}.mp4"

    frac = face_center(video, start, end) if crop == "face" else None
    if frac is None:
        x_expr = "(iw-ow)/2"  # centre crop
    else:
        x_expr = f"max(0,min(iw-ow,{frac:.4f}*iw-ow/2))"  # keep the face centred
    vf = f"crop=w='min(iw,ih*9/16)':h='min(ih,iw*16/9)':x='{x_expr}':y='(ih-oh)/2',scale=1080:1920"
    ass_name = None
    if captions:
        words = [w for s in segments for w in s.words if w.start >= start - 0.05 and w.end <= end + 0.05]
        if words:
            ass_name = f"{name}.ass"
            build_ass(words, start, out_dir / ass_name, style)
            vf += f",ass={ass_name}"

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-progress", "pipe:1", "-nostats",
        "-ss", f"{start:.3f}", "-i", str(Path(video).resolve()),
        "-t", f"{end - start:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        out_file.name,
    ]
    duration = end - start
    proc = subprocess.Popen(cmd, cwd=out_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = []  # cwd above lets the ass= path stay simple
    for line in proc.stdout:
        line = line.strip()
        if line.startswith(("out_time_us=", "out_time_ms=")):
            try:
                seconds = int(line.split("=", 1)[1]) / 1_000_000
            except ValueError:
                continue
            if on_progress and duration > 0:
                on_progress(max(0.0, min(seconds / duration, 1.0)))
        elif line and not re.match(r"^\w+=", line):
            log.append(line)
    if proc.wait() != 0:
        raise RuntimeError("FFmpeg failed: " + " | ".join(log[-5:]))
    if ass_name:
        (out_dir / ass_name).unlink(missing_ok=True)
    return out_file
