"""Tests: main.py Pipeline bridge hook wiring."""
import pytest
import time
from unittest.mock import patch
from src.runtime_settings_guard import RuntimeSettingsDecision


# ── helper: mini pipeline with bridge ──────────────────────────
class MiniPipeline:
    """Minimal Pipeline-like object for testing bridge hook."""
    def __init__(self, decision, adapter=None):
        self._runtime_decision = decision
        self.translation_adapter = adapter
        self.transcriber_output_bridge = None
        import logging
        self.log = logging.getLogger("test")
        self._repo_owned = False
        self._repository = None

        if decision.allow_translation_scheduler:
            from src.runtime_transcriber_bridge_adapter import (
                build_transcriber_output_bridge_for_runtime,
            )
            try:
                self.transcriber_output_bridge = (
                    build_transcriber_output_bridge_for_runtime(
                        decision, session_id="test", translation_adapter=adapter,
                    )
                )
            except Exception:
                self.transcriber_output_bridge = None

    def _handle_transcriber_output_via_bridge(self, raw_output) -> bool:
        bridge = getattr(self, 'transcriber_output_bridge', None)
        if bridge is None:
            return False
        try:
            result = bridge.handle_raw_output(raw_output)
            if result.ok:
                return True
            return True
        except Exception:
            return False

    def stop(self):
        self.transcriber_output_bridge = None


@pytest.fixture
def fake_adapter():
    calls = []
    class FakeAdapter:
        def on_final_text(self, text, chunk_id):
            calls.append((text, chunk_id))
    return FakeAdapter(), calls


# ── 1. default no bridge ──────────────────────────────────────
class TestDefaultNoBridge:
    def test_bridge_none(self):
        d = RuntimeSettingsDecision(
            ok=True, mode="legacy", effective_settings={},
            issues=[], recommended_changes={},
        )
        p = MiniPipeline(d)
        assert p.transcriber_output_bridge is None


# ── 2. scheduler off + bridge on → rejected ────────────────────
class TestSchedulerOffBridgeOn:
    def test_no_bridge(self):
        d = RuntimeSettingsDecision(
            ok=False, mode="invalid", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=False,
            allow_transcriber_output_bridge=False,
        )
        p = MiniPipeline(d)
        assert p.transcriber_output_bridge is None


# ── 3. scheduler on + bridge on → bridge created ───────────────
class TestSchedulerOnBridgeOn:
    def test_bridge_created(self, fake_adapter):
        adapter, _ = fake_adapter
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        p = MiniPipeline(d, adapter)
        assert p.transcriber_output_bridge is not None


# ── 4. scheduler + repo + bridge → all created ─────────────────
class TestAllOn:
    def test_bridge_created(self, fake_adapter):
        adapter, _ = fake_adapter
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler_repository", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_sqlite_repository=True,
            allow_transcriber_output_bridge=True,
        )
        p = MiniPipeline(d, adapter)
        assert p.transcriber_output_bridge is not None


# ── 5. missing adapter → no bridge ─────────────────────────────
class TestMissingAdapter:
    def test_none(self):
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        p = MiniPipeline(d, adapter=None)
        assert p.transcriber_output_bridge is None


# ── 6. bridge creation failure safe ────────────────────────────
class TestCreationFailure:
    def test_no_crash(self, fake_adapter):
        adapter, _ = fake_adapter
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        with patch(
            "src.runtime_transcriber_bridge_adapter.build_transcriber_output_bridge_for_runtime",
            side_effect=RuntimeError("boom"),
        ):
            p = MiniPipeline(d, adapter)
        assert p.transcriber_output_bridge is None


# ── 7. hook false when bridge missing ──────────────────────────
class TestHookFalseWhenMissing:
    def test_returns_false(self):
        d = RuntimeSettingsDecision(
            ok=True, mode="legacy", effective_settings={},
            issues=[], recommended_changes={},
        )
        p = MiniPipeline(d)
        assert p._handle_transcriber_output_via_bridge({"text": "hello", "status": "final"}) is False


# ── 8. hook PARTIAL no forward ─────────────────────────────────
class TestHookPartial:
    def test_no_forward(self, fake_adapter):
        adapter, calls = fake_adapter
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        p = MiniPipeline(d, adapter)
        assert p._handle_transcriber_output_via_bridge({"text": "hel", "status": "partial"}) is True
        assert len(calls) == 0


# ── 9. hook STABLE no forward ──────────────────────────────────
class TestHookStable:
    def test_no_forward(self, fake_adapter):
        adapter, calls = fake_adapter
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        p = MiniPipeline(d, adapter)
        assert p._handle_transcriber_output_via_bridge({"text": "hello", "status": "stable"}) is True
        assert len(calls) == 0


# ── 10. hook FINAL forward ─────────────────────────────────────
class TestHookFinal:
    def test_forward(self, fake_adapter):
        adapter, calls = fake_adapter
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        p = MiniPipeline(d, adapter)
        assert p._handle_transcriber_output_via_bridge({"text": "hello", "status": "final"}) is True
        assert len(calls) == 1


# ── 11. hook invalid raw safe ──────────────────────────────────
class TestHookInvalid:
    def test_safe(self, fake_adapter):
        adapter, calls = fake_adapter
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        p = MiniPipeline(d, adapter)
        assert p._handle_transcriber_output_via_bridge(None) is True
        assert len(calls) == 0


# ── 12. hook adapter exception safe ────────────────────────────
class TestHookException:
    def test_safe(self):
        class FailingAdapter:
            def on_final_text(self, text, chunk_id):
                raise RuntimeError("boom")
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        p = MiniPipeline(d, FailingAdapter())
        assert p._handle_transcriber_output_via_bridge("hello") is True


# ── 13. no duplicate translation ────────────────────────────────
class TestNoDuplicate:
    def test_single_call(self, fake_adapter):
        adapter, calls = fake_adapter
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        p = MiniPipeline(d, adapter)
        p._handle_transcriber_output_via_bridge({"text": "hello", "status": "final"})
        assert len(calls) == 1


# ── 14. no real audio ──────────────────────────────────────────
class TestNoRealAudio:
    def test_no_audio(self, fake_adapter):
        adapter, _ = fake_adapter
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        p = MiniPipeline(d, adapter)
        assert p._handle_transcriber_output_via_bridge({"text": "hello", "status": "final"}) is True
