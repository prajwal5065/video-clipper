"""Face-aware horizontal crop position (OpenCV Haar cascade, no model download)."""
import statistics
import subprocess
import tempfile
from pathlib import Path


def _keyframe_images(video, start, end, max_frames=24):
    """Small (480 px high) frames taken at the keyframes inside [start, end].

    Decoding only keyframes is 10-20x faster than seeking to 12 exact times in a long video, because each exact seek
    has to decode from the previous keyframe. Returns [] if FFmpeg cannot do it (the caller then seeks instead)."""
    import cv2  # lazy import

    with tempfile.TemporaryDirectory() as tmp:
        base = ["ffmpeg", "-v", "error", "-skip_frame", "nokey", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
                "-i", str(video), "-vf", "scale=-2:480"]
        tail = ["-q:v", "4", "-frames:v", str(max_frames), str(Path(tmp) / "%03d.jpg")]
        # keep one frame per keyframe (no duplicates): the option is called -fps_mode in FFmpeg 5.1+, -vsync before
        for sync in (["-fps_mode", "vfr"], ["-vsync", "vfr"]):
            try:
                subprocess.run(base + sync + tail, check=True, timeout=60,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
            except (OSError, subprocess.SubprocessError):
                for f in Path(tmp).glob("*.jpg"):
                    f.unlink(missing_ok=True)
        else:
            return []
        return [img for img in (cv2.imread(str(f)) for f in sorted(Path(tmp).glob("*.jpg"))) if img is not None]


def _seek_images(video, start, end, samples):
    """Frames at `samples` evenly spaced exact times (slower, works for any video)."""
    import cv2  # lazy import

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return []
    out = []
    for i in range(samples):
        t = start + (end - start) * (i + 0.5) / samples
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        scale = 480 / h if h > 480 else 1.0
        out.append(cv2.resize(frame, (int(w * scale), int(h * scale))) if scale != 1.0 else frame)
    cap.release()
    return out


def face_center(video, start, end, samples=12):
    """Return the median horizontal face position as a 0..1 fraction of frame width,
    or None if no face is found reliably (caller falls back to centre crop)."""
    import cv2  # lazy import

    if not hasattr(cv2, "CascadeClassifier"):  # e.g. OpenCV 5 dropped it: fall back to centre crop
        return None

    frames = _keyframe_images(video, start, end)
    if len(frames) < 4:  # long gaps between keyframes: too few frames to trust, use exact times instead
        frames = _seek_images(video, start, end, samples)
    if len(frames) > samples:  # spread the frames we look at evenly over the clip
        frames = [frames[int(i * len(frames) / samples)] for i in range(samples)]
    if not frames:
        return None

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    xs = []
    for small in frames:
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        if len(faces):
            x, _y, fw, _fh = max(faces, key=lambda f: f[2] * f[3])
            xs.append((x + fw / 2) / small.shape[1])
    if len(xs) < max(2, len(frames) // 4):
        return None
    return statistics.median(xs)
