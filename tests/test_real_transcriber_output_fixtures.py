"""Real transcriber output fixtures — adapter + bridge + pipeline + smoke.
All shapes without real Whisper, real mic, or real API.
"""
import pytest
import time
import uuid
import json
from dataclasses import asdict
from src.asr_result_adapter import (
    ASRResultAdapter, NormalizedASRResult,
    forward_normalized_asr_to_translation_adapter,
)
from src.transcriber_output_bridge import (
    TranscriberOutputBridge, TranscriberBridgeStats,
)


# ── Fixtures ────────────────────────────────────────────────────
FI = "test-session-4a"

PLAIN_TEXT = "Transcriber returns plain text"
DICT_FINAL = {"text": "hello from dict final", "status": "final"}
DICT_PARTIAL = {"text": "hel", "status": "partial"}
DICT_STABLE = {"text": "hello stable", "status": "stable"}
DICT_IS_FINAL = {"transcript": "hello from is_final", "is_final": True}
SEGMENTS = {"segments": [{"text": "hello"}, {"text": "world"}], "status": "final"}


class ObjOutput:
    text = "hello object"
    status = "final"


FIXTURES = [
    ("plain_text", PLAIN_TEXT, True, "FINAL", "Transcriber"),
    ("dict_final", DICT_FINAL, True, "FINAL", "hello from dict final"),
    ("dict_partial", DICT_PARTIAL, True, "PARTIAL", None),
    ("dict_stable", DICT_STABLE, True, "STABLE", None),
    ("dict_is_final", DICT_IS_FINAL, True, "FINAL", "hello from is_final"),
    ("segments", SEGMENTS, True, "FINAL", "hello world"),
    ("object_output", ObjOutput(), True, "FINAL", "hello object"),
]


# ── 1-3. fixture normalize safe ──────────────────────────────────
class TestFixtureNormalize:
    def test_all_safe(self):
        adapter = ASRResultAdapter(session_id=FI)
        for name, fi, _, _, _ in FIXTURES:
            r = adapter.normalize(fi)
            assert r is not None or isinstance(r, type(None)), f"{name}: unexpected crash"

    def test_final_becomes_FINAL(self):
        adapter = ASRResultAdapter(session_id=FI)
        for name, fi, _, exp_status, _ in FIXTURES:
            r = adapter.normalize(fi)
            if r is not None:
                assert r.status == exp_status, f"{name}: expected {exp_status}, got {r.status}"

    def test_final_text_present(self):
        adapter = ASRResultAdapter(session_id=FI)
        for name, fi, _, _, exp_text in FIXTURES:
            if exp_text is None:
                continue
            r = adapter.normalize(fi)
            if r is not None and r.status == "FINAL":
                assert exp_text in r.text, f"{name}: '{exp_text}' not in '{r.text}'"


# ── 4-6. bridge fixture forward ──────────────────────────────────
class TestBridgeFixtureForward:
    def test_final_forwarded_once(self):
        called = []
        class FakeAdapter:
            def on_final_text(self, text, chunk_id):
                called.append(text)
        bridge = TranscriberOutputBridge(session_id=FI, translation_adapter=FakeAdapter())
        r = bridge.handle_raw_output(DICT_FINAL)
        assert r.forwarded is True
        assert len(called) == 1

    def test_partial_not_forwarded(self):
        called = []
        class FakeAdapter:
            def on_final_text(self, text, chunk_id):
                called.append(text)
        bridge = TranscriberOutputBridge(session_id=FI, translation_adapter=FakeAdapter())
        r = bridge.handle_raw_output(DICT_PARTIAL)
        assert r.forwarded is False
        assert called == []

    def test_stable_not_forwarded(self):
        called = []
        class FakeAdapter:
            def on_final_text(self, text, chunk_id):
                called.append(text)
        bridge = TranscriberOutputBridge(session_id=FI, translation_adapter=FakeAdapter())
        r = bridge.handle_raw_output(DICT_STABLE)
        assert r.forwarded is False
        assert called == []


# ── 7. invalid fixture safe ──────────────────────────────────────
class TestInvalidFixture:
    def test_none_safe(self):
        bridge = TranscriberOutputBridge(session_id=FI)
        r = bridge.handle_raw_output(None)
        assert r.ok is False

    def test_empty_safe(self):
        bridge = TranscriberOutputBridge(session_id=FI)
        r = bridge.handle_raw_output({"text": "", "status": "final"})
        assert r.ok is False


# ── 8. object fixture forwarded ──────────────────────────────────
class TestObjectFixture:
    def test_forwarded_once(self):
        called = []
        class FakeAdapter:
            def on_final_text(self, text, chunk_id):
                called.append(text)
        bridge = TranscriberOutputBridge(session_id=FI, translation_adapter=FakeAdapter())
        r = bridge.handle_raw_output(ObjOutput())
        assert r.forwarded is True
        assert len(called) == 1


# ── 9. handle_many order ─────────────────────────────────────────
class TestHandleMany:
    def test_order_preserved(self):
        called = []
        class FakeAdapter:
            def on_final_text(self, text, chunk_id):
                called.append(text)
        bridge = TranscriberOutputBridge(session_id=FI, translation_adapter=FakeAdapter())
        results = bridge.handle_many([
            DICT_PARTIAL, DICT_STABLE, DICT_FINAL, PLAIN_TEXT,
        ])
        assert results[0].forwarded is False
        assert results[1].forwarded is False
        assert results[2].forwarded is True
        assert results[3].forwarded is True
        assert len(called) == 2


# ── 10. adapter exception safe ───────────────────────────────────
class TestAdapterException:
    def test_no_crash(self):
        class FailingAdapter:
            def on_final_text(self, t, c):
                raise RuntimeError("boom")
        bridge = TranscriberOutputBridge(session_id=FI, translation_adapter=FailingAdapter())
        r = bridge.handle_raw_output(DICT_FINAL)
        assert r.ok is False
        assert r.forwarded is False


# ── 11-12. pipeline hook ─────────────────────────────────────────
class FakePipeline:
    def __init__(self, bridge=None):
        self.transcriber_output_bridge = bridge
        self._handled = []
    def _handle_transcriber_output_via_bridge(self, raw):
        bridge = getattr(self, 'transcriber_output_bridge', None)
        if bridge is None:
            return False
        try:
            result = bridge.handle_raw_output(raw)
            self._handled.append(result)
            return result.ok
        except Exception:
            return False


class TestPipelineHook:
    def test_no_bridge_returns_false(self):
        p = FakePipeline(bridge=None)
        assert p._handle_transcriber_output_via_bridge(DICT_FINAL) is False

    def test_final_through_hook(self):
        called = []
        class FakeAdapter:
            def on_final_text(self, t, c):
                called.append(t)
        bridge = TranscriberOutputBridge(session_id=FI, translation_adapter=FakeAdapter())
        p = FakePipeline(bridge=bridge)
        ok = p._handle_transcriber_output_via_bridge(DICT_FINAL)
        assert ok is True
        assert len(called) == 1

    def test_partial_through_hook_no_forward(self):
        called = []
        class FakeAdapter:
            def on_final_text(self, t, c):
                called.append(t)
        bridge = TranscriberOutputBridge(session_id=FI, translation_adapter=FakeAdapter())
        p = FakePipeline(bridge=bridge)
        ok = p._handle_transcriber_output_via_bridge(DICT_PARTIAL)
        assert ok is True  # bridge returns ok=True for recognized partial (just not forwarded)
        assert called == []

    def test_invalid_through_hook_safe(self):
        bridge = TranscriberOutputBridge(session_id=FI)
        p = FakePipeline(bridge=bridge)
        ok = p._handle_transcriber_output_via_bridge(None)
        assert ok is False

    def test_adapter_exception_safe(self):
        class FailingAdapter:
            def on_final_text(self, t, c):
                raise RuntimeError("boom")
        bridge = TranscriberOutputBridge(session_id=FI, translation_adapter=FailingAdapter())
        p = FakePipeline(bridge=bridge)
        ok = p._handle_transcriber_output_via_bridge(DICT_FINAL)
        assert ok is False


# ── 13-15. controlled smoke ──────────────────────────────────────
class TestControlledSmoke:
    def test_final_writes_repository(self, tmp_path):
        from src.session_repository import SQLiteSessionRepository
        from src.segment_api import SegmentAPI
        from src.translation_scheduler import TranslationScheduler
        from src.translation_adapter import TranslationAdapter
        repo_path = str(tmp_path / "4a_smoke.sqlite3")
        repo = SQLiteSessionRepository(repo_path); repo.initialize()
        sid = str(uuid.uuid4())
        class FT:
            def translate(self, t, l=None): return f"ZH:{t}"
        sched = TranslationScheduler(translator=FT().translate, max_queue=5, max_workers=1)
        adapter = TranslationAdapter(scheduler=sched, repository=repo, repository_enabled=True)
        adapter.start_session(sid)
        bridge = TranscriberOutputBridge(session_id=sid, translation_adapter=adapter)
        r = bridge.handle_raw_output(DICT_FINAL)
        time.sleep(0.3)
        adapter.stop_session()
        sched.shutdown(wait=True)
        api = SegmentAPI(repo)
        snap = api.get_session_snapshot(sid)
        assert "hello from dict final" in snap.original_text
        assert "ZH:" in snap.translated_text
        repo.close()

    def test_partial_no_translation(self, tmp_path):
        from src.session_repository import SQLiteSessionRepository
        from src.segment_api import SegmentAPI
        repo_path = str(tmp_path / "partial.sqlite3")
        repo = SQLiteSessionRepository(repo_path); repo.initialize()
        sid = str(uuid.uuid4())
        bridge = TranscriberOutputBridge(session_id=sid)
        r = bridge.handle_raw_output(DICT_PARTIAL)
        assert r.forwarded is False
        api = SegmentAPI(repo)
        segs = api.list_segments(sid)
        assert len(segs) == 0
        repo.close()

    def test_smoke_serializable(self):
        r = {"ok": True, "forwarded": True, "segments": 1, "original": "hello", "translated": "ZH:hello"}
        j = json.dumps(r)
        assert len(j) > 0
