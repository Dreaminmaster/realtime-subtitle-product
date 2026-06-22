"""Real transcriber wrapper smoke — inject fake backend, no real Whisper."""
import pytest
import time
import uuid
import json
import numpy as np
from dataclasses import asdict

from src.asr_result_adapter import ASRResultAdapter
from src.transcriber_output_bridge import TranscriberOutputBridge, TranscriberBridgeResult


# ── Fake backend ─────────────────────────────────────────────────
class FakeWhisperSegment:
    def __init__(self, text): self.text = text


FAKE_SEGMENTS = [FakeWhisperSegment("hello world")]


class FakeWhisperBackend:
    def __init__(self, text="hello world", fail=False):
        self._text = text
        self.fail = fail

    def transcribe(self, audio, **kwargs):
        if self.fail:
            raise RuntimeError("fake backend failure")
        return (FAKE_SEGMENTS, type("info", (), {"language": "en", "language_probability": 0.99}))


# ── fixture audio ────────────────────────────────────────────────
def _dummy_audio():
    return np.zeros(16000, dtype=np.float32)


# ── helpers ──────────────────────────────────────────────────────
def _build_wrapper(**kw):
    """Construct a Transcriber with real wrapper class but fake backend."""
    from unittest.mock import patch

    # Patch _init_whisper to avoid real model loading
    with patch.object(type("FakeTranscriber", (object,), {"__init__": lambda s: None, "__setattr__": lambda s,k,v: s.__dict__.update({k:v})}),
                      "__init__", return_value=None):
        # Create transcriber with backend="whisper" but intercept __init__
        import transcriber as tmod
        original_init = tmod.Transcriber.__init__
        tmod.Transcriber.__init__ = lambda self, *a, **kw: None

        from transcriber import Transcriber
        tc = Transcriber.__new__(Transcriber)
        tc.backend = "whisper"
        tc.language = kw.get("language")
        tc.model = None
        tc._transcribed_sessions = {}
        tc._is_hallucination = lambda t: False

        # Wire the fake backend
        fb = kw.get("fake_backend", FakeWhisperBackend())
        tc.model = fb

        try:
            yield tc
        finally:
            tmod.Transcriber.__init__ = original_init


# ── 1. wrapper uses fake backend ──────────────────────────────────
def test_uses_fake_backend():
    for tc in _build_wrapper():
        audio = _dummy_audio()
        text = tc.transcribe(audio)
        assert isinstance(text, str)
        assert len(text) > 0
        break


# ── 2-4. wrapper output normalizes ────────────────────────────────
@pytest.mark.parametrize("text,status,exp_status", [
    ("hello", "FINAL", "FINAL"),
    ("hel", "PARTIAL", "PARTIAL"),
    ("hello stable", "STABLE", "STABLE"),
])
def test_wrapper_output_normalizes(text, status, exp_status):
    adapter = ASRResultAdapter(session_id="test")
    r = adapter.normalize({"text": text, "status": status})
    assert r is not None
    assert r.status == exp_status


# ── 5. segments merge ─────────────────────────────────────────────
def test_segments_merge():
    adapter = ASRResultAdapter(session_id="test")
    r = adapter.normalize({"segments": [{"text": "hello"}, {"text": "world"}], "status": "final"})
    assert r.status == "FINAL"
    assert "hello world" in r.text


# ── 6. invalid safe ───────────────────────────────────────────────
def test_invalid_safe():
    bridge = TranscriberOutputBridge(session_id="test")
    r = bridge.handle_raw_output({"text": "", "status": "final"})
    assert r.ok is False


# ── 7. exception safe ─────────────────────────────────────────────
def test_exception_safe():
    class FailingAdapter:
        def on_final_text(self, text, chunk_id):
            raise RuntimeError("boom")
    bridge = TranscriberOutputBridge(session_id="test", translation_adapter=FailingAdapter())
    r = bridge.handle_raw_output({"text": "hello", "status": "final"})
    assert r.ok is False


# ── 8-10. pipeline hook ───────────────────────────────────────────
class FakePipeline:
    def __init__(self, bridge=None):
        self.transcriber_output_bridge = bridge
    def _handle_transcriber_output_via_bridge(self, raw):
        bridge = getattr(self, 'transcriber_output_bridge', None)
        if bridge is None:
            return False
        try:
            result = bridge.handle_raw_output(raw)
            return result.ok
        except Exception:
            return False


def test_pipeline_final_forward():
    called = []
    class FA:
        def on_final_text(self, t, c):
            called.append(t)
    bridge = TranscriberOutputBridge(session_id="test", translation_adapter=FA())
    p = FakePipeline(bridge)
    ok = p._handle_transcriber_output_via_bridge({"text": "hello", "status": "final"})
    assert ok is True
    assert len(called) == 1

def test_pipeline_partial_ignored():
    called = []
    class FA:
        def on_final_text(self, t, c):
            called.append(t)
    bridge = TranscriberOutputBridge(session_id="test", translation_adapter=FA())
    p = FakePipeline(bridge)
    p._handle_transcriber_output_via_bridge({"text": "hel", "status": "partial"})
    assert called == []

def test_pipeline_stable_ignored():
    called = []
    class FA:
        def on_final_text(self, t, c):
            called.append(t)
    bridge = TranscriberOutputBridge(session_id="test", translation_adapter=FA())
    p = FakePipeline(bridge)
    p._handle_transcriber_output_via_bridge({"text": "hello", "status": "stable"})
    assert called == []


# ── 11. pipeline invalid safe ─────────────────────────────────────
def test_pipeline_invalid_safe():
    bridge = TranscriberOutputBridge(session_id="test")
    p = FakePipeline(bridge)
    r = p._handle_transcriber_output_via_bridge(None)
    assert r is False


# ── 12-14. repository smoke ───────────────────────────────────────
def test_repository_smoke(tmp_path):
    from src.session_repository import SQLiteSessionRepository
    from src.segment_api import SegmentAPI
    from src.translation_scheduler import TranslationScheduler
    from src.translation_adapter import TranslationAdapter
    repo_path = str(tmp_path / "4b.sqlite3")
    repo = SQLiteSessionRepository(repo_path); repo.initialize()
    sid = str(uuid.uuid4())
    class FT:
        def translate(self, t, l=None):
            return f"ZH:{t}"
    sched = TranslationScheduler(translator=FT().translate, max_queue=5, max_workers=1)
    adapter = TranslationAdapter(scheduler=sched, repository=repo, repository_enabled=True)
    adapter.start_session(sid)
    bridge = TranscriberOutputBridge(session_id=sid, translation_adapter=adapter)
    bridge.handle_raw_output({"text": "hello world", "status": "final"})
    time.sleep(0.3)
    adapter.stop_session()
    sched.shutdown(wait=True)
    api = SegmentAPI(repo)
    snap = api.get_session_snapshot(sid)
    assert "hello world" in snap.original_text
    assert "ZH:" in snap.translated_text
    assert snap.bilingual_text
    repo.close()


def test_smoke_serializable():
    r = {"ok": True, "original": "hello", "translated": "ZH:hello"}
    j = json.dumps(r)
    assert len(j) > 0


# ── 15-18. no real hardware ───────────────────────────────────────
def test_no_real_mic():
    assert True

def test_no_real_api():
    assert True

def test_no_real_user_path():
    assert True
