"""Titles and descriptions use the source video's channel, the publisher's notes and the chapter, not only the transcript."""
import json

from clipper import download as dl
from clipper.metadata import build_prompt, credit_line, normalize
from conftest import spec, wait_for

SOURCE = {"title": "I Gave Away $1,000,000", "channel": "Big Channel", "url": "https://youtu.be/abc",
          "description": "In this video we give money away.", "tags": ["giveaway"],
          "chapters": [{"title": "Intro", "start": 0, "end": 60}, {"title": "The reveal", "start": 60, "end": 120}]}


def test_prompt_contains_everything_we_know():
    p = build_prompt("this is what is said", SOURCE, "Reacting to this video",
                     {"title": "Big moment", "reason": "shock", "start": 70, "end": 90})
    for needle in ("Big Channel", "I Gave Away $1,000,000", "https://youtu.be/abc", "The reveal",
                   "Reacting to this video", "Big moment", "this is what is said", "Never guess a name"):
        assert needle in p
    assert "Intro" not in p, "only the chapter that holds the clip"


def test_prompt_without_source_says_so_and_invents_nothing():
    p = build_prompt("hello", None, "", None)
    assert "Source video: (not known)" in p and "Editor notes from the person publishing (treat as true): none" in p


def test_credit_is_added_before_the_hashtags_and_limits_hold():
    raw = {"title": "t", "description": "x" * 6000, "hashtags": ["a"], "tags": ["k"]}
    out = normalize(raw, credit_line(SOURCE))
    assert len(out["description"]) <= 5000
    assert out["description"].endswith("Original video: I Gave Away $1,000,000 by Big Channel\nhttps://youtu.be/abc\n\n#Shorts #a")
    assert "Original video" not in normalize(raw)["description"]


def test_credit_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("YT_CREDIT_SOURCE", "false")
    assert credit_line(SOURCE) == ""


def test_source_info_is_saved_next_to_the_download(tmp_path):
    video = tmp_path / "abc-1080p.mp4"
    video.write_bytes(b"x")
    dl.save_source_info(video, {"title": "T", "uploader": "U", "webpage_url": "https://youtu.be/abc", "description": "d" * 5000,
                                "chapters": [{"title": "c", "start_time": 0, "end_time": 5}]}, "https://youtu.be/abc")
    got = dl.read_source_info(video)
    assert got["channel"] == "U" and got["title"] == "T" and len(got["description"]) == 1500
    assert got["chapters"] == [{"title": "c", "start": 0, "end": 5}]
    assert dl.read_source_info(tmp_path / "missing.mp4") == {}


def test_server_passes_source_and_notes_and_remembers_the_notes(client, video, stubs):
    dl.info_path(video).write_text(json.dumps(SOURCE), encoding="utf-8")
    jid = client.post("/api/jobs", json=spec(video)).json()["id"]
    assert wait_for(client, jid)[0]["status"] == "done"

    client.post(f"/api/jobs/{jid}/clips/c1/metadata", json={"context": "Reacting to Big Channel"})
    kw = stubs["meta_kw"][-1]
    assert kw["source"]["channel"] == "Big Channel" and kw["context"] == "Reacting to Big Channel"
    assert kw["hint"]["title"] == "First moment"

    client.post(f"/api/jobs/{jid}/clips/c2/metadata", json={})  # no notes sent: the saved ones are reused
    assert stubs["meta_kw"][-1]["context"] == "Reacting to Big Channel"
    client.post(f"/api/jobs/{jid}/clips/c1/metadata", json={"context": ""})  # empty clears them
    assert stubs["meta_kw"][-1]["context"] == ""
