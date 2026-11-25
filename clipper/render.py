"""Cut a segment, frame it as 9:16, burn captions, encode with FFmpeg."""
import os
import re
import subprocess
from pathlib import Path

from .captions import build_ass
from .framing import face_center


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "clip"


FRAMING_MODES = ("face", "center", "fit", "fit-black")

# Output quality levels. 'standard' keeps the original behaviour.
#   crf: lower = better picture and bigger file; preset: slower = smaller file at the same quality.
QUALITY = {
    "draft":    dict(w=720,  h=1280, crf=24, preset="veryfast", audio="128k", max_height=720,  sharpen=False),
    "standard": dict(w=1080, h=1920, crf=20, preset="veryfast", audio="160k", max_height=1080, sharpen=False),
    "high":     dict(w=1080, h=1920, crf=17, preset="medium",   audio="192k", max_height=1440, sharpen=True),
    "max":      dict(w=1080, h=1920, crf=14, preset="slow",     audio="256k", max_height=2160, sharpen=True),
}
SHARPEN = "unsharp=5:5:0.7:5:5:0.0"  # mild, luma only: brings back detail lost when enlarging a crop


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


def _framing_filter(mode, face_frac, w=1080, h=1920, sharpen=False):
    """FFmpeg filter that turns any video into w x h (default 1080x1920).
    face / center: crop the middle (or the face) of the frame  -> fills the screen, loses the sides.
    fit:           whole frame kept, blurred copy of the video fills the empty space.
    fit-black:     whole frame kept, black bars above and below."""
    sh = f",{SHARPEN}" if sharpen else ""
    if mode == "fit":
        return (f"split=2[a][b];"
                f"[a]scale={w // 4}:{h // 4}:force_original_aspect_ratio=increase,crop={w // 4}:{h // 4},"
                f"boxblur=10:3,scale={w}:{h}[bg];"
                f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos{sh}[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2")
    if mode == "fit-black":
        return (f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos{sh},"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black")
    if face_frac is None:
        x_expr = "(iw-ow)/2"  # centre crop
    else:
        x_expr = f"max(0,min(iw-ow,{face_frac:.4f}*iw-ow/2))"  # keep the face centred
    return (f"crop=w='min(iw,ih*9/16)':h='min(ih,iw*16/9)':x='{x_expr}':y='(ih-oh)/2',"
            f"scale={w}:{h}:flags=lanczos{sh}")


def render_clip(video, clip, segments, out_dir, index, captions=True, crop="face", style="classic",
                on_progress=None, words=None, out_name=None, preview=False, quality="standard"):
    """on_progress(fraction 0..1) is called while FFmpeg encodes this clip.
    words:    optional replacement caption words (absolute times), e.g. after the user fixed spelling.
    out_name: output file name (default: <index>-<title>.mp4).
    preview:  fast low-resolution render (540x960) for checking an edit before saving.
    quality:  one of QUALITY (draft / standard / high / max)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    start, end = float(clip["start"]), float(clip["end"])
    name = f"{index:02d}-{_slug(clip.get('title', 'clip'))}"
    out_file = out_dir / (out_name or f"{name}.mp4")
    # FFmpeg writes to a temp file; it replaces out_file only when it succeeds, so a failed or cancelled
    # render never destroys the clip that is already there.
    tmp_file = out_dir / f"{out_file.stem}.part.mp4"

    frac = face_center(video, start, end) if crop == "face" else None
    q = QUALITY.get(quality, QUALITY["standard"])
    vf = _framing_filter(crop, frac, q["w"], q["h"], q["sharpen"] and not preview)
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
        "-c:v", "libx264", "-preset", "ultrafast" if preview else q["preset"], "-crf", "30" if preview else str(q["crf"]),
        "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k" if preview else q["audio"], "-movflags", "+faststart",
        tmp_file.name,
    ]
    duration = end - start
    proc = subprocess.Popen(cmd, cwd=out_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = []  # cwd above lets the ass= path stay simple
    try:
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
    except BaseException:  # e.g. the job was cancelled inside on_progress: do not leave FFmpeg running
        proc.kill()
        proc.wait()
        tmp_file.unlink(missing_ok=True)
        if ass_name:
            (out_dir / ass_name).unlink(missing_ok=True)
        raise
    if proc.wait() != 0:
        tmp_file.unlink(missing_ok=True)
        if ass_name:
            (out_dir / ass_name).unlink(missing_ok=True)
        raise RuntimeError("FFmpeg failed: " + " | ".join(log[-5:]))
    os.replace(tmp_file, out_file)
    if ass_name:
        (out_dir / ass_name).unlink(missing_ok=True)
    return out_file
