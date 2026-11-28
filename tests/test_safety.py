"""A failed render keeps the old clip; a transcript is tied to its exact file; foreign Host headers are refused."""
import shutil

import pytest

from clipper import transcribe as tr
from clipper.render import render_clip


def test_failed_render_keeps_the_existing_clip(tmp_path):
    out = tmp_path / "clips"
    out.mkdir()
    existing = out / "01-clip.mp4"
    existing.write_bytes(b"the good clip")
    clip = {"start": 0, "end": 5, "title": "clip"}
    with pytest.raises(RuntimeError):
        render_clip(tmp_path / "missing.mp4", clip, [], out, 1, captions=False, crop="center", quality="draft")
    assert existing.read_bytes() == b"the good clip"
    assert [p.name for p in out.iterdir()] == ["01-clip.mp4"], "no half-written leftovers"


def test_successful_render_replaces_the_clip(tmp_path, video):
    out = tmp_path / "clips"
    out.mkdir()
    (out / "01-clip.mp4").write_bytes(b"old")
    f = render_clip(video, {"start": 0, "end": 3, "title": "clip"}, [], out, 1, captions=False,
                    crop="center", quality="draft")
    assert f.stat().st_size > 1000
    assert [p.name for p in out.iterdir()] == ["01-clip.mp4"]


def test_same_name_different_files_get_different_fingerprints(tmp_path, video):
    a, b = tmp_path / "a" / "talk.mp4", tmp_path / "b" / "talk.mp4"
    a.parent.mkdir()
    b.parent.mkdir()
    shutil.copy(video, a)
    shutil.copy(video, b)
    assert tr.fingerprint(a) != tr.fingerprint(b)
    assert tr.fingerprint(a) == tr.fingerprint(a)


def test_requests_for_other_host_names_are_refused(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health", headers={"Host": "localhost:8000"}).status_code == 200
    assert client.get("/api/health", headers={"Host": "evil.example.com"}).status_code == 400
