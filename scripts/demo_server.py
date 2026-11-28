"""Demo mode: the real server and interface, with FAKE download / Whisper / Gemini / YouTube.

    py -3.11 scripts/demo_server.py          ->  http://127.0.0.1:8010

Use it to look at the interface without waiting for real processing. Clips are made with the real FFmpeg from a
generated test video, so FFmpeg must be installed. Nothing is uploaded anywhere. Data goes to output_demo/.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

from clipper import transcribe as tr  # noqa: E402

DELAY = float(os.environ.get("DEMO_DELAY", "0.5"))
SAMPLE = Path(tempfile.gettempdir()) / "video_clipper_demo_sample.mp4"


def sample_video():
    if not SAMPLE.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=40",
                        "-f", "lavfi", "-i", "sine=frequency=300:duration=40", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-shortest", str(SAMPLE)], check=True)
    return SAMPLE


def fake_download(url, out_dir, max_height=1080, on_progress=None):
    gb = 1024 ** 3
    for done in (0.3, 0.8, 1.4, 2.0, 2.67):
        on_progress and on_progress({"stage": "downloading", "done": done * gb, "total": 2.67 * gb, "fraction": done / 2.67,
                                     "speed": 3.35 * 1024 ** 2, "eta": int((2.67 - done) * gb / (3.35 * 1024 ** 2)), "kind": "video"})
        time.sleep(DELAY)
    on_progress and on_progress({"stage": "processing"})
    time.sleep(DELAY)
    return sample_video()


def fake_transcribe(src, model, device, compute, chunk_seconds=600, on_progress=None):
    words = [tr.Word(i * 0.5, i * 0.5 + 0.4, w) for i, w in enumerate(
        ("here is the one thing nobody tells you about growing a channel fast and it changes how you plan "
         "every single video from now on so listen closely because this part matters most").split() * 3)]
    for done in range(0, 41, 5):
        on_progress and on_progress(done, 40)
        time.sleep(DELAY / 2)
    return [tr.Segment(0, 40, "demo", words)]


def fake_pick(segments, n, mn, mx, model=None):
    time.sleep(DELAY)
    picks = [(1, 11, "The one thing nobody tells you", 94, "Opens with a bold claim."),
             (14, 26, "How this changes every video", 88, "A complete, self-contained idea."),
             (28, 38, "Listen closely: this part matters", 81, "Strong closing hook.")]
    return [{"start": a, "end": b, "title": t, "score": s, "reason": r} for a, b, t, s, r in picks[:n]]


def main():
    port = int(os.environ.get("DEMO_PORT", "8010"))
    root = os.environ.get("CLIPPER_DATA_DIR", str(ROOT / "output_demo"))
    sample_video()
    Path(root).mkdir(parents=True, exist_ok=True)
    fake_secret = Path(root) / "demo_client_secret.json"  # so the YouTube screens look "set up"; uploads are fake
    fake_secret.write_text("{}")
    env = {"GEMINI_API_KEY": "demo-key", "YT_ACCOUNTS": "main,second", "CLIPPER_DATA_DIR": root,
           "YT_CLIENT_SECRET_FILE": str(fake_secret)}
    with mock.patch.dict(os.environ, env), mock.patch("clipper.pipeline.download", fake_download), \
            mock.patch("clipper.transcribe.transcribe", fake_transcribe), mock.patch("clipper.pipeline.pick_clips", fake_pick), \
            mock.patch("server.jobs.generate_metadata", lambda t, model=None, **kw: {
                "title": "Demo title", "description": "Demo description\n\n#Shorts", "hashtags": ["Shorts"], "tags": ["demo"]}), \
            mock.patch("clipper.youtube.upload", lambda path, meta, **k: (time.sleep(DELAY * 2), "https://youtu.be/demo")[1]):
        from server.main import create_app
        print(f"\nDemo mode (fake download, Whisper, Gemini and YouTube): http://127.0.0.1:{port}\n")
        uvicorn.run(create_app(root), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
