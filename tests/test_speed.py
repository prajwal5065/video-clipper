"""Speed settings: Whisper uses the CPU it has, face detection reads keyframes, stage timings are printed."""
import sys
import types

import pytest

from clipper import framing
from conftest import spec, wait_for


class _FakeWhisper:
    created = []

    def __init__(self, size, device="auto", compute_type="int8", cpu_threads=0, **kw):
        self.created.append({"size": size, "cpu_threads": cpu_threads})
        self.calls = []

    def transcribe(self, path, **kw):
        _FakeWhisper.created[-1].update(kw)
        return iter(()), None


@pytest.fixture
def fake_whisper(monkeypatch):
    _FakeWhisper.created.clear()
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=_FakeWhisper))
    return _FakeWhisper


def test_whisper_uses_more_than_four_threads_and_greedy_decoding(fake_whisper, video, monkeypatch):
    from clipper import transcribe as tr
    monkeypatch.delenv("WHISPER_THREADS", raising=False)
    monkeypatch.delenv("WHISPER_BEAM_SIZE", raising=False)
    monkeypatch.setattr("os.cpu_count", lambda: 16)
    tr.transcribe(video, "tiny")
    assert fake_whisper.created[-1]["cpu_threads"] == 8
    assert fake_whisper.created[-1]["beam_size"] == 1


def test_whisper_settings_can_be_overridden(fake_whisper, video, monkeypatch):
    from clipper import transcribe as tr
    monkeypatch.setenv("WHISPER_THREADS", "3")
    monkeypatch.setenv("WHISPER_BEAM_SIZE", "5")
    tr.transcribe(video, "tiny")
    assert fake_whisper.created[-1]["cpu_threads"] == 3
    assert fake_whisper.created[-1]["beam_size"] == 5


def test_whisper_never_drops_below_four_threads(monkeypatch):
    from clipper import transcribe as tr
    monkeypatch.delenv("WHISPER_THREADS", raising=False)
    monkeypatch.setattr("os.cpu_count", lambda: 2)
    assert tr._threads() == 4


def _fake_cascade(monkeypatch):
    import cv2

    class Cascade:
        def __init__(self, *a):
            pass

        def detectMultiScale(self, gray, **kw):
            return [[100, 50, 60, 60]]  # a face centred 130 px from the left of the small frame

    monkeypatch.setattr(cv2, "CascadeClassifier", Cascade)


def _small_width(video):
    import cv2
    cap = cv2.VideoCapture(str(video))
    w, h = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    cap.release()
    return 480 * w / h if h > 480 else w


def test_face_position_comes_from_keyframes(video, monkeypatch):
    _fake_cascade(monkeypatch)
    monkeypatch.setattr(framing, "_seek_images", lambda *a, **k: pytest.fail("should not need exact seeking"))
    monkeypatch.setattr(framing, "_keyframe_images", lambda *a, **k: [__import__("numpy").zeros((480, 270, 3), "uint8")] * 6)
    assert framing.face_center(video, 0, 10) == pytest.approx(130 / 270)


def test_face_position_falls_back_to_exact_times_when_keyframes_are_too_few(video, monkeypatch):
    _fake_cascade(monkeypatch)
    monkeypatch.setattr(framing, "_keyframe_images", lambda *a, **k: [])
    got = framing.face_center(video, 0, 4)
    assert got == pytest.approx(130 / _small_width(video), abs=0.02)


def test_real_ffmpeg_keyframe_frames_are_small(video):
    frames = framing._keyframe_images(video, 0, 4)
    assert frames and all(f.shape[0] == 480 for f in frames)


def test_stage_timings_are_printed(client, video, stubs, capsys):
    jid = client.post("/api/jobs", json=spec(video)).json()["id"]
    assert wait_for(client, jid)[0]["status"] == "done"
    out = capsys.readouterr().out
    assert "[timing]" in out and "transcribe" in out and "render" in out and "total" in out
