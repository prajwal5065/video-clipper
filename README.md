# Video Clipper

Turn long videos into short, vertical (9:16), captioned clips of their best moments, preview and edit them, and publish them to YouTube. Everything runs on your own computer.

**How it works:** faster-whisper writes the transcript, Gemini picks the best moments, FFmpeg cuts, reframes and burns in word-by-word captions.

## Quick start (Windows)

1. Install **Python 3.11** and **FFmpeg** (`ffmpeg -version` must work in a terminal).
2. In this folder: `py -3.11 -m pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and put your free Gemini key in it (https://aistudio.google.com).
4. Start it: double-click **`start.bat`** (or run `py -3.11 -m server`). Your browser opens at http://127.0.0.1:8000. Leave the black window open while you use the app.

The app only listens on this computer. It can upload to your YouTube channel, so it is never exposed to the network.

## Using it

- **New clips:** paste a link, upload a file, or give a local file path. Choose how many clips, how long, the framing, quality and caption style. Press **Generate clips**.
- **Progress:** download speed and time left, where transcription is, which clip is rendering. You can cancel. Jobs are saved, so they survive closing the page or restarting.
- **Under each clip:**
  - **Edit:** trim (you see the real video frame at the start and end), change framing, captions and style, fix caption spelling (same number of words), make a fast **Preview**, then **Save changes** to re-render at full quality.
  - **YouTube:** title, description, hashtags and tags written by AI or by you; choose account, visibility, made-for-kids; upload now or schedule.
  - **Download** the MP4.
- **Schedule all:** upload every clip, one published every N days.
- **Library:** every job you have run. **Settings:** whether your keys are found, YouTube accounts, sign out.

### Framing

| Option | What it does |
|---|---|
| Follow the face | Fills the screen and keeps the speaker in frame; cuts off the sides (falls back to centre if no face is found) |
| Center crop | Fills the screen with the middle of the picture; cuts off the sides |
| Full frame, blurred background | Keeps the whole picture; a blurred copy fills the space above and below |
| Full frame, black bars | Keeps the whole picture with black bars |

Caption styles: classic, hormozi, mrbeast, minimal.

### Output quality

| Level | Output | Encoder | Link download up to |
|---|---|---|---|
| Draft | 720x1280 | fast, smaller files | 720p |
| Standard | 1080x1920 | balanced | 1080p |
| High | 1080x1920 | better encoder settings + mild sharpening | 1440p |
| Max | 1080x1920 | best settings, slowest | 4K |

The picture can never be sharper than the source video. Cropping a widescreen video to vertical uses only about a third of its pixels, so crop modes look softer than the full-frame modes. YouTube re-compresses uploads, so Max rarely looks better than High there.

## YouTube setup (one time)

An API key cannot upload videos; YouTube needs a Google sign-in (OAuth).

1. https://console.cloud.google.com -> create a project.
2. APIs & Services -> Library -> enable **YouTube Data API v3**.
3. OAuth consent screen: choose External, fill the basics, add your own Google account under **Test users**.
4. Credentials -> Create credentials -> **OAuth client ID** -> **Desktop app**. Download the JSON and save it as `client_secret.json` in this folder.
5. Restart the app. The first upload to an account opens a Google sign-in window once; after that it is remembered (`token.json`).

**More accounts:** set `YT_ACCOUNTS=main,second` in `.env` (keep `main` first). Pick the account in the YouTube panel. Every account must be added as a Test user. **Settings -> Sign out** forgets an account's login. Accounts share one Google Cloud project, so they share its daily quota.

Good to know:
- New Google Cloud projects can be forced to **private** uploads until Google verifies the app. Scheduled uploads need the same permission; if a video stays plain private, publish or schedule it in YouTube Studio.
- Age restriction cannot be set through the upload API; set it in YouTube Studio if needed. Made-for-kids is set per upload (default from `YT_MADE_FOR_KIDS`).
- Keywords come from the clip's own transcript; there is no live trend data.
- Never share or commit `.env`, `client_secret.json` or `token*.json` (they are in `.gitignore`).

## Command line

Without the interface:

```
py -3.11 clip.py my_video.mp4 --clips 5
py -3.11 clip.py "https://www.youtube.com/watch?v=..." --clips 5 --quality high
py -3.11 clip.py my_video.mp4 --dry-run              # only show the chosen moments
py -3.11 clip.py my_video.mp4 --crop fit --style hormozi --whisper base
py -3.11 clip.py my_video.mp4 --device cuda --compute-type float16   # NVIDIA GPU
```

Output goes to `output/<video-name>/`; the transcript is cached, so re-runs skip the slow step.

## Troubleshooting

- **Link download fails:** `py -3.11 -m pip install -U yt-dlp` (YouTube changes often). If it still fails, download the file yourself and upload it.
- **Out of memory while transcribing:** close other programs, choose the `base` or `tiny` speech model (Advanced), and try a shorter video first.
- **"GEMINI_API_KEY is missing":** put the key in `.env` and restart.
- **Page shows "Cannot reach the server":** the start window was closed; run `start.bat` again.

## Try it without waiting

`py -3.11 scripts/demo_server.py` starts a demo at http://127.0.0.1:8010 with a fake download, Whisper, Gemini and YouTube (real FFmpeg). Nothing is downloaded or uploaded.

## For developers

- Backend: `server/` (FastAPI; API docs at http://127.0.0.1:8000/api/docs), pipeline in `clipper/`.
- Frontend: `frontend/` (React, TypeScript, Vite, Tailwind). `cd frontend && npm install`, then `npm run dev` (http://localhost:5173, talks to the server on :8000), `npm test`, `npm run build` (writes the site into `webui/`, which is committed so Node is not needed just to use the app).
- Tests: `pip install -r requirements-dev.txt` then `pytest tests` (Whisper, Gemini, yt-dlp and YouTube are faked; FFmpeg is real). `python scripts/capture_fixtures.py` re-records the API responses used by the React tests; `tests/test_frontend_contract.py` fails if the API shape drifts from them.
