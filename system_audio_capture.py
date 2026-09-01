"""Native system-audio input selected for the current desktop platform."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import threading

import numpy as np

from audio_capture import AudioCaptureError


class MacOSSystemAudioCapture:
    """Expose ScreenCaptureKit PCM output through the AudioCapture interface."""

    def __init__(self, *, sample_rate=16000, streaming_step_size=0.2, **_ignored):
        self.sample_rate = int(sample_rate)
        self.streaming_step_size = float(streaming_step_size)
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()
        self._process = None
        self._process_lock = threading.RLock()

    @staticmethod
    def helper_path() -> Path:
        override = os.getenv("REALTIME_SUBTITLE_SYSTEM_AUDIO_HELPER")
        if override:
            return Path(override).expanduser()
        resources = Path(__file__).resolve().parent
        bundled = resources / "bin" / "system-audio-capture"
        if bundled.exists():
            return bundled
        return resources / "native" / "system-audio-capture"

    @classmethod
    def is_available(cls) -> bool:
        helper = cls.helper_path()
        return helper.is_file() and os.access(helper, os.X_OK)

    def prepare_start(self):
        self._stop_event.clear()
        self.running = True

    def start(self):
        self.prepare_start()

    def stop(self):
        self.running = False
        self._stop_event.set()
        with self._process_lock:
            process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1.0)
        with self._process_lock:
            self._process = None

    def generator(self):
        if self._stop_event.is_set():
            return
        if not self.running:
            self.prepare_start()

        from permission_guide import request_screen_capture_access
        permission = request_screen_capture_access()
        if permission is not True:
            self.running = False
            raise AudioCaptureError(
                "System audio permission is not enabled. Open System Settings > "
                "Privacy & Security > Screen & System Audio Recording, allow "
                "Realtime Subtitle, then restart the app.",
                stage="permission",
                requested_device="system_audio",
            )

        helper = self.helper_path()
        if not self.is_available():
            raise AudioCaptureError(
                "Native system-audio support is missing from this app bundle. "
                "Please reinstall the latest Realtime Subtitle build.",
                stage="open",
                requested_device="system_audio",
            )

        command = [str(helper), "--sample-rate", str(self.sample_rate)]
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except OSError as exc:
            self.running = False
            raise AudioCaptureError(
                f"Could not start native system-audio capture: {exc}",
                stage="open",
                requested_device="system_audio",
            ) from exc

        with self._process_lock:
            self._process = process

        # 100 ms keeps cancellation responsive while reducing pipe overhead.
        samples_per_read = max(320, int(self.sample_rate * 0.1))
        bytes_per_read = samples_per_read * np.dtype(np.float32).itemsize
        try:
            while self.running and not self._stop_event.is_set():
                data = process.stdout.read(bytes_per_read)
                if not data:
                    break
                usable = len(data) - (len(data) % 4)
                if usable:
                    yield np.frombuffer(data[:usable], dtype="<f4").copy()
        finally:
            return_code = process.poll()
            if return_code is None:
                process.terminate()
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1.0)
            with self._process_lock:
                if self._process is process:
                    self._process = None
            self.running = False

        if not self._stop_event.is_set() and return_code not in (0, None):
            detail = process.stderr.read().decode("utf-8", errors="replace").strip()
            if "permission" in detail.lower() or "not authorized" in detail.lower():
                detail = (
                    "System audio permission is not enabled. Open System Settings > "
                    "Privacy & Security > Screen & System Audio Recording, allow "
                    "Realtime Subtitle, then restart the app."
                )
            raise AudioCaptureError(
                detail or "Native system-audio capture stopped unexpectedly.",
                stage="permission" if "permission" in detail.lower() else "read",
                requested_device="system_audio",
            )


if os.name == "nt":
    from windows_system_audio import WindowsSystemAudioCapture as SystemAudioCapture
else:
    SystemAudioCapture = MacOSSystemAudioCapture
