"""Unit tests for TranscriberOutputBridge."""
import pytest
import json
from dataclasses import asdict
from src.transcriber_output_bridge import (
    TranscriberOutputBridge, TranscriberBridgeResult, TranscriberBridgeStats,
)
from src.asr_result_adapter import NormalizedASRResult


@pytest.fixture
def bridge():
    return TranscriberOutputBridge(session_id="test")


@pytest.fixture
def bridge_with_adapter():
    called = []
    class FakeAdapter:
        def on_final_text(self, text, chunk_id):
            called.append((text, chunk_id))
    return TranscriberOutputBridge(session_id="test", translation_adapter=FakeAdapter()), called


# ── 1. invalid None ──────────────────────────────────────────────
class TestInvalidNone:
    def test_safe(self, bridge):
        r = bridge.handle_raw_output(None)
        assert r.ok is False
        assert r.normalized is None
        assert r.forwarded is False


# ── 2. empty text ────────────────────────────────────────────────
class TestEmptyText:
    def test_invalid(self, bridge):
        r = bridge.handle_raw_output({"text": "", "status": "final"})
        assert r.ok is False



# ── 3. unknown status ────────────────────────────────────────────
class TestUnknownStatus:
    def test_invalid(self, bridge):
        r = bridge.handle_raw_output({"text": "hello", "status": "weird"})
        assert r.ok is False
        assert r.forwarded is False


# ── 4. PARTIAL ───────────────────────────────────────────────────
class TestPartial:
    def test_not_forwarded(self, bridge_with_adapter):
        bridge, called = bridge_with_adapter
        r = bridge.handle_raw_output({"text": "hel", "status": "partial", "segment_id": "s1"})
        assert r.ok is True
        assert r.forwarded is False
        assert r.normalized.status == "PARTIAL"
        assert called == []


# ── 5. STABLE ────────────────────────────────────────────────────
class TestStable:
    def test_not_forwarded(self, bridge_with_adapter):
        bridge, called = bridge_with_adapter
        r = bridge.handle_raw_output({"text": "hello", "status": "stable", "segment_id": "s1"})
        assert r.ok is True
        assert r.forwarded is False
        assert r.normalized.status == "STABLE"
        assert called == []


# ── 6. FINAL ─────────────────────────────────────────────────────
class TestFinal:
    def test_forwarded(self, bridge_with_adapter):
        bridge, called = bridge_with_adapter
        r = bridge.handle_raw_output({"text": "hello", "status": "final", "segment_id": "s1"})
        assert r.ok is True
        assert r.forwarded is True
        assert r.normalized.status == "FINAL"
        assert len(called) == 1


# ── 7. plain str ─────────────────────────────────────────────────
class TestPlainStr:
    def test_forwarded(self, bridge_with_adapter):
        bridge, called = bridge_with_adapter
        r = bridge.handle_raw_output("hello")
        assert r.ok is True
        assert r.forwarded is True
        assert r.normalized.status == "FINAL"
        assert len(called) == 1


# ── 8. object output ─────────────────────────────────────────────
class TestObjectOutput:
    def test_forwarded(self, bridge_with_adapter):
        class FakeOutput:
            text = "hello"
            status = "final"
        bridge, called = bridge_with_adapter
        r = bridge.handle_raw_output(FakeOutput())
        assert r.ok is True
        assert r.forwarded is True
        assert r.normalized.status == "FINAL"


# ── 9. adapter missing ───────────────────────────────────────────
class TestAdapterMissing:
    def test_safe(self, bridge):
        r = bridge.handle_raw_output({"text": "hello", "status": "final"})
        assert r.ok is True
        assert r.forwarded is False
        assert "notranslationadapter" in r.message.lower().replace(" ", "")



# ── 10. adapter exception ────────────────────────────────────────
class TestAdapterException:
    def test_safe(self):
        class FailingAdapter:
            def on_final_text(self, text, chunk_id):
                raise RuntimeError("boom")
        bridge = TranscriberOutputBridge(session_id="test", translation_adapter=FailingAdapter())
        r = bridge.handle_raw_output({"text": "hello", "status": "final"})
        assert r.ok is False
        assert r.forwarded is False
        assert "forward" in r.message.lower()


# ── 11. handle_many ──────────────────────────────────────────────
class TestHandleMany:
    def test_order(self, bridge_with_adapter):
        bridge, called = bridge_with_adapter
        results = bridge.handle_many([
            {"text": "hel", "status": "partial", "segment_id": "s1"},
            {"text": "hello", "status": "stable", "segment_id": "s1"},
            {"text": "hello", "status": "final", "segment_id": "s1"},
        ])
        assert len(results) == 3
        assert results[0].forwarded is False
        assert results[1].forwarded is False
        assert results[2].forwarded is True
        assert len(called) == 1


# ── 12. stats serializable ───────────────────────────────────────
class TestStatsSerializable:
    def test_json(self, bridge):
        bridge.handle_raw_output({"text": "hello", "status": "final"})
        s = bridge.get_stats()
        j = json.dumps(asdict(s), default=str)
        assert len(j) > 0


# ── 13. result serializable ──────────────────────────────────────
class TestResultSerializable:
    def test_json(self, bridge):
        r = bridge.handle_raw_output({"text": "hello", "status": "final"})
        j = json.dumps(asdict(r), default=str)
        assert len(j) > 0


# ── 14. raw not mutated ──────────────────────────────────────────
class TestRawNotMutated:
    def test_dict(self, bridge):
        raw = {"text": "hello", "status": "final"}
        orig = dict(raw)
        bridge.handle_raw_output(raw)
        assert raw == orig


# ── 15. no side effects ──────────────────────────────────────────
class TestNoSideEffects:
    def test_no_io(self, bridge):
        r = bridge.handle_raw_output({"text": "hello", "status": "final"})
        assert r is not None
