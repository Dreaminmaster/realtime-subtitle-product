"""Unit tests for RuntimeSettingsGuard."""
import pytest
import json
from dataclasses import asdict
from src.runtime_settings_guard import (
    RuntimeSettingsGuard, RuntimeSettingsDecision, RuntimeSettingsIssue,
    settings_from_config,
)
from src.settings_dependency_engine import SettingsDependencyEngine


@pytest.fixture
def guard():
    return RuntimeSettingsGuard()


# ── 1. legacy defaults ─────────────────────────────────────────
class TestLegacyDefaults:
    def test_decision(self, guard):
        d = guard.evaluate({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": False,
        })
        assert d.ok is True
        assert d.mode == "legacy"
        assert d.allow_translation_scheduler is False
        assert d.allow_sqlite_repository is False
        assert d.should_fallback_to_legacy is False


# ── 2. scheduler only ──────────────────────────────────────────
class TestSchedulerOnly:
    def test_decision(self, guard):
        d = guard.evaluate({
            "use_translation_scheduler": True,
            "use_sqlite_session_repository": False,
        })
        assert d.ok is True
        assert d.mode == "scheduler"
        assert d.allow_translation_scheduler is True
        assert d.allow_sqlite_repository is False


# ── 3. scheduler + repository ──────────────────────────────────
class TestSchedulerRepo:
    def test_decision(self, guard):
        d = guard.evaluate({
            "use_translation_scheduler": True,
            "use_sqlite_session_repository": True,
        })
        assert d.ok is True
        assert d.mode == "scheduler_repository"
        assert d.allow_translation_scheduler is True
        assert d.allow_sqlite_repository is True
        assert d.allow_segment_history is False  # not explicitly true
        assert d.allow_segment_export is False


# ── 4. repo without scheduler rejected ─────────────────────────
class TestRepoWithoutScheduler:
    def test_decision(self, guard):
        d = guard.evaluate({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": True,
        })
        assert d.ok is False
        assert d.mode == "invalid"
        assert d.allow_sqlite_repository is False
        assert d.should_fallback_to_legacy is True
        codes = {i.code for i in d.issues}
        assert "repository_requires_scheduler" in codes


# ── 5. history without repo rejected ───────────────────────────
class TestHistoryWithoutRepo:
    def test_decision(self, guard):
        d = guard.evaluate({
            "use_segment_api_for_history": True,
            "use_sqlite_session_repository": False,
        })
        assert d.ok is False
        assert d.allow_segment_history is False
        assert d.should_fallback_to_legacy is True


# ── 6. export without repo rejected ────────────────────────────
class TestExportWithoutRepo:
    def test_decision(self, guard):
        d = guard.evaluate({
            "use_segment_api_for_export": True,
            "use_sqlite_session_repository": False,
        })
        assert d.ok is False
        assert d.allow_segment_export is False
        assert d.should_fallback_to_legacy is True


# ── 7. overlay warning does not block ──────────────────────────
class TestOverlayWarning:
    def test_decision(self, guard):
        d = guard.evaluate({
            "use_segment_api_for_overlay": True,
            "use_sqlite_session_repository": False,
        })
        assert d.ok is True
        assert d.allow_segment_overlay is False
        warnings = [i for i in d.issues if i.severity == "warning"]
        assert any("overlay_segment_api_requires_repository" == i.code for i in warnings)
        assert d.should_fallback_to_legacy is False


# ── 8. unknown settings safe ───────────────────────────────────
class TestUnknownSettings:
    def test_decision(self, guard):
        d = guard.evaluate({"some_future_flag": True})
        assert isinstance(d, RuntimeSettingsDecision)


# ── 9. non-bool normalized ─────────────────────────────────────
class TestNonBool:
    def test_decision(self, guard):
        inp = {
            "use_translation_scheduler": "true",
            "use_sqlite_session_repository": 1,
        }
        orig = dict(inp)
        d = guard.evaluate(inp)
        assert d.effective_settings["use_translation_scheduler"] is True
        assert d.effective_settings["use_sqlite_session_repository"] is True
        assert inp == orig


# ── 10. serializable ───────────────────────────────────────────
class TestSerializable:
    def test_json(self, guard):
        d = guard.evaluate({"use_translation_scheduler": False})
        j = json.dumps(asdict(d), default=str)
        assert len(j) > 0


# ── 11. no side effects ────────────────────────────────────────
class TestNoSideEffects:
    def test_no_io(self, guard):
        d = guard.evaluate({"use_translation_scheduler": False})
        assert d is not None


# ── 12. settings_from_config helper ────────────────────────────
class TestSettingsFromConfig:
    def test_extracts(self):
        class FakeCfg:
            use_translation_scheduler = True
            use_sqlite_session_repository = False
        d = settings_from_config(FakeCfg())
        assert d["use_translation_scheduler"] is True
        assert d["use_sqlite_session_repository"] is False

    def test_missing_keys_omitted(self):
        class FakeCfg:
            use_translation_scheduler = False
        d = settings_from_config(FakeCfg())
        assert "use_sqlite_session_repository" not in d


# ── 13. falsy string safe ──────────────────────────────────────
class TestFalsyString:
    def test_normalized(self, guard):
        d = guard.evaluate({
            "use_translation_scheduler": "false",
            "use_sqlite_session_repository": False,
        })
        assert d.mode == "legacy"
        assert d.allow_translation_scheduler is False
