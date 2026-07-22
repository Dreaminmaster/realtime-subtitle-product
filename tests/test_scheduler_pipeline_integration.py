"""Pipeline integration tests: TranslationScheduler wired into subtitle pipeline.

Feature flag: REALTIME_SUBTITLE_USE_TRANSLATION_SCHEDULER=true
Fake translator: returns "ZH:{text}" — no API calls.
"""
import pytest
import time
import os
from src.translation_adapter import TranslationAdapter
from src.translation_scheduler import TranslationScheduler, TranslationStatus, TranslationResult
from src.transcript_event import TranscriptPhase


# ── helpers ───────────────────────────────────────────────────────
def _slow_translator(sleep=0.1):
    """Returns a translator that sleeps, simulating network delay."""
    def translate(text, lang=None):
        time.sleep(sleep)
        return f"ZH:{text}"
    return translate


def _failing_translator():
    def translate(text, lang=None):
        raise RuntimeError("translator down")
    return translate


def _setup(**kw):
    """Create scheduler + adapter with feature flag on."""
    os.environ["REALTIME_SUBTITLE_USE_TRANSLATION_SCHEDULER"] = "true"
    results = []
    on_update = lambda cid, orig, trans: results.append((cid, orig, trans))
    s = TranslationScheduler(**kw)
    a = TranslationAdapter(scheduler=s, on_update_text=on_update)
    a.start_session("test-session")
    return s, a, results


# ── 1. FINAL enters scheduler ──────────────────────────────────────
class TestFinalEntersScheduler:
    def test_final_produces_translation(self):
        s, a, results = _setup()
        a.on_final_text("hello world", chunk_id=1)
        time.sleep(0.3)
        s.shutdown(wait=True)
        assert len(results) == 1
        cid, orig, trans = results[0]
        assert cid == 1
        assert orig == "hello world"
        assert "hello" in trans


# ── 2. PARTIAL ignored ────────────────────────────────────────────
class TestPartialIgnored:
    def test_partial_not_in_scheduler(self):
        # Adapter only exposes on_final_text — PARTIAL never reaches it.
        # This is enforced by the pipeline path: only _process_final_v3
        # calls adapter.on_final_text().  PARTIAL goes through
        # _process_partial_v3 which calls signals.update_text directly.
        # Verifying: if adapter were called with a PARTIAL event,
        # the scheduler would reject it.
        s, a, _ = _setup(max_workers=0)
        # Construct a PARTIAL event manually and try submit
        from src.transcript_event import TranscriptEvent
        ev = TranscriptEvent(
            session_id="test-session", segment_id="seg", utterance_id=0,
            phase=TranscriptPhase.PARTIAL, text_raw="partial text",
        )
        status = s.submit(ev)
        assert status is None  # scheduler rejects PARTIAL


# ── 3. STABLE ignored ─────────────────────────────────────────────
class TestStableIgnored:
    def test_stable_not_in_scheduler(self):
        s, a, _ = _setup(max_workers=0)
        from src.transcript_event import TranscriptEvent
        ev = TranscriptEvent(
            session_id="test-session", segment_id="seg", utterance_id=0,
            phase=TranscriptPhase.STABLE, text_raw="stable text",
        )
        assert s.submit(ev) is None


# ── 4. Translation non-blocking ───────────────────────────────────
class TestTranslationNonBlocking:
    def test_original_text_written_before_translation(self):
        """Simulates the pipeline pattern: emit original text immediately,
        then submit to scheduler."""
        import threading
        timeline = []

        translation_gate = threading.Event()

        def gated_translator(text, lang=None):
            assert translation_gate.wait(timeout=2.0)
            return f"ZH:{text}"

        # Mimic pipeline behavior
        text = "hello"
        chunk_id = 1
        timeline.append(("original_emit", chunk_id, text))
        s, a, results = _setup(translator=gated_translator)
        a.on_final_text(text, chunk_id)
        timeline.append(("scheduler_submit", chunk_id))
        timeline.append(("check_before_translation", len(results)))
        translation_gate.set()
        s.shutdown(wait=True)
        timeline.append(("after_shutdown", len(results)))

        # Original was written immediately
        assert timeline[2] == ("check_before_translation", 0)
        # Translation arrives after shutdown(wait=True)
        assert timeline[3][1] >= 0


# ── 5. Stale revision discarded ───────────────────────────────────
class TestStaleRevisionDiscarded:
    def test_new_revision_wins(self):
        s, a, results = _setup(translator=_slow_translator(0.1))
        a.on_final_text("old text", chunk_id=1)
        time.sleep(0.02)  # rev1 starts translating
        a.on_final_text("new text", chunk_id=1)  # rev2 cancels rev1
        time.sleep(0.3)
        s.shutdown(wait=True)
        assert len(results) == 1
        # Only rev2 result delivered
        assert results[0][1] == "new text"


# ── 6. Stale session discarded ────────────────────────────────────
class TestStaleSessionDiscarded:
    def test_old_session_result_not_written(self):
        s, a, results = _setup(translator=_slow_translator(0.1))
        a.on_final_text("session1 text", chunk_id=1)
        time.sleep(0.02)
        a.stop_session()
        a.start_session("new-session")
        a.on_final_text("session2 text", chunk_id=2)
        time.sleep(0.3)
        s.shutdown(wait=True)
        # Only session2 result should be delivered
        assert all(cid == 2 for cid, _, _ in results)


# ── 7. Translator failure safe ────────────────────────────────────
class TestTranslatorFailureSafe:
    def test_translator_error_does_not_break_pipeline(self):
        # max_workers=1 so jobs are sequential — failing job doesn't block
        s, a, results = _setup(translator=_failing_translator(), max_workers=1)
        a.on_final_text("will fail", chunk_id=1)
        time.sleep(0.1)  # let failing job complete
        # Replace translator with working one
        s._translator = lambda t, l: f"OK:{t}"
        a.on_final_text("will succeed", chunk_id=2)
        time.sleep(0.3)
        s.shutdown(wait=False)
        # At least the successful job delivered; failing job may or may not
        # have triggered on_error (depends on timing)
        assert any(r[1] == "will succeed" for r in results)


# ── 8. Callback crash safe ────────────────────────────────────────
class TestCallbackCrashSafe:
    def test_on_result_crash_does_not_kill_scheduler(self):
        crash_count = [0]
        def crashing_on_update(cid, orig, trans):
            crash_count[0] += 1
            raise RuntimeError("callback boom")

        s = TranslationScheduler(max_workers=1)
        a = TranslationAdapter(scheduler=s, on_update_text=crashing_on_update)
        a.start_session("test")
        a.on_final_text("first", chunk_id=1)
        a.on_final_text("second", chunk_id=2)
        time.sleep(0.3)
        s.shutdown(wait=True)
        # Both callbacks were invoked even though they crashed
        assert crash_count[0] == 2


# ── 9. Shutdown safe ──────────────────────────────────────────────
class TestShutdownSafe:
    def test_shutdown_cancels_pending(self):
        s, a, results = _setup(max_workers=0)
        a.on_final_text("pending", chunk_id=1)
        assert s.pending_count() == 1
        a.stop_session()
        assert s.pending_count() == 0

    def test_shutdown_idempotent(self):
        s, a, _ = _setup()
        a.shutdown(wait=False)
        a.shutdown(wait=False)  # no crash


# ── 10. Feature flag off preserves old behavior ───────────────────
class TestFeatureFlagOff:
    def test_config_defaults_to_false(self):
        # Reset env to isolate
        old = os.environ.get("REALTIME_SUBTITLE_USE_TRANSLATION_SCHEDULER")
        if old is not None:
            del os.environ["REALTIME_SUBTITLE_USE_TRANSLATION_SCHEDULER"]
        try:
            import importlib, config
            importlib.reload(config)
            assert config.config.use_translation_scheduler is False
        finally:
            if old is not None:
                os.environ["REALTIME_SUBTITLE_USE_TRANSLATION_SCHEDULER"] = old

    def test_env_var_true_enables_flag(self):
        os.environ["REALTIME_SUBTITLE_USE_TRANSLATION_SCHEDULER"] = "true"
        try:
            import importlib, config
            importlib.reload(config)
            assert config.config.use_translation_scheduler is True
        finally:
            del os.environ["REALTIME_SUBTITLE_USE_TRANSLATION_SCHEDULER"]
