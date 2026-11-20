"""Jobs: run the pipeline in the background, keep progress, save everything to disk."""
import copy
import json
import os
import re
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from clipper import pipeline
from clipper import transcribe as tr
from clipper import youtube as yt
from clipper.metadata import generate_metadata, normalize, transcript_for
from clipper.render import clip_words, render_clip

PERSIST_EVERY = 1.0  # seconds: progress is kept in memory, written to disk at most this often


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def friendly(e):
    """Turn an exception into a message a user can act on."""
    if isinstance(e, KeyError) and "GEMINI_API_KEY" in str(e):
        return "GEMINI_API_KEY is missing. Add it to your .env file and restart the server."
    return str(e) or type(e).__name__


class JobStore:
    def __init__(self, root):
        self.root = Path(root)
        self.jobs_dir = self.root / "jobs"
        self.cache_dir = self.root / "_cache"
        self.uploads_dir = self.root / "_uploads"
        for d in (self.jobs_dir, self.cache_dir, self.uploads_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.jobs, self._written, self._segments = {}, {}, {}
        self.job_pool = ThreadPoolExecutor(max_workers=1)   # one heavy job at a time
        self.edit_pool = ThreadPoolExecutor(max_workers=2)  # edits, previews, uploads
        self._load()

    # ---------- storage ----------
    def job_dir(self, jid):
        return self.jobs_dir / jid

    def _load(self):
        for f in sorted(self.jobs_dir.glob("*/job.json")):
            try:
                job = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if job.get("status") in ("queued", "running"):
                job.update(status="interrupted", message="The server was restarted while this job was running.")
            for c in job.get("clips", []):
                if (c.get("edit") or {}).get("state") == "rendering":
                    c["edit"] = {"state": "error", "error": "Interrupted by a restart."}
                if (c.get("yt") or {}).get("state") == "uploading":
                    c["yt"] = {**c["yt"], "state": "error", "error": "Interrupted by a restart."}
            self.jobs[job["id"]] = job

    def _persist(self, job, force=False):
        now = time.time()
        if not force and now - self._written.get(job["id"], 0) < PERSIST_EVERY:
            return
        self._written[job["id"]] = now
        d = self.job_dir(job["id"])
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "job.json.tmp"
        tmp.write_text(json.dumps(job, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, d / "job.json")

    # ---------- reading ----------
    def get(self, jid):
        with self.lock:
            if jid not in self.jobs:
                raise ApiError(404, "Job not found.")
            return self.jobs[jid]

    @staticmethod
    def public(job):
        out = copy.deepcopy(job)
        for c in out.get("clips", []):
            c.pop("transcript", None)
        return out

    def summary(self, job):
        return {k: job.get(k) for k in ("id", "created", "status", "stage", "progress", "message", "label")} | {
            "clips": len(job.get("clips", [])), "thumbnail_clip": (job.get("clips") or [{}])[0].get("id")}

    def list(self):
        with self.lock:
            return [self.summary(j) for j in sorted(self.jobs.values(), key=lambda j: j["created"], reverse=True)]

    def update(self, jid, force=False, **fields):
        with self.lock:
            job = self.get(jid)
            job.update(fields)
            job["updated"] = time.time()
            self._persist(job, force or "status" in fields)

    def _clip(self, job, cid):
        for c in job.get("clips", []):
            if c["id"] == cid:
                return c
        raise ApiError(404, "Clip not found.")

    def update_clip(self, jid, cid, force=False, **fields):
        with self.lock:
            job = self.get(jid)
            self._clip(job, cid).update(fields)
            job["updated"] = time.time()
            self._persist(job, force)

    def segments(self, jid):
        with self.lock:
            if jid not in self._segments:
                self._segments[jid] = tr.load(self.job_dir(jid) / "transcript.json")
            return self._segments[jid]

    def clip_path(self, jid, cid, preview=False):
        job = self.get(jid)
        clip = self._clip(job, cid)
        name = (clip.get("preview") or {}).get("file") if preview else clip.get("file")
        path = self.job_dir(jid) / "clips" / name if name else None
        if not path or not path.exists():
            raise ApiError(404, "That video file does not exist (yet).")
        return path

    # ---------- creating and running jobs ----------
    def create(self, spec):
        jid = uuid.uuid4().hex[:10]
        label = spec["source"] if spec["source_type"] == "link" else Path(spec["source"]).name
        job = {"id": jid, "created": time.time(), "updated": time.time(), "status": "queued", "stage": "queued",
               "progress": 0.0, "message": "Waiting to start", "label": label, "spec": spec, "error": None,
               "download": None, "transcribe": None, "render": None, "duration": None, "source": None, "clips": []}
        with self.lock:
            self.jobs[jid] = job
            self._persist(job, force=True)
        self.job_pool.submit(self._run, jid)
        return job

    def _cancelled(self, jid):
        return bool(self.jobs[jid].get("cancel"))

    def _run(self, jid):
        job = self.get(jid)
        if self._cancelled(jid):
            return self.update(jid, status="cancelled", message="Cancelled")
        self.update(jid, status="running", stage="download", message="Starting")

        def report(stage, overall, message, **extra):
            if self._cancelled(jid):
                raise pipeline.Cancelled()
            self.update(jid, stage=stage, progress=round(overall, 4), message=message, **extra)

        try:
            result = pipeline.process(job["spec"], self.job_dir(jid), self.cache_dir, report)
            with self.lock:
                self._segments[jid] = result["segments"]
            self.update(jid, status="done", stage="done", progress=1.0, duration=result["duration"],
                        source={"path": str(result["source"]), "name": Path(result["source"]).name},
                        clips=result["clips"], message=f"{len(result['clips'])} clips ready", force=True)
        except pipeline.Cancelled:
            self.update(jid, status="cancelled", message="Cancelled", force=True)
        except Exception as e:  # shown to the user, never crashes the server
            self.update(jid, status="failed", error=friendly(e), message="Failed", force=True)

    def cancel(self, jid):
        job = self.get(jid)
        if job["status"] not in ("queued", "running"):
            raise ApiError(409, "This job is not running.")
        with self.lock:
            job["cancel"] = True
        self.update(jid, message="Cancelling...")

    def delete(self, jid):
        job = self.get(jid)
        if job["status"] in ("queued", "running"):
            raise ApiError(409, "Cancel the job before deleting it.")
        with self.lock:
            self.jobs.pop(jid, None)
            self._segments.pop(jid, None)
        shutil.rmtree(self.job_dir(jid), ignore_errors=True)

    # ---------- editing a clip ----------
    def caption_text(self, jid, cid):
        clip = self._clip(self.get(jid), cid)
        words = clip_words(self.segments(jid), clip["start"], clip["end"])
        return {"text": " ".join(w.text for w in words), "count": len(words)}

    def start_edit(self, jid, cid, e):
        job = self.get(jid)
        clip = self._clip(job, cid)
        if job["status"] != "done":
            raise ApiError(409, "The job is not finished yet.")
        if (clip.get("edit") or {}).get("state") == "rendering":
            raise ApiError(409, "This clip is already rendering.")
        length, dur = e.end - e.start, job.get("duration")
        if length < 3 or length > 180:
            raise ApiError(422, "The clip must be between 3 and 180 seconds long (end must be after start).")
        if dur and e.end > dur + 0.01:
            raise ApiError(422, f"The end time is past the end of the video ({dur:.1f}s).")
        captions = clip["captions"] if e.captions is None else e.captions
        words = None
        if captions and e.text is not None:
            base = clip_words(self.segments(jid), clip["start"], clip["end"])
            if e.text.strip() != " ".join(w.text for w in base).strip():
                if (e.start, e.end) != (clip["start"], clip["end"]):
                    raise ApiError(422, "Save the new start/end first, then fix the captions.")
                parts = e.text.split()
                if len(parts) != len(base):
                    raise ApiError(422, f"Keep the same number of words: the clip has {len(base)}, you wrote {len(parts)}.")
                words = [tr.Word(w.start, w.end, p) for w, p in zip(base, parts)]
        params = {"mode": e.mode, "start": e.start, "end": e.end, "captions": captions,
                  "crop": e.crop or clip["crop"], "style": e.style or clip["style"]}
        self.update_clip(jid, cid, force=True, edit={"state": "rendering", "kind": e.mode, "progress": 0.0, "error": None})
        self.edit_pool.submit(self._do_edit, jid, cid, params, words)

    def _do_edit(self, jid, cid, p, words):
        job = self.get(jid)
        clip = copy.deepcopy(self._clip(job, cid))
        preview = p["mode"] == "preview"

        def progress(f):
            self.update_clip(jid, cid, edit={"state": "rendering", "kind": p["mode"], "progress": round(f, 3), "error": None})

        try:
            out = render_clip(job["source"]["path"], {**clip, "start": p["start"], "end": p["end"]}, self.segments(jid),
                              self.job_dir(jid) / "clips", clip["index"], captions=p["captions"], crop=p["crop"],
                              style=p["style"], quality=clip["quality"], words=words, on_progress=progress,
                              out_name=f"preview-{clip['index']:02d}.mp4" if preview else None, preview=preview)
        except Exception as e:
            return self.update_clip(jid, cid, force=True, edit={"state": "error", "kind": p["mode"], "error": friendly(e)})
        with self.lock:
            c = self._clip(self.get(jid), cid)
            if preview:
                c["preview"] = {"file": out.name, "rev": time.time(), "start": p["start"], "end": p["end"]}
            else:
                if words:  # keep the corrected spelling for every later render
                    fixed = {(w.start, w.end): w.text for w in words}
                    for seg in self.segments(jid):
                        for w in seg.words:
                            w.text = fixed.get((w.start, w.end), w.text)
                    tr.save(self.segments(jid), self.job_dir(jid) / "transcript.json")
                old_preview = (c.get("preview") or {}).get("file")
                c.update(start=p["start"], end=p["end"], crop=p["crop"], style=p["style"], captions=p["captions"],
                         file=out.name, rev=c.get("rev", 1) + 1, preview=None,
                         transcript=transcript_for(self.segments(jid), p["start"], p["end"]))
                if not (c.get("yt") or {}).get("url"):
                    c["meta"] = None  # title/description are written again for the new cut
                if old_preview:
                    (self.job_dir(jid) / "clips" / old_preview).unlink(missing_ok=True)
            c["edit"] = {"state": "idle", "kind": p["mode"], "progress": 1.0, "error": None}
            self._persist(self.get(jid), force=True)

    # ---------- YouTube metadata and upload ----------
    def make_meta(self, jid, cid, model=None):
        clip = self._clip(self.get(jid), cid)
        try:
            meta = generate_metadata(clip.get("transcript", ""), model=model)
        except Exception as e:
            raise ApiError(502, friendly(e))
        self.update_clip(jid, cid, force=True, meta=meta)
        return meta

    def set_meta(self, jid, cid, body):
        meta = normalize({"title": body.title, "description": body.description,
                          "hashtags": body.hashtags, "tags": body.tags})
        self.update_clip(jid, cid, force=True, meta=meta)
        return meta

    def start_upload(self, jid, cid, b):
        job = self.get(jid)
        clip = self._clip(job, cid)
        if job["status"] != "done":
            raise ApiError(409, "The job is not finished yet.")
        if (clip.get("yt") or {}).get("state") == "uploading":
            raise ApiError(409, "This clip is already uploading.")
        accounts = yt.accounts()
        account = b.account or accounts[0]
        if account not in accounts:
            raise ApiError(422, f"Unknown YouTube account '{account}'. Known accounts: {', '.join(accounts)}.")
        when = None
        if b.publish_at:
            try:
                when = datetime.fromisoformat(b.publish_at.replace("Z", "+00:00"))
            except ValueError:
                raise ApiError(422, "publish_at must be an ISO 8601 date-time, e.g. 2026-11-25T18:00:00+05:30.")
            if when.tzinfo is None:
                raise ApiError(422, "publish_at needs a time zone, e.g. +05:30 or Z.")
            if when <= datetime.now(timezone.utc) + timedelta(minutes=10):
                raise ApiError(422, "The publish time must be at least 10 minutes in the future.")
        path = self.clip_path(jid, cid)
        self.update_clip(jid, cid, force=True, yt={"state": "uploading", "account": account, "url": None, "error": None,
                         "scheduled": b.publish_at, "message": "Preparing the upload (a browser window may open for Google sign-in)"})
        self.edit_pool.submit(self._do_upload, jid, cid, path, account, when, b)

    def _do_upload(self, jid, cid, path, account, when, b):
        try:
            clip = self._clip(self.get(jid), cid)
            meta = clip.get("meta") or self.make_meta(jid, cid, b.model)
            url = yt.upload(path, meta, privacy=b.privacy, made_for_kids=b.made_for_kids,
                            publish_at=when, account=account)
            yt_state = {"state": "done", "account": account, "url": url, "error": None, "scheduled": b.publish_at}
        except ApiError as e:
            yt_state = {"state": "error", "account": account, "url": None, "error": e.message}
        except Exception as e:
            yt_state = {"state": "error", "account": account, "url": None, "error": friendly(e)}
        self.update_clip(jid, cid, force=True, yt=yt_state)
