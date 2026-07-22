"""Unit tests for SQLiteSessionRepository."""
import pytest
import time
import json
import os
import tempfile
from pathlib import Path
from src.session_repository import SQLiteSessionRepository, RepositoryError


@pytest.fixture
def repo():
    r = SQLiteSessionRepository(":memory:")
    r.initialize()
    yield r
    r.close()


@pytest.fixture
def tmp_repo():
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    r = SQLiteSessionRepository(path)
    r.initialize()
    yield r
    r.close()
    if os.path.exists(path):
        os.unlink(path)


# ── 1. initialize creates schema ───────────────────────────────────
class TestInitialize:
    def test_schema_created(self, repo):
        conn = repo._conn
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {r[0] for r in tables}
        assert "sessions" in names
        assert "segments" in names

    def test_indexes_created(self, repo):
        conn = repo._conn
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        ).fetchall()
        names = {r[0] for r in indexes}
        assert "idx_segments_session_updated" in names
        assert "idx_segments_session_segment" in names

    def test_initialize_idempotent(self, repo):
        repo.initialize()  # second call — no crash


# ── 2. create/get session ──────────────────────────────────────────
class TestSessionCRUD:
    def test_create_and_get(self, repo):
        repo.create_session("s1")
        s = repo.get_session("s1")
        assert s is not None
        assert s["session_id"] == "s1"
        assert s["status"] == "ACTIVE"
        assert s["created_at"] > 0
        assert s["updated_at"] > 0

    def test_create_idempotent(self, repo):
        repo.create_session("s1")
        repo.create_session("s1")  # no crash
        s = repo.get_session("s1")
        assert s is not None
        assert s["status"] == "ACTIVE"

    def test_list_sessions(self, repo):
        for sid in ("a", "b", "c"):
            repo.create_session(sid)
        lst = repo.list_sessions(limit=2)
        assert len(lst) == 2

    def test_close_session(self, repo):
        repo.create_session("s1")
        repo.close_session("s1")
        s = repo.get_session("s1")
        assert s["status"] == "CLOSED"
        assert s["closed_at"] is not None

    def test_delete_and_clear_sessions(self, repo):
        for sid in ("one", "two"):
            repo.create_session(sid)
            repo.upsert_original_segment(
                session_id=sid, segment_id="seg", revision=1,
                status="FINAL", original_text=sid,
            )
        assert repo.delete_session("one") is True
        assert repo.get_session("one") is None
        assert repo.list_segments(session_id="one") == []
        assert repo.clear_sessions() == 1
        assert repo.list_sessions() == []

    def test_close_session_idempotent(self, repo):
        repo.create_session("s1")
        repo.close_session("s1")
        repo.close_session("s1")  # no crash


# ── 5. upsert original segment ─────────────────────────────────────
class TestUpsertOriginal:
    def test_upsert_and_get(self, repo):
        repo.create_session("s1")
        repo.upsert_original_segment(
            session_id="s1", segment_id="seg1", revision=1,
            status="FINAL", original_text="hello",
        )
        seg = repo.get_latest_segment(session_id="s1", segment_id="seg1")
        assert seg is not None
        assert seg["original_text"] == "hello"
        assert seg["revision"] == 1

    def test_newer_revision_becomes_latest(self, repo):
        repo.create_session("s1")
        repo.upsert_original_segment(
            session_id="s1", segment_id="seg1", revision=1,
            status="FINAL", original_text="rev1",
        )
        repo.upsert_original_segment(
            session_id="s1", segment_id="seg1", revision=2,
            status="FINAL", original_text="rev2",
        )
        seg = repo.get_latest_segment(session_id="s1", segment_id="seg1")
        assert seg["revision"] == 2
        assert seg["original_text"] == "rev2"


# ── 7-8. apply translation ─────────────────────────────────────────
class TestApplyTranslation:
    def test_apply_to_latest(self, repo):
        repo.create_session("s1")
        repo.upsert_original_segment(
            session_id="s1", segment_id="seg1", revision=1,
            status="FINAL", original_text="hello",
        )
        ok = repo.apply_translation(
            session_id="s1", segment_id="seg1", revision=1,
            translated_text="你好",
        )
        assert ok is True
        seg = repo.get_latest_segment(session_id="s1", segment_id="seg1")
        assert seg["translated_text"] == "你好"
        assert seg["translation_status"] == "DONE"

    def test_stale_revision_rejected(self, repo):
        repo.create_session("s1")
        repo.upsert_original_segment(
            session_id="s1", segment_id="seg1", revision=1,
            status="FINAL", original_text="old",
        )
        repo.upsert_original_segment(
            session_id="s1", segment_id="seg1", revision=2,
            status="FINAL", original_text="new",
        )
        # Apply translation to latest
        repo.apply_translation(
            session_id="s1", segment_id="seg1", revision=2,
            translated_text="new trans",
        )
        # Try to apply to stale revision
        ok = repo.apply_translation(
            session_id="s1", segment_id="seg1", revision=1,
            translated_text="old trans",
        )
        assert ok is False
        seg = repo.get_latest_segment(session_id="s1", segment_id="seg1")
        assert seg["translated_text"] == "new trans"
        assert seg["revision"] == 2

    def test_missing_segment_rejected(self, repo):
        repo.create_session("s1")
        ok = repo.apply_translation(
            session_id="s1", segment_id="missing", revision=1,
            translated_text="x",
        )
        assert ok is False

    def test_mark_translation_failed(self, repo):
        repo.create_session("s1")
        repo.upsert_original_segment(
            session_id="s1", segment_id="seg1", revision=1,
            status="FINAL", original_text="fail me",
        )
        ok = repo.mark_translation_failed(
            session_id="s1", segment_id="seg1", revision=1,
            error="timeout",
        )
        assert ok is True
        seg = repo.get_latest_segment(session_id="s1", segment_id="seg1")
        assert seg["translation_status"] == "FAILED"
        assert seg["translated_text"] == "timeout"

    def test_mark_failed_stale_revision(self, repo):
        repo.create_session("s1")
        repo.upsert_original_segment(session_id="s1", segment_id="seg1", revision=1, status="FINAL", original_text="rev1")
        repo.upsert_original_segment(session_id="s1", segment_id="seg1", revision=2, status="FINAL", original_text="rev2")
        ok = repo.mark_translation_failed(session_id="s1", segment_id="seg1", revision=1)
        assert ok is False


# ── 10. list segments ──────────────────────────────────────────────
class TestListSegments:
    def test_list_returns_ordered(self, repo):
        repo.create_session("s1")
        repo.upsert_original_segment(session_id="s1", segment_id="a", revision=1, status="FINAL", original_text="a1")
        time.sleep(0.01)
        repo.upsert_original_segment(session_id="s1", segment_id="b", revision=1, status="FINAL", original_text="b1")
        segs = repo.list_segments(session_id="s1")
        assert len(segs) == 2
        # Most recently updated first
        assert segs[0]["updated_at"] >= segs[1]["updated_at"]


# ── 11. persistence across reopen ──────────────────────────────────
class TestPersistence:
    def test_data_survives_reopen(self, tmp_repo):
        tmp_repo.create_session("s1")
        tmp_repo.upsert_original_segment(
            session_id="s1", segment_id="seg1", revision=1,
            status="FINAL", original_text="persist",
        )
        tmp_repo.apply_translation(
            session_id="s1", segment_id="seg1", revision=1,
            translated_text="持久化",
        )
        tmp_repo.close()

        path = tmp_repo._db_path
        r2 = SQLiteSessionRepository(path)
        r2.initialize()
        s = r2.get_session("s1")
        assert s is not None
        assert s["status"] == "ACTIVE"
        seg = r2.get_latest_segment(session_id="s1", segment_id="seg1")
        assert seg is not None
        assert seg["original_text"] == "persist"
        assert seg["translated_text"] == "持久化"
        r2.close()


# ── 12. close idempotent ───────────────────────────────────────────
class TestClose:
    def test_close_idempotent(self, repo):
        repo.close()
        repo.close()
        repo.close()

    def test_operation_after_close_raises(self, repo):
        repo.close()
        with pytest.raises(RepositoryError, match="closed"):
            repo.create_session("s2")


# ── 14. in-memory works ────────────────────────────────────────────
class TestInMemory:
    def test_basic_operations(self):
        r = SQLiteSessionRepository(":memory:")
        r.initialize()
        r.create_session("m1")
        r.upsert_original_segment(
            session_id="m1", segment_id="seg1", revision=1,
            status="FINAL", original_text="mem",
        )
        seg = r.get_latest_segment(session_id="m1", segment_id="seg1")
        assert seg["original_text"] == "mem"
        r.close()


# ── 15. metadata roundtrip ─────────────────────────────────────────
class TestMetadata:
    def test_metadata_roundtrip(self, repo):
        repo.create_session("s1", metadata={"model": "small", "mode": "test"})
        s = repo.get_session("s1")
        assert s["metadata"] == {"model": "small", "mode": "test"}
