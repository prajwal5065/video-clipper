"""HTTP API for the video clipper (FastAPI). Start it with:  py -3.11 -m server"""
import os
import re
import shutil
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from clipper import youtube as yt
from clipper.captions import STYLES

from .jobs import ApiError, JobStore
from .schemas import EditSpec, GenerateMetaBody, JobSpec, MetaBody, UploadBody

WEBUI_DIR = Path(__file__).resolve().parent.parent / "webui"  # the built React app, if present

FRAMING = [
    {"id": "face", "label": "Follow the face", "description": "Fills the screen and keeps the speaker in frame; cuts off the sides."},
    {"id": "center", "label": "Center crop", "description": "Fills the screen with the middle of the picture; cuts off the sides."},
    {"id": "fit", "label": "Full frame, blurred background", "description": "Keeps the whole picture; a blurred copy fills the space."},
    {"id": "fit-black", "label": "Full frame, black bars", "description": "Keeps the whole picture with black bars above and below."},
]
QUALITY_LEVELS = [
    {"id": "draft", "label": "Draft", "description": "720p, fastest"},
    {"id": "standard", "label": "Standard", "description": "1080p, balanced"},
    {"id": "high", "label": "High", "description": "1080p, sharper, slower"},
    {"id": "max", "label": "Max", "description": "Best quality, slowest, big downloads"},
]
WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-3.8-flash", "gemini-2.0-flash", "gemini-1.5-flash"]


def create_app(root=None, webui_dir=None):
    load_dotenv()
    store = JobStore(root or os.environ.get("CLIPPER_DATA_DIR", "output"))
    app = FastAPI(title="Video Clipper API", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.store = store
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(ApiError)
    async def api_error(_request, e: ApiError):
        return JSONResponse({"detail": e.message}, status_code=e.status)

    # ---------- app info ----------
    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/config")
    def config():
        accounts = [{"name": a, "signed_in": yt.token_path(a).exists()} for a in yt.accounts()]
        default_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        return {
            "gemini_key_set": bool(os.environ.get("GEMINI_API_KEY")),
            "youtube_ready": Path(os.environ.get("YT_CLIENT_SECRET_FILE", "client_secret.json")).exists(),
            "accounts": accounts,
            "framing": FRAMING, "quality": QUALITY_LEVELS, "whisper_models": WHISPER_MODELS,
            "caption_styles": list(STYLES),
            "gemini_models": GEMINI_MODELS if default_model in GEMINI_MODELS else [default_model, *GEMINI_MODELS],
            "defaults": {"gemini_model": default_model, "privacy": os.environ.get("YT_PRIVACY", "private"),
                         "made_for_kids": os.environ.get("YT_MADE_FOR_KIDS", "false").lower() in ("1", "true", "yes"),
                         "clips": 5, "min_len": 20, "max_len": 60, "whisper": "small", "device": "auto",
                         "compute_type": "int8", "crop": "face", "quality": "standard", "captions": True,
                         "style": "classic"},
        }

    @app.post("/api/accounts/{name}/sign-out", status_code=204)
    def sign_out(name: str):
        if name not in yt.accounts():
            raise ApiError(404, "Unknown account.")
        yt.forget_account(name)

    # ---------- files in ----------
    @app.post("/api/uploads")
    def upload_video(file: UploadFile = File(...)):
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", file.filename or "video")[-80:]
        dest = store.uploads_dir / f"{uuid.uuid4().hex[:8]}-{safe}"
        with open(dest, "wb") as out:
            shutil.copyfileobj(file.file, out, 1024 * 1024)
        return {"path": str(dest), "name": file.filename, "size": dest.stat().st_size}

    # ---------- jobs ----------
    @app.post("/api/jobs", status_code=201)
    def create_job(spec: JobSpec):
        data = spec.model_dump()
        if spec.source_type == "path":
            p = Path(spec.source)
            if not p.is_file():
                raise ApiError(422, f"File not found: {spec.source}")
        return store.public(store.create(data))

    @app.get("/api/jobs")
    def list_jobs():
        return store.list()

    @app.get("/api/jobs/{jid}")
    def get_job(jid: str):
        with store.lock:
            return store.public(store.get(jid))

    @app.post("/api/jobs/{jid}/cancel", status_code=204)
    def cancel_job(jid: str):
        store.cancel(jid)

    @app.delete("/api/jobs/{jid}", status_code=204)
    def delete_job(jid: str):
        store.delete(jid)

    # ---------- clips ----------
    @app.get("/api/jobs/{jid}/clips/{cid}/video")
    def clip_video(jid: str, cid: str):
        return FileResponse(store.clip_path(jid, cid), media_type="video/mp4")

    @app.get("/api/jobs/{jid}/clips/{cid}/preview")
    def clip_preview(jid: str, cid: str):
        return FileResponse(store.clip_path(jid, cid, preview=True), media_type="video/mp4")

    @app.get("/api/jobs/{jid}/clips/{cid}/download")
    def clip_download(jid: str, cid: str):
        path = store.clip_path(jid, cid)
        return FileResponse(path, media_type="video/mp4", filename=path.name)

    @app.get("/api/jobs/{jid}/clips/{cid}/caption-text")
    def caption_text(jid: str, cid: str):
        return store.caption_text(jid, cid)

    @app.post("/api/jobs/{jid}/clips/{cid}/edit", status_code=202)
    def edit_clip(jid: str, cid: str, body: EditSpec):
        store.start_edit(jid, cid, body)
        return {"started": True}

    @app.post("/api/jobs/{jid}/clips/{cid}/metadata")
    def generate_meta(jid: str, cid: str, body: GenerateMetaBody | None = None):
        return store.make_meta(jid, cid, body.model if body else None)

    @app.put("/api/jobs/{jid}/clips/{cid}/metadata")
    def save_meta(jid: str, cid: str, body: MetaBody):
        return store.set_meta(jid, cid, body)

    @app.post("/api/jobs/{jid}/clips/{cid}/upload", status_code=202)
    def upload_clip(jid: str, cid: str, body: UploadBody):
        store.start_upload(jid, cid, body)
        return {"started": True}

    # ---------- the built React app (if present) ----------
    web_root = Path(webui_dir) if webui_dir else WEBUI_DIR
    if web_root.is_dir():
        @app.get("/{path:path}", include_in_schema=False)
        def web(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            target = (web_root / path).resolve()
            if path and target.is_file() and web_root.resolve() in target.parents:
                return FileResponse(target)
            return FileResponse(web_root / "index.html")  # client-side routes (/jobs/abc) load the app

    return app


app = create_app()
