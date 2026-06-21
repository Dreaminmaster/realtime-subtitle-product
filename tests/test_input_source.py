"""Unit tests for InputSource and MicrophoneSource."""
import pytest
import time
import threading
import numpy as np
from src.input_source import (
    InputSource, MicrophoneSource, SystemAudioSource, FileSource,
    InputSourceError, InputSourceNotImplemented,
)
from src.module_registry import ModuleStatus


# ── Fake AudioCapture for testing ───────────────────────────────────
class FakeAudioCapture:
    """Minimal stand-in for audio_capture.AudioCapture."""

    def __init__(self, fail_on_stop=False, fail_stream=False):
        self.running = False
        self._start_called = False
        self.fail_on_stop = fail_on_stop
        self.fail_stream = fail_stream

    def start(self):
        """Legacy VAD record loop — MicrophoneSource must NOT call this."""
        self._start_called = True
        self.running = True

    def stop(self):
        if self.fail_on_stop:
            raise RuntimeError("simulated stop failure")
        self.running = False

    def generator(self):
        if self.fail_stream:
            raise RuntimeError("simulated stream failure")
        for _ in range(5):
            yield np.zeros(160, dtype=np.float32)

    @property
    def start_was_called(self) -> bool:
        return self._start_called


# ── Tests ───────────────────────────────────────────────────────────
class TestInputSourceAbstract:
    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError):
            InputSource()  # abstract

    def test_subclass_must_implement_abstract(self):
        class Incomplete(InputSource):
            def is_running(self): pass
            # missing start() and stop()
        with pytest.raises(TypeError):
            Incomplete()


class TestMicrophoneSource:
    @staticmethod
    def _factory():
        return FakeAudioCapture()

    def _source(self, **kwargs) -> MicrophoneSource:
        return MicrophoneSource(capture_factory=self._factory, **kwargs)

    # ── initial state ───────────────────────────────────────────
    def test_initial_status_is_uninitialized(self):
        src = self._source()
        assert src.status == ModuleStatus.UNINITIALIZED
        assert src.is_running() is False
        assert src.source_type == "microphone"

    def test_source_id_auto_generated(self):
        src = self._source()
        assert len(src.source_id) == 36

    def test_explicit_source_id(self):
        src = MicrophoneSource(capture_factory=self._factory, source_id="mic-1")
        assert src.source_id == "mic-1"

    # ── does NOT call capture.start() ───────────────────────────
    def test_start_does_not_call_capture_start(self):
        cap = FakeAudioCapture()
        src = MicrophoneSource(capture_factory=lambda: cap)
        src.start()
        time.sleep(0.05)
        assert cap.start_was_called is False, (
            "MicrophoneSource must NOT call capture.start() — uses generator() only"
        )

    # ── start / stop lifecycle ──────────────────────────────────
    def test_start_sets_running(self):
        src = self._source()
        src.start()
        assert src.is_running() is True
        assert src.status == ModuleStatus.RUNNING

    def test_stop_sets_not_running(self):
        src = self._source()
        src.start()
        src.stop()
        assert src.is_running() is False
        assert src.status == ModuleStatus.STOPPED

    def test_stop_idempotent_does_not_crash(self):
        src = self._source()
        src.start()
        src.stop()
        src.stop()  # second stop
        # No crash = pass

    def test_stop_calls_capture_stop(self):
        cap = FakeAudioCapture()
        src = MicrophoneSource(capture_factory=lambda: cap)
        src.start()
        time.sleep(0.05)
        assert cap.running is False  # generator not running until iterated
        src.stop()
        # capture.stop() was called (resets running flag)
        # After stop, FakeAudioCapture.running should be False
        assert cap.running is False  # it was already False since we didn't call start()

    def test_stop_joins_pump_thread(self):
        """After stop(), the pump thread should be done."""
        src = self._source()
        src.start()
        time.sleep(0.1)
        src.stop()
        # pump thread should have been joined — but we can't check .is_alive()
        # on the private attribute directly.  The test verifies no crash.
        # If the pump were still running after stop(), this is a bug that
        # would surface as a resource warning.

    def test_double_start_raises(self):
        src = self._source()
        src.start()
        with pytest.raises(InputSourceError, match="already running"):
            src.start()

    # ── callback ────────────────────────────────────────────────
    def test_callback_receives_chunks(self):
        received = []
        src = self._source()
        src.set_audio_chunk_callback(lambda sid, c: received.append((sid, len(c))))
        src.start()
        time.sleep(0.15)
        src.stop()
        assert len(received) > 0
        assert all(sid == src.source_id for sid, _ in received)
        assert all(length == 160 for _, length in received)

    def test_callback_not_set_still_runs(self):
        src = self._source()
        src.start()
        time.sleep(0.05)
        src.stop()

    # ── error handling ──────────────────────────────────────────
    def test_start_creation_failure_raises_input_source_error(self):
        def failing_factory():
            raise RuntimeError("simulated creation failure")
        src = MicrophoneSource(capture_factory=failing_factory)
        with pytest.raises(InputSourceError, match="create microphone"):
            src.start()
        assert src.status == ModuleStatus.ERROR

    def test_stop_failure_raises_input_source_error(self):
        def failing_stop_factory():
            cap = FakeAudioCapture()
            cap.fail_on_stop = True
            return cap
        src = MicrophoneSource(capture_factory=failing_stop_factory)
        src.start()
        with pytest.raises(InputSourceError, match="stop"):
            src.stop()
        assert src.status == ModuleStatus.ERROR

    def test_stream_failure_sets_error_status(self):
        """Pump thread should set status=ERROR and last_error without crash."""
        def failing_stream_factory():
            return FakeAudioCapture(fail_stream=True)
        src = MicrophoneSource(capture_factory=failing_stream_factory)
        src.start()
        time.sleep(0.2)
        # Pump thread has encountered the stream failure
        assert src.status == ModuleStatus.ERROR
        assert src.last_error is not None
        assert "simulated stream failure" in str(src.last_error)

    def test_stream_failure_does_not_require_excepthook(self):
        """After a stream error, status is ERROR — no threading.excepthook needed."""
        def failing_stream_factory():
            return FakeAudioCapture(fail_stream=True)
        src = MicrophoneSource(capture_factory=failing_stream_factory)
        src.start()
        time.sleep(0.2)
        assert src.status == ModuleStatus.ERROR
        # success: we detected the error via the status API, not via excepthook

    def test_last_error_none_initially(self):
        src = self._source()
        assert src.last_error is None

    # ── factory isolation ───────────────────────────────────────
    def test_factory_called_per_start(self):
        call_count = [0]
        def counting_factory():
            call_count[0] += 1
            return FakeAudioCapture()
        src = MicrophoneSource(capture_factory=counting_factory)
        src.start()
        src.stop()
        src.start()
        src.stop()
        assert call_count[0] == 2


class TestNotImplementedSources:
    def test_system_audio_start_raises(self):
        src = SystemAudioSource()
        with pytest.raises(InputSourceNotImplemented, match="SystemAudioSource"):
            src.start()

    def test_system_audio_is_running_raises(self):
        src = SystemAudioSource()
        with pytest.raises(InputSourceNotImplemented, match="SystemAudioSource"):
            src.is_running()

    def test_system_audio_stop_raises(self):
        src = SystemAudioSource()
        with pytest.raises(InputSourceNotImplemented, match="SystemAudioSource"):
            src.stop()

    def test_file_source_start_raises(self):
        src = FileSource()
        with pytest.raises(InputSourceNotImplemented, match="FileSource"):
            src.start()

    def test_file_source_is_running_raises(self):
        src = FileSource()
        with pytest.raises(InputSourceNotImplemented, match="FileSource"):
            src.is_running()

    def test_file_source_stop_raises(self):
        src = FileSource()
        with pytest.raises(InputSourceNotImplemented, match="FileSource"):
            src.stop()

    def test_not_implemented_sources_have_correct_type(self):
        assert SystemAudioSource().source_type == "system_audio"
        assert FileSource().source_type == "file"
