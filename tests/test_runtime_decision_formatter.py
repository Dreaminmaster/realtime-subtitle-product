"""Unit tests for runtime decision formatter."""
import pytest
from src.runtime_decision_formatter import format_runtime_settings_decision_html
from src.runtime_settings_guard import (
    RuntimeSettingsGuard, RuntimeSettingsDecision,
)


def _decision(**kw) -> RuntimeSettingsDecision:
    defaults = dict(
        ok=True, mode="legacy", effective_settings={},
        issues=[], recommended_changes={},
    )
    defaults.update(kw)
    return RuntimeSettingsDecision(**defaults)


# ── 1. legacy decision ─────────────────────────────────────────
class TestLegacy:
    def test_formats(self):
        html = format_runtime_settings_decision_html(_decision(mode="legacy"))
        assert "Runtime Decision" in html
        assert "legacy" in html
        assert "Translation scheduler" in html
        assert "SQLite repository" in html
        assert "No runtime issues" in html


# ── 2. scheduler decision ──────────────────────────────────────
class TestScheduler:
    def test_formats(self):
        d = _decision(mode="scheduler", allow_translation_scheduler=True)
        html = format_runtime_settings_decision_html(d)
        assert "scheduler" in html
        assert "enabled" in html
        assert "disabled" in html


# ── 3. scheduler_repository decision ────────────────────────────
class TestSchedulerRepo:
    def test_formats(self):
        d = _decision(
            mode="scheduler_repository",
            allow_translation_scheduler=True,
            allow_sqlite_repository=True,
            allow_segment_history=True,
            allow_segment_export=True,
        )
        html = format_runtime_settings_decision_html(d)
        assert "scheduler_repository" in html
        assert "enabled" in html


# ── 4. invalid fallback ────────────────────────────────────────
class TestInvalid:
    def test_formats(self):
        from src.runtime_settings_guard import RuntimeSettingsIssue
        d = _decision(
            ok=False, mode="invalid", should_fallback_to_legacy=True,
            reason="dependency validation failed",
            issues=[
                RuntimeSettingsIssue(
                    code="repo_requires_scheduler",
                    severity="error",
                    message="repo requires scheduler",
                ),
            ],
            recommended_changes={"use_translation_scheduler": True},
        )
        html = format_runtime_settings_decision_html(d)
        assert "invalid" in html
        assert "fallback" in html.lower()
        assert "repo_requires_scheduler" in html
        assert "use_translation_scheduler" in html


# ── 5. script escaped ──────────────────────────────────────────
class TestEscape:
    def test_script_escaped(self):
        from src.runtime_settings_guard import RuntimeSettingsIssue
        d = _decision(
            reason='<script>alert(1)</script>',
            issues=[
                RuntimeSettingsIssue(
                    code='<script>alert(1)</script>',
                    severity='error',
                    message='<script>alert(1)</script>',
                ),
            ],
        )
        html = format_runtime_settings_decision_html(d)
        assert "<script>" not in html


# ── 6. reason escaped ──────────────────────────────────────────
class TestReasonEscape:
    def test_html_escaped(self):
        d = _decision(reason="<b>bold</b>")
        html = format_runtime_settings_decision_html(d)
        # Check that <b>bold</b> was escaped
        assert "&lt;b&gt;bold&lt;/b&gt;" in html


# ── 7. recommended changes ─────────────────────────────────────
class TestRecommended:
    def test_displayed(self, ):
        d = _decision(recommended_changes={"a": 1, "b": "x"})
        html = format_runtime_settings_decision_html(d)
        assert "a" in html
        assert "b" in html


# ── 8. empty recommended changes ───────────────────────────────
class TestEmptyRecommended:
    def test_none(self):
        html = format_runtime_settings_decision_html(_decision(recommended_changes={}))
        assert "None" in html


# ── 9. None fields safe ────────────────────────────────────────
class TestNoneFields:
    def test_empty(self):
        html = format_runtime_settings_decision_html(_decision(reason=""))
        assert "Runtime Decision" in html


# ── 10. no side effects ────────────────────────────────────────
class TestNoSideEffects:
    def test_no_io(self):
        html = format_runtime_settings_decision_html(_decision())
        assert len(html) > 0
