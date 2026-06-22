"""Unit tests for HistoryViewModelBuilder."""
import pytest
import json
from dataclasses import asdict
from src.history_viewmodel import (
    HistoryViewModelBuilder, HistoryDashboardViewModel,
    HistorySessionItem, HistorySegmentItem,
)


class FakeSnapshot:
    def __init__(self, sid, orig="hello", trans="你好", bil="hello\n你好"):
        self.session = FakeSessionView(sid)
        self.segments = [
            FakeSegmentView(sid, "seg1", 1, orig, trans, "DONE"),
        ]
        self.original_text = orig
        self.translated_text = trans
        self.bilingual_text = bil

class FakeSessionView:
    def __init__(self, sid): self.session_id = sid

class FakeSegmentView:
    def __init__(self, sid, seg, rev, orig, trans, tstat):
        self.session_id = sid
        self.segment_id = seg
        self.revision = rev
        self.original_text = orig
        self.translated_text = trans
        self.translation_status = tstat
        self.status = "FINAL"
        class Session: pass
        self.session = Session()


class FakeAPI:
    def __init__(self, sessions=None, snapshot=None, recover=None, raise_on=None):
        self._sessions = sessions or []
        self._snapshot = snapshot or {}
        self._recover = recover
        self._raise = raise_on or set()

    def list_sessions(self, limit=20):
        if "list_sessions" in self._raise:
            raise RuntimeError("boom")
        return self._sessions

    def get_session_snapshot(self, sid):
        if "snapshot" in self._raise:
            raise RuntimeError("snap fail")
        sn = self._snapshot.get(sid)
        if sn is None:
            raise ValueError("not found")
        return sn

    def recover_last_session(self):
        if "recover" in self._raise:
            raise RuntimeError("recover fail")
        return self._recover

    def export_transcript(self, sid, format="txt"):
        if "export" in self._raise:
            raise RuntimeError("export fail")
        return "TXT" if format == "txt" else '{}'


# ── 1. no segment api ─────────────────────────────────────────────
class TestNoAPI:
    def test_unavailable(self):
        b = HistoryViewModelBuilder(segment_api=None)
        vm = b.build()
        assert vm.available is False
        assert vm.sessions == []
        assert len(vm.messages) > 0


# ── 2. no sessions ────────────────────────────────────────────────
class TestNoSessions:
    def test_empty(self):
        api = FakeAPI(sessions=[])
        b = HistoryViewModelBuilder(api)
        vm = b.build()
        assert vm.available is True
        assert "No transcript sessions" in vm.summary
        assert vm.selected_session_id is None


# ── 3. recover selects session ────────────────────────────────────
class TestRecover:
    def test_recover_priority(self):
        api = FakeAPI(
            sessions=[
                {"session_id": "s1", "status": "CLOSED", "created_at": 1, "updated_at": 1},
                {"session_id": "s2", "status": "ACTIVE", "created_at": 2, "updated_at": 2},
            ],
            recover=FakeSessionView("s2"),
        )
        b = HistoryViewModelBuilder(api)
        vm = b.build()
        assert vm.selected_session_id == "s2"


# ── 4. fallback to first ─────────────────────────────────────────
class TestFallback:
    def test_first_when_no_recover(self):
        api = FakeAPI(
            sessions=[
                {"session_id": "s1", "status": "CLOSED", "created_at": 1, "updated_at": 1},
                {"session_id": "s2", "status": "CLOSED", "created_at": 2, "updated_at": 2},
            ],
            recover=None,
        )
        b = HistoryViewModelBuilder(api)
        vm = b.build()
        assert vm.selected_session_id == "s1"


# ── 5. snapshot shown ─────────────────────────────────────────────
class TestSnapshot:
    def test_filled(self):
        api = FakeAPI(
            sessions=[{"session_id": "s1", "status": "ACTIVE", "created_at": 1, "updated_at": 1}],
            snapshot={"s1": FakeSnapshot("s1")},
        )
        b = HistoryViewModelBuilder(api)
        vm = b.build()
        assert "hello" in vm.original_text
        assert "你好" in vm.translated_text


# ── 6. missing session safe ───────────────────────────────────────
class TestMissingSession:
    def test_no_crash(self):
        api = FakeAPI(
            sessions=[{"session_id": "s1", "status": "ACTIVE", "created_at": 1, "updated_at": 1}],
            snapshot={},
        )
        b = HistoryViewModelBuilder(api)
        vm = b.build()
        assert any("not found" in m.lower() for m in vm.messages)


# ── 7. export preview ─────────────────────────────────────────────
class TestExportPreview:
    def test_filled(self):
        api = FakeAPI(
            sessions=[{"session_id": "s1", "status": "ACTIVE", "created_at": 1, "updated_at": 1}],
            snapshot={"s1": FakeSnapshot("s1")},
        )
        b = HistoryViewModelBuilder(api)
        vm = b.build()
        assert vm.export_preview_txt == "TXT"
        assert vm.export_preview_json == "{}"


# ── 8. export error safe ──────────────────────────────────────────
class TestExportError:
    def test_no_crash(self):
        api = FakeAPI(
            sessions=[{"session_id": "s1", "status": "ACTIVE", "created_at": 1, "updated_at": 1}],
            snapshot={"s1": FakeSnapshot("s1")},
            raise_on={"export"},
        )
        b = HistoryViewModelBuilder(api)
        vm = b.build()
        assert any("export" in m.lower() for m in vm.messages)


# ── 9. repository error safe ──────────────────────────────────────
class TestRepoError:
    def test_list_fails_no_crash(self):
        api = FakeAPI(raise_on={"list_sessions"})
        b = HistoryViewModelBuilder(api)
        vm = b.build()
        assert vm.available is False
        assert len(vm.messages) > 0


# ── 10. serializable ──────────────────────────────────────────────
class TestSerializable:
    def test_json(self):
        api = FakeAPI(
            sessions=[{"session_id": "s1", "status": "ACTIVE", "created_at": 1, "updated_at": 1}],
            snapshot={"s1": FakeSnapshot("s1")},
        )
        vm = HistoryViewModelBuilder(api).build()
        d = asdict(vm)
        j = json.dumps(d, default=str)
        assert len(j) > 0


# ── 11. read-only ─────────────────────────────────────────────────
class TestReadOnly:
    def test_no_write_calls(self):
        call_log = []
        class TrackingAPI(FakeAPI):
            def create_session(self, *a, **kw): call_log.append("write")
            def upsert_original_segment(self, *a, **kw): call_log.append("write")
            def apply_translation(self, *a, **kw): call_log.append("write")

        api = TrackingAPI(
            sessions=[{"session_id": "s1", "status": "ACTIVE", "created_at": 1, "updated_at": 1}],
            snapshot={"s1": FakeSnapshot("s1")},
        )
        HistoryViewModelBuilder(api).build()
        assert len(call_log) == 0


# ── 12. no side effects ───────────────────────────────────────────
class TestNoSideEffects:
    def test_pure(self):
        api = FakeAPI(
            sessions=[{"session_id": "s1", "status": "ACTIVE", "created_at": 1, "updated_at": 1}],
            snapshot={"s1": FakeSnapshot("s1")},
        )
        HistoryViewModelBuilder(api).build()
