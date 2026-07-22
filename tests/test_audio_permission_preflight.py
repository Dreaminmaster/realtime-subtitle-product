import pytest
import threading
import time

import numpy as np

import permission_guide
from audio_capture import AudioCapture, AudioCaptureError


def test_permission_state_maps_avfoundation_status(monkeypatch):
    class FakeDevice:
        @staticmethod
        def authorizationStatusForMediaType_(_media_type):
            return 3

    class FakeAVFoundation:
        AVMediaTypeAudio = "audio"
        AVCaptureDevice = FakeDevice

    monkeypatch.setattr(permission_guide.platform, "system", lambda: "Darwin")
    monkeypatch.setitem(__import__("sys").modules, "AVFoundation", FakeAVFoundation)
    assert permission_guide.microphone_permission_state() == "authorized"


def test_locked_session_uses_fast_ioreg_probe(monkeypatch):
    class Result:
        stdout = '{ "IOConsoleLocked" = Yes }'

    monkeypatch.setattr(permission_guide.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(permission_guide.subprocess, "run", lambda *a, **k: Result())
    assert permission_guide.screen_session_is_locked()


def test_audio_capture_denied_permission_fails_before_device_probe(monkeypatch):
    monkeypatch.setattr(permission_guide, "screen_session_is_locked", lambda: False)
    monkeypatch.setattr(
        permission_guide,
        "microphone_permission_state",
        lambda: "denied",
    )
    capture = AudioCapture()
    with pytest.raises(AudioCaptureError) as exc:
        capture._ensure_microphone_permission()
    assert exc.value.stage == "permission"
    assert "System Settings" in str(exc.value)


def test_audio_capture_permission_wait_can_be_cancelled(monkeypatch):
    monkeypatch.setattr(permission_guide, "screen_session_is_locked", lambda: False)
    monkeypatch.setattr(
        permission_guide,
        "microphone_permission_state",
        lambda: "not_determined",
    )

    capture = AudioCapture()
    capture.running = True

    def cancelled_request(*, timeout, cancelled):
        assert timeout == 30.0
        capture.running = False
        assert cancelled()
        return None

    monkeypatch.setattr(
        permission_guide,
        "request_microphone_access",
        cancelled_request,
    )
    assert capture._ensure_microphone_permission() is False


def test_audio_capture_locked_session_fails_before_portaudio(monkeypatch):
    monkeypatch.setattr(permission_guide, "screen_session_is_locked", lambda: True)
    capture = AudioCapture()
    with pytest.raises(AudioCaptureError) as exc:
        capture._ensure_microphone_permission()
    assert exc.value.stage == "open"
    assert "locked" in str(exc.value).lower()


def test_emergency_interrupt_releases_active_stream():
    calls = []

    class FakeStream:
        def abort(self, ignore_errors=False):
            calls.append(("abort", ignore_errors))

        def close(self, ignore_errors=False):
            calls.append(("close", ignore_errors))

    capture = AudioCapture()
    capture.running = True
    capture._set_active_stream(FakeStream())
    capture._interrupt_active_stream()

    assert calls == [("abort", True), ("close", True)]
    assert capture._active_stream is None


def test_callback_generator_stops_while_waiting_for_audio(monkeypatch):
    monkeypatch.setattr(permission_guide, "screen_session_is_locked", lambda: False)
    monkeypatch.setattr(
        permission_guide,
        "microphone_permission_state",
        lambda: "authorized",
    )

    stream_holder = {}

    class FakeStream:
        def __init__(self, **kwargs):
            assert kwargs["callback"] is not None
            self.callback = kwargs["callback"]
            stream_holder["stream"] = self

        def __enter__(self):
            self.callback(
                np.ones((16, 1), dtype=np.float32),
                16,
                None,
                None,
            )
            return self

        def __exit__(self, *args):
            return False

        def abort(self, ignore_errors=False):
            pass

        def close(self, ignore_errors=False):
            pass

    monkeypatch.setattr(
        "audio_capture.sd.query_devices",
        lambda *args, **kwargs: {
            "index": 7,
            "name": "Fake microphone",
            "max_input_channels": 1,
        },
    )
    monkeypatch.setattr("audio_capture.sd.InputStream", FakeStream)

    capture = AudioCapture(device_index=7, streaming_step_size=0.01)
    audio_gen = capture.generator()
    assert np.array_equal(next(audio_gen), np.ones(16, dtype=np.float32))

    outcome = []

    def wait_for_next_chunk():
        try:
            next(audio_gen)
        except StopIteration:
            outcome.append("stopped")

    waiter = threading.Thread(target=wait_for_next_chunk)
    waiter.start()
    time.sleep(0.02)

    started = time.monotonic()
    capture.stop()
    waiter.join(timeout=0.5)

    assert not waiter.is_alive()
    assert outcome == ["stopped"]
    assert time.monotonic() - started < 0.5
    assert stream_holder["stream"] is not None
