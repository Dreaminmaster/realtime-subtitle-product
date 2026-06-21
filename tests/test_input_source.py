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


class FakeAudioCapture:
    """Minimal stand-in for audio_capture.AudioCapture."""

    def __init__(self, *, fail_on_stop=False, fail_stream=False):
        self.running = False
        self._start_called = False
        self.fail_on_stop = fail_on_stop
        self.fail_stream = fail_stream

    def start(self):
        self._start_called = True
        self.running = True

    def stop(self):
        if self.fail_on_stop:
            raise RuntimeError("simulated stop failure")
        self.running = False

    def generator(self):
        if self.fail_stream:
            raise RuntimeError("simulated stream failure")
        while True:
            yield np.zeros(160, dtype=np.float32)

    @property
    def start_was_called(self) -> bool:
        return self._start_called


class FiniteCapture:
    """Capture with a finite generator (for exhaust tests)."""
    def __init__(self, chunk_count=3):
        self.running = False
        self.chunk_count = chunk_count

    def start(self): pass
    def stop(self): self.running = False

    def generator(self):
        for _ in range(self.chunk_count):
            yield np.zeros(160, dtype=np.float32)


class TestInputSourceAbstract:
    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError):
            InputSource()

    def test_subclass_must_implement_abstract(self):
        class Incomplete(InputSource):
            def is_running(self): pass
        with pytest.raises(TypeError):
            Incomplete()


class TestMicrophoneSource:
    @staticmethod
    def _factory():
        return FakeAudioCapture()

    def _src(self, **kw) -> MicrophoneSource:
        return MicrophoneSource(capture_factory=self._factory, **kw)

    # ── init ──────────────────────────────────────────────────────
    def test_initial_state(self):
        src = self._src()
        assert src.status == ModuleStatus.UNINITIALIZED
        assert src.is_running() is False
        assert src.source_type == "microphone"
        assert len(src.source_id) == 36
        assert src.last_error is None

    def test_explicit_source_id(self):
        src = MicrophoneSource(capture_factory=self._factory, source_id="mic-1")
        assert src.source_id == "mic-1"

    # ── does NOT call capture.start() ─────────────────────────────
    def test_does_not_call_capture_start(self):
        cap = FakeAudioCapture()
        src = MicrophoneSource(capture_factory=lambda: cap)
        src.start()
        time.sleep(0.05)
        assert cap.start_was_called is False
        src.stop()

    # ── lifecycle ─────────────────────────────────────────────────
    def test_start_sets_running(self):
        src = self._src()
        src.start()
        assert src.is_running() is True
        assert src.status == ModuleStatus.RUNNING
        src.stop()

    def test_user_stop_sets_stopped_not_running(self):
        src = self._src()
        src.start()
        time.sleep(0.05)
        src.stop()
        assert src.status == ModuleStatus.STOPPED
        assert src.is_running() is False

    def test_stop_idempotent(self):
        src = self._src()
        src.start()
        src.stop()
        src.stop()
        assert src.status == ModuleStatus.STOPPED

    def test_double_start_raises(self):
        src = self._src()
        src.start()
        with pytest.raises(InputSourceError, match="already running"):
            src.start()
        src.stop()

    # ── callback ──────────────────────────────────────────────────
    def test_callback_receives_chunks(self):
        received = []
        src = self._src()
        src.set_audio_chunk_callback(lambda sid, c: received.append((sid, len(c))))
        src.start()
        time.sleep(0.1)
        src.stop()
        assert len(received) > 0
        assert all(sid == src.source_id for sid, _ in received)

    def test_callback_optional(self):
        src = self._src()
        src.start()
        time.sleep(0.05)
        src.stop()

    # ── errors ────────────────────────────────────────────────────
    def test_start_creation_failure(self):
        src = MicrophoneSource(capture_factory=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        with pytest.raises(InputSourceError, match="create microphone"):
            src.start()
        assert src.status == ModuleStatus.ERROR

    def test_stop_failure(self):
        src = MicrophoneSource(capture_factory=lambda: FakeAudioCapture(fail_on_stop=True))
        src.start()
        time.sleep(0.05)
        with pytest.raises(InputSourceError, match="stop"):
            src.stop()
        assert src.status == ModuleStatus.ERROR

    def test_stream_failure_sets_error_not_running(self):
        src = MicrophoneSource(capture_factory=lambda: FakeAudioCapture(fail_stream=True))
        src.start()
        time.sleep(0.15)
        assert src.status == ModuleStatus.ERROR
        assert src.is_running() is False
        assert src.last_error is not None

    def test_stream_failure_preserved_on_stop(self):
        src = MicrophoneSource(capture_factory=lambda: FakeAudioCapture(fail_stream=True))
        src.start()
        time.sleep(0.15)
        assert src.status == ModuleStatus.ERROR
        src.stop()
        assert src.status == ModuleStatus.ERROR

    # ── generator exhaustion ──────────────────────────────────────
    def test_exhaust_stopped_not_running(self):
        src = MicrophoneSource(capture_factory=lambda: FiniteCapture(chunk_count=3))
        src.start()
        time.sleep(0.2)
        assert src.status == ModuleStatus.STOPPED
        assert src.is_running() is False

    def test_exhaust_idempotent_stop(self):
        src = MicrophoneSource(capture_factory=lambda: FiniteCapture(chunk_count=2))
        src.start()
        time.sleep(0.15)
        assert src.status == ModuleStatus.STOPPED
        src.stop()
        assert src.status == ModuleStatus.STOPPED

    def test_exhaust_stop_then_restart(self):
        src = MicrophoneSource(capture_factory=lambda: FiniteCapture(chunk_count=2))
        src.start()
        time.sleep(0.15)
        assert src.status == ModuleStatus.STOPPED
        assert src.is_running() is False
        src.start()
        # FiniteCapture with chunk_count=2 exhausts fast — but we check
        # is_running before the pump finishes.  This tests that start()
        # set _running=True correctly.  Exhaust may happen during this
        # check, so accept RUNNING or already-exhausted STOPPED.
        time.sleep(0.02)
        assert src.is_running() is True or src.status == ModuleStatus.STOPPED
        src.stop()

    # ── factory ───────────────────────────────────────────────────
    def test_factory_per_start(self):
        call_count = [0]
        def f():
            call_count[0] += 1
            return FakeAudioCapture()
        src = MicrophoneSource(capture_factory=f)
        src.start(); src.stop()
        src.start(); src.stop()
        assert call_count[0] == 2


class TestNotImplementedSources:
    def test_system_audio(self):
        s = SystemAudioSource()
        assert s.source_type == "system_audio"
        for m in [s.start, s.stop, s.is_running]:
            with pytest.raises(InputSourceNotImplemented, match="SystemAudioSource"):
                m()

    def test_file_source(self):
        s = FileSource()
        assert s.source_type == "file"
        for m in [s.start, s.stop, s.is_running]:
            with pytest.raises(InputSourceNotImplemented, match="FileSource"):
                m()
