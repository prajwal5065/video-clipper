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

Framing (`--crop`): `face` (default) crops and keeps the speaker's face in the frame, falling back to centre if no face is found; `center` crops the middle; `fit` keeps the whole original frame on a blurred background; `fit-black` keeps the whole frame with black bars. In the UI this is the **Framing** dropdown.

Caption styles: `--style classic|hormozi|mrbeast|minimal` (or pick one in the UI).

Output goes to `output/<video-name>/` (clips, `transcript.json`, `clips.json`).
The transcript is cached, so re-runs skip the slow step.

## Roadmap

- Caption style presets

## Troubleshooting

- Link download fails: run `pip install -U yt-dlp` (YouTube changes often). If it still fails, download the file yourself and upload it.

## YouTube upload setup (one time)

An API key cannot upload videos; YouTube needs a Google sign-in (OAuth).

1. Go to https://console.cloud.google.com and create a project.
2. APIs & Services -> Library -> enable **YouTube Data API v3**.
3. APIs & Services -> OAuth consent screen: choose External, fill the basics, and add your own Google account under **Test users**.
4. Credentials -> Create credentials -> **OAuth client ID** -> Application type **Desktop app**. Download the JSON and save it as `client_secret.json` in this folder.
5. Click **Upload to YouTube** under any clip. A browser window opens once to sign in; after that it is remembered (`token.json`).

What the button does: writes the title, description, hashtags and tags with Gemini, sets the settings from `.env`, and uploads.

Notes:
- New Google Cloud projects are forced to **private** uploads until YouTube audits them. Publish the video from YouTube Studio, or apply for the audit.
- "Made for kids" is set from `YT_MADE_FOR_KIDS`. Age restriction cannot be set through this upload API as far as I know; set it in YouTube Studio if needed.
- Keywords come from the clip's own transcript. There is no live trend data.
- Never commit `client_secret.json`, `token.json` or `.env` (they are in `.gitignore`).

## Scheduling

Open **Schedule all clips on YouTube**, pick the first date, time and gap in days, and click the button. Each clip is uploaded now and YouTube publishes it at its slot. Check YouTube Studio afterwards: if the videos show a scheduled date, it worked. If they stay plain private, YouTube's API lock is blocking it; schedule them by hand in Studio instead.

## Multiple YouTube accounts

Set `YT_ACCOUNTS=main,second` in `.env` (any names, comma separated; keep `main` first). Pick the account in the sidebar; every upload and schedule goes to it.

- The first upload to each account opens a Google sign-in. Choose the right Google account (and channel) at that point.
- Every Google account you use must be added under **Test users** on the OAuth consent screen.
- "Forget sign-in for this account" in the sidebar deletes that account's saved login (use it to switch to a different channel or if sign-in expires).
- All accounts share the same Google Cloud project, so they share its daily API quota.

## Editing a clip

Under each clip, open **Edit this clip** to change the start/end time, framing, caption style, or fix the caption text (same number of words, so the timing still matches). **Preview (fast)** makes a quick low-resolution version to check; **Save final** re-renders the clip at full quality and replaces it. If you saved a new cut before uploading, the YouTube title and description are written again for it.

## Output quality

`Output quality` in the sidebar (CLI: `--quality draft|standard|high|max`):

| Level | Output | Encoder | Link download up to |
|---|---|---|---|
| draft | 720x1280 | fast, smaller files | 720p |
| standard | 1080x1920 | balanced (the original behaviour) | 1080p |
| high | 1080x1920 | better encoder settings + mild sharpening | 1440p |
| max | 1080x1920 | best settings, slowest | 4K |

The picture can never be sharper than the source video. Cropping a widescreen video to vertical uses only about a third of its pixels, so crop modes look softer than the full-frame modes; a higher-resolution source (or `high`) helps most there. YouTube re-compresses uploads, so `max` rarely looks better than `high` on YouTube.

## API server (backend for the new React interface)

Start it with `py -3.11 -m server`. It listens on http://127.0.0.1:8000 (this computer only; it can upload to your YouTube channel, so it is never exposed to the network). Open http://127.0.0.1:8000/api/docs to see every endpoint and try them in the browser.

- Jobs run in the background one at a time, with live progress (download speed, transcription, rendering) and can be cancelled.
- Everything is saved to disk (`output/jobs/<id>/`), so clips and progress survive a restart, which the Streamlit page could not do.
- Clips can be previewed, trimmed, re-framed, re-styled, caption-corrected, given AI or hand-written YouTube metadata, uploaded to a chosen account, or scheduled.
- Tests: `pip install -r requirements-dev.txt` then `pytest tests` (Whisper, Gemini, yt-dlp and YouTube are faked; FFmpeg is real).

The Streamlit page (`streamlit run app.py`) still works unchanged while the React interface is built.

## New interface (React)

1. Start the server: `py -3.11 -m server`
2. Open http://127.0.0.1:8000

The finished site is in `webui/` (committed), so you do not need Node.js just to use it. Screens: **New clips** (paste a link / upload / local path, then clip count and length, framing, quality, captions), **live progress** (download speed and time left, transcription position, which clip is rendering, cancel), **Library** (every job, saved on this computer) and **Settings** (Gemini key, YouTube accounts). Clip editing and YouTube upload screens come in the next stages; until then the Streamlit page (`streamlit run app.py`) still has them.

Look around without waiting for real processing: `py -3.11 scripts/demo_server.py` (fake download, Whisper, Gemini and YouTube; real FFmpeg), then open http://127.0.0.1:8010.

For developers: `cd frontend && npm install`, then `npm run dev` (http://localhost:5173, talks to the server on :8000), `npm test`, `npm run build` (writes `webui/`). `tests/` also checks that the saved API fixtures used by the React tests still match the real API.
