"""Unit tests for audio smoke harness."""
import pytest
import tempfile
from pathlib import Path
from dataclasses import asdict
from src.audio_smoke_harness import (
    run_fake_audio_smoke, fake_chunk, FakeTranscriber, FakeTranslator,
    AudioSmokeResult,
)


# ── 1. fake chunk shape ────────────────────────────────────────
class TestFakeChunk:
    def test_shape(self):
        c = fake_chunk()
        assert c.shape == (1600,)
        assert c.dtype.name == "float32"


# ── 2. fake transcriber ────────────────────────────────────────
class TestFakeTranscriber:
    def test_returns_text(self):
        t = FakeTranscriber(text="test")
        assert t.transcribe(fake_chunk()) == "test"

    def test_call_count(self):
        t = FakeTranscriber(text="hi")
        t.transcribe(fake_chunk())
        t.transcribe(fake_chunk())
        assert t.call_count == 2


# ── 3. fake translator ────────────────────────────────────────
class TestFakeTranslator:
    def test_prefix(self):
        tr = FakeTranslator(prefix="JP:")
        assert tr.translate("hello") == "JP:hello"

    def test_call_count(self):
        tr = FakeTranslator()
        tr.translate("a")
        tr.translate("b")
        assert tr.call_count == 2


# ── 4. audio boundary works ────────────────────────────────────
class TestAudioBoundary:
    def test_full_chain(self):
        result = run_fake_audio_smoke(num_chunks=5)
        assert result.ok is True
        assert result.chunks_processed == 5
        assert result.finals_produced == 5


# ── 5. partial smoke not in this harness ───────────────────────
# (skipped — partial handling is tested in adapter layer)


# ── 6. FINAL→adapter boundary ──────────────────────────────────
class TestFinalAdapter:
    def test_final_triggers_translation(self, tmp_path):
        result = run_fake_audio_smoke(num_chunks=3, tmp_path=tmp_path)
        assert result.translations_delivered >= 1


# ── 7. translation→repository boundary ─────────────────────────
class TestTranslationRepo:
    def test_segments_written(self, tmp_path):
        result = run_fake_audio_smoke(num_chunks=3, tmp_path=tmp_path)
        assert result.segments_written >= 1
        assert result.original_text
        assert result.translated_text


# ── 8. repository→SegmentAPI boundary ──────────────────────────
class TestRepoRead:
    def test_api_can_read(self, tmp_path):
        from src.session_repository import SQLiteSessionRepository
        from src.segment_api import SegmentAPI
        result = run_fake_audio_smoke(num_chunks=3, tmp_path=tmp_path)
        repo = SQLiteSessionRepository(result.repo_path)
        repo.initialize()
        api = SegmentAPI(repo)
        segs = api.list_segments(result.session_id)
        assert len(segs) >= 1
        repo.close()


# ── 9. no real microphone ──────────────────────────────────────
class TestNoRealMicrophone:
    def test_fake_audio_used(self, tmp_path):
        result = run_fake_audio_smoke(num_chunks=1, tmp_path=tmp_path)
        assert result.chunks_processed == 1


# ── 10. no real Whisper ────────────────────────────────────────
class TestNoRealWhisper:
    def test_fake_transcriber_counts(self):
        t = FakeTranscriber()
        t.transcribe(fake_chunk())
        assert t.call_count == 1


# ── 11. serializable ───────────────────────────────────────────
class TestSerializable:
    def test_json(self, tmp_path):
        result = run_fake_audio_smoke(num_chunks=2, tmp_path=tmp_path)
        d = asdict(result)
        import json
        j = json.dumps(d, default=str)
        assert len(j) > 0
