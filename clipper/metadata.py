"""Generate YouTube title / description / hashtags / tags for a clip with Gemini."""
import json
import os
import re

from .select import _ask

PROMPT = """You write YouTube Shorts metadata that gets clicks without clickbait lies.
Based on this transcript of a short clip, return ONLY JSON:
{{"title":"max 70 chars, strong hook, no quotes around it",
"description":"2-3 short sentences that hook the viewer and say what the clip is about, then a one-line call to action",
"hashtags":["5 to 8 relevant hashtags without the # sign"],
"tags":["10 to 15 search keywords / phrases people would actually type"]}}

Use keywords that match the clip's real topic. Do not invent facts that are not in the transcript.

TRANSCRIPT:
{transcript}
"""


def transcript_for(segments, start, end):
    return " ".join(s.text for s in segments if s.end > start and s.start < end).strip()


def _clean(text):
    return re.sub(r"[<>]", "", str(text)).strip()


def normalize(raw):
    """Enforce YouTube limits: title <=100, description <=5000, tags <=500 chars total."""
    title = _clean(raw.get("title", "")) or "Short clip"
    title = title[:100]
    hashtags = []
    for h in raw.get("hashtags", []):
        h = re.sub(r"[^\w]", "", str(h))
        if h and h.lower() != "shorts" and h not in hashtags:
            hashtags.append(h)
    hashtags = ["Shorts"] + hashtags[:7]
    desc = _clean(raw.get("description", ""))
    desc = (desc + "\n\n" + " ".join("#" + h for h in hashtags))[:5000]
    tags, total = [], 0
    for t in raw.get("tags", []):
        t = _clean(t)
        if t and total + len(t) + 1 <= 480:
            tags.append(t)
            total += len(t) + 1
    return {"title": title, "description": desc, "hashtags": hashtags, "tags": tags}


def generate_metadata(transcript, model=None):
    model = model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    text = _ask(PROMPT.format(transcript=transcript[:12000]), model)
    data = json.loads(text)
    if isinstance(data, list):
        data = data[0]
    return normalize(data)
