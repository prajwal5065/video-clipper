"""The whole clipping pipeline in one place, for any front end:
download -> transcribe -> pick moments -> render clips."""
from pathlib import Path

from . import transcribe as tr
from .download import download
from .metadata import transcript_for
from .render import QUALITY, render_clip, video_duration
from .select import pick_clips


class Cancelled(Exception):
    """Raised (from report) to stop a running job."""


def mmss(seconds):
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def process(spec, out_dir, cache_dir, report):
    """Run the pipeline.

    spec:      dict with source_type ("link" | "path"), source, clips, min_len, max_len, whisper, device,
               compute_type, crop, quality, captions, style, model
    out_dir:   job folder (clips go to out_dir/clips, transcript to out_dir/transcript.json)
    cache_dir: shared cache (downloaded videos, transcripts)
    report:    report(stage, overall_fraction, message, **extra); it may raise Cancelled.
    Overall progress: download 0-10%, transcribe 10-60%, select 60-68%, render 68-100%.
    """
    out_dir, cache_dir = Path(out_dir), Path(cache_dir)
    clips_dir = out_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    quality = spec["quality"]

    # 1. the source video
    if spec["source_type"] == "link":
        state = {"best": 0.0}

        def on_download(info):
            if info.get("stage") == "processing":
                state["best"] = 1.0
            elif info.get("fraction") is not None:  # never moves backwards (video file, then audio file)
                state["best"] = max(state["best"], min(info["fraction"], 1.0))
            msg = "Merging video and audio" if info.get("stage") == "processing" else "Downloading video"
            report("download", 0.10 * state["best"], msg, download={**info, "best": state["best"]})

        report("download", 0.0, "Starting download")
        src = download(spec["source"], cache_dir / "downloads",
                       max_height=QUALITY[quality]["max_height"], on_progress=on_download)
        report("download", 0.10, "Download complete",
               download={"stage": "done", "done": src.stat().st_size, "total": src.stat().st_size, "best": 1.0})
    else:
        src = Path(spec["source"])
        report("download", 0.10, "Using the local file")
    duration = video_duration(src)

    # 2. transcript (cached per video + Whisper model)
    cache_file = cache_dir / "transcripts" / f"{src.stem}__{spec['whisper']}.json"
    if cache_file.exists():
        segments = tr.load(cache_file)
        report("transcribe", 0.60, "Using the saved transcript")
    else:
        report("transcribe", 0.10, f"Loading Whisper '{spec['whisper']}' (the first run downloads the model)")

        def on_transcribe(done, total):
            report("transcribe", 0.10 + 0.50 * (done / total if total else 1),
                   f"Transcribing speech: {mmss(done)} of {mmss(total)}",
                   transcribe={"done": done, "total": total})

        segments = tr.transcribe(src, spec["whisper"], spec["device"], spec["compute_type"],
                                 on_progress=on_transcribe)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        tr.save(segments, cache_file)
    if not segments:
        raise ValueError("No speech found in this video.")
    transcript_file = out_dir / "transcript.json"
    tr.save(segments, transcript_file)

    # 3. best moments
    report("select", 0.62, "Asking Gemini for the best moments")
    picked = pick_clips(segments, spec["clips"], spec["min_len"], spec["max_len"], model=spec.get("model"))

    # 4. render
    clips = []
    for i, c in enumerate(picked, 1):
        def on_render(f, i=i):
            report("render", 0.68 + 0.32 * ((i - 1 + f) / len(picked)), f"Rendering clip {i} of {len(picked)}",
                   render={"index": i, "total": len(picked), "title": c.get("title", "")})

        on_render(0.0)
        f = render_clip(src, c, segments, clips_dir, i, captions=spec["captions"], crop=spec["crop"],
                        style=spec["style"], quality=quality, on_progress=on_render)
        clips.append({
            "id": f"c{i}", "index": i, "title": c.get("title") or f"Clip {i}", "reason": c.get("reason", ""),
            "score": c.get("score"), "start": float(c["start"]), "end": float(c["end"]), "file": f.name,
            "crop": spec["crop"], "style": spec["style"], "captions": spec["captions"], "quality": quality,
            "transcript": transcript_for(segments, c["start"], c["end"]),
            "rev": 1, "meta": None, "yt": None, "edit": None, "preview": None,
        })
    return {"source": src, "duration": duration, "segments": segments, "clips": clips,
            "transcript_file": transcript_file}
