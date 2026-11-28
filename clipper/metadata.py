"""Generate YouTube title / description / hashtags / tags for a clip with Gemini."""
import json
import os
import re

from .select import DEFAULT_MODEL, _ask, _clean_json

MASTER_PROMPT = """You are the growth editor of a YouTube Shorts channel that publishes clips of podcasts, interviews, reactions and commentary. Write the title, description, hashtags and search tags for ONE clip so the right viewers find it and click, without misleading anyone.

WHAT YOU KNOW
{facts}

HOW TO THINK (silently; output only the JSON)
1. Work out who is speaking and who or what the clip is about. A name may be used only if it appears in the source info, the editor notes or the transcript. Never guess a name.
2. Is this a reaction to, or commentary on, someone else's video or person? If the source channel or the editor notes name a well-known person or channel, that name is what viewers search for, so use it.
3. Find the single strongest hook: a surprising claim, a conflict, a number, a question, a reveal. Use only what is really said or shown.

TITLE
- At most 70 characters, no quotes around it, no ALL-CAPS words (acronyms are fine), at most one emoji.
- Put the name or topic people search for in the first 40 characters.
- Use the name of a person or channel only when they are in the clip or the clip reacts to their video. Patterns that work: "<Name> on <surprising thing>", "<Name> <does/says what really happens>", "Reacting to <Name>: <hook>" (only if it is a reaction).
- Never say or imply that the person endorses, approves of or works with this channel. Never put words in anyone's mouth.

DESCRIPTION
- First 1-2 sentences (the part visible before "show more", about 125 characters): the hook, the name and the topic keywords, in natural language.
- Then 1-2 sentences on what happens in the clip and why it matters.
- Then one short call to action, for example to follow for more clips like this.
- Plain text. No hashtags, no links, no credit line (those are added automatically), no emoji spam.

TAGS: 12 to 15 phrases people really type: the name and its common spellings, the topic, "<name> clips" and "<name> reaction" (only when true), the key moment, other names that appear.
HASHTAGS: 5 to 8, no # sign, one of them the main name or topic as a single word.

Never invent facts, quotes or events. If no known name applies, write about the topic and do not invent one.

Return ONLY this JSON:
{{"title":"...","description":"...","hashtags":["..."],"tags":["..."]}}
"""

_NONE = "(not known)"


def chapter_at(source, start, end):
    """The chapter of the source video that holds the middle of the clip, or ''."""
    if start is None or end is None:
        return ""
    mid = (float(start) + float(end)) / 2
    for c in (source or {}).get("chapters") or []:
        try:
            if c.get("start") is not None and c.get("end") is not None and float(c["start"]) <= mid < float(c["end"]):
                return str(c.get("title") or "")
        except (TypeError, ValueError):
            continue
    return ""


def build_prompt(transcript, source=None, context="", hint=None):
    """The master prompt for one clip: everything we know about it, not only the transcript."""
    source, hint = source or {}, hint or {}
    lines = []
    if source.get("title") or source.get("channel"):
        lines.append("Source video (this clip was cut from it):")
        lines.append(f"- Channel: {source.get('channel') or _NONE}")
        lines.append(f"- Title: {source.get('title') or _NONE}")
        if source.get("url"):
            lines.append(f"- Link: {source['url']}")
        chapter = chapter_at(source, hint.get("start"), hint.get("end"))
        if chapter:
            lines.append(f"- Chapter at this moment: {chapter}")
        if source.get("tags"):
            lines.append("- Source tags: " + ", ".join(source["tags"][:10]))
        if source.get("description"):
            lines.append("- Source description (excerpt): " + " ".join(str(source["description"]).split())[:800])
    else:
        lines.append("Source video: " + _NONE + " (an uploaded or local file).")
    context = " ".join(str(context or "").split())[:600]
    lines.append("Editor notes from the person publishing (treat as true): " + (context or "none"))
    if hint.get("title") or hint.get("reason"):
        lines.append(f"Why this moment was picked: {hint.get('title') or ''} - {hint.get('reason') or ''}".strip(" -"))
    lines.append("")
    lines.append("TRANSCRIPT OF THE CLIP (what is actually said):")
    lines.append(str(transcript)[:12000])
    return MASTER_PROMPT.format(facts="\n".join(lines))


def credit_line(source):
    """'Original video: title by channel' + link, added to the description by code so it is always correct."""
    if os.environ.get("YT_CREDIT_SOURCE", "true").strip().lower() not in ("1", "true", "yes"):
        return ""
    source = source or {}
    title, channel, url = source.get("title"), source.get("channel"), source.get("url")
    if not (title or channel):
        return ""
    text = "Original video: " + (f"{title}" if title else "") + (f" by {channel}" if channel else "")
    return (text.strip() + (f"\n{url}" if url else ""))[:600]


def transcript_for(segments, start, end):
    return " ".join(s.text for s in segments if s.end > start and s.start < end).strip()


def _clean(text):
    return re.sub(r"[<>]", "", str(text)).strip()


def normalize(raw, credit=""):
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
    tail = "\n\n".join(x for x in (_clean(credit) if credit else "", " ".join("#" + h for h in hashtags)) if x)
    desc = (desc[:max(0, 5000 - len(tail) - 2)] + "\n\n" + tail)[:5000]
    tags, total = [], 0
    for t in raw.get("tags", []):
        t = _clean(t)
        if t and total + len(t) + 1 <= 480:
            tags.append(t)
            total += len(t) + 1
    return {"title": title, "description": desc, "hashtags": hashtags, "tags": tags}


def generate_metadata(transcript, model=None, source=None, context="", hint=None):
    """source: what is known about the original video (see download.read_source_info); context: the publisher's
    own notes (e.g. "reacting to <creator>'s video"); hint: the picked moment ({title, reason, start, end})."""
    model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    text = _ask(build_prompt(transcript, source, context, hint), model)
    data = json.loads(_clean_json(text))
    if isinstance(data, list):
        data = data[0]
    return normalize(data, credit=credit_line(source))
