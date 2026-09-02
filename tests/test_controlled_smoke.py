"""Unit tests for controlled smoke test."""
import pytest
import json
import os
import sys
import tempfile
from pathlib import Path
from dataclasses import asdict
from src.controlled_smoke import run_controlled_smoke, SmokeResult
from unittest.mock import patch, MagicMock


class FakeConfig:
    use_translation_scheduler = False
    use_sqlite_session_repository = False


# ── 1. flag off does not run full smoke ─────────────────────────
class TestFlagOff:
    def test_config_snapshot_ok(self, tmp_path):
        cfg = FakeConfig()
        result = run_controlled_smoke(config=cfg, tmpdir=tmp_path)
        assert result.ok is True
        # With flags off, smoke still runs the isolated pipeline —
        # it doesn't read real user data, just builds isolated repo
        assert result.default_config_changed is False


# ── 2. isolated temp dir ────────────────────────────────────────
class TestIsolated:
    def test_uses_tmpdir(self, tmp_path):
        result = run_controlled_smoke(config=FakeConfig(), tmpdir=tmp_path)
        assert Path(result.repo_path).is_relative_to(tmp_path)


# ── 3. creates session ──────────────────────────────────────────
class TestSession:
    def test_session_created(self, tmp_path):
        result = run_controlled_smoke(config=FakeConfig(), tmpdir=tmp_path)
        assert len(result.session_id) == 36
        assert result.ok is True


# ── 4-6. transcripts ────────────────────────────────────────────
class TestTranscripts:
    def test_generated(self, tmp_path):
        result = run_controlled_smoke(config=FakeConfig(), tmpdir=tmp_path)
        assert result.ok is True
        assert len(result.original_text) > 0
        assert len(result.translated_text) > 0
        assert len(result.bilingual_text) > 0


# ── 7. segments ─────────────────────────────────────────────────
class TestSegments:
    def test_count(self, tmp_path):
        result = run_controlled_smoke(config=FakeConfig(), tmpdir=tmp_path)
        assert result.segment_count == 3


# ── 8. repo write + close ───────────────────────────────────────
class TestRepoClose:
    def test_closed(self, tmp_path):
        result = run_controlled_smoke(config=FakeConfig(), tmpdir=tmp_path)
        assert result.repo_closed is True


# ── 9. dashboard adapter reads result ───────────────────────────
class TestDashboardRead:
    def test_can_read(self, tmp_path):
        result = run_controlled_smoke(config=FakeConfig(), tmpdir=tmp_path)
        # Verify the dashboard adapter step passed
        steps = {s["step"]: s for s in result.steps}
        assert steps["dashboard_adapter"]["ok"] is True


# ── 11. structured error ────────────────────────────────────────
class TestErrorHandling:
    def test_bad_repo_path_fails_gracefully(self, tmp_path):
        blocker = tmp_path / "not-a-directory"
        blocker.write_text("blocked", encoding="utf-8")
        result = run_controlled_smoke(config=FakeConfig(), tmpdir=blocker / "child")
        assert result.ok is False
        assert len(result.errors) > 0


# ── 12-14. default config + runtime untouched ───────────────────
class TestDefaultUntouched:
    def test_default_config_unchanged(self, tmp_path):
        result = run_controlled_smoke(config=FakeConfig(), tmpdir=tmp_path)
        assert result.default_config_changed is False
        assert result.default_runtime_touched is False

    def test_no_real_user_path(self, tmp_path):
        result = run_controlled_smoke(config=FakeConfig(), tmpdir=tmp_path)
        assert "/Application Support/RealtimeSubtitle" not in str(result.repo_path)


# ── 15. serializable ────────────────────────────────────────────
class TestSerializable:
    def test_json(self, tmp_path):
        result = run_controlled_smoke(config=FakeConfig(), tmpdir=tmp_path)
        d = asdict(result)
        j = json.dumps(d, default=str)
        assert len(j) > 0
