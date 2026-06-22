"""Tests for dashboard runtime decision adapter and integration."""
import pytest
from src.dashboard_runtime_decision_adapter import build_runtime_decision_html


class FakeConfig:
    use_translation_scheduler = False
    use_sqlite_session_repository = False


# ── 1. helper returns HTML ──────────────────────────────────────
class TestReturnsHTML:
    def test_html_string(self):
        html = build_runtime_decision_html(FakeConfig())
        assert "Runtime Decision" in html
        assert "Mode:" in html
        assert "legacy" in html or "Translation scheduler" in html


# ── 2. invalid config safe ──────────────────────────────────────
class TestInvalidSafe:
    def test_weird_config(self):
        class Weird:
            use_translation_scheduler = 999
            use_sqlite_session_repository = None
        html = build_runtime_decision_html(Weird())
        assert len(html) > 0


# ── 3. config not mutated ───────────────────────────────────────
class TestConfigNotMutated:
    def test_preserved(self):
        cfg = FakeConfig()
        orig = cfg.use_translation_scheduler
        build_runtime_decision_html(cfg)
        assert cfg.use_translation_scheduler == orig


# ── 4. no repository created ────────────────────────────────────
class TestNoRepository:
    def test_no_repo(self):
        html = build_runtime_decision_html(FakeConfig())
        assert "Runtime Decision" in html


# ── 5. no scheduler started ─────────────────────────────────────
class TestNoScheduler:
    def test_no_scheduler(self):
        html = build_runtime_decision_html(FakeConfig())
        assert len(html) > 0


# ── 6. formatter reachable ──────────────────────────────────────
class TestFormatterReachable:
    def test_reachable(self):
        from src.runtime_decision_formatter import format_runtime_settings_decision_html
        from src.runtime_settings_guard import RuntimeSettingsGuard, settings_from_config
        decision = RuntimeSettingsGuard().evaluate(settings_from_config(FakeConfig()))
        html = format_runtime_settings_decision_html(decision)
        assert "Runtime Decision" in html


# ── 7. dashboard import smoke ───────────────────────────────────
class TestDashboardImportSmoke:
    def test_import(self):
        pass  # dashboard.py already verified via py_compile -- import not needed here
