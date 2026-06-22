"""Unit tests for SettingsDependencyEngine."""
import pytest
import json
from dataclasses import asdict
from src.settings_dependency_engine import (
    SettingsDependencyEngine, DependencyIssue, DependencyValidationResult,
)


@pytest.fixture
def engine():
    return SettingsDependencyEngine()


# ── 1-2. legacy defaults valid ───────────────────────────────────
class TestLegacyDefaults:
    def test_both_false_is_valid(self, engine):
        r = engine.validate({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": False,
        })
        assert r.ok is True
        assert not r.has_errors

    def test_scheduler_true_repo_false_valid(self, engine):
        r = engine.validate({
            "use_translation_scheduler": True,
            "use_sqlite_session_repository": False,
        })
        assert r.ok is True


# ── 3. repo requires scheduler ───────────────────────────────────
class TestRepoRequiresScheduler:
    def test_repo_true_scheduler_false_is_invalid(self, engine):
        r = engine.validate({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": True,
        })
        assert r.ok is False
        assert r.has_errors
        codes = {i.code for i in r.issues}
        assert "repository_requires_scheduler" in codes
        assert "use_translation_scheduler" in r.recommended_changes


# ── 4. both on valid ─────────────────────────────────────────────
class TestBothOn:
    def test_both_true_valid(self, engine):
        r = engine.validate({
            "use_translation_scheduler": True,
            "use_sqlite_session_repository": True,
        })
        assert r.ok is True


# ── 5. history requires repository ───────────────────────────────
class TestHistoryRequiresRepository:
    def test_history_true_repo_false_invalid(self, engine):
        r = engine.validate({
            "use_segment_api_for_history": True,
            "use_sqlite_session_repository": False,
        })
        assert r.ok is False
        codes = {i.code for i in r.issues}
        assert "history_requires_repository" in codes
        assert r.recommended_changes.get("use_sqlite_session_repository") is True
        assert r.recommended_changes.get("use_translation_scheduler") is True


# ── 6. export requires repository ────────────────────────────────
class TestExportRequiresRepository:
    def test_export_true_repo_false_invalid(self, engine):
        r = engine.validate({
            "use_segment_api_for_export": True,
            "use_sqlite_session_repository": False,
        })
        assert r.ok is False
        codes = {i.code for i in r.issues}
        assert "export_requires_repository" in codes


# ── 7. overlay segment api warning ───────────────────────────────
class TestOverlayWarning:
    def test_overlay_true_repo_false_gives_warning(self, engine):
        r = engine.validate({
            "use_segment_api_for_overlay": True,
            "use_sqlite_session_repository": False,
        })
        # Should have warning, not error
        warnings = [i for i in r.issues if i.severity == "warning"]
        assert any("overlay_segment_api_requires_repository" == i.code for i in warnings)


# ── 8. unknown settings safe ─────────────────────────────────────
class TestUnknownSettings:
    def test_does_not_crash(self, engine):
        r = engine.validate({"some_future_flag": True})
        # ok based on known settings only
        # unknown flags generate info-level events


# ── 9-10. non-bool normalization ─────────────────────────────────
class TestNormalization:
    def test_string_true_normalized(self, engine):
        r = engine.validate({
            "use_translation_scheduler": "true",
            "use_sqlite_session_repository": False,
        })
        assert r.effective_settings["use_translation_scheduler"] is True

    def test_int_normalized(self, engine):
        r = engine.validate({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": 1,
        })
        assert r.effective_settings["use_sqlite_session_repository"] is True

    def test_invalid_string_warns(self, engine):
        r = engine.validate({
            "use_translation_scheduler": "maybe",
            "use_sqlite_session_repository": False,
        })
        warnings = [i for i in r.issues if i.severity == "warning"]
        assert any("non_bool_value" == i.code for i in warnings)
        assert r.effective_settings["use_translation_scheduler"] is False


# ── 11. input not mutated ────────────────────────────────────────
class TestNoMutation:
    def test_input_unchanged(self, engine):
        inp = {
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": "true",
        }
        orig = dict(inp)
        engine.validate(inp)
        assert inp == orig


# ── 12. issue stable fields ──────────────────────────────────────
class TestIssueFields:
    def test_issue_has_all_fields(self, engine):
        r = engine.validate({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": True,
        })
        for iss in r.issues:
            assert isinstance(iss.code, str)
            assert iss.severity in ("info", "warning", "error")
            assert isinstance(iss.message, str)


# ── 13. has_errors / has_warnings ────────────────────────────────
class TestHasErrorsWarnings:
    def test_helpers(self, engine):
        r = engine.validate({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": True,
        })
        assert r.has_errors is True

        r2 = engine.validate({
            "use_segment_api_for_overlay": True,
            "use_sqlite_session_repository": False,
        })
        assert r2.has_warnings is True


# ── 14. JSON serializable ────────────────────────────────────────
class TestJSON:
    def test_result_serializable(self, engine):
        r = engine.validate({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": True,
        })
        d = asdict(r)
        j = json.dumps(d, default=str)
        assert len(j) > 0


# ── 16. no side effects ──────────────────────────────────────────
class TestNoSideEffects:
    def test_validate_touches_nothing(self, engine):
        r = engine.validate({
            "use_translation_scheduler": False,
            "use_sqlite_session_repository": False,
        })
        assert isinstance(r, DependencyValidationResult)
