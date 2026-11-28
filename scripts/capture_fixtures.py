"""Record real API responses (config, jobs at every stage) for the React tests.

    python scripts/capture_fixtures.py

Run it again whenever the API changes; tests/test_frontend_contract.py fails if the saved shapes drift.
Whisper, Gemini and yt-dlp are faked; FFmpeg is real.
"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clipper import transcribe as tr  # noqa: E402
from server.main import create_app  # noqa: E402

OUT = ROOT / "frontend" / "src" / "test" / "fixtures"


def make_video(path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25:duration=14",
                    "-f", "lavfi", "-i", "sine=frequency=300:duration=14", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(path)], check=True)


def fakes(video, delay):
    words = [tr.Word(i * 0.5, i * 0.5 + 0.4, f"word{i}") for i in range(26)]

    def transcribe(src, model, device, compute, chunk_seconds=600, on_progress=None):
        for done in (0, 5, 10, 13):
            on_progress and on_progress(done, 13)
            time.sleep(delay)
        return [tr.Segment(0, 13, "all words", [tr.Word(w.start, w.end, w.text) for w in words])]

    def pick(segments, n, mn, mx, model=None):
        return [{"start": 1.0, "end": 6.0, "title": "Why most startups fail", "score": 92, "reason": "Opens with a bold claim."},
                {"start": 7.0, "end": 12.0, "title": "The one habit that changed everything", "score": 85, "reason": "Complete story."}]

    def download(url, out_dir, max_height=1080, on_progress=None):
        gb = 1024 ** 3
        for done in (0.2, 0.9, 1.5, 2.2, 2.67):
            on_progress({"stage": "downloading", "done": done * gb, "total": 2.67 * gb, "fraction": done / 2.67,
                         "speed": 3.35 * 1024 ** 2, "eta": int((2.67 - done) * gb / (3.35 * 1024 ** 2)), "kind": "video"})
            time.sleep(delay)
        on_progress({"stage": "processing"})
        time.sleep(delay)
        return video

    return transcribe, pick, download


def clean(obj, tmp):
    return json.loads(json.dumps(obj).replace(str(tmp), "C:/videos").replace("\\\\", "/"))


def save(name, obj, tmp):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(clean(obj, tmp), indent=2), encoding="utf-8")
    print("saved", name)


def main():
    tmp = Path(tempfile.mkdtemp())
    video = tmp / "interview.mp4"
    make_video(video)
    transcribe, pick, download = fakes(video, 0.5)
    seen = {}
    with mock.patch("clipper.transcribe.transcribe", transcribe), mock.patch("clipper.pipeline.pick_clips", pick), \
            mock.patch("clipper.pipeline.download", download), \
            mock.patch("server.jobs.generate_metadata", lambda t, model=None, **kw: {
                "title": "The one thing nobody tells you about growing fast", "description": "Most creators miss this.\n\n#Shorts #growth",
                "hashtags": ["Shorts", "growth"], "tags": ["youtube growth", "creator tips"]}), \
            mock.patch("clipper.youtube.upload", lambda path, meta, **k: (time.sleep(0.8), "https://youtu.be/abc123")[1]), \
            mock.patch.dict("os.environ", {"YT_ACCOUNTS": "main,second", "GEMINI_API_KEY": "x"}):
        client = TestClient(create_app(tmp / "data"))
        save("config", client.get("/api/config").json(), tmp)

        # one link job, snapshotted at every stage
        jid = client.post("/api/jobs", json={"source_type": "link", "source": "https://www.youtube.com/watch?v=abc123",
                                             "quality": "draft", "crop": "center"}).json()["id"]
        wants = {
            "job_downloading": lambda j: j["stage"] == "download" and (j["download"] or {}).get("stage") == "downloading" and j["download"]["fraction"] >= 0.3,
            "job_merging": lambda j: (j["download"] or {}).get("stage") == "processing",
            "job_transcribing": lambda j: j["stage"] == "transcribe" and (j["transcribe"] or {}).get("done", 0) >= 5,
            "job_rendering": lambda j: j["stage"] == "render" and j["render"] is not None,
        }
        deadline = time.time() + 120
        while time.time() < deadline:
            job = client.get(f"/api/jobs/{jid}").json()
            for name, ok in wants.items():
                if name not in seen and ok(job):
                    seen[name] = job
            if job["status"] in ("done", "failed"):
                break
            time.sleep(0.05)
        seen["job_done"] = job
        for name, obj in seen.items():
            save(name, obj, tmp)
        save("jobs", client.get("/api/jobs").json(), tmp)

        # clip states: editing, preview, AI metadata, uploading, uploaded
        first = lambda: client.get(f"/api/jobs/{jid}").json()["clips"][0]  # noqa: E731
        client.post(f"/api/jobs/{jid}/clips/c1/edit", json={"mode": "preview", "start": 2.0, "end": 8.0})
        rendering = None
        while True:
            clip = first()
            if rendering is None and clip["edit"]["state"] == "rendering":
                rendering = clip
            if clip["edit"]["state"] in ("idle", "error"):
                break
            time.sleep(0.01)
        previewed = clip
        rendering = rendering or {**previewed, "edit": {"state": "rendering", "kind": "preview", "progress": 0.4, "error": None}}
        meta = client.post(f"/api/jobs/{jid}/clips/c1/metadata", json={}).json()
        client.post(f"/api/jobs/{jid}/clips/c1/upload", json={"account": "second"})
        uploading = None
        while True:
            clip = first()
            if uploading is None and (clip["yt"] or {}).get("state") == "uploading":
                uploading = clip
            if (clip["yt"] or {}).get("state") in ("done", "error"):
                break
            time.sleep(0.02)
        save("clip_states", {"edit_rendering": rendering, "previewed": previewed, "meta": meta,
                             "yt_uploading": uploading or clip, "yt_done": clip}, tmp)

        # a failed job and a cancelled job (local file source)
        with mock.patch("clipper.pipeline.pick_clips", mock.Mock(side_effect=KeyError("GEMINI_API_KEY"))):
            fid = client.post("/api/jobs", json={"source_type": "path", "source": str(video), "quality": "draft"}).json()["id"]
            while client.get(f"/api/jobs/{fid}").json()["status"] not in ("failed", "done"):
                time.sleep(0.05)
            save("job_failed", client.get(f"/api/jobs/{fid}").json(), tmp)
        client.app.state.store.cache_dir  # (transcript cache would skip the slow step; use a different file)
        slow = tmp / "slow.mp4"
        make_video(slow)
        cid = client.post("/api/jobs", json={"source_type": "path", "source": str(slow)}).json()["id"]
        time.sleep(0.8)
        client.post(f"/api/jobs/{cid}/cancel")
        while client.get(f"/api/jobs/{cid}").json()["status"] not in ("cancelled", "done", "failed"):
            time.sleep(0.05)
        save("job_cancelled", client.get(f"/api/jobs/{cid}").json(), tmp)


if __name__ == "__main__":
    main()
