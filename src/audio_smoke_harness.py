"""Audio smoke harness for v2.4.0 architecture.

Verifies the FINAL-transcription-to-adapter boundary using fake audio
and a fake transcriber.  No real microphone, no real Whisper.
"""

from __future__ import annotations
import numpy as np
import tempfile
import time
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any


FAKE_CHUNK_SIZE = 1600  # ~100ms at 16kHz


def fake_chunk() -> np.ndarray:
    """A silent audio chunk."""
    return np.zeros(FAKE_CHUNK_SIZE, dtype=np.float32)


class FakeTranscriber:
    """Returns fixed text for every transcribe call."""
    def __init__(self, text: str = "hello world"):
        self.text = text
        self.call_count = 0

    def transcribe(self, audio_data, prompt=""):
        self.call_count += 1
        return self.text


class FakeTranslator:
    """Returns prefixed text."""
    def __init__(self, prefix: str = "ZH:"):
        self.prefix = prefix
        self.call_count = 0

    def translate(self, text, target_lang=None):
        self.call_count += 1
        return f"{self.prefix}{text}"


@dataclass
class AudioSmokeResult:
    ok: bool = False
    session_id: str = ""
    chunks_processed: int = 0
    finals_produced: int = 0
    translations_delivered: int = 0
    segments_written: int = 0
    original_text: str = ""
    translated_text: str = ""
    repo_path: str = ""
    repo_closed: bool = False
    errors: list[str] = field(default_factory=list)


def run_fake_audio_smoke(
    *,
    num_chunks: int = 5,
    transcriber_text: str = "hello world",
    translator_prefix: str = "ZH:",
    tmp_path: Path | None = None,
) -> AudioSmokeResult:
    """E2E audio smoke without real microphone or real Whisper."""

    result = AudioSmokeResult()

    if tmp_path is None:
        tmp_path = Path(tempfile.mkdtemp(prefix="audio_smoke_"))
    repo_path = str(tmp_path / "audio_smoke.sqlite3")
    result.repo_path = repo_path

    from src.session_repository import SQLiteSessionRepository
    from src.segment_api import SegmentAPI
    from src.translation_scheduler import TranslationScheduler
    from src.translation_adapter import TranslationAdapter

    repo = None
    session_id = str(uuid.uuid4())

    try:
        repo = SQLiteSessionRepository(repo_path)
        repo.initialize()

        transcriber = FakeTranscriber(text=transcriber_text)
        translator = FakeTranslator(prefix=translator_prefix)

        scheduler = TranslationScheduler(
            translator=translator.translate,
            max_queue=10,
            max_workers=1,
        )
        adapter = TranslationAdapter(
            scheduler=scheduler,
            repository=repo,
            repository_enabled=True,
        )
        adapter.start_session(session_id)

        # Simulate audio → transcribe → FINAL → adapter
        result.chunks_processed = num_chunks
        for i in range(num_chunks):
            chunk = fake_chunk()
            text = transcriber.transcribe(chunk)
            if i < num_chunks:
                adapter.on_final_text(text, chunk_id=i + 1)
                result.finals_produced += 1

        time.sleep(0.3)  # allow translation to complete

        adapter.stop_session()
        scheduler.shutdown(wait=True)
        result.session_id = session_id
        result.translations_delivered = translator.call_count

        # Verify via API
        api = SegmentAPI(repo)
        segs = api.list_segments(session_id)
        result.segments_written = len(segs)

        snap = api.get_session_snapshot(session_id)
        if snap:
            result.original_text = snap.original_text[:200]
            result.translated_text = snap.translated_text[:200]

        result.ok = (
            result.finals_produced == num_chunks
            and result.segments_written > 0
        )

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
