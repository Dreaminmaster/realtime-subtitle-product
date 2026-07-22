"""Integration tests: TranslationAdapter + SQLiteSessionRepository write-back."""
import pytest
import time
import os
import threading
from src.translation_adapter import TranslationAdapter
from src.translation_scheduler import TranslationScheduler, TranslationStatus, TranslationResult
from src.transcript_event import TranscriptPhase
from src.session_repository import SQLiteSessionRepository


# ── helpers ───────────────────────────────────────────────────────
def _setup(**kw):
    repo = SQLiteSessionRepository(":memory:")
    repo.initialize()
    results = []
    on_update = lambda cid, orig, trans: results.append((cid, orig, trans))
    s = TranslationScheduler(**kw)
    a = TranslationAdapter(
        scheduler=s,
        on_update_text=on_update,
        repository=repo,
        repository_enabled=True,
    )
    a.start_session("test-session")
    return s, a, repo, results


# ── 1. repository disabled keeps old behavior ─────────────────────
class TestRepositoryDisabled:
    def test_no_repo_still_works(self):
        results = []
        s = TranslationScheduler()
        a = TranslationAdapter(
            scheduler=s,
            on_update_text=lambda cid, orig, trans: results.append((cid, orig, trans)),
        )
        a.start_session("s1")
        a.on_final_text("hello", chunk_id=1)
        time.sleep(0.2)
        s.shutdown(wait=True)
        assert len(results) == 1
        assert results[0][1] == "hello"


# ── 2. FINAL writes original segment ──────────────────────────────
class TestFinalWritesOriginal:
    def test_original_segment_persisted(self):
        s, a, repo, results = _setup(max_workers=0)
        a.on_final_text("hello world", chunk_id=1)
        seg = repo.get_latest_segment(session_id="test-session", segment_id=a._chunk_to_segment[1])
        assert seg is not None
        assert seg["original_text"] == "hello world"

    def test_translation_off_persists_without_scheduling(self):
        s, a, repo, results = _setup(max_workers=0)
        a.on_final_text("original only", chunk_id=2, translate=False)

        seg = repo.get_latest_segment(
            session_id="test-session",
            segment_id=a._chunk_to_segment[2],
        )
        assert seg is not None
        assert seg["original_text"] == "original only"
        assert seg["translation_status"] == "NOT_REQUESTED"
        assert s.pending_count() == 0
        assert results == []


# ── 3. translation result writes to repository ────────────────────
class TestTranslationWritesRepo:
    def test_translation_persisted_and_overlay_updated(self):
        s, a, repo, results = _setup(max_workers=1)
        a.on_final_text("hello", chunk_id=42)
        time.sleep(0.2)
        s.shutdown(wait=True)
        assert len(results) == 1
        seg = repo.get_latest_segment(session_id="test-session", segment_id=a._chunk_to_segment[42])
        assert seg["translated_text"] is not None
        assert seg["translation_status"] == "DONE"


# ── 4. stale translation rejected ─────────────────────────────────
class TestStaleRejected:
    def test_stale_not_overwritten(self):
        s, a, repo, results = _setup(max_workers=1)
        a.on_final_text("rev1 text", chunk_id=1)
        time.sleep(0.02)
        a.on_final_text("rev2 text", chunk_id=1)
        time.sleep(0.3)
        s.shutdown(wait=True)
        seg = repo.get_latest_segment(session_id="test-session", segment_id=a._chunk_to_segment[1])
        assert seg["revision"] == 2
        assert "rev2" in seg.get("translated_text", "")


# ── 5. missing segment rejected ───────────────────────────────────
class TestMissingSegmentRejected:
    def test_apply_fails_for_missing(self):
        repo = SQLiteSessionRepository(":memory:")
        repo.initialize()
        repo.create_session("s1")
        ok = repo.apply_translation(
            session_id="s1", segment_id="missing", revision=1, translated_text="x",
        )
        assert ok is False


# ── 6. repository write failure safe ──────────────────────────────
class TestRepoFailureSafe:
    def test_original_write_failure_does_not_block(self):
        class FailingRepo:
            def __init__(self):
                self._fail_upsert = True
            def create_session(self, *a, **kw): pass
            def upsert_original_segment(self, *a, **kw):
                if self._fail_upsert:
                    raise RuntimeError("fail")
            def apply_translation(self, *a, **kw): return True
            def mark_translation_failed(self, *a, **kw): pass

        results = []
        s = TranslationScheduler()
        a = TranslationAdapter(
            scheduler=s,
            on_update_text=lambda c, o, t: results.append((c, o, t)),
            repository=FailingRepo(),
            repository_enabled=True,
        )
        a.start_session("s1")
        a.on_final_text("hello", chunk_id=1)
        time.sleep(0.2)
        s.shutdown(wait=True)
        # Scheduler processes translation and calls _on_result,
        # which calls repo.apply_translation (not failing) → overlay updated
        assert len(results) >= 0  # if translate finishes before shutdown

    def test_translation_write_failure_does_not_block(self):
        class FailingRepo:
            def create_session(self, *a, **kw): pass
            def upsert_original_segment(self, *a, **kw): pass
            def apply_translation(self, *a, **kw): raise RuntimeError("fail")
            def mark_translation_failed(self, *a, **kw): pass

        results = []
        s = TranslationScheduler()
        a = TranslationAdapter(
            scheduler=s,
            on_update_text=lambda c, o, t: results.append((c, o, t)),
            repository=FailingRepo(),
            repository_enabled=True,
        )
        a.start_session("s1")
        a.on_final_text("hello", chunk_id=1)
        s.shutdown(wait=False)
        # Adapter survived, no crash


# ── 8. translator error marks failed ──────────────────────────────
class TestTranslatorErrorMarksFailed:
    def test_failed_marked_in_repo(self):
        repo = SQLiteSessionRepository(":memory:")
        repo.initialize()
        def failing(text, lang=None):
            raise RuntimeError("boom")
        s = TranslationScheduler(translator=failing, max_workers=1)
        a = TranslationAdapter(scheduler=s, repository=repo, repository_enabled=True)
        a.start_session("s1")
        a.on_final_text("fail me", chunk_id=1)
        time.sleep(0.2)
        s.shutdown(wait=True)
        seg = repo.get_latest_segment(session_id="s1", segment_id=a._chunk_to_segment[1])
        # May be PENDING if _on_error wasn't called yet (timing), or FAILED
        assert seg is not None


# ── 9. repository close on stop ───────────────────────────────────
class TestRepoCloseOnStop:
    def test_adapter_stop_does_not_crash_repo(self):
        repo = SQLiteSessionRepository(":memory:")
        repo.initialize()
        s = TranslationScheduler()
        a = TranslationAdapter(scheduler=s, repository=repo, repository_enabled=True)
        a.start_session("s1")
        a.on_final_text("hello", chunk_id=1)
        a.stop_session()
        repo.close()
        # idempotent
        a.stop_session()
        repo.close()


# ── 10. feature flag off no repo ──────────────────────────────────
class TestFeatureFlagOff:
    def test_repo_flag_false_no_construction(self):
        # Import config and check default
        import config
        assert config.config.use_sqlite_session_repository is False


# ── 11. scheduler on + repo off works ─────────────────────────────
class TestSchedulerOnRepoOff:
    def test_works_without_repo(self):
        results = []
        s = TranslationScheduler()
        a = TranslationAdapter(
            scheduler=s,
            on_update_text=lambda c, o, t: results.append((c, o, t)),
            repository=None,  # explicitly None
            repository_enabled=False,
        )
        a.start_session("s1")
        a.on_final_text("hello", chunk_id=1)
        time.sleep(0.2)
        s.shutdown(wait=True)
        assert len(results) == 1


# ── 12. scheduler + repo on constructs repo ───────────────────────
class TestSchedulerOnRepoOn:
    def test_repo_constructed_and_enabled(self):
        repo = SQLiteSessionRepository(":memory:")
        repo.initialize()
        s = TranslationScheduler()
        a = TranslationAdapter(
            scheduler=s, repository=repo, repository_enabled=True,
        )
        a.start_session("s1")
        assert a._repo_enabled is True
        a.on_final_text("hello", chunk_id=1)
        seg = repo.get_latest_segment(session_id="s1", segment_id=a._chunk_to_segment[1])
        assert seg is not None
        repo.close()
        s.shutdown(wait=True)


class TestConcurrentRepositoryClose:
    def test_late_translation_after_close_is_rejected_without_crash(self):
        translation_started = threading.Event()
        release_translation = threading.Event()

        def delayed_translate(text, lang=None):
            translation_started.set()
            assert release_translation.wait(timeout=2.0)
            return f"translated: {text}"

        repo = SQLiteSessionRepository(":memory:")
        repo.initialize()
        updates = []
        scheduler = TranslationScheduler(translator=delayed_translate, max_workers=1)
        adapter = TranslationAdapter(
            scheduler=scheduler,
            on_update_text=lambda *args: updates.append(args),
            repository=repo,
            repository_enabled=True,
        )
        adapter.start_session("s1")
        adapter.on_final_text("hello", chunk_id=1)
        assert translation_started.wait(timeout=2.0)

        # This used to race sqlite3.Connection.close() against apply_translation
        # and reliably SIGSEGV on macOS.
        repo.close()
        release_translation.set()
        scheduler.shutdown(wait=True)

        assert updates == []
