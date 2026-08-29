"""Session-owned WAV recording for saved subtitle sessions.

The recorder consumes the exact float32 mono chunks already used by the ASR
pipeline.  It never opens a second microphone or system-audio stream.
"""

from __future__ import annotations

import threading
import wave
from pathlib import Path

import numpy as np


def get_recordings_dir() -> Path:
    path = (
        Path.home()
        / "Library"
        / "Application Support"
        / "RealtimeSubtitle"
        / "recordings"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_session_recording_path(session_id: str) -> Path:
    safe_id = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in "-_")
    if not safe_id:
        raise ValueError("session_id must contain a safe filename character")
    return get_recordings_dir() / f"{safe_id}.wav"


def delete_session_recording(path: str | Path | None) -> bool:
    """Delete only a recording that belongs to this app's recordings folder."""
    if not path:
        return False
    candidate = Path(path).expanduser().resolve()
    recordings = get_recordings_dir().resolve()
    if candidate.parent != recordings or candidate.suffix.lower() != ".wav":
        return False
    if candidate.is_file():
        candidate.unlink()
        return True
    return False


class SessionAudioRecorder:
    """Thread-safe mono PCM recorder with a sample-accurate elapsed clock."""

    def __init__(self, path: str | Path, sample_rate: int):
        self.path = Path(path)
        self.sample_rate = int(sample_rate)
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        self._wave: wave.Wave_write | None = None
        self._samples_written = 0
        self._lock = threading.RLock()

    @property
    def duration(self) -> float:
        with self._lock:
            return self._samples_written / float(self.sample_rate)

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._wave is not None

    def start(self) -> None:
        with self._lock:
            if self._wave is not None:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = wave.open(str(self.path), "wb")
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self.sample_rate)
            self._wave = handle

    def write(self, chunk) -> tuple[float, float]:
        """Append one float32 chunk and return its [start, end] offsets."""
        samples = np.asarray(chunk, dtype=np.float32).reshape(-1)
        with self._lock:
            if self._wave is None:
                raise RuntimeError("recorder is not started")
            start = self._samples_written / float(self.sample_rate)
            if samples.size:
                pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2")
                self._wave.writeframesraw(pcm.tobytes())
                self._samples_written += int(samples.size)
            end = self._samples_written / float(self.sample_rate)
            return start, end

    def stop(self) -> float:
        with self._lock:
            handle = self._wave
            self._wave = None
            if handle is not None:
                handle.close()
            return self._samples_written / float(self.sample_rate)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
