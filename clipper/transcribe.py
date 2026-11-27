"""Local speech-to-text with word-level timestamps (faster-whisper)."""
import gc
import hashlib
import json
import subprocess
import tempfile
import wave
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


def fingerprint(video_path):
    """Short id of one particular video file (path + size + modified time), so a cached transcript is only
    reused for the same file, not for another file that happens to have the same name."""
    p = Path(video_path)
    st = p.stat()
    return hashlib.sha1(f"{p.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode("utf-8")).hexdigest()[:10]


def _split_audio(video_path, out_dir, chunk_seconds):
    """Extract mono 16 kHz audio and cut it into chunks so Whisper never holds the whole video in RAM."""
    pattern = str(Path(out_dir) / "chunk%04d.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", "-f", "segment", "-segment_time", str(chunk_seconds),
         "-reset_timestamps", "1", pattern],
        check=True)
    return sorted(Path(out_dir).glob("chunk*.wav"))


def _wav_seconds(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def transcribe(video_path, model_size="small", device="auto", compute_type="int8", chunk_seconds=600,
               on_progress=None):
    """on_progress(done_seconds, total_seconds) is called as audio gets transcribed."""
    from faster_whisper import WhisperModel  # imported lazily: heavy

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, offset = [], 0.0
    with tempfile.TemporaryDirectory() as tmp:
        chunks = _split_audio(video_path, tmp, chunk_seconds)
        durations = [_wav_seconds(c) for c in chunks]
        total = sum(durations)
        if on_progress:
            on_progress(0.0, total)
        for chunk, dur in zip(chunks, durations):
            raw, _info = model.transcribe(str(chunk), word_timestamps=True, vad_filter=True)
            for s in raw:
                words = [Word(w.start + offset, w.end + offset, w.word.strip())
                         for w in (s.words or []) if w.word.strip()]
                segments.append(Segment(s.start + offset, s.end + offset, s.text.strip(), words))
                if on_progress:
                    on_progress(min(offset + s.end, total), total)
            offset += dur
            if on_progress:
                on_progress(min(offset, total), total)
            Path(chunk).unlink(missing_ok=True)
            gc.collect()
    return segments


def save(segments, path):
    Path(path).write_text(json.dumps([asdict(s) for s in segments], ensure_ascii=False, indent=1), encoding="utf-8")


def load(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Segment(d["start"], d["end"], d["text"], [Word(**w) for w in d["words"]]) for d in data]
