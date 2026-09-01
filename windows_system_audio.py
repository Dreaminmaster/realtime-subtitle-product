"""Windows system-audio capture using native WASAPI loopback.

The SoundCard dependency is a thin BSD-3-Clause CFFI wrapper around Windows'
WASAPI loopback endpoint.  Capturing the output mix therefore needs neither a
virtual cable nor a change to the user's default playback device.
"""

from __future__ import annotations

import platform
import threading

import numpy as np

from audio_capture import AudioCaptureError


class WindowsSystemAudioCapture:
    def __init__(
        self,
        *,
        sample_rate=16000,
        streaming_step_size=0.2,
        output_device_id: str | None = None,
        capture_sample_rate=48000,
        **_ignored,
    ):
        self.sample_rate = int(sample_rate)
        self.capture_sample_rate = max(self.sample_rate, int(capture_sample_rate))
        self.streaming_step_size = float(streaming_step_size)
        self.output_device_id = str(output_device_id or "").strip() or None
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()
        self._recorder = None

    @classmethod
    def is_available(cls) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            import soundcard as sc

            return sc.default_speaker() is not None
        except Exception:
            return False

    @staticmethod
    def output_devices() -> list[tuple[str, str]]:
        if platform.system() != "Windows":
            return []
        try:
            import soundcard as sc

            return [(str(item.id), str(item.name)) for item in sc.all_speakers()]
        except Exception:
            return []

    def prepare_start(self):
        self._stop_event.clear()
        self.running = True

    def start(self):
        self.prepare_start()

    def stop(self):
        self.running = False
        self._stop_event.set()
        recorder = self._recorder
        if recorder is not None:
            try:
                recorder.__exit__(None, None, None)
            except Exception:
                pass
        self._recorder = None

    def _speaker(self, sc):
        if self.output_device_id:
            for speaker in sc.all_speakers():
                if str(speaker.id) == self.output_device_id:
                    return speaker
        return sc.default_speaker()

    @staticmethod
    def _mono(data: np.ndarray) -> np.ndarray:
        values = np.asarray(data, dtype=np.float32)
        if values.ndim == 2:
            values = values.mean(axis=1)
        return values.reshape(-1)

    def _resample(self, data: np.ndarray) -> np.ndarray:
        if self.capture_sample_rate == self.sample_rate or data.size == 0:
            return data.astype(np.float32, copy=False)
        output_count = max(1, round(data.size * self.sample_rate / self.capture_sample_rate))
        source_x = np.linspace(0.0, 1.0, num=data.size, endpoint=False)
        target_x = np.linspace(0.0, 1.0, num=output_count, endpoint=False)
        return np.interp(target_x, source_x, data).astype(np.float32, copy=False)

    def generator(self):
        if platform.system() != "Windows":
            raise AudioCaptureError(
                "WASAPI loopback is available only on Windows.",
                stage="open",
                requested_device="system_audio",
            )
        if not self.running:
            self.prepare_start()
        try:
            import soundcard as sc

            speaker = self._speaker(sc)
            if speaker is None:
                raise RuntimeError("Windows has no active playback device")
            loopback = sc.get_microphone(id=str(speaker.id), include_loopback=True)
            if loopback is None:
                raise RuntimeError(f"No WASAPI loopback endpoint for {speaker.name}")
            frames = max(960, round(self.capture_sample_rate * 0.1))
            recorder = loopback.recorder(
                samplerate=self.capture_sample_rate,
                channels=[0, 1],
                blocksize=max(frames * 2, 2048),
            )
            self._recorder = recorder
            recorder.__enter__()
            while self.running and not self._stop_event.is_set():
                values = recorder.record(numframes=frames)
                chunk = self._resample(self._mono(values))
                if chunk.size:
                    yield chunk
        except AudioCaptureError:
            raise
        except Exception as exc:
            raise AudioCaptureError(
                "Windows could not capture system audio through WASAPI. "
                "Make sure an output device is active and not in exclusive mode. "
                f"Details: {exc}",
                stage="open",
                requested_device="system_audio",
            ) from exc
        finally:
            self.stop()
