"""Local speech-to-text with word-level timestamps (faster-whisper)."""
import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list


def transcribe(video_path, model_size="small", device="auto", compute_type="int8"):
    from faster_whisper import WhisperModel  # imported lazily: heavy

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    raw, _info = model.transcribe(str(video_path), word_timestamps=True, vad_filter=True)
    segments = []
    for s in raw:
        words = [Word(w.start, w.end, w.word.strip()) for w in (s.words or []) if w.word.strip()]
        segments.append(Segment(s.start, s.end, s.text.strip(), words))
    return segments


def save(segments, path):
    Path(path).write_text(json.dumps([asdict(s) for s in segments], ensure_ascii=False, indent=1), encoding="utf-8")


def load(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Segment(d["start"], d["end"], d["text"], [Word(**w) for w in d["words"]]) for d in data]
