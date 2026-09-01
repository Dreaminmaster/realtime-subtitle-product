import io
import os
import uuid

import numpy as np
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from single_instance import SingleInstance
from system_audio_capture import MacOSSystemAudioCapture


def test_second_instance_notifies_primary(tmp_path):
    app = QApplication.instance() or QApplication([])
    name = f"rts-test-{uuid.uuid4().hex[:8]}"
    primary = SingleInstance(name)
    received = []
    primary.message_received.connect(received.append)

    secondary = SingleInstance(name)
    QTest.qWait(120)

    assert primary.is_primary is True
    assert secondary.is_primary is False
    assert received == ["show-controls"]
    primary.release()


def test_system_audio_reads_float_pcm_from_helper(monkeypatch, tmp_path):
    helper = tmp_path / "system-audio-capture"
    helper.write_text("helper")
    helper.chmod(0o755)
    samples = np.array([0.25, -0.5, 0.75], dtype="<f4")

    class FakeProcess:
        def __init__(self):
            self.stdout = io.BytesIO(samples.tobytes())
            self.stderr = io.BytesIO()

        def poll(self):
            return 0

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    monkeypatch.setenv("REALTIME_SUBTITLE_SYSTEM_AUDIO_HELPER", os.fspath(helper))
    monkeypatch.setattr(
        "permission_guide.request_screen_capture_access", lambda: True
    )
    monkeypatch.setattr("system_audio_capture.subprocess.Popen", lambda *a, **k: FakeProcess())

    capture = MacOSSystemAudioCapture(sample_rate=16000)
    chunks = list(capture.generator())

    assert len(chunks) == 1
    assert np.allclose(chunks[0], samples)


def test_system_audio_helper_is_part_of_build_contract():
    from pathlib import Path

    script = Path("build_dmg.sh").read_text(encoding="utf-8")
    assert "native/SystemAudioCapture.swift" in script
    assert "NSScreenCaptureUsageDescription" in script
    assert "system-audio-capture" in script
