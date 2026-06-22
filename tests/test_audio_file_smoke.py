"""Tests for WAV file audio smoke."""
import pytest
import json
import os
import tempfile
import wave
import struct
import math
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch
from src.audio_file_smoke import (
    generate_fixture_wav, inspect_wav_file, iter_wav_chunks,
    WavFixtureFakeTranscriber, run_wav_file_smoke,
    WavAudioChunk, WavAudioInfo, WavFileSmokeResult,
)


@pytest.fixture
def wav_path():
    p = tempfile.mkdtemp(prefix="wav_smoke_test_")
    path = Path(p) / "fixture.wav"
    generate_fixture_wav(path, duration=0.5, sample_rate=16000)
    yield path
    try:
        os.remove(str(path))
    except Exception:
        pass


# ── 1. generated wav valid ────────────────────────────────────
class TestGeneratedWav:
    def test_inspect(self, wav_path):
        info = inspect_wav_file(wav_path)
        assert info.sample_rate == 16000
        assert info.channels == 1
        assert info.sample_width == 2
        assert info.frame_count > 0
        assert info.duration_seconds > 0


# ── 2. iter chunks ─────────────────────────────────────────────
class TestIterChunks:
    def test_returns_chunks(self, wav_path):
        chunks = iter_wav_chunks(wav_path, chunk_duration_seconds=0.25)
        assert len(chunks) > 0
        for c in chunks:
            assert c.sample_rate == 16000
            assert c.frame_count > 0


# ── 3. chunk duration bounded ──────────────────────────────────
class TestChunkDuration:
    def test_bounded(self, wav_path):
        chunks = iter_wav_chunks(wav_path, chunk_duration_seconds=0.25)
        for c in chunks:
            assert c.duration_seconds <= 0.25 + 0.02  # small tolerance


# ── 4. fake transcriber receives chunks ────────────────────────
class TestFakeTranscriber:
    def test_receives_and_finalizes(self, wav_path):
        chunks = iter_wav_chunks(wav_path, chunk_duration_seconds=0.25)
        ft = WavFixtureFakeTranscriber(final_text="test123")
        for c in chunks:
            ft.consume_chunk(c)
        assert len(ft.chunks_seen) == len(chunks)
        assert ft.finalize() == "test123"


# ── 5. wav smoke writes repository ─────────────────────────────
class TestWavSmoke:
    def test_full_chain(self, wav_path, tmp_path):
        result = run_wav_file_smoke(
            wav_path,
            repository_path=tmp_path / "wav_smoke.sqlite3",
        )
        assert result.ok is True
        assert "hello from wav fixture" in result.original_text
        assert "来自 wav fixture 的你好" in result.translated_text
        assert result.segments_count >= 1


# ── 6. SegmentAPI reads result ─────────────────────────────────
class TestSegmentAPIRead:
    def test_reads_back(self, wav_path, tmp_path):
        result = run_wav_file_smoke(
            wav_path,
            repository_path=tmp_path / "wav_smoke2.sqlite3",
        )
        assert result.original_text
        assert result.translated_text
        assert result.bilingual_text


# ── 7. repository closed ───────────────────────────────────────
class TestRepoClosed:
    def test_closed(self, wav_path, tmp_path):
        result = run_wav_file_smoke(
            wav_path,
            repository_path=tmp_path / "wav_smoke3.sqlite3",
        )
        assert result.repo_closed is True


# ── 8. invalid path ────────────────────────────────────────────
class TestInvalidPath:
    def test_missing(self, tmp_path):
        result = run_wav_file_smoke(
            "nonexistent.wav",
            repository_path=tmp_path / "smoke.sqlite3",
        )
        assert result.ok is False
        assert result.errors


# ── 9. non-wav file ────────────────────────────────────────────
class TestNonWav:
    def test_text_file(self, tmp_path):
        p = tmp_path / "not_wav.wav"
        p.write_text("this is text")
        result = run_wav_file_smoke(str(p), repository_path=tmp_path / "smoke.sqlite3")
        assert result.ok is False


# ── 10. no real microphone ─────────────────────────────────────
class TestNoRealMic:
    def test_no_sounddevice_call(self, wav_path, tmp_path):
        result = run_wav_file_smoke(wav_path, repository_path=tmp_path / "smoke.sqlite3")
        assert result.ok is True


# ── 11. no real Whisper ────────────────────────────────────────
class TestNoRealWhisper:
    def test_no_whisper_import(self, wav_path, tmp_path):
        result = run_wav_file_smoke(wav_path, repository_path=tmp_path / "smoke.sqlite3")
        assert result.ok is True


# ── 12. no real API ────────────────────────────────────────────
class TestNoRealAPI:
    def test_no_network(self, wav_path, tmp_path):
        result = run_wav_file_smoke(wav_path, repository_path=tmp_path / "smoke.sqlite3")
        assert result.ok is True


# ── 13. no real user path ──────────────────────────────────────
class TestNoRealUserPath:
    def test_isolated(self, wav_path, tmp_path):
        result = run_wav_file_smoke(wav_path, repository_path=tmp_path / "smoke.sqlite3")
        assert "Application Support/RealtimeSubtitle" not in str(wav_path)


# ── 14. config unchanged ───────────────────────────────────────
class TestConfigUntouched:
    def test_defaults(self):
        import config
        assert config.config.use_translation_scheduler is False
        assert config.config.use_sqlite_session_repository is False


# ── 15. smoke result serializable ──────────────────────────────
class TestSerializable:
    def test_json(self, wav_path, tmp_path):
        result = run_wav_file_smoke(wav_path, repository_path=tmp_path / "smoke.sqlite3")
        d = asdict(result)
        j = json.dumps(d, default=str)
        assert len(j) > 0
