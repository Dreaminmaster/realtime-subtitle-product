"""Unit tests for runtime transcriber bridge adapter + guard + decision."""
import pytest
from src.runtime_transcriber_bridge_adapter import build_transcriber_output_bridge_for_runtime
from src.runtime_settings_guard import (
    RuntimeSettingsGuard, RuntimeSettingsDecision, settings_from_config,
)
from src.settings_dependency_engine import SettingsDependencyEngine


class FakeCfg:
    use_translation_scheduler = False
    use_sqlite_session_repository = False
    use_transcriber_output_bridge = False


# ── 1. flag off → no bridge ─────────────────────────────────────
class TestFlagOff:
    def test_no_bridge(self):
        cfg = FakeCfg()
        d = RuntimeSettingsGuard().evaluate(settings_from_config(cfg))
        b = build_transcriber_output_bridge_for_runtime(d, session_id="test", translation_adapter=object())
        assert b is None


# ── 2. scheduler off + bridge on → rejected ─────────────────────
class TestSchedulerOffBridgeOn:
    def test_rejected(self):
        cfg = FakeCfg()
        cfg.use_transcriber_output_bridge = True
        d = RuntimeSettingsGuard().evaluate(settings_from_config(cfg))
        assert d.ok is False
        assert d.allow_transcriber_output_bridge is False
        codes = {i.code for i in d.issues}
        assert "transcriber_bridge_requires_scheduler" in codes
        assert d.should_fallback_to_legacy is True


# ── 3. scheduler on + bridge on → allowed ────────────────────────
class TestSchedulerOnBridgeOn:
    def test_allowed(self):
        cfg = FakeCfg()
        cfg.use_translation_scheduler = True
        cfg.use_transcriber_output_bridge = True
        d = RuntimeSettingsGuard().evaluate(settings_from_config(cfg))
        assert d.allow_transcriber_output_bridge is True
        assert d.ok is True


# ── 4. scheduler + repo + bridge → all allowed ──────────────────
class TestAllOn:
    def test_all_allowed(self):
        cfg = FakeCfg()
        cfg.use_translation_scheduler = True
        cfg.use_sqlite_session_repository = True
        cfg.use_transcriber_output_bridge = True
        d = RuntimeSettingsGuard().evaluate(settings_from_config(cfg))
        assert d.allow_translation_scheduler is True
        assert d.allow_sqlite_repository is True
        assert d.allow_transcriber_output_bridge is True


# ── 5. build bridge when allowed ─────────────────────────────────
class TestBuildBridge:
    def test_returns_bridge(self):
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        class FakeAdapter:
            def on_final_text(self, text, chunk_id): pass
        b = build_transcriber_output_bridge_for_runtime(d, session_id="test", translation_adapter=FakeAdapter())
        assert b is not None

    def test_no_adapter_returns_none(self):
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        b = build_transcriber_output_bridge_for_runtime(d, session_id="test", translation_adapter=None)
        assert b is None


# ── 6. bridge forwards FINAL ─────────────────────────────────────
class TestBridgeForwardFinal:
    def test_called_once(self):
        called = []
        class FakeAdapter:
            def on_final_text(self, text, chunk_id):
                called.append((text, chunk_id))
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        b = build_transcriber_output_bridge_for_runtime(d, session_id="test", translation_adapter=FakeAdapter())
        r = b.handle_raw_output({"text": "hello", "status": "final"})
        assert r.ok is True
        assert r.forwarded is True
        assert len(called) == 1


# ── 7. bridge does not forward PARTIAL/STABLE ────────────────────
class TestBridgeNoForward:
    def test_partial(self):
        called = []
        class FakeAdapter:
            def on_final_text(self, text, chunk_id):
                called.append(text)
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_translation_scheduler=True,
            allow_transcriber_output_bridge=True,
        )
        b = build_transcriber_output_bridge_for_runtime(d, session_id="test", translation_adapter=FakeAdapter())
        r = b.handle_raw_output({"text": "hel", "status": "partial"})
        assert r.forwarded is False
        assert called == []


# ── 8. adapter exception safe ────────────────────────────────────
class TestAdapterExceptionSafe:
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
        b = build_transcriber_output_bridge_for_runtime(d, session_id="test", translation_adapter=FailingAdapter())
        r = b.handle_raw_output("hello")
        assert r.ok is False
        assert r.forwarded is False


# ── 9. no side effects ──────────────────────────────────────────
class TestNoSideEffects:
    def test_no_construction(self):
        cfg = FakeCfg()
        cfg.use_translation_scheduler = True
        cfg.use_transcriber_output_bridge = True
        d = RuntimeSettingsGuard().evaluate(settings_from_config(cfg))
        b = build_transcriber_output_bridge_for_runtime(d, session_id="test", translation_adapter=object())
        assert b is not None


# ── 10-14. engine, guard, formatter updates ─────────────────────
class TestEngineRule:
    def test_rule_present(self):
        eng = SettingsDependencyEngine()
        r = eng.validate({"use_transcriber_output_bridge": True, "use_translation_scheduler": False})
        assert r.ok is False
        codes = {i.code for i in r.issues}
        assert "transcriber_bridge_requires_scheduler" in codes

    def test_rule_passes(self):
        eng = SettingsDependencyEngine()
        r = eng.validate({"use_transcriber_output_bridge": True, "use_translation_scheduler": True})
        assert r.ok is True

    def test_engine_rule_no_side_effects(self):
        inp = {"use_transcriber_output_bridge": False, "use_translation_scheduler": False}
        orig = dict(inp)
        SettingsDependencyEngine().validate(inp)
        assert inp == orig


class TestRuntimeGuardDecision:
    def test_scheduler_on_bridge_on_allow(self):
        d = RuntimeSettingsGuard().evaluate({
            "use_translation_scheduler": True,
            "use_transcriber_output_bridge": True,
        })
        assert d.allow_transcriber_output_bridge is True

    def test_scheduler_off_bridge_on_disallow(self):
        d = RuntimeSettingsGuard().evaluate({
            "use_translation_scheduler": False,
            "use_transcriber_output_bridge": True,
        })
        assert d.allow_transcriber_output_bridge is False


class TestFormatterShows:
    def test_transcriber_bridge_in_display(self):
        from src.runtime_decision_formatter import format_runtime_settings_decision_html
        d = RuntimeSettingsDecision(
            ok=True, mode="scheduler", effective_settings={},
            issues=[], recommended_changes={},
            allow_transcriber_output_bridge=False,
        )
        html = format_runtime_settings_decision_html(d)
        assert "Transcriber bridge" in html
        assert "disabled" in html


class TestDefaults:
    def test_default_false(self):
        d = RuntimeSettingsGuard().evaluate(settings_from_config(FakeCfg()))
        assert d.allow_transcriber_output_bridge is False


class TestConfigFlagMissing:
    def test_default_no_flag(self):
        class NoFlag:
            use_translation_scheduler = True
        s = settings_from_config(NoFlag())
        assert "use_transcriber_output_bridge" not in s
