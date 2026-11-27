"""Local speech-to-text with word-level timestamps (faster-whisper)."""
import gc
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


def transcribe(video_path, model_size="base", device="auto", compute_type="int8", chunk_seconds=120,
               on_progress=None):
    """on_progress(done_seconds, total_seconds) is called as audio gets transcribed."""
    import os
    from faster_whisper import WhisperModel  # imported lazily: heavy

    # Limit CPU threads to avoid Intel MKL memory allocation errors (mkl_malloc) on CPU
    cpu_threads = min(4, os.cpu_count() or 4) if device in ("auto", "cpu") else 0
    model = WhisperModel(model_size, device=device, compute_type=compute_type, cpu_threads=cpu_threads)
    segments, offset = [], 0.0
    with tempfile.TemporaryDirectory() as tmp:
        chunks = _split_audio(video_path, tmp, chunk_seconds)
        durations = [_wav_seconds(c) for c in chunks]
        total = sum(durations)
        if on_progress:
            on_progress(0.0, total)
        for chunk, dur in zip(chunks, durations):
            # beam_size=1 (greedy search) is 3-4x faster than beam_size=5 on CPU,
            # prevents mkl_malloc out-of-memory errors, and condition_on_previous_text=False
            # prevents hallucination loops on long videos.
            raw, _info = model.transcribe(
                str(chunk),
                beam_size=1,
                best_of=1,
                word_timestamps=True,
                vad_filter=True,
                condition_on_previous_text=False
            )
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
