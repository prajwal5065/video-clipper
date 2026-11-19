"""Ask an LLM (Gemini) which parts of the transcript make good short clips."""
import json
import logging
import os
import random
import time

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"
FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

PROMPT = """You are an expert short-form video editor (TikTok / Reels / Shorts).
Below is a timestamped transcript of a long video. Pick the {n} best moments to turn into
standalone short clips.

Rules:
- Each clip must be between {min_len} and {max_len} seconds long.
- Start on a strong hook (a bold claim, question, or story start). End on a complete thought.
- The clip must make sense without the rest of the video.
- Clips must not overlap.
- Use start/end times that match the transcript timestamps.
- score is 1-100: how likely the clip is to hold attention.

Return ONLY JSON in this shape:
{{"clips":[{{"start":0.0,"end":0.0,"title":"short catchy title","reason":"why it works","score":0}}]}}

TRANSCRIPT:
{transcript}
"""


def _clean_json(text):
    text = (text or "").strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _ask(prompt, model=None, max_retries=2, initial_delay=2.0):
    from google import genai  # lazy import
    from google.genai.errors import APIError, ServerError, ClientError

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise KeyError("GEMINI_API_KEY is missing in environment or .env file.")

    primary_model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    # Build model cascade: primary first, followed by fallback options
    models_to_try = [primary_model]
    for fb in FALLBACK_MODELS:
        if fb != primary_model and fb not in models_to_try:
            models_to_try.append(fb)

    client = genai.Client(api_key=api_key)

    last_error = None
    for attempt_model in models_to_try:
        delay = initial_delay
        for attempt in range(max_retries + 1):
            try:
                resp = client.models.generate_content(
                    model=attempt_model,
                    contents=prompt,
                    config={"response_mime_type": "application/json"},
                )
                if attempt_model != primary_model:
                    logger.warning(
                        "Primary model '%s' unavailable. Successfully fell back to '%s'.",
                        primary_model,
                        attempt_model,
                    )
                return resp.text
            except (ServerError, ClientError, APIError) as e:
                last_error = e
                status_code = getattr(e, "code", None) or getattr(e, "status_code", None)
                msg = str(e).lower()
                is_transient = (
                    status_code in (429, 500, 502, 503, 504)
                    or "high demand" in msg
                    or "unavailable" in msg
                    or "rate limit" in msg
                    or "resource_exhausted" in msg
                )

                if is_transient and attempt < max_retries:
                    sleep_time = delay + random.uniform(0.5, 1.5)
                    logger.warning(
                        "Gemini model '%s' busy or unavailable (%s). Retrying in %.1fs (attempt %d/%d)...",
                        attempt_model,
                        e,
                        sleep_time,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(sleep_time)
                    delay *= 2
                else:
                    logger.warning(
                        "Gemini model '%s' failed (%s). Attempting fallback if available...",
                        attempt_model,
                        e,
                    )
                    break
            except Exception as e:
                last_error = e
                logger.warning("Error calling Gemini model '%s': %s", attempt_model, e)
                break

    if last_error:
        raise last_error
    raise RuntimeError("Failed to generate content: all candidate Gemini models failed.")


def _snap(value, points):
    return min(points, key=lambda p: abs(p - value))


def clean(clips, segments, min_len, max_len, n):
    """Snap to segment boundaries, enforce length, drop overlaps, keep best n."""
    starts = [s.start for s in segments]
    ends = [s.end for s in segments]
    video_end = ends[-1]
    out = []
    for c in clips:
        try:
            start = _snap(float(c["start"]), starts)
            end = _snap(float(c["end"]), ends)
        except (KeyError, TypeError, ValueError):
            continue
        end = min(end, video_end)
        if end - start > max_len:
            end = start + max_len
        if end - start < min_len * 0.7:
            continue
        out.append({**c, "start": start, "end": end})
    out.sort(key=lambda c: -float(c.get("score", 0)))
    kept = []
    for c in out:
        if all(c["end"] <= k["start"] or c["start"] >= k["end"] for k in kept):
            kept.append(c)
        if len(kept) == n:
            break
    return sorted(kept, key=lambda c: c["start"])


def pick_clips(segments, n=5, min_len=20, max_len=60, model=None):
    model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    transcript = "\n".join(f"[{s.start:.1f}-{s.end:.1f}] {s.text}" for s in segments)
    text = _ask(PROMPT.format(n=n, min_len=min_len, max_len=max_len, transcript=transcript), model)
    data = json.loads(_clean_json(text))
    clips = data["clips"] if isinstance(data, dict) else data
    return clean(clips, segments, min_len, max_len, n)
