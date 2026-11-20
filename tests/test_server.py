import json
import subprocess
import time
import types
import sys
from datetime import datetime, timedelta, timezone

import pytest

from conftest import spec, wait_clip, wait_for


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


# ---------- app info and validation ----------
def test_config_lists_choices_and_accounts(client):
    c = client.get("/api/config").json()
    assert [a["name"] for a in c["accounts"]] == ["main", "second"]
    assert {x["id"] for x in c["framing"]} == {"face", "center", "fit", "fit-black"}
    assert [x["id"] for x in c["quality"]] == ["draft", "standard", "high", "max"]
    assert "classic" in c["caption_styles"] and c["defaults"]["quality"] == "standard"


@pytest.mark.parametrize("bad", [
    {"source_type": "link", "source": "not-a-link"},
    {"source_type": "path", "source": "x", "min_len": 50, "max_len": 20},
    {"source_type": "path", "source": "x", "style": "nope"},
    {"source_type": "path", "source": "x", "clips": 99},
    {"source_type": "path", "source": "x", "crop": "zoom"},
])
def test_bad_job_requests_are_rejected(client, bad):
    assert client.post("/api/jobs", json=bad).status_code == 422


def test_missing_local_file_is_rejected(client, tmp_path):
    r = client.post("/api/jobs", json={"source_type": "path", "source": str(tmp_path / "nope.mp4")})
    assert r.status_code == 422 and "File not found" in r.json()["detail"]


def test_unknown_job_is_404(client):
    assert client.get("/api/jobs/nope").status_code == 404


# ---------- the main flow ----------
def test_upload_then_clip(client, video, stubs):
    stubs["sleep"] = 0.1
    with open(video, "rb") as f:
        up = client.post("/api/uploads", files={"file": ("my video.mp4", f, "video/mp4")}).json()
    assert up["size"] == video.stat().st_size and "my_video.mp4" in up["path"]

    jid = client.post("/api/jobs", json=spec(up["path"], model="gemini-3.8-flash")).json()["id"]
    job, seen = wait_for(client, jid)

    assert job["status"] == "done" and len(job["clips"]) == 2 and job["message"] == "2 clips ready"
    assert stubs["pick_models"] == ["gemini-3.8-flash"]
    progress = [p for _, _, p in seen]
    assert progress == sorted(progress), "progress must never move backwards"
    assert {"transcribe", "render"} <= {s for _, s, _ in seen}, "UI should see the stages"
    assert job["duration"] == pytest.approx(14, abs=0.5)
    assert "transcript" not in job["clips"][0], "long transcripts are not sent to the browser"

    clip = job["clips"][0]
    assert (clip["title"], clip["score"], clip["quality"], clip["crop"]) == ("First moment", 91, "draft", "center")
    w, h, d = probe(client.app.state.store.job_dir(jid) / "clips" / clip["file"])
    assert (w, h) == (720, 1280) and d == pytest.approx(5.0, abs=0.3)  # draft = 720x1280


def test_video_supports_seeking_and_download(client, done_job):
    jid, job = done_job
    cid = job["clips"][0]["id"]
    full = client.get(f"/api/jobs/{jid}/clips/{cid}/video")
    assert full.status_code == 200 and full.headers["content-type"] == "video/mp4"
    part = client.get(f"/api/jobs/{jid}/clips/{cid}/video", headers={"Range": "bytes=0-99"})
    assert part.status_code == 206 and len(part.content) == 100  # browsers need this to scrub the video
    dl = client.get(f"/api/jobs/{jid}/clips/{cid}/download")
    assert "attachment" in dl.headers["content-disposition"]
    assert client.get(f"/api/jobs/{jid}/clips/{cid}/preview").status_code == 404  # no preview yet


def test_link_job_reports_download_progress(client, stubs, video, monkeypatch, tmp_path):
    stubs["sleep"] = 0.15

    def fake_download(url, out_dir, max_height=1080, on_progress=None):
        for done in (0, 40, 80):
            on_progress({"stage": "downloading", "done": done, "total": 100, "fraction": done / 100,
                         "speed": 5e6, "eta": 3, "kind": "video"})
            time.sleep(0.15)
        on_progress({"stage": "processing"})
        time.sleep(0.15)
        return video
    monkeypatch.setattr("clipper.pipeline.download", fake_download)

    jid = client.post("/api/jobs", json={"source_type": "link", "source": "https://youtube.com/watch?v=x",
                                         "quality": "draft", "crop": "center"}).json()["id"]
    job, seen = wait_for(client, jid)
    assert job["status"] == "done"
    assert any(s == "download" for _, s, _ in seen)
    assert job["download"]["stage"] == "done"


def test_errors_are_reported_not_raised(client, video, monkeypatch):
    def boom(*a, **k):
        raise KeyError("GEMINI_API_KEY")
    monkeypatch.setattr("clipper.pipeline.pick_clips", boom)
    jid = client.post("/api/jobs", json=spec(video)).json()["id"]
    job, _ = wait_for(client, jid)
    assert job["status"] == "failed" and "GEMINI_API_KEY is missing" in job["error"]


def test_cancel(client, video, stubs):
    stubs["sleep"] = 0.3
    jid = client.post("/api/jobs", json=spec(video)).json()["id"]
    time.sleep(0.4)
    assert client.post(f"/api/jobs/{jid}/cancel").status_code == 204
    job, _ = wait_for(client, jid)
    assert job["status"] == "cancelled"
    assert client.post(f"/api/jobs/{jid}/cancel").status_code == 409  # already finished


# ---------- editing ----------
def test_preview_then_final_edit(client, done_job):
    jid, job = done_job
    cid, store = job["clips"][0]["id"], client.app.state.store
    final_file = store.job_dir(jid) / "clips" / job["clips"][0]["file"]
    before = final_file.stat().st_mtime_ns

    r = client.post(f"/api/jobs/{jid}/clips/{cid}/edit", json={"mode": "preview", "start": 2.0, "end": 8.0})
    assert r.status_code == 202
    clip = wait_clip(client, jid, cid, "edit", ("idle", "error"))
    assert clip["edit"]["state"] == "idle" and clip["preview"]["file"] == "preview-01.mp4"
    w, h, d = probe(store.job_dir(jid) / "clips" / "preview-01.mp4")
    assert (w, h) == (540, 960) and d == pytest.approx(6.0, abs=0.3)
    assert final_file.stat().st_mtime_ns == before and clip["start"] == 1.0  # the saved clip is untouched
    assert client.get(f"/api/jobs/{jid}/clips/{cid}/preview").status_code == 200

    client.post(f"/api/jobs/{jid}/clips/{cid}/edit",
                json={"mode": "final", "start": 2.0, "end": 8.0, "crop": "fit", "style": "hormozi"})
    clip = wait_clip(client, jid, cid, "edit", ("idle", "error"))
    assert (clip["start"], clip["end"], clip["crop"], clip["style"]) == (2.0, 8.0, "fit", "hormozi")
    assert clip["rev"] == 2 and clip["preview"] is None
    assert probe(final_file)[2] == pytest.approx(6.0, abs=0.3)
    assert not (store.job_dir(jid) / "clips" / "preview-01.mp4").exists()


def test_caption_fix_is_kept(client, done_job, monkeypatch):
    jid, job = done_job
    cid = job["clips"][0]["id"]
    base = client.get(f"/api/jobs/{jid}/clips/{cid}/caption-text").json()
    assert base["count"] == len(base["text"].split()) and base["count"] > 3
    parts = base["text"].split(); parts[1] = "CORRECTED"

    seen = []
    import clipper.render as rd, server.jobs as sj
    real = rd.render_clip
    monkeypatch.setattr(sj, "render_clip", lambda *a, **k: (seen.append(k.get("words")), real(*a, **k))[1])
    client.post(f"/api/jobs/{jid}/clips/{cid}/edit",
                json={"mode": "final", "start": 1.0, "end": 6.0, "text": " ".join(parts)})
    wait_clip(client, jid, cid, "edit", ("idle", "error"))
    assert [w.text for w in seen[0]][1] == "CORRECTED"
    # remembered for later renders and for the next editing session
    assert "CORRECTED" in client.get(f"/api/jobs/{jid}/clips/{cid}/caption-text").json()["text"]
    saved = json.loads((client.app.state.store.job_dir(jid) / "transcript.json").read_text())
    assert any(w["text"] == "CORRECTED" for s in saved for w in s["words"])


@pytest.mark.parametrize("body,message", [
    ({"mode": "preview", "start": 5.0, "end": 6.0}, "between 3 and 180"),
    ({"mode": "preview", "start": 0.0, "end": 400.0}, "between 3 and 180"),
    ({"mode": "preview", "start": 10.0, "end": 20.0}, "past the end of the video"),
    ({"mode": "final", "start": 2.0, "end": 6.0, "text": "different words entirely"}, "Save the new start/end first"),
    ({"mode": "final", "start": 1.0, "end": 6.0, "text": "only three words"}, "same number of words"),
])
def test_edit_validation(client, done_job, body, message):
    jid, job = done_job
    r = client.post(f"/api/jobs/{jid}/clips/{job['clips'][0]['id']}/edit", json=body)
    assert r.status_code == 422 and message in r.json()["detail"]


# ---------- YouTube ----------
def test_metadata_generate_and_edit(client, done_job, stubs):
    jid, job = done_job
    cid = job["clips"][0]["id"]
    meta = client.post(f"/api/jobs/{jid}/clips/{cid}/metadata", json={"model": "gemini-2.0-flash"}).json()
    assert meta["title"] == "Generated title" and stubs["meta_models"] == ["gemini-2.0-flash"]
    edited = client.put(f"/api/jobs/{jid}/clips/{cid}/metadata",
                        json={"title": "My <b>own</b> title " + "x" * 150, "description": "Hi", "hashtags": ["#a", "b"],
                              "tags": ["one", "two"]}).json()
    assert len(edited["title"]) <= 100 and "<" not in edited["title"] and edited["hashtags"][0] == "Shorts"
    stored = next(c for c in client.get(f"/api/jobs/{jid}").json()["clips"] if c["id"] == cid)
    assert stored["meta"]["tags"] == ["one", "two"]


def test_upload_with_account_and_schedule(client, done_job, stubs):
    jid, job = done_job
    cid = job["clips"][0]["id"]
    when = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    r = client.post(f"/api/jobs/{jid}/clips/{cid}/upload",
                    json={"account": "second", "publish_at": when.isoformat(), "privacy": "private"})
    assert r.status_code == 202
    clip = wait_clip(client, jid, cid, "yt", ("done", "error"))
    assert clip["yt"] == {"state": "done", "account": "second", "url": "https://youtu.be/fake123", "error": None,
                          "scheduled": when.isoformat()}
    kw = stubs["upload"][0]
    assert kw["account"] == "second" and kw["publish_at"] == when and kw["privacy"] == "private"
    assert clip["meta"]["title"] == "Generated title"  # written automatically when missing


@pytest.mark.parametrize("body,status", [
    ({"account": "nobody"}, 422),
    ({"publish_at": "2020-01-01T10:00:00+00:00"}, 422),
    ({"publish_at": "2099-01-01T10:00:00"}, 422),   # no time zone
    ({"publish_at": "tomorrow"}, 422),
])
def test_upload_validation(client, done_job, body, status):
    jid, job = done_job
    assert client.post(f"/api/jobs/{jid}/clips/{job['clips'][0]['id']}/upload", json=body).status_code == status


def test_upload_failure_is_shown(client, done_job, monkeypatch):
    jid, job = done_job
    cid = job["clips"][0]["id"]
    def fail(*a, **k):
        raise FileNotFoundError("'client_secret.json' not found. See the README.")
    monkeypatch.setattr("clipper.youtube.upload", fail)
    client.post(f"/api/jobs/{jid}/clips/{cid}/upload", json={})
    clip = wait_clip(client, jid, cid, "yt", ("done", "error"))
    assert clip["yt"]["state"] == "error" and "client_secret.json" in clip["yt"]["error"]


def test_sign_out_removes_token(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "token_second.json").write_text("{}")
    assert client.get("/api/config").json()["accounts"][1]["signed_in"] is True
    assert client.post("/api/accounts/second/sign-out").status_code == 204
    assert not (tmp_path / "token_second.json").exists()
    assert client.post("/api/accounts/ghost/sign-out").status_code == 404


# ---------- storage ----------
def test_jobs_survive_a_restart(make_client, video, stubs):
    c1 = make_client()
    jid = c1.post("/api/jobs", json=spec(video)).json()["id"]
    wait_for(c1, jid)
    # a second job that is "running" when the server stops
    store = c1.app.state.store
    store.jobs["ghost"] = {**store.jobs[jid], "id": "ghost", "status": "running", "created": time.time() + 1}
    store._persist(store.jobs["ghost"], force=True)

    c2 = make_client()                                   # = the server was restarted
    listing = {j["id"]: j for j in c2.get("/api/jobs").json()}
    assert listing[jid]["status"] == "done" and listing[jid]["clips"] == 2
    assert listing["ghost"]["status"] == "interrupted"
    assert c2.get(f"/api/jobs/{jid}/clips/c1/video").status_code == 200  # the clips are still there
    assert c2.get(f"/api/jobs/{jid}/clips/c1/caption-text").json()["count"] > 0  # and still editable


def test_delete_removes_files(client, done_job):
    jid, _ = done_job
    folder = client.app.state.store.job_dir(jid)
    assert client.delete(f"/api/jobs/{jid}").status_code == 204
    assert not folder.exists() and client.get(f"/api/jobs/{jid}").status_code == 404
