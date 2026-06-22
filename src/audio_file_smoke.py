"""WAV file audio smoke for v2.4.0 architecture.

WAV fixture → real audio loader → fake transcriber → FINAL → adapter → repo → API.

No real microphone, no real Whisper, no real API, no real user path.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import math
import struct
import tempfile
import time
import uuid
import wave


# ── WAV fixture generator ──────────────────────────────────────
def generate_fixture_wav(
    path: Path | str,
    *,
    duration: float = 1.0,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,  # 16-bit PCM
    frequency: float = 440.0,
) -> None:
    """Generate a tiny WAV file for testing. No external deps."""
    path = Path(path)
    n_frames = int(sample_rate * duration)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        for i in range(n_frames):
            t = i / sample_rate
            sample = int(16000 * math.sin(2 * math.pi * frequency * t))
            if sample_width == 2:
                wf.writeframes(struct.pack("<h", max(-32768, min(32767, sample))))


# ── WAV info ────────────────────────────────────────────────────
@dataclass(frozen=True)
class WavAudioInfo:
    path: str
    sample_rate: int
    channels: int
    sample_width: int
    frame_count: int
    duration_seconds: float


def inspect_wav_file(path: str | Path) -> WavAudioInfo:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"WAV file not found: {path}")
    try:
        with wave.open(str(path), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            fc = wf.getnframes()
            dur = fc / sr if sr > 0 else 0.0
            return WavAudioInfo(
                path=str(path),
                sample_rate=sr,
                channels=ch,
                sample_width=sw,
                frame_count=fc,
                duration_seconds=dur,
            )
    except wave.Error as e:
        raise ValueError(f"Not a valid WAV file: {path} ({e})") from e


# ── WAV chunks ──────────────────────────────────────────────────
@dataclass(frozen=True)
class WavAudioChunk:
    sample_rate: int
    channels: int
    frames: bytes
    frame_count: int
    duration_seconds: float
    index: int


def iter_wav_chunks(
    path: str | Path,
    *,
    chunk_duration_seconds: float = 0.25,
) -> list[WavAudioChunk]:
    chunks: list[WavAudioChunk] = []
    info = inspect_wav_file(path)
    chunk_frames = int(info.sample_rate * chunk_duration_seconds)
    chunk_bytes = chunk_frames * info.channels * info.sample_width

    with wave.open(str(path), "rb") as wf:
        idx = 0
        while True:
            frames = wf.readframes(chunk_frames)
            if not frames:
                break
            chunks.append(WavAudioChunk(
                sample_rate=info.sample_rate,
                channels=info.channels,
                frames=frames,
                frame_count=len(frames) // (info.channels * info.sample_width),
                duration_seconds=len(frames) / (info.sample_rate * info.channels * info.sample_width),
                index=idx,
            ))
            idx += 1
    return chunks


# ── Fake transcriber ────────────────────────────────────────────
class WavFixtureFakeTranscriber:
    def __init__(self, final_text: str = "hello from wav fixture"):
        self.final_text = final_text
        self.chunks_seen: list[WavAudioChunk] = []

    def consume_chunk(self, chunk: WavAudioChunk) -> None:
        self.chunks_seen.append(chunk)

    def finalize(self) -> str:
        return self.final_text


# ── Smoke result ────────────────────────────────────────────────
@dataclass
class WavFileSmokeResult:
    ok: bool = False
    session_id: str = ""
    wav_sample_rate: int = 0
    wav_channels: int = 0
    wav_chunk_count: int = 0
    segments_count: int = 0
    original_text: str = ""
    translated_text: str = ""
    bilingual_text: str = ""
    repo_closed: bool = False
    errors: list[str] = field(default_factory=list)


def run_wav_file_smoke(
    wav_path: str | Path,
    *,
    repository_path: str | Path | None = None,
    fake_transcript_text: str = "hello from wav fixture",
    fake_translation_text: str = "来自 wav fixture 的你好",
    chunk_duration_seconds: float = 0.25,
) -> WavFileSmokeResult:
    result = WavFileSmokeResult()

    if repository_path is None:
        repository_path = Path(tempfile.mkdtemp(prefix="wav_smoke_")) / "smoke.sqlite3"
    repo_path = str(repository_path)

    from src.session_repository import SQLiteSessionRepository
    from src.segment_api import SegmentAPI
    from src.translation_scheduler import TranslationScheduler
    from src.translation_adapter import TranslationAdapter

    repo = None
    session_id = str(uuid.uuid4())

    try:
        # ── 1. inspect WAV ──────────────────────────────────────
        info = inspect_wav_file(wav_path)
        result.wav_sample_rate = info.sample_rate
        result.wav_channels = info.channels

        # ── 2. chunk + transcribe ───────────────────────────────
        chunks = iter_wav_chunks(wav_path, chunk_duration_seconds=chunk_duration_seconds)
        result.wav_chunk_count = len(chunks)
        transcriber = WavFixtureFakeTranscriber(final_text=fake_transcript_text)
        for c in chunks:
            transcriber.consume_chunk(c)

        # ── 3. setup adapter ────────────────────────────────────
        repo = SQLiteSessionRepository(repo_path)
        repo.initialize()

        class FakeTranslator:
            def __init__(self, text): self.text = text
            def translate(self, *a, **kw): return self.text

        scheduler = TranslationScheduler(
            translator=FakeTranslator(fake_translation_text).translate,
            max_queue=10,
            max_workers=1,
        )
        adapter = TranslationAdapter(
            scheduler=scheduler,
            repository=repo,
            repository_enabled=True,
        )
        adapter.start_session(session_id)

        # ── 4. FINAL → adapter ──────────────────────────────────
        final_text = transcriber.finalize()
        adapter.on_final_text(final_text, chunk_id=1)
        time.sleep(0.3)
        adapter.stop_session()
        scheduler.shutdown(wait=True)
        result.session_id = session_id

        # ── 5. verify ───────────────────────────────────────────
        api = SegmentAPI(repo)
        segs = api.list_segments(session_id)
        result.segments_count = len(segs)
        snap = api.get_session_snapshot(session_id)
        if snap:
            result.original_text = snap.original_text[:200]
            result.translated_text = snap.translated_text[:200]
            result.bilingual_text = snap.bilingual_text[:200]

        result.ok = result.segments_count > 0

    except Exception as e:
        result.ok = False
        result.errors.append(str(e))
    finally:
        if repo is not None:
            try:
                repo.close()
                result.repo_closed = True
            except Exception:
                pass

    return result
