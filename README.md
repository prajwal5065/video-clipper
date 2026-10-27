# video-clipper

Personal tool: turn long videos into short, vertical (9:16), subtitled clips.
Runs locally. No server, no database, no deployment.

Pipeline: **faster-whisper** (transcript + word timestamps) -> **Gemini** (picks best moments)
-> **FFmpeg** (cut, crop to 9:16, burn word-by-word captions).

## Setup

1. Install Python 3.10+ and [FFmpeg](https://ffmpeg.org/download.html) (`ffmpeg -version` must work).
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and add your free Gemini API key (https://aistudio.google.com).

## Use

Browser UI (easiest):

```
streamlit run app.py
```

Paste a link in the page, upload a file, or enter a local path.

Or the command line (file path or link):

```
python clip.py my_video.mp4 --clips 5
python clip.py "https://www.youtube.com/watch?v=..." --clips 5
python clip.py my_video.mp4 --dry-run          # only show the chosen moments
python clip.py my_video.mp4 --whisper base     # faster, less accurate
python clip.py my_video.mp4 --device cuda --compute-type float16   # NVIDIA GPU
```

`--crop face` (default) keeps the speaker's face in the vertical frame; `--crop center` disables it.
If no face is found it falls back to centre crop.

Caption styles: `--style classic|hormozi|mrbeast|minimal` (or pick one in the UI).

Output goes to `output/<video-name>/` (clips, `transcript.json`, `clips.json`).
The transcript is cached, so re-runs skip the slow step.

## Roadmap

- Caption style presets

## Troubleshooting

- Link download fails: run `pip install -U yt-dlp` (YouTube changes often). If it still fails, download the file yourself and upload it.
