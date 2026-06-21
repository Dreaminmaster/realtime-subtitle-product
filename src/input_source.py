"""Input source abstraction for v2.4.0 architecture.

Phase 1c: only MicrophoneSource is fully implemented.
SystemAudioSource and FileSource are declared but raise NotImplementedError.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import threading
import time
import uuid
import numpy as np

# Re-use ModuleStatus from Phase 1a
from src.module_registry import ModuleStatus


class InputSourceError(RuntimeError):
    """Wraps errors from underlying capture hardware / driver."""
    def __init__(self, message: str, *, source_id: str | None = None, cause: Exception | None = None):
        super().__init__(message)
        self.source_id = source_id
        self.cause = cause


class InputSourceNotImplemented(NotImplementedError):
    """Raised when an InputSource subclass is not yet implemented."""
    pass


class InputSource(ABC):
    """Abstract audio input source.

    Subclasses implement start/stop/is_running + call the
    audio_chunk_callback with (source_id, np.ndarray).
    """

    def __init__(self, source_id: str | None = None):
        self._source_id = source_id or str(uuid.uuid4())
        self._status: ModuleStatus = ModuleStatus.UNINITIALIZED
        self._callback: callable | None = None
        self._lock = threading.Lock()

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def source_type(self) -> str:
        """Human-readable source type. Override in subclasses."""
        return self.__class__.__name__

    @property
    def status(self) -> ModuleStatus:
        with self._lock:
            return self._status

    def set_audio_chunk_callback(self, callback: callable) -> None:
        """callback(source_id: str, chunk: np.ndarray)"""
        self._callback = callback

    def _emit_chunk(self, chunk: np.ndarray) -> None:
        if self._callback is not None:
            self._callback(self._source_id, chunk)

    def _set_status(self, s: ModuleStatus) -> None:
        """Caller must hold self._lock."""
        self._status = s

    def _status_locked(self, s: ModuleStatus) -> None:
        """Set status from outside the lock."""
        with self._lock:
            self._status = s

    @abstractmethod
    def is_running(self) -> bool: ...

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...


# ── MicrophoneSource ────────────────────────────────────────────────
class MicrophoneSource(InputSource):
    """Wraps existing AudioCapture without changing its internals.

    Phase 1c uses AudioCapture.generator() raw mode — the pump thread
    iterates over yield'ed audio chunks and pushes them to the callback.

    It does NOT call AudioCapture.start(), because that launches the
    legacy VAD record loop.  Using generator() directly gives us raw
    float32 audio chunks that match the existing real-time pipeline.
    """

    def __init__(self, capture_factory=None, source_id: str | None = None):
        super().__init__(source_id)
        self._capture_factory = capture_factory or self._default_factory
        self._capture = None
        self._running = False
        self._pump_thread: threading.Thread | None = None
        self._last_error: Exception | None = None

    @property
    def source_type(self) -> str:
        return "microphone"

    @property
    def last_error(self) -> Exception | None:
        with self._lock:
            return self._last_error

    @staticmethod
    def _default_factory():
        """Create a real AudioCapture. Import is deferred so tests don't need
        sounddevice installed."""
        from audio_capture import AudioCapture
        return AudioCapture()

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start(self) -> None:
        with self._lock:
            if self._running:
                raise InputSourceError(
                    "MicrophoneSource is already running", source_id=self._source_id
                )
            self._set_status(ModuleStatus.STARTING)

        try:
            self._capture = self._capture_factory()
            # Do NOT call self._capture.start() — that launches the
            # legacy VAD record loop.  We use generator() directly.
        except Exception as e:
            self._status_locked(ModuleStatus.ERROR)
            raise InputSourceError(
                f"Failed to create microphone capture: {e}", source_id=self._source_id,
                cause=e
            ) from e

        self._running = True
        self._stop_requested = False
        self._status_locked(ModuleStatus.RUNNING)

        def _pump():
            try:
                gen = self._capture.generator()
                for chunk in gen:
                    if not self._running:
                        break
                    self._emit_chunk(chunk)
            except Exception as e:
                # Stream failure → ERROR, not running
                with self._lock:
                    self._last_error = e
                    self._running = False
                    self._status = ModuleStatus.ERROR
                # Do NOT re-raise — the pump runs on a daemon thread and
                # the main thread will never see an exception here.
                # Callers should check self.last_error / self.status.
            else:
                # Generator exhausted normally — set status to STOPPED.
                # Keep _running=True so that stop() can do cleanup
                # (e.g., capture.stop(), join pump thread, final status).
                with self._lock:
                    if self._status not in (ModuleStatus.ERROR, ModuleStatus.STOPPING, ModuleStatus.STOPPED):
                        self._status = ModuleStatus.STOPPED

        self._pump_thread = threading.Thread(target=_pump, daemon=True, name="MicrophonePump")
        self._pump_thread.start()

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_requested = True
            prev_status = self._status
            self._status = ModuleStatus.STOPPING

        error_raised = False
        try:
            if self._capture is not None:
                self._capture.stop()
        except Exception as e:
            error_raised = True
            self._status_locked(ModuleStatus.ERROR)
            raise InputSourceError(
                f"Failed to stop microphone: {e}", source_id=self._source_id, cause=e
            ) from e
        finally:
            if not error_raised:
                # Preserve ERROR if the pump already set it
                with self._lock:
                    if self._status != ModuleStatus.ERROR:
                        self._status = ModuleStatus.STOPPED

        # Wait for the pump thread to finish
        t = self._pump_thread
        if t is not None and t.is_alive():
            t.join(timeout=1.0)


# ── SystemAudioSource (NOT IMPLEMENTED in Phase 1c) ────────────────
class SystemAudioSource(InputSource):

    @property
    def source_type(self) -> str:
        return "system_audio"

    def is_running(self) -> bool:
        raise InputSourceNotImplemented(
            "SystemAudioSource is not implemented in Phase 1c"
        )

    def start(self) -> None:
        raise InputSourceNotImplemented(
            "SystemAudioSource is not implemented in Phase 1c"
        )

    def stop(self) -> None:
        raise InputSourceNotImplemented(
            "SystemAudioSource is not implemented in Phase 1c"
        )


# ── FileSource (NOT IMPLEMENTED in Phase 1c) ───────────────────────
class FileSource(InputSource):

    @property
    def source_type(self) -> str:
        return "file"

    def is_running(self) -> bool:
        raise InputSourceNotImplemented(
            "FileSource is not implemented in Phase 1c"
        )

    def start(self) -> None:
        raise InputSourceNotImplemented(
            "FileSource is not implemented in Phase 1c"
        )

    def stop(self) -> None:
        raise InputSourceNotImplemented(
            "FileSource is not implemented in Phase 1c"
        )
