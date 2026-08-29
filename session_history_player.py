"""Transcript timeline and optional local recording playback widget."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

def format_clock(milliseconds: int | float) -> str:
    seconds = max(0, int(float(milliseconds) / 1000))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class SessionHistoryPlayer(QWidget):
    """Shows one saved session as a seekable, Chat-style transcript."""

    status_changed = pyqtSignal(str)

    def __init__(self, parent=None, language="en"):
        super().__init__(parent)
        self.language = language
        self._segments = []
        self._audio_path: Path | None = None
        self._duration_ms = 0
        self._seeking = False
        self.player = None
        self.audio_output = None
        self._player_class = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.header = QLabel("Select a session")
        self.header.setObjectName("HistoryTitle")
        root.addWidget(self.header)

        transport = QFrame()
        transport.setObjectName("Transport")
        transport_layout = QHBoxLayout(transport)
        transport_layout.setContentsMargins(12, 9, 12, 9)
        transport_layout.setSpacing(10)
        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("SecondaryButton")
        self.play_button.setFixedWidth(74)
        self.play_button.clicked.connect(self._toggle_playback)
        transport_layout.addWidget(self.play_button)
        self.position_label = QLabel("00:00")
        self.position_label.setObjectName("Muted")
        transport_layout.addWidget(self.position_label)
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0, 0)
        self.timeline.sliderPressed.connect(self._begin_seek)
        self.timeline.sliderReleased.connect(self._finish_seek)
        transport_layout.addWidget(self.timeline, 1)
        self.duration_label = QLabel("00:00")
        self.duration_label.setObjectName("Muted")
        transport_layout.addWidget(self.duration_label)
        root.addWidget(transport)

        self.recording_hint = QLabel("This session has no recording")
        self.recording_hint.setObjectName("Muted")
        root.addWidget(self.recording_hint)

        self.transcript = QListWidget()
        self.transcript.setObjectName("TranscriptTimeline")
        self.transcript.itemClicked.connect(self._seek_to_item)
        root.addWidget(self.transcript, 1)

        self._update_transport_enabled()

    def _t(self, text):
        from localization import translate
        return translate(text, self.language)

    def _ensure_player(self):
        if self.player is not None:
            return True
        try:
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
        except Exception:
            return False
        self._player_class = QMediaPlayer
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.8)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.errorOccurred.connect(self._on_error)
        return True

    def clear_session(self, message="Select a saved session to read it here."):
        if self.player is not None:
            self.player.stop()
            self.player.setSource(QUrl())
        self._segments = []
        self._audio_path = None
        self._duration_ms = 0
        self.header.setText(self._t("Select a session"))
        self.transcript.clear()
        self.recording_hint.setText(message)
        self.timeline.setRange(0, 0)
        self.position_label.setText("00:00")
        self.duration_label.setText("00:00")
        self._update_transport_enabled()

    def set_session(self, session, segments):
        if self.player is not None:
            self.player.stop()
        self._segments = list(segments or [])
        metadata = getattr(session, "metadata", {}) or {}
        self.header.setText(self._t("Session timeline"))
        self.transcript.clear()

        for segment in self._segments:
            start = getattr(segment, "start_offset", None)
            stamp = format_clock((start or 0.0) * 1000) if start is not None else "--:--"
            original = (getattr(segment, "original_text", "") or "").strip()
            translated = (getattr(segment, "translated_text", "") or "").strip()
            line = f"{stamp}    {original}"
            if translated:
                line += f"\n          {translated}"
            item = QListWidgetItem(line)
            item.setData(Qt.ItemDataRole.UserRole, start)
            item.setToolTip("Click to play from this subtitle" if start is not None else "")
            self.transcript.addItem(item)

        if not self._segments:
            self.transcript.addItem("No subtitle lines were saved in this session.")

        raw_path = metadata.get("audio_path") if metadata.get("record_audio") else None
        path = Path(raw_path).expanduser() if raw_path else None
        self._audio_path = path if path and path.is_file() else None
        duration = float(metadata.get("audio_duration") or 0.0)
        self._duration_ms = max(0, round(duration * 1000))
        self.timeline.setRange(0, self._duration_ms)
        self.duration_label.setText(format_clock(self._duration_ms))
        self.position_label.setText("00:00")

        if self._audio_path and self._ensure_player():
            self.player.setSource(QUrl.fromLocalFile(str(self._audio_path)))
            self.recording_hint.setText(self._t("Local recording available · click any subtitle to jump to it"))
        elif metadata.get("record_audio"):
            self.recording_hint.setText("The recording file is missing or was moved")
        else:
            self.recording_hint.setText(self._t("Transcript only · audio recording was not enabled"))
        self._update_transport_enabled()

    def _update_transport_enabled(self):
        enabled = self.player is not None and self._audio_path is not None
        self.play_button.setEnabled(enabled)
        self.timeline.setEnabled(enabled)

    def _toggle_playback(self):
        if self.player is None or self._audio_path is None:
            return
        if self.player.playbackState() == self._player_class.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _begin_seek(self):
        self._seeking = True

    def _finish_seek(self):
        self._seeking = False
        if self.player is not None:
            self.player.setPosition(self.timeline.value())

    def _seek_to_item(self, item):
        start = item.data(Qt.ItemDataRole.UserRole)
        if start is None or self.player is None or self._audio_path is None:
            return
        self.player.setPosition(max(0, round(float(start) * 1000)))
        self.player.play()

    def _on_position_changed(self, position):
        if not self._seeking:
            self.timeline.setValue(position)
        self.position_label.setText(format_clock(position))
        active = -1
        for index, segment in enumerate(self._segments):
            start = getattr(segment, "start_offset", None)
            end = getattr(segment, "end_offset", None)
            if start is not None and position >= start * 1000:
                active = index
            if end is not None and start is not None and start * 1000 <= position <= end * 1000:
                active = index
                break
        if active >= 0 and active < self.transcript.count():
            self.transcript.setCurrentRow(active)
            self.transcript.scrollToItem(self.transcript.item(active))

    def _on_duration_changed(self, duration):
        if duration > 0:
            self._duration_ms = duration
            self.timeline.setRange(0, duration)
            self.duration_label.setText(format_clock(duration))

    def _on_state_changed(self, state):
        playing = state == self._player_class.PlaybackState.PlayingState
        self.play_button.setText(self._t("Pause" if playing else "Play"))

    def _on_error(self, error, message=""):
        del error
        self.status_changed.emit(message or "Unable to play this recording")
