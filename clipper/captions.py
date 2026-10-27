"""Word-by-word captions (ASS subtitle file) with the current word highlighted."""

WHITE = "&H00FFFFFF&"
YELLOW = "&H0000FFFF&"  # ASS colours are BGR
GREEN = "&H0000FF00&"
CYAN = "&H00FFFF00&"

STYLES = {
    # classic: bold white, yellow current word
    "classic": dict(font="Arial", size=84, outline=7, margin_v=520, per_chunk=3,
                    normal=WHITE, highlight=YELLOW, upper=True),
    # hormozi: big, tight 2-word chunks, green highlight
    "hormozi": dict(font="Arial", size=104, outline=9, margin_v=560, per_chunk=2,
                    normal=WHITE, highlight=GREEN, upper=True),
    # mrbeast: huge, 1-2 words, very thick outline, yellow highlight
    "mrbeast": dict(font="Arial", size=120, outline=12, margin_v=600, per_chunk=2,
                    normal=WHITE, highlight=YELLOW, upper=True),
    # minimal: smaller, sentence case, longer lines, cyan highlight
    "minimal": dict(font="Arial", size=64, outline=4, margin_v=300, per_chunk=5,
                    normal=WHITE, highlight=CYAN, upper=False),
}


def _header(st):
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,{st['font']},{st['size']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{st['outline']},2,2,60,60,{st['margin_v']},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""


def _t(seconds):
    seconds = max(0.0, seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def build_ass(words, clip_start, out_path, style="classic"):
    """words: list of Word (absolute video times). Times are shifted to clip-relative."""
    st = STYLES[style]
    n = st["per_chunk"]
    lines = [_header(st)]
    for i in range(0, len(words), n):
        chunk = words[i:i + n]
        for j, w in enumerate(chunk):
            start = w.start - clip_start
            nxt = chunk[j + 1].start if j + 1 < len(chunk) else (
                words[i + n].start if i + n < len(words) else w.end)
            end = max(nxt, w.end) - clip_start
            parts = []
            for k, cw in enumerate(chunk):
                color = st["highlight"] if k == j else st["normal"]
                txt = cw.text.upper() if st["upper"] else cw.text
                parts.append("{\\c" + color + "}" + txt.replace("{", "(").replace("}", ")"))
            lines.append(f"Dialogue: 0,{_t(start)},{_t(end)},Default,,0,0,0,,{' '.join(parts)}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
