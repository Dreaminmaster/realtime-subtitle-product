"""Tests for history dashboard HTML formatter."""
import pytest
from src.history_dashboard_formatter import format_history_viewmodel_html
from src.history_viewmodel import HistoryDashboardViewModel


# ── 1. unavailable formatting ──────────────────────────────────
class TestUnavailable:
    def test_formats_unavailable(self):
        vm = HistoryDashboardViewModel(
            available=False,
            title="Unavailable",
            summary="History is not available.",
            messages=["Repository not configured."],
        )
        html = format_history_viewmodel_html(vm)
        assert "Transcript History" in html
        assert "Unavailable" in html
        assert "Repository not configured" in html


# ── 2. sessions formatting ────────────────────────────────────
class TestSessions:
    def test_formats_sessions(self):
        from src.history_viewmodel import HistorySessionItem
        vm = HistoryDashboardViewModel(
            available=True,
            title="History",
            summary="3 sessions",
            sessions=[
                HistorySessionItem(session_id="s1", status="ACTIVE", created_at=1, updated_at=1, label="s1 (ACTIVE)"),
            ],
        )
        html = format_history_viewmodel_html(vm)
        assert "s1" in html
        assert "ACTIVE" in html


# ── 3. transcript formatting ──────────────────────────────────
class TestTranscripts:
    def test_formats_original_translated(self):
        vm = HistoryDashboardViewModel(
            available=True, title="H", summary="ok",
            original_text="hello world", translated_text="你好世界", bilingual_text="hello\n你好",
        )
        html = format_history_viewmodel_html(vm)
        assert "hello world" in html
        assert "你好世界" in html


# ── 4. messages escaped ───────────────────────────────────────
class TestMessageEscape:
    def test_script_escaped(self):
        vm = HistoryDashboardViewModel(
            available=False, title="X", summary="ok",
            messages=['<script>alert(1)</script>'],
        )
        html = format_history_viewmodel_html(vm)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ── 5. transcript escaped ─────────────────────────────────────
class TestTranscriptEscape:
    def test_html_in_transcript_escaped(self):
        vm = HistoryDashboardViewModel(
            available=True, title="H", summary="ok",
            original_text='hello <b>bold</b>',
        )
        html = format_history_viewmodel_html(vm)
        # The escaped text should be inside a <pre> block
        assert '&lt;b&gt;bold&lt;/b&gt;' in html
        # The raw <b> may appear in HTML labels — that's fine.
        # What matters: user text is escaped.


# ── 6. long transcript truncated ──────────────────────────────
class TestTruncation:
    def test_long_truncated(self):
        long_text = "x" * 2000
        vm = HistoryDashboardViewModel(
            available=True, title="H", summary="ok",
            original_text=long_text,
        )
        html = format_history_viewmodel_html(vm)
        assert "truncated" in html


# ── 7. export preview ─────────────────────────────────────────
class TestExportPreview:
    def test_shows_lengths(self):
        vm = HistoryDashboardViewModel(
            available=True, title="H", summary="ok",
            export_preview_txt="abc", export_preview_json='{"x":1}',
        )
        html = format_history_viewmodel_html(vm)
        assert "TXT length" in html
        assert "JSON length" in html


# ── 8. None fields safe ───────────────────────────────────────
class TestNoneFields:
    def test_all_empty(self):
        vm = HistoryDashboardViewModel(
            available=True, title="Empty", summary="Nothing here.",
        )
        html = format_history_viewmodel_html(vm)
        assert "Transcript History" in html
