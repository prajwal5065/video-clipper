"""Local web UI for video-clipper.  Run:  streamlit run app.py"""
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from clipper import transcribe as tr
from clipper.captions import STYLES
from clipper.download import download
from clipper.metadata import generate_metadata, transcript_for
from clipper.youtube import upload
from clipper.render import render_clip
from clipper.select import pick_clips

load_dotenv()
st.set_page_config(page_title="Video Clipper", layout="wide")
st.title("Video Clipper")
st.caption("Long video in, short vertical captioned clips out. Everything runs on your computer.")

with st.sidebar:
    st.header("Settings")
    n_clips = st.slider("Number of clips", 1, 10, 5)
    min_len, max_len = st.slider("Clip length (seconds)", 10, 90, (20, 60))
    whisper = st.selectbox("Whisper model", ["tiny", "base", "small", "medium", "large-v3"], index=2)
    device = st.selectbox("Device", ["auto", "cpu", "cuda"])
    compute = st.selectbox("Compute type", ["int8", "float16"], help="int8 for CPU, float16 for NVIDIA GPU")
    crop = st.selectbox("Crop", ["face", "center"])
    captions = st.checkbox("Burn in captions", value=True)
    style = st.selectbox("Caption style", list(STYLES), disabled=not captions)

link = st.text_input("Paste a video link (YouTube or similar)")
uploaded = st.file_uploader("Upload a video", type=["mp4", "mov", "mkv", "webm", "m4v"])
local_path = st.text_input("...or paste a local file path (better for very large videos)")

if st.button("Generate clips", type="primary"):
    if link.strip():
        try:
            with st.spinner("Downloading video..."):
                src = download(link.strip(), Path("output") / "_downloads")
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
        with st.status("Working...", expanded=True) as status:
            if transcript_file.exists():
                st.write("Using cached transcript.")
                segments = tr.load(transcript_file)
            else:
                st.write(f"Transcribing with Whisper '{whisper}' (slowest step)...")
                segments = tr.transcribe(src, whisper, device, compute)
                tr.save(segments, transcript_file)
            if not segments:
                st.error("No speech found in this video.")
                st.stop()
            st.write("Asking Gemini for the best moments...")
            clips = pick_clips(segments, n_clips, min_len, max_len)
            for c in clips:
                c["transcript"] = transcript_for(segments, c["start"], c["end"])
            results = []
            bar = st.progress(0.0)
            for i, c in enumerate(clips, 1):
                st.write(f"Rendering clip {i}/{len(clips)}: {c.get('title', '')}")
                f = render_clip(src, c, segments, out_dir, i, captions=captions, crop=crop, style=style)
                results.append((c, str(f)))
                bar.progress(i / len(clips))
            status.update(label="Done", state="complete")
        st.session_state["results"] = results
    except KeyError as e:
        if "GEMINI_API_KEY" in str(e):
            st.error("GEMINI_API_KEY is missing. Add it to your .env file and restart.")
        else:
            raise

results = st.session_state.get("results", [])
if results:
    st.subheader("Your clips")
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
                            sc["yt_url"] = upload(spath, sc["meta"], publish_at=when)
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
            st.download_button("Download", Path(path).read_bytes(), file_name=Path(path).name,
                               mime="video/mp4", key=f"dl{idx}")
            if st.button("Upload to YouTube", key=f"up{idx}"):
                try:
                    with st.spinner("Writing title, description and tags, then uploading..."):
                        c["meta"] = c.get("meta") or generate_metadata(c.get("transcript", ""))
                        c["yt_url"] = upload(path, c["meta"])
                except FileNotFoundError as e:
                    st.error(str(e))
                except KeyError as e:
                    st.error("GEMINI_API_KEY is missing in .env." if "GEMINI" in str(e) else f"Missing: {e}")
                except Exception as e:
                    st.error(f"Upload failed: {e}")
            if c.get("yt_url"):
                when = c.get("scheduled")
                st.success(f"Uploaded: {c['yt_url']}" + (f" (scheduled {when:%d %b, %H:%M})" if when else ""))
            if c.get("meta"):
                with st.expander("Title, description and tags"):
                    st.write(c["meta"]["title"])
                    st.text(c["meta"]["description"])
                    st.caption(", ".join(c["meta"]["tags"]))
