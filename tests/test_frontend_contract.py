"""The React tests use recorded API responses (frontend/src/test/fixtures). If the API changes shape,
this fails: run `python scripts/capture_fixtures.py` and update the TypeScript types."""
import json
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "frontend" / "src" / "test" / "fixtures"


def load(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def test_job_shape_matches_fixture(client, done_job):
    jid, job = done_job
    saved = load("job_done")
    assert set(job) == set(saved)
    assert set(job["clips"][0]) == set(saved["clips"][0])
    assert set(job["spec"]) == set(saved["spec"])
    assert set(job["source"]) == set(saved["source"])


def test_summary_and_config_shape_match_fixtures(client, done_job):
    assert set(client.get("/api/jobs").json()[0]) == set(load("jobs")[0])
    live, saved = client.get("/api/config").json(), load("config")
    assert set(live) == set(saved) and set(live["defaults"]) == set(saved["defaults"])
    assert set(live["framing"][0]) == set(saved["framing"][0])
    assert set(live["accounts"][0]) == set(saved["accounts"][0])


def test_progress_detail_shapes_match_fixtures(client, video, stubs):
    saved = load("job_transcribing")
    assert set(saved["transcribe"]) == {"done", "total"}
    assert set(load("job_rendering")["render"]) == {"index", "total", "title"}
    assert {"stage", "done", "total", "fraction", "speed", "eta", "kind", "best"} == set(load("job_downloading")["download"])
