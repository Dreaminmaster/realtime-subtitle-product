"""Unit tests for settings validation ViewModel."""
import pytest
import json
from dataclasses import asdict
from src.settings_validation_viewmodel import (
    build_settings_validation_viewmodel, SettingsValidationViewModel,
    SettingsValidationMessage,
)


# ── 1. legacy mode ────────────────────────────────────────────────
class TestLegacyMode:
    def test_legacy_defaults(self):
        vm = build_settings_validation_viewmodel({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": False,
        })
        assert vm.ok is True
        assert "Legacy" in vm.title
        assert vm.can_use_new_architecture is False
        assert vm.can_use_history is False
        assert vm.can_use_export is False
        assert not any(m.severity == "error" for m in vm.messages)


# ── 2. scheduler only ─────────────────────────────────────────────
class TestSchedulerOnly:
    def test_scheduler_only(self):
        vm = build_settings_validation_viewmodel({
            "use_translation_scheduler": True,
            "use_sqlite_session_repository": False,
        })
        assert vm.ok is True
        assert vm.can_use_new_architecture is True
        assert vm.can_use_history is False
        assert vm.can_use_export is False


# ── 3. scheduler + repository ─────────────────────────────────────
class TestSchedulerPlusRepo:
    def test_both_on(self):
        vm = build_settings_validation_viewmodel({
            "use_translation_scheduler": True,
            "use_sqlite_session_repository": True,
        })
        assert vm.ok is True
        assert vm.can_use_new_architecture is True
        assert vm.can_use_history is True
        assert vm.can_use_export is True
        assert "Scheduler + persistent" in vm.mode_label or "New architecture" in vm.title


# ── 4. invalid repository only ────────────────────────────────────
class TestInvalidRepoOnly:
    def test_repo_without_scheduler(self):
        vm = build_settings_validation_viewmodel({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": True,
        })
        assert vm.ok is False
        assert vm.can_use_new_architecture is False
        assert vm.messages
        assert vm.recommended_changes


# ── 5. history without repository ─────────────────────────────────
class TestHistoryWithoutRepo:
    def test_history_requires_repo(self):
        vm = build_settings_validation_viewmodel({
            "use_segment_api_for_history": True,
            "use_sqlite_session_repository": False,
        })
        assert vm.ok is False
        codes = {m.code for m in vm.messages}
        assert "history_requires_repository" in codes
        assert vm.can_use_history is False


# ── 6. export without repository ──────────────────────────────────
class TestExportWithoutRepo:
    def test_export_requires_repo(self):
        vm = build_settings_validation_viewmodel({
            "use_segment_api_for_export": True,
            "use_sqlite_session_repository": False,
        })
        assert vm.ok is False
        codes = {m.code for m in vm.messages}
        assert "export_requires_repository" in codes
        assert vm.can_use_export is False


# ── 7. overlay warning ────────────────────────────────────────────
class TestOverlayWarning:
    def test_overlay_warning(self):
        vm = build_settings_validation_viewmodel({
            "use_segment_api_for_overlay": True,
            "use_sqlite_session_repository": False,
        })
        warnings = [m for m in vm.messages if m.severity == "warning"]
        assert any("overlay_segment_api_requires_repository" == m.code for m in warnings)


# ── 8. unknown settings safe ──────────────────────────────────────
class TestUnknownSettings:
    def test_no_crash(self):
        vm = build_settings_validation_viewmodel({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": False,
            "some_future_flag": True,
        })
        assert isinstance(vm, SettingsValidationViewModel)


# ── 9. normalization ──────────────────────────────────────────────
class TestNormalization:
    def test_string_bool_normalized(self):
        vm = build_settings_validation_viewmodel({
            "use_translation_scheduler": "true",
            "use_sqlite_session_repository": 1,
        })
        assert vm.effective_settings["use_translation_scheduler"] is True
        assert vm.effective_settings["use_sqlite_session_repository"] is True


# ── 10. recommended changes display-only ──────────────────────────
class TestRecommendedChanges:
    def test_not_applied(self):
        inp = {
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": True,
        }
        orig = dict(inp)
        build_settings_validation_viewmodel(inp)
        assert inp == orig  # unchanged


# ── 11. serializable ──────────────────────────────────────────────
class TestSerializable:
    def test_json(self):
        vm = build_settings_validation_viewmodel({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": True,
        })
        d = asdict(vm)
        j = json.dumps(d, default=str)
        assert len(j) > 0


# ── 12. no side effects ───────────────────────────────────────────
class TestNoSideEffects:
    def test_pure(self):
        build_settings_validation_viewmodel({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": False,
        })
        # no filesystem, no network, no crash
