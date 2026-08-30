"""Unit tests for SegmentAPI."""
import pytest
import json
import time
from src.segment_api import SegmentAPI, SessionView, SegmentView, TranscriptSnapshot
from src.session_repository import SQLiteSessionRepository, RepositoryError


@pytest.fixture
def repo():
    r = SQLiteSessionRepository(":memory:")
    r.initialize()
    return r


@pytest.fixture
def api(repo):
    return SegmentAPI(repo)


def _add_session(repo, sid, **kw):
    repo.create_session(sid, **kw)


def _add_segment(repo, sid, seg, rev, text, translated=None, translation_status="PENDING"):
    repo.upsert_original_segment(session_id=sid, segment_id=seg, revision=rev, status="FINAL", original_text=text)
    if translated and translation_status == "DONE":
        repo.apply_translation(session_id=sid, segment_id=seg, revision=rev, translated_text=translated)
    elif translated and translation_status == "FAILED":
        repo.mark_translation_failed(session_id=sid, segment_id=seg, revision=rev, error=translated)


# ── 1. list_sessions ──────────────────────────────────────────
class TestListSessions:
    def test_returns_session_views(self, repo, api):
        repo.create_session("s1")
        repo.create_session("s2")
        lst = api.list_sessions()
        assert len(lst) == 2
        assert all(isinstance(s, SessionView) for s in lst)


# ── 2. get_session ────────────────────────────────────────────
class TestGetSession:
    def test_returns_view(self, repo, api):
        repo.create_session("s1")
        s = api.get_session("s1")
        assert s is not None
        assert s.session_id == "s1"
        assert s.status == "ACTIVE"

    def test_missing_returns_none(self, api):
        assert api.get_session("missing") is None


# ── 3. missing session ────────────────────────────────────────
# (covered above)


# ── 4. list_segments ──────────────────────────────────────────
class TestListSegments:
    def test_returns_segment_views(self, repo, api):
        repo.create_session("s1")
        repo.upsert_original_segment(session_id="s1", segment_id="seg1", revision=1, status="FINAL", original_text="hello")
        segs = api.list_segments("s1")
        assert len(segs) == 1
        assert isinstance(segs[0], SegmentView)

    def test_exposes_recording_offsets(self, repo, api):
        repo.create_session("s1")
        repo.upsert_original_segment(
            session_id="s1", segment_id="seg1", revision=1,
            status="FINAL", original_text="hello",
            start_offset=0.75, end_offset=2.25,
        )
        segment = api.list_segments("s1")[0]
        assert segment.start_offset == pytest.approx(0.75)
        assert segment.end_offset == pytest.approx(2.25)


# ── 5. get_latest_segment ─────────────────────────────────────
class TestGetLatestSegment:
    def test_highest_revision_wins(self, repo, api):
        repo.create_session("s1")
        repo.upsert_original_segment(session_id="s1", segment_id="seg1", revision=1, status="FINAL", original_text="old")
        repo.upsert_original_segment(session_id="s1", segment_id="seg1", revision=2, status="FINAL", original_text="new")
        seg = api.get_latest_segment("s1", "seg1")
        assert seg.revision == 2
        assert seg.original_text == "new"


# ── 6. latest transcript ──────────────────────────────────────
class TestLatestTranscript:
    def test_uses_latest_revisions(self, repo, api):
        repo.create_session("s1")
        repo.upsert_original_segment(session_id="s1", segment_id="a", revision=1, status="FINAL", original_text="old")
        repo.upsert_original_segment(session_id="s1", segment_id="a", revision=2, status="FINAL", original_text="new")
        repo.upsert_original_segment(session_id="s1", segment_id="b", revision=1, status="FINAL", original_text="world")
        t = api.get_latest_transcript("s1")
        assert "new" in t
        assert "old" not in t


# ── 7. translated transcript ──────────────────────────────────
class TestTranslatedTranscript:
    def test_uses_done_translation(self, repo, api):
        repo.create_session("s1")
        _add_segment(repo, "s1", "a", 1, "hello", translated="你好", translation_status="DONE")
        _add_segment(repo, "s1", "b", 1, "world", translated="世界", translation_status="DONE")
        t = api.get_translated_transcript("s1")
        assert "你好" in t
        assert "世界" in t

    def test_fallback_missing(self, repo, api):
        repo.create_session("s1")
        _add_segment(repo, "s1", "a", 1, "hello")
        t = api.get_translated_transcript("s1")
        assert "hello" in t

    def test_fallback_failed(self, repo, api):
        repo.create_session("s1")
        _add_segment(repo, "s1", "a", 1, "hello", translated="FAIL", translation_status="FAILED")
        t = api.get_translated_transcript("s1")
        assert "hello" in t


# ── 10. bilingual snapshot ────────────────────────────────────
class TestSnapshot:
    def test_contains_all(self, repo, api):
        repo.create_session("s1")
        _add_segment(repo, "s1", "a", 1, "hello", translated="你好", translation_status="DONE")
        _add_segment(repo, "s1", "b", 1, "world", translated="世界", translation_status="DONE")
        snap = api.get_session_snapshot("s1")
        assert snap is not None
        assert "hello" in snap.original_text
        assert "world" in snap.original_text
        assert "你好" in snap.translated_text
        assert "世界" in snap.translated_text

    def test_failed_translation_in_bilingual(self, repo, api):
        repo.create_session("s1")
        _add_segment(repo, "s1", "a", 1, "hello", translated="FAIL", translation_status="FAILED")
        snap = api.get_session_snapshot("s1")
        assert "[translation failed]" in snap.bilingual_text


# ── 11-13. recover_last_session ───────────────────────────────
class TestRecover:
    def test_returns_active_first(self, repo, api):
        repo.create_session("s1"); repo.close_session("s1")
        repo.create_session("s2")  # active
        s = api.recover_last_session()
        assert s.session_id == "s2"

    def test_returns_latest_when_no_active(self, repo, api):
        repo.create_session("s1"); repo.close_session("s1")
        time.sleep(0.01)
        repo.create_session("s2"); repo.close_session("s2")
        s = api.recover_last_session()
        assert s is not None

    def test_returns_none_when_empty(self, api):
        assert api.recover_last_session() is None


# ── 14-16. export ─────────────────────────────────────────────
class TestExport:
    def test_txt_contains_session_and_text(self, repo, api):
        repo.create_session("s1")
        _add_segment(repo, "s1", "a", 1, "hello", "你好", "DONE")
        t = api.export_transcript("s1", format="txt")
        assert "s1" in t
        assert "hello" in t
        assert "你好" in t

    def test_json_parseable(self, repo, api):
        repo.create_session("s1")
        _add_segment(repo, "s1", "a", 1, "hello", "你好", "DONE")
        j = api.export_transcript("s1", format="json")
        d = json.loads(j)
        assert d["session"]["session_id"] == "s1"
        assert len(d["segments"]) == 1
        assert "你好" in d["bilingual_text"]

    def test_txt_follows_selected_display_mode(self, repo, api):
        repo.create_session("s1")
        _add_segment(repo, "s1", "a", 1, "hello", "你好", "DONE")
        original = api.export_transcript("s1", format="txt", display_mode="original_only")
        translated = api.export_transcript("s1", format="txt", display_mode="translation_only")
        assert "hello" in original and "你好" not in original
        assert "你好" in translated and "hello" not in translated

    def test_missing_session_raises(self, api):
        with pytest.raises(ValueError):
            api.export_transcript("missing")


# ── 17. invalid metadata ──────────────────────────────────────
class TestInvalidMetadata:
    def test_broken_json_safe(self, repo, api):
        repo.create_session("s1")
        conn = repo._conn
        conn.execute("UPDATE sessions SET metadata_json = ? WHERE session_id = ?", ("not json", "s1"))
        conn.commit()
        s = api.get_session("s1")
        assert s.metadata == {}


# ── 18. repo close safe ───────────────────────────────────────
class TestRepoCloseSafe:
    def test_after_close_raises(self, repo, api):
        repo.close()
        with pytest.raises(RepositoryError):
            api.list_sessions()


# ── 19. API read-only ─────────────────────────────────────────
class TestAPIIsReadOnly:
    def test_does_not_call_write_methods(self, repo):
        # Create a wrapping spy
        write_calls = []
        orig_upsert = repo.upsert_original_segment
        repo.upsert_original_segment = lambda **kw: (write_calls.append("upsert"), orig_upsert(**kw))[1]
        api = SegmentAPI(repo)
        repo.create_session("s1")
        orig_upsert(session_id="s1", segment_id="a", revision=1, status="FINAL", original_text="hello")
        api.list_sessions()
        api.get_session("s1")
        api.list_segments("s1")
        api.get_latest_segment("s1", "a")
        api.get_latest_transcript("s1")
        api.get_translated_transcript("s1")
        api.get_session_snapshot("s1")
        api.recover_last_session()
        # upsert was only called once (by the test setup), not by the API
        assert len(write_calls) == 0
