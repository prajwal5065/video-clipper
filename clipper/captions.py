"""Word-by-word captions (ASS subtitle file) with the current word highlighted."""

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,2,60,60,520,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

HIGHLIGHT = "&H0000FFFF&"  # yellow (BGR)
NORMAL = "&H00FFFFFF&"


def _t(seconds):
    seconds = max(0.0, seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def build_ass(words, clip_start, out_path, words_per_chunk=3):
    """words: list of Word (absolute video times). Times are shifted to clip-relative."""
    lines = [HEADER]
    for i in range(0, len(words), words_per_chunk):
        chunk = words[i:i + words_per_chunk]
        for j, w in enumerate(chunk):
            start = w.start - clip_start
            nxt = chunk[j + 1].start if j + 1 < len(chunk) else (
                words[i + words_per_chunk].start if i + words_per_chunk < len(words) else w.end)
            end = max(nxt, w.end) - clip_start
            parts = []
            for k, cw in enumerate(chunk):
                color = HIGHLIGHT if k == j else NORMAL
                parts.append("{\\c" + color + "}" + cw.text.upper().replace("{", "(").replace("}", ")"))
            text = " ".join(parts)
            lines.append(f"Dialogue: 0,{_t(start)},{_t(end)},Default,,0,0,0,,{text}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
