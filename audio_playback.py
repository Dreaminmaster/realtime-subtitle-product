"""Reliable local recording playback with a native macOS backend.

``QMediaPlayer`` is kept as a cross-platform fallback, but saved WAV sessions
use ``AVAudioPlayer`` on macOS.  That removes dependency on Qt's asynchronous
media-plugin discovery and gives the transcript timeline a stable clock.
"""

from __future__ import annotations

from pathlib import Path
import sys
import wave

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal


class LocalAudioPlayer(QObject):
    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    state_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backend = None
        self._native_player = None
        self._qt_player = None
        self._qt_audio_output = None
        self._duration_ms = 0
        self._requested_position_ms = 0
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._poll_native_position)

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    @property
    def is_loaded(self) -> bool:
        return self._backend in ("avfoundation", "qt")

    def load(self, path: str | Path) -> bool:
        self.unload()
        source = Path(path).expanduser()
        if not source.is_file() or source.stat().st_size <= 44:
            self.error_occurred.emit("The recording file is missing or empty")
            return False
        # Qt Multimedia discovers metadata asynchronously on Windows. Saved
        # sessions are PCM WAV files, so read their duration synchronously to
        # make the timeline and seek controls usable immediately after load.
        try:
            with wave.open(str(source), "rb") as handle:
                frames = handle.getnframes()
                rate = handle.getframerate()
            if rate > 0:
                self._duration_ms = max(0, round(frames / rate * 1000))
        except (OSError, EOFError, wave.Error):
            self._duration_ms = 0
        if sys.platform == "darwin" and self._load_avfoundation(source):
            return True
        return self._load_qt(source)

    def _load_avfoundation(self, source: Path) -> bool:
        try:
            import AVFoundation
            import Foundation

            url = Foundation.NSURL.fileURLWithPath_(str(source))
            result = AVFoundation.AVAudioPlayer.alloc().initWithContentsOfURL_error_(url, None)
            player, error = result if isinstance(result, tuple) else (result, None)
            if player is None:
                raise RuntimeError(str(error or "AVAudioPlayer could not open the file"))
            player.setVolume_(0.9)
            # Headless visual tests can report no output route even for a
            # valid WAV.  Duration is the reliable file-read signal; the real
            # app still prepares again when playback begins.
            player.prepareToPlay()
            if float(player.duration()) <= 0:
                raise RuntimeError("macOS could not read this recording")
            self._native_player = player
            self._backend = "avfoundation"
            self._duration_ms = max(0, round(float(player.duration()) * 1000))
            self.duration_changed.emit(self._duration_ms)
            self.position_changed.emit(0)
            return True
        except Exception as exc:
            # Keep the Qt fallback available for unusual AVFoundation failures.
            self._native_player = None
            self._backend = None
            self._native_error = str(exc)
            return False

    def _load_qt(self, source: Path) -> bool:
        try:
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

            self._qt_audio_output = QAudioOutput(self)
            self._qt_audio_output.setVolume(0.9)
            self._qt_player = QMediaPlayer(self)
            self._qt_player.setAudioOutput(self._qt_audio_output)
            self._qt_player.positionChanged.connect(self._on_qt_position)
            self._qt_player.durationChanged.connect(self._on_qt_duration)
            self._qt_player.playbackStateChanged.connect(self._on_qt_state)
            self._qt_player.errorOccurred.connect(self._on_qt_error)
            self._qt_player.setSource(QUrl.fromLocalFile(str(source)))
            self._backend = "qt"
            if self._duration_ms:
                self.duration_changed.emit(self._duration_ms)
            self.position_changed.emit(0)
            return True
        except Exception as exc:
            native_error = getattr(self, "_native_error", "")
            detail = f"{native_error}; {exc}" if native_error else str(exc)
            self.error_occurred.emit(f"Unable to open this recording: {detail}")
            self._backend = None
            return False

    def unload(self):
        self._timer.stop()
        if self._native_player is not None:
            try:
                self._native_player.stop()
            except Exception:
                pass
        if self._qt_player is not None:
            try:
                self._qt_player.stop()
                self._qt_player.setSource(QUrl())
            except Exception:
                pass
        self._native_player = None
        self._qt_player = None
        self._qt_audio_output = None
        self._backend = None
        self._duration_ms = 0
        self._requested_position_ms = 0

    def play(self):
        if self._backend == "avfoundation":
            if self.position_ms() >= max(0, self._duration_ms - 80):
                self._native_player.setCurrentTime_(0.0)
            if self._native_player.play():
                self._timer.start()
                self.state_changed.emit(True)
            else:
                self.error_occurred.emit("macOS could not start audio playback")
        elif self._backend == "qt":
            self._qt_player.play()

    def pause(self):
        if self._backend == "avfoundation":
            self._native_player.pause()
            self._timer.stop()
            self.state_changed.emit(False)
        elif self._backend == "qt":
            self._qt_player.pause()

    def stop(self):
        if self._backend == "avfoundation":
            self._native_player.stop()
            self._native_player.setCurrentTime_(0.0)
            self._timer.stop()
            self.position_changed.emit(0)
            self.state_changed.emit(False)
        elif self._backend == "qt":
            self._qt_player.stop()

    def seek(self, milliseconds: int):
        value = max(0, min(int(milliseconds), self._duration_ms or int(milliseconds)))
        if self._backend == "avfoundation":
            self._native_player.setCurrentTime_(value / 1000.0)
            self.position_changed.emit(value)
        elif self._backend == "qt":
            self._requested_position_ms = value
            self._qt_player.setPosition(value)

    def position_ms(self) -> int:
        if self._backend == "avfoundation" and self._native_player is not None:
            return max(0, round(float(self._native_player.currentTime()) * 1000))
        if self._backend == "qt" and self._qt_player is not None:
            reported = max(0, int(self._qt_player.position()))
            if reported == 0 and self._requested_position_ms > 0:
                return self._requested_position_ms
            return reported
        return 0

    def is_playing(self) -> bool:
        if self._backend == "avfoundation" and self._native_player is not None:
            return bool(self._native_player.isPlaying())
        if self._backend == "qt" and self._qt_player is not None:
            from PyQt6.QtMultimedia import QMediaPlayer

            return self._qt_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        return False

    def _poll_native_position(self):
        if self._backend != "avfoundation" or self._native_player is None:
            self._timer.stop()
            return
        position = self.position_ms()
        self.position_changed.emit(position)
        if not self._native_player.isPlaying():
            self._timer.stop()
            if self._duration_ms and position >= self._duration_ms - 120:
                self.position_changed.emit(self._duration_ms)
            self.state_changed.emit(False)

    def _on_qt_duration(self, duration):
        value = max(0, int(duration))
        if value > 0:
            self._duration_ms = value
            self.duration_changed.emit(self._duration_ms)

    def _on_qt_position(self, position):
        value = max(0, int(position))
        self._requested_position_ms = value
        self.position_changed.emit(value)

    def _on_qt_state(self, state):
        from PyQt6.QtMultimedia import QMediaPlayer

        self.state_changed.emit(state == QMediaPlayer.PlaybackState.PlayingState)

    def _on_qt_error(self, error, message=""):
        del error
        self.error_occurred.emit(message or "Unable to play this recording")
