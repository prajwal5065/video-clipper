"""Download a video from a link (YouTube and many other sites) with yt-dlp."""
from pathlib import Path


def is_url(text):
    return str(text).strip().lower().startswith(("http://", "https://"))


def download(url, out_dir, max_height=1080, on_progress=None):
    """on_progress(fraction 0..1) is called while downloading."""
    import yt_dlp  # lazy import

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": f"bv*[height<={max_height}]+ba/b[height<={max_height}]/b",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    if on_progress:
        def hook(d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                if total:
                    on_progress(min(d.get("downloaded_bytes", 0) / total, 1.0))
        opts["progress_hooks"] = [hook]
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        files = info.get("requested_downloads") or []
        path = files[0]["filepath"] if files else ydl.prepare_filename(info)
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError("Download finished but the video file was not found.")
    return path
