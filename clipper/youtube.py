"""Upload a clip to YouTube (Data API v3, OAuth)."""
import os
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _env_bool(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes")


def build_body(meta, privacy=None, made_for_kids=None, category=None):
    return {
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


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    secret = os.environ.get("YT_CLIENT_SECRET_FILE", "client_secret.json")
    token = Path("token.json")
    creds = None
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(secret).exists():
                raise FileNotFoundError(
                    f"'{secret}' not found. Download your OAuth client file from Google Cloud "
                    "(see README, 'YouTube upload setup') and put it in the project folder.")
            creds = InstalledAppFlow.from_client_secrets_file(secret, SCOPES).run_local_server(port=0)
        token.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload(video_path, meta, privacy=None, made_for_kids=None, category=None):
    """Upload and return the video URL."""
    from googleapiclient.http import MediaFileUpload

    body = build_body(meta, privacy, made_for_kids, category)
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=-1)
    req = _service().videos().insert(
        part="snippet,status", body=body, media_body=media, notifySubscribers=False)
    resp = None
    while resp is None:
        _status, resp = req.next_chunk()
    return f"https://youtu.be/{resp['id']}"
