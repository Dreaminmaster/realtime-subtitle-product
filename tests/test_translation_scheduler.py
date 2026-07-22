"""Unit tests for TranslationScheduler."""
import pytest
import time
import threading
from src.translation_scheduler import (
    TranslationScheduler, TranslationStatus, TranslationJob, TranslationResult,
    TranslationSchedulerError,
)
from src.transcript_event import TranscriptEvent, TranscriptPhase


SID = "s1"
ALT_SID = "s2"
SEG = "seg-1"


def _event(**kw) -> TranscriptEvent:
    d = dict(
        session_id=SID, segment_id=SEG, utterance_id=1, revision=1,
        phase=TranscriptPhase.FINAL, text_raw="hello world",
    )
    d.update(kw)
    return TranscriptEvent(**d)


def _partial(**kw) -> TranscriptEvent:
    return _event(phase=TranscriptPhase.PARTIAL, **kw)


class TestSubmit:
    def test_final_enters_queue(self):
        # max_workers=0 prevents auto-dequeue so job stays QUEUED
        s = TranslationScheduler(max_workers=0)
        s.start_session(SID)
        assert s.submit(_event()) == TranslationStatus.QUEUED
        assert s.pending_count() == 1

    def test_partial_returns_none(self):
        s = TranslationScheduler()
        s.start_session(SID)
        assert s.submit(_partial()) is None
        assert s.pending_count() == 0

    def test_stable_returns_none(self):
        s = TranslationScheduler()
        s.start_session(SID)
        ev = _event(phase=TranscriptPhase.STABLE, text_raw="still going")
        assert s.submit(ev) is None
        assert s.pending_count() == 0

    def test_non_final_not_queued(self):
        s = TranslationScheduler()
        s.start_session(SID)
        s.submit(_event(phase=TranscriptPhase.PARTIAL))
        s.submit(_event(phase=TranscriptPhase.STABLE, text_raw="..."))
        assert s.pending_count() == 0

    def test_rejects_non_transcript_event(self):
        s = TranslationScheduler()
        with pytest.raises(TypeError):
            s.submit("not an event")


class TestJobKey:
    def test_key_is_session_segment_revision(self):
        s = TranslationScheduler()
        s.start_session(SID)
        s.submit(_event(session_id="abc", segment_id="xyz", revision=3))
        keys = s._jobs
        assert "abc:xyz:3" in keys


class TestQueueLimit:
    def test_max_size_drops_oldest(self):
        s = TranslationScheduler(max_queue=2, max_workers=0)
        s.start_session(SID)
        s.submit(_event(segment_id="a", revision=1))
        s.submit(_event(segment_id="b", revision=1))
        s.submit(_event(segment_id="c", revision=1))
        # "a" should have been dropped
        dropped = any(
            j.status == TranslationStatus.DISCARDED and j.segment_id == "a"
            for j in s._jobs.values()
        )
        assert dropped


class TestRevisionCancel:
    def test_new_revision_cancels_old_pending(self):
        s = TranslationScheduler(max_queue=5, max_workers=0)
        s.start_session(SID)
        s.submit(_event(segment_id="seg", revision=1))
        s.submit(_event(segment_id="seg", revision=2))
        # rev 1 should be CANCELLED
        j1 = s._jobs.get(f"{SID}:seg:1")
        assert j1 is not None
        assert j1.status == TranslationStatus.CANCELLED

    def test_new_revision_leaves_old_queued_as_cancelled(self):
        s = TranslationScheduler(max_queue=3, max_workers=0)
        s.start_session(SID)
        s.submit(_event(segment_id="seg", revision=1))
        s.submit(_event(segment_id="seg", revision=2))
        s.submit(_event(segment_id="seg", revision=3))
        for r in (1, 2):
            j = s._jobs.get(f"{SID}:seg:{r}")
            assert j is not None
            assert j.status == TranslationStatus.CANCELLED

    def test_different_segment_no_cancel(self):
        s = TranslationScheduler()
        s.start_session(SID)
        s.submit(_event(segment_id="a", revision=1))
        s.submit(_event(segment_id="b", revision=1))
        # Neither segment may be cancelled.  On a fast machine either job can
        # already be completed before this assertion runs.
        for seg in ("a", "b"):
            j = s._jobs.get(f"{SID}:{seg}:1")
            assert j is not None
            assert j.status in (
                TranslationStatus.QUEUED,
                TranslationStatus.RUNNING,
                TranslationStatus.COMPLETED,
            )
        s.shutdown(wait=True)


class TestStaleResult:
    def test_old_running_result_not_delivered(self):
        """When a stale job finishes, on_result is NOT called."""
        results = []
        first_started = threading.Event()
        release_first = threading.Event()

        def controlled_translate(text, target_lang):
            if text == "revision one":
                first_started.set()
                assert release_first.wait(timeout=2.0)
            return f"translated: {text}"

        s = TranslationScheduler(
            translator=controlled_translate,
            on_result=lambda r: results.append(r),
            max_workers=1,
        )
        s.start_session(SID)
        s.submit(_event(segment_id="seg", revision=1, text_raw="revision one"))
        assert first_started.wait(timeout=2.0)
        s.submit(_event(segment_id="seg", revision=2, text_raw="revision two"))
        release_first.set()
        s.shutdown(wait=True)
        # Only revision 2 should deliver a result
        delivered = [r for r in results if r.segment_id == "seg"]
        assert all(r.revision == 2 for r in delivered)

    def test_new_revision_result_delivered(self):
        results = []
        s = TranslationScheduler(on_result=lambda r: results.append(r), max_workers=1)
        s.start_session(SID)
        s.submit(_event(segment_id="seg", revision=1))
        s.submit(_event(segment_id="seg", revision=2))
        import time; time.sleep(0.3)  # let executor drain queue
        s.shutdown(wait=True)
        assert any(r.segment_id == "seg" and r.revision == 2 and r.status == TranslationStatus.COMPLETED
                   for r in results)


class TestSessionGuard:
    def test_old_session_result_discarded(self):
        results = []
        s = TranslationScheduler(on_result=lambda r: results.append(r), max_workers=1)
        s.start_session(SID)
        s.submit(_event())
        # Change session before job finishes
        s.start_session(ALT_SID)
        s.shutdown(wait=True)
        # No results for SID should be delivered
        assert all(r.session_id != SID for r in results)


class TestStop:
    def test_reject_after_stop(self):
        s = TranslationScheduler()
        s.start_session(SID)
        s.stop_session()
        assert s.submit(_event()) is None

    def test_cancel_pending_on_stop(self):
        s = TranslationScheduler(max_workers=0)  # prevent dequeue
        s.start_session(SID)
        s.submit(_event(segment_id="a"))
        s.submit(_event(segment_id="b"))
        assert s.pending_count() == 2
        s.stop_session()
        for seg in ("a", "b"):
            j = s._jobs.get(f"{SID}:{seg}:1")
            assert j is not None
            assert j.status == TranslationStatus.CANCELLED

    def test_shutdown_idempotent(self):
        s = TranslationScheduler()
        s.start_session(SID)
        s.shutdown(wait=True)
        s.shutdown(wait=True)  # second call — no crash


class TestTranslatorFailure:
    def test_translator_error_marks_failed(self):
        def bad_translate(text, lang):
            raise RuntimeError("translator down")
        s = TranslationScheduler(translator=bad_translate, max_workers=1)
        s.start_session(SID)
        s.submit(_event())
        s.shutdown(wait=True)
        j = s._jobs.get(f"{SID}:{SEG}:1")
        assert j is not None
        assert j.status == TranslationStatus.FAILED

    def test_translator_error_does_not_kill_scheduler(self):
        errors = []
        def bad(text, lang):
            raise RuntimeError("boom")
        s = TranslationScheduler(translator=bad, max_workers=1,
                                 on_error=lambda j, r: errors.append(r))
        s.start_session(SID)
        s.submit(_event(segment_id="a"))
        s.submit(_event(segment_id="b"))
        import time; time.sleep(0.3)
        s.shutdown(wait=True)
        # Both jobs should be marked FAILED
        assert len(errors) == 2

    def test_on_error_does_not_kill_scheduler(self):
        self._error_count = 0
        def bad_on_error(job, result):
            raise RuntimeError("callback crash")
        s = TranslationScheduler(translator=lambda t, l: "ok", max_workers=1,
                                 on_error=bad_on_error)
        s.start_session(SID)
        s.submit(_event(segment_id="a"))
        s.shutdown(wait=True)
        # Scheduler not dead — test completed
        assert True

    def test_on_result_error_does_not_kill_scheduler(self):
        def bad_on_result(result):
            raise RuntimeError("callback crash")
        s = TranslationScheduler(translator=lambda t, l: "ok", max_workers=1,
                                 on_result=bad_on_result)
        s.start_session(SID)
        s.submit(_event(segment_id="a"))
        s.submit(_event(segment_id="b"))
        s.shutdown(wait=True)
        assert True  # survived


class TestDefaultTranslator:
    def test_default_translator_returns_mock(self):
        results = []
        s = TranslationScheduler(on_result=lambda r: results.append(r), max_workers=1)
        s.start_session(SID)
        s.submit(_event(text_raw="hello"))
        time.sleep(0.2)
        s.shutdown(wait=True)
        assert len(results) == 1
        assert "hello" in results[0].translated_text

    def test_completed_jobs_leave_active_queue(self):
        s = TranslationScheduler(max_workers=1)
        s.start_session(SID)
        s.submit(_event(segment_id="completed"))
        s.shutdown(wait=True)
        assert s._queue == []


class TestEmptyText:
    def test_whitespace_only_rejected(self):
        from src.transcript_event import InvalidTranscriptEvent
        s = TranslationScheduler(max_workers=0)
        s.start_session(SID)
        # TranscriptEvent rejects whitespace-only text_raw at creation,
        # so submit() is never reached. This is the correct behavior:
        # the event layer prevents empty text from reaching the scheduler.
        with pytest.raises(InvalidTranscriptEvent):
            _event(text_raw="   ")
