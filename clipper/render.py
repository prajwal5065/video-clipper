"""Cut a segment, frame it as 9:16, burn captions, encode with FFmpeg."""
import re
import subprocess
from pathlib import Path

from .captions import build_ass
from .framing import face_center


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "clip"


FRAMING_MODES = ("face", "center", "fit", "fit-black")


def clip_words(segments, start, end):
    """Words that fall inside [start, end] (absolute video time)."""
    return [w for s in segments for w in s.words if w.start >= start - 0.05 and w.end <= end + 0.05]


def video_duration(path):
    """Length of a video in seconds (None if FFprobe cannot read it)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, check=True).stdout.strip()
        return float(out)
    except Exception:
        return None


def _framing_filter(mode, face_frac):
    """FFmpeg filter that turns any video into 1080x1920.
    face / center: crop the middle (or the face) of the frame  -> fills the screen, loses the sides.
    fit:           whole frame kept, blurred copy of the video fills the empty space.
    fit-black:     whole frame kept, black bars above and below."""
    if mode == "fit":
        return ("split=2[a][b];"
                "[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,"
                "boxblur=10:3,scale=1080:1920[bg];"
                "[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2")
    if mode == "fit-black":
        return "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
    if face_frac is None:
        x_expr = "(iw-ow)/2"  # centre crop
    else:
        x_expr = f"max(0,min(iw-ow,{face_frac:.4f}*iw-ow/2))"  # keep the face centred
    return f"crop=w='min(iw,ih*9/16)':h='min(ih,iw*16/9)':x='{x_expr}':y='(ih-oh)/2',scale=1080:1920"


def render_clip(video, clip, segments, out_dir, index, captions=True, crop="face", style="classic",
                on_progress=None, words=None, out_name=None, preview=False):
    """on_progress(fraction 0..1) is called while FFmpeg encodes this clip.
    words:    optional replacement caption words (absolute times), e.g. after the user fixed spelling.
    out_name: output file name (default: <index>-<title>.mp4).
    preview:  fast low-resolution render (540x960) for checking an edit before saving."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    start, end = float(clip["start"]), float(clip["end"])
    name = f"{index:02d}-{_slug(clip.get('title', 'clip'))}"
    out_file = out_dir / (out_name or f"{name}.mp4")

    frac = face_center(video, start, end) if crop == "face" else None
    vf = _framing_filter(crop, frac)
    ass_name = None
    if captions:
        caption_words = words if words is not None else clip_words(segments, start, end)
        if caption_words:
            ass_name = f"{out_file.stem}.ass"
            build_ass(caption_words, start, out_dir / ass_name, style)
            vf += f",ass={ass_name}"
    if preview:
        vf += ",scale=540:960"

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-progress", "pipe:1", "-nostats",
        "-ss", f"{start:.3f}", "-i", str(Path(video).resolve()),
        "-t", f"{end - start:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "ultrafast" if preview else "veryfast", "-crf", "30" if preview else "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k" if preview else "160k", "-movflags", "+faststart",
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
