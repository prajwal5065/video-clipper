import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clipper import transcribe as tr  # noqa: E402
from server.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def video(tmp_path_factory):
    """A 14-second 320x180 test video with audio."""
    p = tmp_path_factory.mktemp("media") / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25:duration=14",
         "-f", "lavfi", "-i", "sine=frequency=300:duration=14", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(p)], check=True)
    return p


@pytest.fixture
def stubs(monkeypatch):
    """Replace Whisper, Gemini, yt-dlp and YouTube with fast fakes (FFmpeg stays real)."""
    rec = {"upload": [], "meta_models": [], "meta_kw": [], "pick_models": [], "sleep": 0.0}
    words = [tr.Word(i * 0.5, i * 0.5 + 0.4, f"word{i}") for i in range(26)]
    segs = [tr.Segment(0, 13, "all", words)]

    def fake_transcribe(src, model, device, compute, chunk_seconds=600, on_progress=None):
        for done in (0, 5, 10, 13):
            if on_progress:
                on_progress(done, 13)
            time.sleep(rec["sleep"])
        return [tr.Segment(s.start, s.end, s.text, [tr.Word(w.start, w.end, w.text) for w in s.words]) for s in segs]

    def fake_pick(segments, n, mn, mx, model=None):
        rec["pick_models"].append(model)
        return [{"start": 1.0, "end": 6.0, "title": "First moment", "score": 91, "reason": "Strong hook"},
                {"start": 7.0, "end": 12.0, "title": "Second moment", "score": 80, "reason": "Good story"}][:n]

    monkeypatch.setattr("clipper.transcribe.transcribe", fake_transcribe)
    monkeypatch.setattr("clipper.pipeline.pick_clips", fake_pick)
    monkeypatch.setattr("server.jobs.generate_metadata", lambda t, model=None, **kw: (
        rec["meta_models"].append(model), rec["meta_kw"].append(kw),
        {"title": "Generated title", "description": "Generated description\n\n#Shorts", "hashtags": ["Shorts"],
         "tags": ["tag"]})[2])
    monkeypatch.setattr("clipper.youtube.upload", lambda path, meta, **k: (
        rec["upload"].append(k), time.sleep(rec["sleep"]), "https://youtu.be/fake123")[2])
    monkeypatch.setenv("YT_ACCOUNTS", "main,second")
    return rec


@pytest.fixture
def client(tmp_path, stubs):
    return TestClient(create_app(tmp_path / "data"))


@pytest.fixture
def make_client(tmp_path, stubs):
    def make():
        return TestClient(create_app(tmp_path / "data"))
    return make


def wait_for(client, jid, states=("done", "failed", "cancelled"), timeout=120):
    """Poll a job until it reaches one of the states; returns (final job, every progress value seen)."""
    seen, deadline = [], time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{jid}").json()
        seen.append((job["status"], job["stage"], job["progress"]))
        if job["status"] in states:
            return job, seen
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {seen[-1]}")


def wait_clip(client, jid, cid, key, done_states, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        clip = next(c for c in client.get(f"/api/jobs/{jid}").json()["clips"] if c["id"] == cid)
        if (clip.get(key) or {}).get("state") in done_states:
            return clip
        time.sleep(0.05)
    raise AssertionError(f"{key} did not finish")


def spec(video, **kw):
    return {"source_type": "path", "source": str(video), "quality": "draft", "crop": "center", **kw}


@pytest.fixture
def done_job(client, video):
    jid = client.post("/api/jobs", json=spec(video)).json()["id"]
    job, _ = wait_for(client, jid)
    assert job["status"] == "done", job
    return jid, job
