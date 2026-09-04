"""Lyrics-style transcript timeline with reliable local recording playback."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from audio_playback import LocalAudioPlayer
from ui_components import SegmentedControl


def format_clock(milliseconds: int | float) -> str:
    seconds = max(0, int(float(milliseconds) / 1000))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class TranscriptLine(QFrame):
    """One time-coded line that brightens and grows while it is playing."""

    seek_requested = pyqtSignal(float)
    geometry_changed = pyqtSignal()

    def __init__(self, segment, display_mode="bilingual", parent=None):
        super().__init__(parent)
        self.segment = segment
        self.display_mode = display_mode
        self._active = None
        self.setObjectName("TranscriptLine")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 9)
        root.setSpacing(12)
        start = getattr(segment, "start_offset", None)
        self.time_label = QLabel(format_clock((start or 0.0) * 1000) if start is not None else "--:--")
        self.time_label.setObjectName("TranscriptTime")
        self.time_label.setFixedWidth(44)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self.time_label)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(5)
        self.original = QLabel((getattr(segment, "original_text", "") or "").strip())
        self.original.setObjectName("TranscriptOriginal")
        self.original.setWordWrap(True)
        self.original.setMinimumWidth(0)
        self.original.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        translated = (getattr(segment, "translated_text", "") or "").strip()
        translation_status = getattr(segment, "translation_status", None)
        if not translated and translation_status in ("FAILED", "TIMEOUT"):
            translated = "Translation unavailable"
        self.translation = QLabel(translated)
        self.translation.setObjectName("TranscriptTranslation")
        self.translation.setWordWrap(True)
        self.translation.setMinimumWidth(0)
        self.translation.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        text_column.addWidget(self.original)
        text_column.addWidget(self.translation)
        root.addLayout(text_column, 1)
        self.set_display_mode(display_mode)
        self.set_active(False)

    def set_display_mode(self, mode):
        self.display_mode = mode if mode in ("bilingual", "original_only", "translation_only") else "bilingual"
        self.original.setVisible(self.display_mode != "translation_only")
        self.translation.setVisible(self.display_mode != "original_only")
        self.updateGeometry()
        self.geometry_changed.emit()

    def set_active(self, active):
        active = bool(active)
        if active == self._active:
            return
        self._active = active
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.original.setStyleSheet(
            "font-size: 17px; font-weight: 750; color: #fff7ed;"
            if active else
            "font-size: 14px; font-weight: 620; color: #d9d4cb;"
        )
        self.translation.setStyleSheet(
            "font-size: 15px; font-weight: 680; color: #ffae70;"
            if active else
            "font-size: 13px; color: #b98560;"
        )
        self.time_label.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #ffae70;"
            if active else
            "font-size: 10px; color: #777168;"
        )
        self.updateGeometry()
        self.geometry_changed.emit()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            start = getattr(self.segment, "start_offset", None)
            if start is not None:
                self.seek_requested.emit(float(start))
                event.accept()
                return
        super().mousePressEvent(event)


class SessionHistoryPlayer(QWidget):
    """Shows one saved session as a view-switchable, seekable transcript."""

    status_changed = pyqtSignal(str)
    display_mode_changed = pyqtSignal(str)

    def __init__(self, parent=None, language="en"):
        super().__init__(parent)
        self.language = language
        self._segments = []
        self._line_widgets: list[TranscriptLine] = []
        self._line_items: list[QListWidgetItem] = []
        self._audio_path: Path | None = None
        self._duration_ms = 0
        self._seeking = False
        self._active_index = -1
        self._session = None
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.timeout.connect(self._sync_all_line_sizes)
        self.player = LocalAudioPlayer(self)
        self.player.position_changed.connect(self._on_position_changed)
        self.player.duration_changed.connect(self._on_duration_changed)
        self.player.state_changed.connect(self._on_state_changed)
        self.player.error_occurred.connect(self._on_error)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        header_row = QHBoxLayout()
        self.header = QLabel("Select a session")
        self.header.setObjectName("HistoryTitle")
        self.header.setWordWrap(True)
        self.header.setMinimumWidth(0)
        header_row.addWidget(self.header)
        header_row.addStretch()
        self.view_mode = SegmentedControl()
        self.view_mode.addItem("Both", "bilingual")
        self.view_mode.addItem("Original", "original_only")
        self.view_mode.addItem("Translation", "translation_only")
        self.view_mode.setMaximumWidth(330)
        self.view_mode.currentIndexChanged.connect(self._change_display_mode)
        header_row.addWidget(self.view_mode)
        root.addLayout(header_row)

        self.transport = QFrame()
        self.transport.setObjectName("Transport")
        transport_layout = QHBoxLayout(self.transport)
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
        root.addWidget(self.transport)

        self.recording_hint = QLabel("This session has no recording")
        self.recording_hint.setObjectName("Muted")
        self.recording_hint.setWordWrap(True)
        root.addWidget(self.recording_hint)

        self.transcript = QListWidget()
        self.transcript.setObjectName("TranscriptTimeline")
        self.transcript.setSpacing(0)
        self.transcript.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.transcript.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.transcript.setStyleSheet(
            "QListWidget#TranscriptTimeline { padding: 4px 10px; }"
            "QListWidget#TranscriptTimeline::item { padding: 0; margin: 0; border: none; }"
        )
        root.addWidget(self.transcript, 1)
        self._update_transport_enabled()

    def _t(self, text):
        from localization import translate

        return translate(text, self.language)

    def set_language(self, language):
        """Refresh player-owned dynamic copy after an app-language switch."""
        from localization import apply_language, normalize_language

        self.language = normalize_language(language)
        apply_language(self, self.language)
        if self._session is None:
            self.header.setText(self._t("Select a session"))
            return
        self.header.setText(self._t("Session timeline"))
        metadata = getattr(self._session, "metadata", {}) or {}
        if self._audio_path and self.player.is_loaded:
            source = "Recording ready · the current subtitle will follow playback"
        elif metadata.get("record_audio"):
            source = "Recording was enabled, but the audio file is missing or empty"
        else:
            source = "This session saved subtitles only · enable ‘Subtitle + recording’ before the next session"
        self.recording_hint.setText(self._t(source))
        self.play_button.setText(self._t("Pause" if self.player.is_playing() else "Play"))

    def current_display_mode(self):
        return self.view_mode.currentData() or "bilingual"

    def current_audio_path(self):
        return self._audio_path

    def current_session(self):
        return self._session

    def clear_session(self, message="Select a saved session to read it here."):
        self.player.unload()
        self._segments = []
        self._line_widgets = []
        self._line_items = []
        self._audio_path = None
        self._duration_ms = 0
        self._active_index = -1
        self._session = None
        self.header.setText(self._t("Select a session"))
        self.transcript.clear()
        self.recording_hint.setText(message)
        self.timeline.setRange(0, 0)
        self.position_label.setText("00:00")
        self.duration_label.setText("00:00")
        self._update_transport_enabled()

    def set_session(self, session, segments):
        self.player.unload()
        self._session = session
        self._segments = list(segments or [])
        self._line_widgets = []
        self._line_items = []
        self._active_index = -1
        metadata = getattr(session, "metadata", {}) or {}
        self.header.setText(self._t("Session timeline"))
        self._render_transcript()

        raw_path = metadata.get("audio_path") if metadata.get("record_audio") else None
        path = Path(raw_path).expanduser() if raw_path else None
        self._audio_path = path if path and path.is_file() else None
        duration = float(metadata.get("audio_duration") or 0.0)
        self._duration_ms = max(0, round(duration * 1000))
        self.timeline.setRange(0, self._duration_ms)
        self.duration_label.setText(format_clock(self._duration_ms))
        self.position_label.setText("00:00")

        if self._audio_path and self.player.load(self._audio_path):
            self.recording_hint.setText(self._t("Recording ready · the current subtitle will follow playback"))
        elif metadata.get("record_audio"):
            self.recording_hint.setText(self._t("Recording was enabled, but the audio file is missing or empty"))
        else:
            self.recording_hint.setText(
                self._t("This session saved subtitles only · enable ‘Subtitle + recording’ before the next session")
            )
        self._update_transport_enabled()

    def _render_transcript(self):
        self.transcript.clear()
        self._line_widgets = []
        self._line_items = []
        mode = self.current_display_mode()
        for segment in self._segments:
            item = QListWidgetItem()
            line = TranscriptLine(segment, mode)
            line.seek_requested.connect(self._seek_to_seconds)
            line.geometry_changed.connect(
                lambda current_item=item, current_line=line: self._sync_line_size(current_item, current_line)
            )
            item.setSizeHint(line.sizeHint())
            self.transcript.addItem(item)
            self.transcript.setItemWidget(item, line)
            self._line_items.append(item)
            self._line_widgets.append(line)

        self._schedule_reflow()

        if not self._segments:
            empty = QListWidgetItem(self._t("No subtitle lines were saved in this session."))
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.transcript.addItem(empty)

    def _change_display_mode(self, *_):
        mode = self.current_display_mode()
        for item, line in zip(self._line_items, self._line_widgets):
            line.set_display_mode(mode)
            item.setSizeHint(line.sizeHint())
        self.display_mode_changed.emit(mode)

    def _sync_line_size(self, item, line):
        width = self._available_line_width()
        line.setFixedWidth(width)
        line.layout().activate()
        height = line.layout().heightForWidth(width)
        if height < 0:
            height = line.sizeHint().height()
        height = max(48, height)
        line.resize(width, height)
        item.setSizeHint(QSize(width, height))

    def _sync_all_line_sizes(self):
        for item, line in zip(self._line_items, self._line_widgets):
            self._sync_line_size(item, line)

    def _available_line_width(self):
        viewport_width = self.transcript.viewport().width()
        # Never force a line wider than its viewport.  This is what previously
        # produced a horizontal scrollbar and apparently huge transcript text
        # after the main window was narrowed.
        return max(80, viewport_width - 22)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_reflow()

    def _schedule_reflow(self):
        """Coalesce layout work in an object-owned timer.

        A parented QTimer is cancelled with the player.  This avoids queued
        Python callbacks touching transcript widgets after a window closes.
        """
        self._reflow_timer.start(0)

    def _update_transport_enabled(self):
        enabled = self._audio_path is not None and self.player.is_loaded
        self.transport.setVisible(enabled)
        self.play_button.setEnabled(enabled)
        self.timeline.setEnabled(enabled)

    def _toggle_playback(self):
        if self._audio_path is None:
            self.status_changed.emit(self._t("This session does not contain a recording"))
            return
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()

    def _begin_seek(self):
        self._seeking = True

    def _finish_seek(self):
        self._seeking = False
        self.player.seek(self.timeline.value())

    def _seek_to_seconds(self, start):
        if self._audio_path is None:
            return
        self.player.seek(max(0, round(float(start) * 1000)))
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
        self._set_active_line(active)

    def _set_active_line(self, active):
        if active == self._active_index:
            return
        self._active_index = active
        for index, (item, line) in enumerate(zip(self._line_items, self._line_widgets)):
            line.set_active(index == active)
            item.setSizeHint(line.sizeHint())
        if 0 <= active < len(self._line_items):
            item = self._line_items[active]
            self.transcript.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)

    def _on_duration_changed(self, duration):
        if duration > 0:
            self._duration_ms = duration
            self.timeline.setRange(0, duration)
            self.duration_label.setText(format_clock(duration))
        self._update_transport_enabled()

    def _on_state_changed(self, playing):
        self.play_button.setText(self._t("Pause" if playing else "Play"))

    def _on_error(self, message):
        self.recording_hint.setText(message or self._t("Unable to play this recording"))
        self.status_changed.emit(message or self._t("Unable to play this recording"))
