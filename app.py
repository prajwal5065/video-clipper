"""Local web UI for video-clipper.  Run:  streamlit run app.py"""
import os
import time
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from clipper import transcribe as tr
from clipper.captions import STYLES
from clipper.download import describe, download, human_size, human_time
from clipper.metadata import generate_metadata, transcript_for
from clipper.youtube import accounts, forget_account, upload
from clipper.render import QUALITY, clip_words, render_clip, video_duration
from clipper.select import pick_clips

load_dotenv()
st.set_page_config(page_title="Video Clipper", layout="wide")
st.title("Video Clipper")
st.caption("Long video in, short vertical captioned clips out. Everything runs on your computer.")

class Tracker:
    """One overall progress bar + a status line with percent and elapsed time."""

    def __init__(self):
        self.start = time.time()
        self.bar = st.progress(0.0)
        self.text = st.empty()

    def set(self, frac, message):
        frac = max(0.0, min(float(frac), 1.0))
        elapsed = int(time.time() - self.start)
        self.bar.progress(frac)
        self.text.markdown(f"**{message}**  \n{int(frac * 100)}% done · elapsed {elapsed // 60}:{elapsed % 60:02d}")


def _mmss(seconds):
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


FRAMING_LABELS = {
    "Crop: follow the face": "face",
    "Crop: center": "center",
    "Full frame + blurred background": "fit",
    "Full frame + black bars": "fit-black",
}


QUALITY_LABELS = {
    "Draft: 720p, fastest": "draft",
    "Standard: 1080p, balanced": "standard",
    "High: 1080p, sharper (slower)": "high",
    "Max: best quality (slowest)": "max",
}


def edit_panel(idx, c, job):
    """Trim, re-frame, restyle and fix the captions of one clip, with a fast preview."""
    segments, src, out_dir = job["segments"], job["src"], job["out_dir"]
    limit = float(job["duration"]) if job.get("duration") else float(c["end"]) + 120
    e1, e2 = st.columns(2)
    start = e1.number_input("Start (seconds)", 0.0, limit, float(c["start"]), step=0.5, format="%.1f", key=f"st{idx}")
    end = e2.number_input("End (seconds)", 0.0, limit, float(c["end"]), step=0.5, format="%.1f", key=f"en{idx}")
    st.caption(f"Clip length: {end - start:.1f}s")
    values = list(FRAMING_LABELS.values())
    f_label = st.selectbox("Framing", list(FRAMING_LABELS), index=values.index(c.get("crop", "face")), key=f"fr{idx}")
    cap_on = st.checkbox("Captions", value=c.get("captions", True), key=f"cp{idx}")
    sty = st.selectbox("Caption style", list(STYLES), index=list(STYLES).index(c.get("style", "classic")),
                       disabled=not cap_on, key=f"sy{idx}")
    base_words = clip_words(segments, c["start"], c["end"])
    base_text = " ".join(w.text for w in base_words)
    text = st.text_area("Caption text (fix spelling or names; keep the same number of words)", base_text,
                        key=f"tx{idx}-{c['start']}-{c['end']}", height=110, disabled=not cap_on)
    if c.get("yt_url"):
        st.caption("This clip is already uploaded. Saving changes only the local file, not the YouTube video.")

    def check():
        """Returns (ok, replacement words or None)."""
        if end - start < 3 or end - start > 180:
            st.error("The clip must be between 3 and 180 seconds long (end must be after start).")
            return False, None
        if cap_on and text.strip() != base_text.strip():
            if (start, end) != (float(c["start"]), float(c["end"])):
                st.warning("Save the new start/end first, then fix the captions.")
                return False, None
            parts = text.split()
            if len(parts) != len(base_words):
                st.error(f"Keep the same number of words: the clip has {len(base_words)}, you wrote {len(parts)}.")
                return False, None
            return True, [tr.Word(w.start, w.end, part) for w, part in zip(base_words, parts)]
        return True, None

    b1, b2 = st.columns(2)
    do_preview = b1.button("Preview (fast)", key=f"pv{idx}")
    do_save = b2.button("Save final", key=f"sv{idx}", type="primary")
    if do_preview or do_save:
        ok, words = check()
        if ok:
            bar = st.progress(0.0)
            try:
                new = {**c, "start": start, "end": end}
                out = render_clip(src, new, segments, out_dir, idx + 1, captions=cap_on,
                                  crop=FRAMING_LABELS[f_label], style=sty, words=words,
                                  quality=c.get("quality", "standard"),
                                  out_name=f"preview-{idx + 1:02d}.mp4" if do_preview else None,
                                  preview=do_preview, on_progress=bar.progress)
            except Exception as e:
                bar.empty()
                st.error(f"Rendering failed: {e}")
            else:
                bar.empty()
                if do_preview:
                    c["preview"] = str(out)
                else:
                    c.update(start=start, end=end, crop=FRAMING_LABELS[f_label], style=sty, captions=cap_on)
                    c["transcript"] = transcript_for(segments, start, end)
                    if "yt_url" not in c:
                        c.pop("meta", None)  # title/description are rewritten for the new cut
                    c.pop("preview", None)
                    st.session_state["flash"] = f"Clip {idx + 1} saved."
                    st.rerun()
    if c.get("preview"):
        st.video(c["preview"])
        st.caption("Low-quality preview, not saved yet. Click Save final to keep it.")


yt_accounts = accounts()
with st.sidebar:
    st.header("Settings")
    n_clips = st.slider("Number of clips", 1, 10, 5)
    min_len, max_len = st.slider("Clip length (seconds)", 10, 90, (20, 60))
    whisper = st.selectbox("Whisper model", ["tiny", "base", "small", "medium", "large-v3"], index=2)
    device = st.selectbox("Device", ["auto", "cpu", "cuda"])
    compute = st.selectbox("Compute type", ["int8", "float16"], help="int8 for CPU, float16 for NVIDIA GPU")
    crop = FRAMING_LABELS[st.selectbox("Framing", list(FRAMING_LABELS), help="Crop fills the screen but cuts off the sides. "
                                       "Full frame keeps everything and fills the space above and below.")]
    quality = QUALITY_LABELS[st.selectbox(
        "Output quality", list(QUALITY_LABELS), index=1,
        help="Higher levels use a better video encoder setting and sharper scaling, so files are bigger and "
             "rendering takes longer. For links they also download a higher-resolution source (1440p / 4K "
             "only if the video has it; those files are large). The picture can never be sharper than the "
             "original video.")]
    captions = st.checkbox("Burn in captions", value=True)
    style = st.selectbox("Caption style", list(STYLES), disabled=not captions)
    st.divider()
    yt_account = st.selectbox("YouTube account to upload to", yt_accounts)
    if st.button("Forget sign-in for this account"):
        forget_account(yt_account)
        st.success(f"Signed out '{yt_account}'. Next upload asks you to sign in again.")

link = st.text_input("Paste a video link (YouTube or similar)")
uploaded = st.file_uploader("Upload a video", type=["mp4", "mov", "mkv", "webm", "m4v"])
local_path = st.text_input("...or paste a local file path (better for very large videos)")

if st.button("Generate clips", type="primary"):
    dl_bar = dl_text = None
    if link.strip():  # a dedicated download bar, shown above the overall bar
        dl_bar = st.progress(0.0)
        dl_text = st.empty()
    tracker = Tracker()
    # Overall bar: download 0-10%, transcription 10-60%, Gemini 60-68%, rendering 68-100%
    if link.strip():
        dl_state = {"best": 0.0, "start": time.time()}

        def on_download(info):
            head, detail = describe(info)
            if info.get("stage") == "processing":
                dl_state["best"] = 1.0
            elif info.get("fraction") is not None:  # never moves backwards (video file, then audio file)
                dl_state["best"] = max(dl_state["best"], min(info["fraction"], 1.0))
            dl_bar.progress(dl_state["best"])
            elapsed = human_time(time.time() - dl_state["start"])
            dl_text.markdown(f"**{head}**  \n{detail + ' · ' if detail else ''}elapsed {elapsed}")
            tracker.set(0.10 * dl_state["best"], "Downloading video...")

        try:
            tracker.set(0.0, "Downloading video...")
            src = download(link.strip(), Path("output") / "_downloads",
                           max_height=QUALITY[quality]["max_height"], on_progress=on_download)
            dl_bar.progress(1.0)
            dl_text.markdown(f"**Downloaded {human_size(Path(src).stat().st_size)}** "
                             f"in {human_time(time.time() - dl_state['start'])}")
        except Exception as e:
            st.error(f"Download failed: {e}. Update yt-dlp (pip install -U yt-dlp) or upload the file instead.")
            st.stop()
    elif uploaded:
        src = Path("output") / "_uploads" / uploaded.name
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(uploaded.getbuffer())
    elif local_path.strip():
        src = Path(local_path.strip().strip('"'))
    else:
        st.error("Paste a link, upload a video, or enter a file path first.")
        st.stop()
    if not src.exists():
        st.error(f"File not found: {src}")
        st.stop()

    out_dir = Path("output") / src.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_file = out_dir / "transcript.json"
    try:
        if transcript_file.exists():
            tracker.set(0.60, "Using the saved transcript")
            segments = tr.load(transcript_file)
        else:
            tracker.set(0.10, f"Preparing audio and loading Whisper '{whisper}' (the first run downloads the model)...")
            segments = tr.transcribe(
                src, whisper, device, compute,
                on_progress=lambda done, total: tracker.set(
                    0.10 + 0.50 * (done / total if total else 1),
                    f"Transcribing speech: {_mmss(done)} of {_mmss(total)}"))
            tr.save(segments, transcript_file)
        if not segments:
            st.error("No speech found in this video.")
            st.stop()
        tracker.set(0.62, "Asking Gemini for the best moments...")
        clips = pick_clips(segments, n_clips, min_len, max_len)
        for c in clips:
            c["transcript"] = transcript_for(segments, c["start"], c["end"])
        results = []
        for i, c in enumerate(clips, 1):
            def on_clip(f, i=i, title=c.get("title", "")):
                tracker.set(0.68 + 0.32 * ((i - 1 + f) / len(clips)), f"Rendering clip {i} of {len(clips)}: {title}")
            on_clip(0.0)
            c["crop"], c["style"], c["captions"], c["quality"] = crop, style, captions, quality
            f = render_clip(src, c, segments, out_dir, i, captions=captions, crop=crop, style=style, quality=quality,
                            on_progress=on_clip)
            results.append((c, str(f)))
        tracker.set(1.0, f"Done: {len(results)} clips ready")
        st.session_state["results"] = results
        st.session_state["job"] = {"src": str(src), "segments": segments, "out_dir": str(out_dir),
                                   "duration": video_duration(src)}
    except KeyError as e:
        if "GEMINI_API_KEY" in str(e):
            st.error("GEMINI_API_KEY is missing. Add it to your .env file and restart.")
        else:
            raise

results = st.session_state.get("results", [])
if results:
    st.subheader("Your clips")
    if st.session_state.get("flash"):
        st.success(st.session_state.pop("flash"))
    with st.expander("Schedule all clips on YouTube"):
        st.caption("Uploads every clip now and tells YouTube when to publish each one. "
                   "Times use your computer's time zone. Check Studio afterwards: scheduled videos show a date.")
        sc1, sc2, sc3 = st.columns(3)
        first_day = sc1.date_input("First clip date", value=date.today() + timedelta(days=1))
        at_time = sc2.time_input("Time of day", value=dtime(18, 0))
        gap = sc3.number_input("Days between clips", 1, 30, 1)
        if st.button("Upload and schedule all", key="sched_all"):
            tz = datetime.now().astimezone().tzinfo
            slots = [datetime.combine(first_day + timedelta(days=i * int(gap)), at_time).replace(tzinfo=tz)
                     for i in range(len(results))]
            if slots[0] <= datetime.now(tz) + timedelta(minutes=10):
                st.error("The first time must be at least 10 minutes in the future.")
            else:
                try:
                    with st.status("Uploading and scheduling...", expanded=True) as sstatus:
                        for (sc, spath), when in zip(results, slots):
                            st.write(f"{sc.get('title', 'Clip')} -> {when:%d %b %Y, %H:%M}")
                            sc["meta"] = sc.get("meta") or generate_metadata(sc.get("transcript", ""))
                            sc["yt_url"] = upload(spath, sc["meta"], publish_at=when, account=yt_account)
                            sc["yt_account"] = yt_account
                            sc["scheduled"] = when
                        sstatus.update(label="All clips uploaded and scheduled", state="complete")
                except FileNotFoundError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Scheduling failed: {e}")
    cols = st.columns(3)
    for idx, (c, path) in enumerate(results):
        with cols[idx % 3]:
            st.video(path)
            st.markdown(f"**{c.get('title', 'Clip')}**  \nscore {c.get('score', '?')} · {c['start']:.0f}s-{c['end']:.0f}s")
            if c.get("reason"):
                st.caption(c["reason"])
            if st.session_state.get("job"):
                with st.expander("Edit this clip"):
                    edit_panel(idx, c, st.session_state["job"])
            st.download_button("Download", Path(path).read_bytes(), file_name=Path(path).name,
                               mime="video/mp4", key=f"dl{idx}")
            if st.button("Upload to YouTube", key=f"up{idx}"):
                try:
                    with st.spinner("Writing title, description and tags, then uploading..."):
                        c["meta"] = c.get("meta") or generate_metadata(c.get("transcript", ""))
                        c["yt_url"] = upload(path, c["meta"], account=yt_account)
                        c["yt_account"] = yt_account
                except FileNotFoundError as e:
                    st.error(str(e))
                except KeyError as e:
                    st.error("GEMINI_API_KEY is missing in .env." if "GEMINI" in str(e) else f"Missing: {e}")
                except Exception as e:
                    st.error(f"Upload failed: {e}")
            if c.get("yt_url"):
                when = c.get("scheduled")
                st.success(f"Uploaded to '{c.get('yt_account', 'main')}': {c['yt_url']}" + (f" (scheduled {when:%d %b, %H:%M})" if when else ""))
            if c.get("meta"):
                with st.expander("Title, description and tags"):
                    st.write(c["meta"]["title"])
                    st.text(c["meta"]["description"])
                    st.caption(", ".join(c["meta"]["tags"]))
