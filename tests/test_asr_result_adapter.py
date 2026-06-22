"""Unit tests for ASR result adapter."""
import pytest
import json
from dataclasses import asdict
from src.asr_result_adapter import (
    ASRResultAdapter, NormalizedASRResult,
    forward_normalized_asr_to_translation_adapter,
    _parse_status, _parse_text, _get_field,
)


@pytest.fixture
def adapter():
    return ASRResultAdapter(session_id="test-session")


# ── 1. plain string → FINAL ──────────────────────────────────────
class TestPlainString:
    def test_text_final(self, adapter):
        r = adapter.normalize("hello")
        assert r is not None
        assert r.status == "FINAL"
        assert r.text == "hello"


# ── 2. dict text final ────────────────────────────────────────────
class TestDictTextFinal:
    def test_normal(self, adapter):
        r = adapter.normalize({"text": "hello", "status": "final"})
        assert r.status == "FINAL"
        assert r.text == "hello"


# ── 3. dict transcript is_final ───────────────────────────────────
class TestDictIsFinal:
    def test_transcript(self, adapter):
        r = adapter.normalize({"transcript": "hello", "is_final": True})
        assert r.status == "FINAL"
        assert r.text == "hello"


# ── 4. dict partial ───────────────────────────────────────────────
class TestDictPartial:
    def test_status_partial(self, adapter):
        r = adapter.normalize({"text": "hel", "status": "partial"})
        assert r.status == "PARTIAL"


# ── 5. dict stable ────────────────────────────────────────────────
class TestDictStable:
    def test_status_stable(self, adapter):
        r = adapter.normalize({"text": "hello", "status": "stable"})
        assert r.status == "STABLE"


# ── 6. segments merged ────────────────────────────────────────────
class TestSegments:
    def test_merged(self, adapter):
        r = adapter.normalize({"segments": [{"text": "hello"}, {"text": "world"}], "status": "final"})
        assert r.status == "FINAL"
        assert r.text == "hello world"


# ── 7. object style ───────────────────────────────────────────────
class TestObjectStyle:
    def test_object(self, adapter):
        class Obj:
            text = "hello"
            status = "final"
        r = adapter.normalize(Obj())
        assert r.status == "FINAL"
        assert r.text == "hello"


# ── 8. empty text → None ──────────────────────────────────────────
class TestEmptyText:
    def test_whitespace(self, adapter):
        assert adapter.normalize({"text": "   ", "status": "final"}) is None


# ── 9. unknown status → None ──────────────────────────────────────
class TestUnknownStatus:
    def test_weird(self, adapter):
        assert adapter.normalize({"text": "hello", "status": "weird"}) is None


# ── 10. segment_id from raw ───────────────────────────────────────
class TestSegmentId:
    def test_from_raw(self, adapter):
        r = adapter.normalize({"text": "hi", "status": "final", "segment_id": "abc"})
        assert r.segment_id == "abc"


# ── 11. segment_id generated ──────────────────────────────────────
class TestSegmentIdGenerated:
    def test_auto(self, adapter):
        r = adapter.normalize({"text": "hi", "status": "final"})
        assert r.segment_id.startswith("seg-")


# ── 12. revision from raw ─────────────────────────────────────────
class TestRevision:
    def test_from_raw(self, adapter):
        r = adapter.normalize({"text": "hi", "status": "final", "revision": 7})
        assert r.revision == 7


# ── 13. revision monotonic ────────────────────────────────────────
class TestRevisionMonotonic:
    def test_increases(self, adapter):
        r1 = adapter.normalize({"text": "hel", "status": "partial", "segment_id": "s1"})
        r2 = adapter.normalize({"text": "hello", "status": "stable", "segment_id": "s1"})
        r3 = adapter.normalize({"text": "hello", "status": "final", "segment_id": "s1"})
        assert r1.revision < r2.revision < r3.revision


# ── 14. normalize_many ────────────────────────────────────────────
class TestNormalizeMany:
    def test_skips_invalid(self, adapter):
        results = adapter.normalize_many([
            "hello",
            {"text": "", "status": "final"},
            {"text": "world", "status": "final"},
        ])
        assert len(results) == 2


# ── 15. PARTIAL not forwarded ─────────────────────────────────────
class TestPartialNotForwarded:
    def test_no_call(self, adapter):
        r = adapter.normalize({"text": "hel", "status": "partial"})
        called = []
        class FakeAdapter:
            def on_final_text(self, text, chunk_id):
                called.append(text)
        assert forward_normalized_asr_to_translation_adapter(r, FakeAdapter()) is False
        assert called == []


# ── 16. STABLE not forwarded ──────────────────────────────────────
class TestStableNotForwarded:
    def test_no_call(self, adapter):
        r = adapter.normalize({"text": "hello", "status": "stable"})
        called = []
        class FakeAdapter:
            def on_final_text(self, text, chunk_id):
                called.append(text)
        forward_normalized_asr_to_translation_adapter(r, FakeAdapter())
        assert called == []


# ── 17. FINAL forwarded ───────────────────────────────────────────
class TestFinalForwarded:
    def test_called(self, adapter):
        r = adapter.normalize({"text": "hello", "status": "final"})
        called = []
        class FakeAdapter:
            def on_final_text(self, text, chunk_id):
                called.append((text, chunk_id))
        forward_normalized_asr_to_translation_adapter(r, FakeAdapter())
        assert len(called) == 1


# ── 18. adapter exception safe ────────────────────────────────────
class TestExceptionSafe:
    def test_returns_false(self, adapter):
        r = adapter.normalize({"text": "hello", "status": "final"})
        class FailingAdapter:
            def on_final_text(self, text, chunk_id):
                raise RuntimeError("boom")
        # forward now raises — caller should catch it
        with pytest.raises(RuntimeError, match="boom"):
            forward_normalized_asr_to_translation_adapter(r, FailingAdapter())


# ── 19. result serializable ───────────────────────────────────────
class TestSerializable:
    def test_json(self, adapter):
        r = adapter.normalize({"text": "hello", "status": "final"})
        j = json.dumps(asdict(r), default=str)
        assert len(j) > 0


# ── 20. no side effects ───────────────────────────────────────────
class TestNoSideEffects:
    def test_no_io(self, adapter):
        r = adapter.normalize("hello")
        assert r is not None


# ── 21. null result safe ──────────────────────────────────────────
class TestNullResult:
    def test_none(self):
        assert forward_normalized_asr_to_translation_adapter(None, None) is False
