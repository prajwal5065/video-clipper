"""Upload a clip to YouTube (Data API v3, OAuth)."""
import os
import re
from datetime import timezone
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# 8 MB chunks: reliable on slow/unstable connections
_CHUNK_SIZE = 8 * 1024 * 1024


def accounts():
    """Account names from YT_ACCOUNTS (comma separated). Default: just 'main'."""
    raw = os.environ.get("YT_ACCOUNTS", "main")
    names = [re.sub(r"[^a-z0-9_-]", "", n.strip().lower()) for n in raw.split(",")]
    out = []
    for n in names:
        if n and n not in out:
            out.append(n)
    return out or ["main"]


def token_path(account):
    # 'main' keeps using token.json, so an existing sign-in keeps working
    return Path("token.json") if account == "main" else Path(f"token_{account}.json")


def forget_account(account):
    token_path(account).unlink(missing_ok=True)


def _env_bool(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes")


def build_body(meta, privacy=None, made_for_kids=None, category=None, publish_at=None):
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": category or os.environ.get("YT_CATEGORY_ID", "22"),
        },
        "status": {
            "privacyStatus": privacy or os.environ.get("YT_PRIVACY", "private"),
            "selfDeclaredMadeForKids": (
                _env_bool("YT_MADE_FOR_KIDS", False) if made_for_kids is None else made_for_kids),
            "embeddable": True,
        },
    }
    if publish_at is not None:
        # scheduled publishing: video is uploaded private and YouTube flips it public at publishAt
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = publish_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return body


def _service(account="main"):
    from google.auth.exceptions import TransportError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    secret_file = os.environ.get("YT_CLIENT_SECRET_FILE", "client_secret.json")
    # Support both a bare filename (resolved relative to this file's folder) and an absolute path
    secret = Path(secret_file)
    if not secret.is_absolute() and not secret.exists():
        # Try the directory where youtube.py lives (the clipper package folder)
        alt = Path(__file__).parent.parent / secret_file
        if alt.exists():
            secret = alt

    token = token_path(account)
    creds = None

    if token.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token), SCOPES)
        except Exception:
            creds = None  # corrupted token file – will re-authenticate

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except TransportError as exc:
                raise RuntimeError(
                    "Could not refresh your YouTube login: no internet connection or Google is unreachable.\n"
                    f"Detail: {exc}"
                ) from exc
            except Exception as exc:
                # Refresh token revoked or expired — delete and force re-auth
                token.unlink(missing_ok=True)
                creds = None

        if not creds or not creds.valid:
            if not secret.exists():
                raise FileNotFoundError(
                    f"OAuth client file '{secret_file}' not found.\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials → "
                    "your OAuth 2.0 Client (Desktop App) → Download JSON, rename to "
                    f"'{secret_file}' and put it in the project folder (next to app.py)."
                )
            try:
                creds = InstalledAppFlow.from_client_secrets_file(
                    str(secret), SCOPES
                ).run_local_server(port=0, prompt="select_account consent")
            except Exception as exc:
                raise RuntimeError(
                    "YouTube sign-in failed. Make sure you are running the app locally "
                    f"(the browser must be able to open). Detail: {exc}"
                ) from exc

        token.write_text(creds.to_json())

    try:
        return build("youtube", "v3", credentials=creds)
    except Exception as exc:
        raise RuntimeError(f"Failed to connect to YouTube API: {exc}") from exc


def upload(video_path, meta, privacy=None, made_for_kids=None, category=None,
           publish_at=None, account="main", on_progress=None):
    """Upload *video_path* to YouTube and return the video URL.

    *on_progress(fraction)* is called with 0.0–1.0 as each chunk completes.
    """
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    video_path = str(video_path)
    file_size = Path(video_path).stat().st_size

    body = build_body(meta, privacy, made_for_kids, category, publish_at)
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True,
                            chunksize=_CHUNK_SIZE)
    try:
        service = _service(account)
        req = service.videos().insert(
            part="snippet,status", body=body, media_body=media,
            notifySubscribers=False)
    except (FileNotFoundError, RuntimeError):
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to start upload: {exc}") from exc

    resp = None
    while resp is None:
        try:
            status, resp = req.next_chunk()
        except HttpError as exc:
            code = exc.resp.status
            if code in (500, 502, 503, 504):
                # Transient server error – googleapiclient will retry automatically
                # but if it bubbles up, give a clear message
                raise RuntimeError(
                    f"YouTube server error {code} during upload. "
                    "This is usually temporary — please try again in a moment."
                ) from exc
            if code == 403:
                raise RuntimeError(
                    "YouTube upload was rejected (403 Forbidden).\n"
                    "Common reasons:\n"
                    "• Your Google Cloud project is in 'Testing' mode — add your Google "
                    "account as a test user under OAuth consent screen → Test users.\n"
                    "• The YouTube Data API v3 is not enabled for your project.\n"
                    "• You have exceeded the daily upload quota (10,000 units/day on the "
                    "free tier; each upload costs ~1,600 units).\n"
                    f"Full error: {exc}"
                ) from exc
            if code == 401:
                token_path(account).unlink(missing_ok=True)
                raise RuntimeError(
                    "YouTube login expired or was revoked (401). Your saved token has been "
                    "deleted — click 'Upload to YouTube' again to re-authenticate."
                ) from exc
            raise RuntimeError(f"YouTube API error {code}: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Upload interrupted: {exc}") from exc

        if status is not None and on_progress is not None and file_size:
            on_progress(min(status.resumable_progress / file_size, 0.99))

    if on_progress is not None:
        on_progress(1.0)

    return f"https://youtu.be/{resp['id']}"
