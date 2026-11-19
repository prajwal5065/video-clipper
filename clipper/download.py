"""Download a video from a link (YouTube and many other sites) with yt-dlp."""
from pathlib import Path


def is_url(text):
    return str(text).strip().lower().startswith(("http://", "https://"))


def human_size(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def human_time(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def describe(info):
    """Turn a progress dict from download() into (headline, detail) text for a UI or terminal."""
    if info.get("stage") == "processing":
        return "Finishing the download: merging video and audio...", "This can take a minute for large videos."
    frac = info.get("fraction")
    head = f"Downloading video: {int(min(frac, 1.0) * 100)}%" if frac is not None else "Downloading video..."
    parts = []
    done, total = info.get("done"), info.get("total")
    if done is not None:
        parts.append(f"{human_size(done)} of {human_size(total)}" if total else human_size(done))
    if info.get("speed"):
        parts.append(f"{human_size(info['speed'])}/s")
    if info.get("eta") is not None:
        parts.append(f"about {human_time(info['eta'])} left")
    return head, " · ".join(parts)


def download(url, out_dir, max_height=1080, on_progress=None):
    """Downloads the best quality up to max_height (if the video has it).

    on_progress(info) is called while downloading, with a dict:
      stage     "downloading" or "processing" (merging video and audio at the end)
      done      bytes downloaded so far (video + audio files together)
      total     total bytes, or None if not known yet
      fraction  done / total (0..1), or None
      speed     bytes per second (current file) or None
      eta       seconds left (current file) or None
      kind      "video" or "audio" (which file is downloading)
    """
    import yt_dlp  # lazy import

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": f"bv*[height<={max_height}]+ba/b[height<={max_height}]/b",
        "outtmpl": str(out_dir / f"%(id)s-{max_height}p.%(ext)s"),  # height in the name: no stale low-quality reuse
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    if on_progress:
        files = {}  # yt-dlp downloads the video and the audio as separate files

        def hook(d):
            status = d.get("status")
            name = d.get("filename") or d.get("tmpfilename") or "file"
            if status == "downloading":
                files[name] = [d.get("downloaded_bytes", 0), d.get("total_bytes") or d.get("total_bytes_estimate")]
            elif status == "finished":
                size = d.get("total_bytes") or d.get("downloaded_bytes") or (files.get(name) or [0])[0]
                files[name] = [size, size]
            else:
                return
            done = sum(f[0] for f in files.values())
            total = sum(f[1] for f in files.values()) if all(f[1] for f in files.values()) else None
            on_progress({
                "stage": "downloading", "done": done, "total": total,
                "fraction": (done / total) if total else None,
                "speed": d.get("speed"), "eta": d.get("eta"),
                "kind": "audio" if (d.get("info_dict") or {}).get("vcodec") == "none" else "video",
            })

        def post_hook(d):
            if d.get("status") == "started":
                on_progress({"stage": "processing"})

        opts["progress_hooks"] = [hook]
        opts["postprocessor_hooks"] = [post_hook]
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        files = info.get("requested_downloads") or []
        path = files[0]["filepath"] if files else ydl.prepare_filename(info)
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError("Download finished but the video file was not found.")
    return path
