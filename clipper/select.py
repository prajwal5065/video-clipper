"""Ask an LLM (Gemini) which parts of the transcript make good short clips."""
import json
import os

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


def _ask(prompt, model):
    from google import genai  # lazy import

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config={"response_mime_type": "application/json"},
    )
    return resp.text


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
    model = model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    transcript = "\n".join(f"[{s.start:.1f}-{s.end:.1f}] {s.text}" for s in segments)
    text = _ask(PROMPT.format(n=n, min_len=min_len, max_len=max_len, transcript=transcript), model)
    data = json.loads(text)
    clips = data["clips"] if isinstance(data, dict) else data
    return clean(clips, segments, min_len, max_len, n)
