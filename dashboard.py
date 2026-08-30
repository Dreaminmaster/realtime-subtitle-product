from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QComboBox, QLineEdit, 
                             QSpinBox, QDoubleSpinBox, QGridLayout,
                             QScrollArea, QSizePolicy, QSpacerItem, QFormLayout, QApplication,
                             QMessageBox, QTextEdit, QDialog, QSlider,
                             QListWidget, QListWidgetItem, QSplitter, QFileDialog)
from PyQt6.QtCore import Qt, QSize, QUrl, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QDesktopServices, QFont, QIcon, QColor, QPixmap
import sys
import os
import sounddevice as sd
from config import config
from localization import apply_language, normalize_language, translate as ui_translate
from product_navigation import ProductNavigation
from ui_components import (
    ColorButton,
    ProviderSelector,
    SegmentedControl,
    SubtitlePreview,
    ThemedComboBox,
)
from session_history_player import SessionHistoryPlayer

# Use one popup implementation everywhere so menus cannot revert to the
# unreadable native light palette or clip long provider/model names.
QComboBox = ThemedComboBox

# Modern QSS Styles
STYLESHEET = """
QWidget {
    background-color: #171716;
    color: #ece9e2;
    font-family: -apple-system, 'Helvetica Neue', Arial;
    font-size: 13px;
}
QFrame#Sidebar { background: #1e1e1c; border-right: 1px solid #34332f; }
QPushButton#NavButton {
    text-align: left; color: #aaa69d; background: transparent;
    border: none; border-radius: 8px; padding: 9px 12px; font-weight: 600;
}
QPushButton#NavButton:hover { background: #2a2926; color: #f4f1ea; }
QPushButton#NavButton:checked { background: #34312b; color: #ffb36a; }
QStackedWidget#ProductStack { background: #171716; }
QFrame#SectionTabs { background: #171716; border: none; }
QFrame#Subnav { background: #1e1e1c; border-bottom: 1px solid #383631; }
QPushButton#SubnavButton {
    background: transparent; color: #aaa59b; border: none; border-radius: 7px;
    padding: 8px 13px; font-weight: 650;
}
QPushButton#SubnavButton:hover { background: #2a2926; color: #f0ece4; }
QPushButton#SubnavButton:checked { background: #3a3129; color: #ffad66; }
QLabel { font-size: 13px; background: transparent; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #262522; border: 1px solid #44413b; border-radius: 7px;
    padding: 7px 10px; min-height: 22px; color: #f0ede6;
    selection-background-color: #9b572d;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #d8874d; }
QComboBox QAbstractItemView {
    background: #282622; color: #f5f1e9; border: 1px solid #565149;
    border-radius: 8px; padding: 5px; outline: 0;
    selection-background-color: #b9612f; selection-color: #ffffff;
}
QComboBox { padding-right: 30px; }
QComboBox::drop-down {
    border: none; width: 0px; background: transparent;
}
QSpinBox, QDoubleSpinBox { padding-right: 10px; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 0px; height: 0px; border: none; background: transparent;
}
QPushButton {
    background-color: #d98246; color: #1d1712; border: none;
    padding: 8px 15px; border-radius: 7px; font-weight: 650;
}
QPushButton:hover { background-color: #eda267; }
QPushButton:disabled { background: #33312d; color: #77736b; }
QPushButton#SecondaryButton { background: #292824; color: #ddd8ce; border: 1px solid #46433d; }
QPushButton#SecondaryButton:hover { background: #34322e; }
QPushButton#DangerButton { background: #4b2c29; color: #f1b7aa; border: 1px solid #6c3e37; }
QPushButton#ProviderOption {
    background: #242320; color: #c7c1b7; border: 1px solid #45413a;
    border-radius: 10px; padding: 10px 14px; text-align: left; font-weight: 650;
}
QPushButton#ProviderOption:hover { border-color: #7a6453; color: #f3eee5; }
QPushButton#ProviderOption:checked { background: #3b2f27; color: #ffb36a; border: 1px solid #c5733b; }
QPushButton#SegmentOption {
    background: transparent; color: #aaa59b; border: none; border-radius: 7px;
    padding: 7px 10px; font-weight: 650;
}
QPushButton#SegmentOption:hover { background: #35322d; color: #f2ede5; }
QPushButton#SegmentOption:checked { background: #b9612f; color: #fff8f1; }
QPushButton#SegmentOption:disabled { background: transparent; color: #65615a; }
QFrame#ModelCard { background: #22211f; border: 1px solid #3e3b35; border-radius: 12px; }
QLabel#ModelName { color: #f2eee6; font-size: 14px; font-weight: 700; }
QLabel#ModelMeta { color: #b2aca2; font-size: 11px; }
QLabel#ModelBestFor { color: #d49a6f; font-size: 11px; }
QLabel#RecommendedPill { color: #9fd3ad; background: #243329; border: 1px solid #395340; border-radius: 8px; padding: 3px 7px; }
QPushButton#ModelInstalled { background: #26362b; color: #a8ddb5; border: 1px solid #3d5b45; }
QPushButton#ModelDownload { background: #d98246; color: #1d1712; }
QFrame#HeroCard, QFrame#SummaryCard, QFrame#SettingsCard {
    background: #22211f; border: 1px solid #3a3833; border-radius: 12px;
}
QFrame#Workbench { background: #211f1c; border: 1px solid #3d3933; border-radius: 18px; }
QFrame#ControlColumn { background: transparent; border: none; }
QFrame#SettingStrip { background: #1e1d1a; border: 1px solid #34322e; border-radius: 12px; }
QFrame#SubtitlePreviewStage { background: #151514; border: 1px solid #34322e; border-radius: 14px; }
QFrame#Transport { background: #22211f; border: 1px solid #3d3933; border-radius: 11px; }
QFrame#TranscriptLine { background: transparent; border: none; border-bottom: 1px solid #302e2a; }
QFrame#TranscriptLine[active="true"] { background: #2b241e; border-left: 3px solid #d98246; }
QLabel#HistoryTitle { color: #f3efe7; font-size: 18px; font-weight: 700; }
QLabel#HeroTitle { color: #f6f2e9; font-size: 24px; font-weight: 700; }
QLabel#HeroCopy, QLabel#Muted { color: #b6b0a6; font-size: 12px; }
QLabel#StatusPill {
    color: #b9dfc0; background: #243329; border: 1px solid #395340;
    border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: 650;
}
QLabel#SummaryLabel { color: #858078; font-size: 10px; font-weight: 700; }
QLabel#SummaryValue { color: #ece9e2; font-size: 14px; font-weight: 600; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: #514d46; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTextEdit { background: #121211; color: #dedad1; border: 1px solid #3f3c37; border-radius: 8px; padding: 9px; }
QListWidget { background: #1d1c1a; color: #e9e4da; border: 1px solid #403d37; border-radius: 10px; padding: 6px; }
QListWidget::item { padding: 10px; border-radius: 7px; }
QListWidget::item:selected { background: #44352b; color: #ffbd80; }
QSlider::groove:horizontal { height: 5px; background: #46423b; border-radius: 2px; }
QSlider::handle:horizontal { width: 17px; margin: -6px 0; background: #ec9251; border-radius: 8px; }
QGroupBox { border: 1px solid #3f3c37; border-radius: 9px; margin-top: 12px; padding-top: 12px; }
QGroupBox::title { subcontrol-origin: margin; padding: 0 7px; color: #d99a69; }
"""

class Dashboard(QWidget):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    model_download_status = pyqtSignal(str, str, int)
    model_download_done = pyqtSignal(str, int, object, int)  # (model_id, terminal_state, error, attempt)
    progress_event = pyqtSignal(object)  # ProgressEvent — update ProgressPanel
    translation_test_finished = pyqtSignal(int, bool, str)
    model_list_finished = pyqtSignal(bool, object, str)
    model_search_finished = pyqtSignal(bool, object, str)

    FORCE_QUIT = "force_quit"
    RETRY = "retry"
    CANCEL = "cancel"
    
    def _show_stop_timeout_dialog(self):
        """Show timeout dialog, returns FORCE_QUIT / RETRY / CANCEL."""
        reply = QMessageBox.critical(
            self, "Stop Timeout",
            "Realtime Subtitle could not stop cleanly.\n"
            "The speech worker is still running.\n\n"
            "• Retry — give more time to finish\n"
            "• Force Quit — kill the process now\n"
            "• Cancel — keep window open",
            QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Abort | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Retry
        )
        if reply == QMessageBox.StandardButton.Retry:
            return self.RETRY
        elif reply == QMessageBox.StandardButton.Abort:
            return self.FORCE_QUIT
        return self.CANCEL
    
    def _attempt_close_after_stop(self):
        """Try stop; on timeout, offer retry/force/cancel. Returns True if cleaned up."""
        success = self.on_stop()
        if success:
            return True
        while True:
            action = self._show_stop_timeout_dialog()
            if action == self.CANCEL:
                return False
            if action == self.FORCE_QUIT:
                import logging, signal, os
                log = logging.getLogger("RealtimeSubtitle")
                log.critical("Force quit requested by user")
                logging.shutdown()
                os.kill(os.getpid(), signal.SIGTERM)
                return False
            # RETRY: try again
            success = self.on_stop()
            if success:
                return True
    
    def closeEvent(self, event):
        """Hide the control center during a session; quit only on a real app exit."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")

        # On macOS the red traffic-light button closes a window, not
        # necessarily the application.  While captions are running, treating
        # that action as Stop is surprising: keep the overlay alive and hide
        # only this control-center window.  QApplication.quit()/Cmd-Q sends a
        # non-spontaneous close event and still follows the cleanup path below.
        session_active = getattr(self, "pipeline", None) is not None
        startup_active = (
            hasattr(self, "startup_worker")
            and self.startup_worker is not None
            and self.startup_worker.isRunning()
        )
        if event.spontaneous() and (session_active or startup_active):
            log.info("Control center closed during active session — hiding only")
            event.ignore()
            self._hide_control_center_for_session()
            return

        # Cancel all active downloads
        if hasattr(self, '_active_downloads'):
            for mid, task in list(self._active_downloads.items()):
                log.info(f"Cancelling download: {mid}")
                task.cancel()
            self._active_downloads.clear()
        
        if not hasattr(self, 'pipeline') or self.pipeline is None:
            event.accept()
            QApplication.quit()
            return
        self._set_localized_text(self.status_label, "Stopping…")
        if self._attempt_close_after_stop():
            log.info("Clean stop before close — quitting")
            event.accept()
            QApplication.quit()
        else:
            event.ignore()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Realtime Subtitle")
        self.setMinimumSize(900, 600)
        self.resize(1040, 720)
        self.setStyleSheet(STYLESHEET)
        self.ui_language = normalize_language(getattr(config, "ui_language", "en"))
        self._did_fit_to_screen = False
        self._control_center_hidden_for_session = False
        self._translation_test_generation = 0
        self._translation_test_fingerprint = None
        
        # Main Layout
        self.layout = QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        
        # ---- Create UI elements BEFORE any tab that needs them ----
        self._active_downloads = {}
        self._progress_model_id = None
        self._progress_backend = None
        self._accuracy_download_model_id = None
        self._accuracy_download_error = None
        self._pending_start_after_accuracy_download = False
        
        from progress_panel import ProgressPanel
        self.progress_panel = ProgressPanel()
        self.progress_panel.setVisible(False)
        self.progress_panel.retry_clicked.connect(self._retry_progress_model)
        self.progress_panel.cancel_clicked.connect(self._cancel_progress_model)
        self.progress_panel.dismiss_clicked.connect(self._dismiss_progress_panel)
        
        # Five product sections; related settings are grouped internally.
        self.tabs = ProductNavigation()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.layout.addWidget(self.tabs)
        
        self.init_home_tab()
        self.init_history_tab()
        self.init_audio_tab()
        self.init_transcription_tab()
        self.init_translation_tab()
        self.init_model_tab()
        self.init_style_tab()
        self.init_diagnostics_tab()
        
        # Connect download signals (must be done after handlers are defined)
        self.model_download_status.connect(self._on_model_status)
        self.model_download_done.connect(self._on_model_done)
        self.progress_event.connect(self.progress_panel.set_progress)
        self.translation_test_finished.connect(self._on_translation_test_finished)
        self.model_list_finished.connect(self._on_model_list_finished)
        self.model_search_finished.connect(self._on_model_search_finished)
        apply_language(self, self.ui_language)
        self._update_accuracy_plan_ui()

    def _set_localized_text(self, widget, source):
        """Set dynamic text while retaining a reversible source string."""
        widget.setProperty("i18n_source_text", source)
        widget.setText(ui_translate(source, self.ui_language))

    def showEvent(self, event):
        """Fit the first launch to the current display without clipping."""
        super().showEvent(event)
        if not self._did_fit_to_screen:
            self._did_fit_to_screen = True
            QTimer.singleShot(0, self._fit_to_screen)

    def _fit_to_screen(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        width = min(max(760, self.width()), max(760, int(available.width() * 0.92)))
        height = min(max(520, self.height()), max(520, int(available.height() * 0.90)))
        self.resize(width, height)
        self.move(
            available.x() + max(0, (available.width() - width) // 2),
            available.y() + max(0, (available.height() - height) // 2),
        )

    def init_home_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)

        heading = QLabel("Live subtitles")
        heading.setObjectName("HeroTitle")
        layout.addWidget(heading)
        copy = QLabel("Start once, then keep only the floating subtitles above your other apps.")
        copy.setObjectName("HeroCopy")
        layout.addWidget(copy)

        workbench = QFrame()
        workbench.setObjectName("Workbench")
        workbench_layout = QHBoxLayout(workbench)
        workbench_layout.setContentsMargins(24, 24, 24, 24)
        workbench_layout.setSpacing(24)

        controls = QFrame()
        controls.setObjectName("ControlColumn")
        hero_layout = QVBoxLayout(controls)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(13)
        eyebrow = QLabel("CAPTION SESSION")
        eyebrow.setObjectName("SummaryLabel")
        hero_layout.addWidget(eyebrow)
        prompt = QLabel("Ready when you are")
        prompt.setStyleSheet("font-size: 21px; font-weight: 700; color: #f4f0e7;")
        hero_layout.addWidget(prompt)
        explanation = QLabel("Audio remains on this Mac. Saved sessions can keep a transcript and an optional recording.")
        explanation.setObjectName("Muted")
        explanation.setWordWrap(True)
        hero_layout.addWidget(explanation)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.start_btn = QPushButton("Start Live Subtitles")
        self.start_btn.setMinimumSize(205, 44)
        self.start_btn.clicked.connect(self.on_start)
        action_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Session")
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.setMinimumSize(145, 44)
        self.stop_btn.clicked.connect(self.on_stop)
        self.stop_btn.hide()
        action_row.addWidget(self.stop_btn)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("StatusPill")
        action_row.addWidget(self.status_label)
        action_row.addStretch()
        hero_layout.addLayout(action_row)

        mode_label = QLabel("Session type")
        mode_label.setObjectName("SummaryLabel")
        hero_layout.addWidget(mode_label)
        self.session_mode_combo = SegmentedControl()
        self.session_mode_combo.addItem("Temporary", "temporary")
        self.session_mode_combo.addItem("Save subtitles", "saved_text")
        self.session_mode_combo.addItem("Subtitles + recording", "saved_recording")
        configured_choice = (
            "temporary"
            if getattr(config, "session_mode", "saved") == "temporary"
            else (
                "saved_recording"
                if bool(getattr(config, "record_session_audio", False))
                else "saved_text"
            )
        )
        self.session_mode_combo.setCurrentIndex(max(0, self.session_mode_combo.findData(configured_choice)))
        self.session_mode_combo.setToolTip(
            "Choose exactly what remains on this Mac after the session."
        )
        self.session_mode_combo.currentIndexChanged.connect(self._on_session_mode_changed)
        hero_layout.addWidget(self.session_mode_combo)
        self.record_audio_hint = QLabel("")
        self.record_audio_hint.setObjectName("Muted")
        self.record_audio_hint.setWordWrap(True)
        hero_layout.addWidget(self.record_audio_hint)
        hero_layout.addStretch()
        workbench_layout.addWidget(controls, 5)

        self.live_preview = SubtitlePreview()
        self.live_preview.set_preview_style(self._current_appearance_style_from_config())
        workbench_layout.addWidget(self.live_preview, 6)
        layout.addWidget(workbench, 1)

        strip = QFrame()
        strip.setObjectName("SettingStrip")
        summaries = QHBoxLayout(strip)
        summaries.setContentsMargins(17, 11, 17, 11)
        summaries.setSpacing(14)
        summary_values = (
            (
                "INPUT",
                "System audio"
                if getattr(config, "input_source", "microphone") == "system_audio"
                else (
                    "Default microphone"
                    if config.device_index is None
                    else str(config.device_index)
                ),
            ),
            ("RECOGNITION", f"Whisper · {config.whisper_model}"),
            (
                "TRANSLATION",
                "Off" if config.translation_mode == "off" else config.target_lang,
            ),
        )
        for index, (label_text, value_text) in enumerate(summary_values):
            card = QWidget()
            card.setStyleSheet("background: transparent;")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(5, 2, 5, 2)
            card_layout.setSpacing(3)
            label = QLabel(label_text)
            label.setObjectName("SummaryLabel")
            value = QLabel(value_text)
            value.setObjectName("SummaryValue")
            value.setWordWrap(True)
            card_layout.addWidget(label)
            card_layout.addWidget(value)
            summaries.addWidget(card, 1)
            if index < len(summary_values) - 1:
                divider = QFrame()
                divider.setFrameShape(QFrame.Shape.VLine)
                divider.setStyleSheet("color: #36332f;")
                summaries.addWidget(divider)
        layout.addWidget(strip)

        self.tabs.addTab(tab, "Home")
        self._on_session_mode_changed()

    def _current_appearance_style_from_config(self):
        return {
            "original_font_size": getattr(config, "original_font_size", 20),
            "translation_font_size": getattr(config, "translation_font_size", 17),
            "original_color": getattr(config, "original_color", "#ffffff"),
            "translation_color": getattr(config, "translation_color", "#d99a69"),
            "window_opacity": getattr(config, "window_opacity", 0.94),
            "window_width": getattr(config, "window_width", 620),
            "visible_subtitles": getattr(config, "visible_subtitles", 3),
            "display_mode": getattr(config, "display_mode", "bilingual"),
        }

    def _on_session_mode_changed(self, *_):
        choice = self.session_mode_combo.currentData() or "temporary"
        messages = {
            "temporary": "Temporary captions leave no transcript or recording.",
            "saved_text": "Saves subtitles only. This session will not have audio playback.",
            "saved_recording": "Saves subtitles and a playable recording locally on this Mac.",
        }
        self._set_localized_text(self.record_audio_hint, messages.get(choice, messages["temporary"]))

    def init_history_tab(self):
        """Chat-style local transcript library with saved/temporary sessions."""
        tab = QWidget()
        root = QVBoxLayout(tab)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("Session History")
        title.setObjectName("HeroTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        refresh = QPushButton("Refresh")
        refresh.setObjectName("SecondaryButton")
        refresh.clicked.connect(self._refresh_history)
        title_row.addWidget(refresh)
        self.history_export_btn = QPushButton("Export")
        self.history_export_btn.setObjectName("SecondaryButton")
        self.history_export_btn.clicked.connect(self._export_history_session)
        title_row.addWidget(self.history_export_btn)
        self.history_delete_btn = QPushButton("Delete")
        self.history_delete_btn.setObjectName("DangerButton")
        self.history_delete_btn.clicked.connect(self._delete_history_session)
        title_row.addWidget(self.history_delete_btn)
        root.addLayout(title_row)

        hint = QLabel("Saved sessions stay only on this Mac. Choose Temporary on Live for a session that leaves no history.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        root.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.history_list = QListWidget()
        self.history_list.setMinimumWidth(220)
        self.history_list.currentItemChanged.connect(self._show_history_session)
        splitter.addWidget(self.history_list)
        self.history_player = SessionHistoryPlayer(language=self.ui_language)
        self.history_player.status_changed.connect(self._set_history_status)
        splitter.addWidget(self.history_player)
        splitter.setSizes([260, 650])
        root.addWidget(splitter, 1)

        self.history_status = QLabel("")
        self.history_status.setObjectName("Muted")
        root.addWidget(self.history_status)
        self.tabs.addTab(tab, "History")
        self._refresh_history()

    def _open_history_repository(self):
        from src.session_repository import SQLiteSessionRepository, get_default_database_path
        repo = SQLiteSessionRepository(get_default_database_path())
        repo.initialize()
        return repo

    def _refresh_history(self):
        selected = self.history_list.currentItem().data(Qt.ItemDataRole.UserRole) if self.history_list.currentItem() else None
        self.history_list.clear()
        try:
            from datetime import datetime
            repo = self._open_history_repository()
            sessions = repo.list_sessions(limit=100)
            repo.close()
            language_names = {
                "auto": "Automatic",
                "en": "English",
                "english": "English",
                "zh": "Chinese",
                "zh-cn": "Chinese",
                "chinese": "Chinese",
                "ja": "Japanese",
                "japanese": "Japanese",
                "fr": "French",
                "french": "French",
                "es": "Spanish",
                "spanish": "Spanish",
                "de": "German",
                "german": "German",
                "ko": "Korean",
                "korean": "Korean",
            }
            for session in sessions:
                stamp = datetime.fromtimestamp(session["created_at"]).strftime("%Y-%m-%d  %H:%M")
                values = []
                for raw in (session.get("source_language"), session.get("target_language")):
                    if raw:
                        source = language_names.get(str(raw).lower(), str(raw))
                        values.append(ui_translate(source, self.ui_language))
                languages = " → ".join(values)
                item = QListWidgetItem(
                    f"{stamp}\n{languages or ui_translate('Live subtitles', self.ui_language)}"
                )
                item.setData(Qt.ItemDataRole.UserRole, session["session_id"])
                self.history_list.addItem(item)
                if session["session_id"] == selected:
                    self.history_list.setCurrentItem(item)
            if self.history_list.count() and self.history_list.currentRow() < 0:
                self.history_list.setCurrentRow(0)
            self.history_status.setText(
                f"已保存 {len(sessions)} 个会话"
                if self.ui_language == "zh-Hans"
                else f"{len(sessions)} saved session(s)"
            )
            if not sessions:
                self.history_player.clear_session(
                    ui_translate(
                        "No saved sessions yet. Start Live with ‘Saved session’ selected.",
                        self.ui_language,
                    )
                )
        except Exception as exc:
            self.history_status.setText(f"History unavailable: {exc}")

    def _set_history_status(self, message):
        self.history_status.setText(message)

    def _show_history_session(self, current, previous=None):
        del previous
        if current is None:
            return
        try:
            from src.segment_api import SegmentAPI
            repo = self._open_history_repository()
            snapshot = SegmentAPI(repo).get_session_snapshot(current.data(Qt.ItemDataRole.UserRole))
            repo.close()
            if snapshot:
                self.history_player.set_session(snapshot.session, snapshot.segments)
            else:
                self.history_player.clear_session("This session is unavailable.")
        except Exception as exc:
            self.history_player.clear_session(f"Unable to read this session: {exc}")

    def _delete_history_session(self):
        item = self.history_list.currentItem()
        if item is None:
            return
        reply = QMessageBox.question(self, "Delete Session", "Delete this saved transcript?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            repo = self._open_history_repository()
            session_id = item.data(Qt.ItemDataRole.UserRole)
            session = repo.get_session(session_id)
            repo.delete_session(session_id)
            repo.close()
            if session:
                import json
                from session_recording import delete_session_recording
                try:
                    metadata = json.loads(session.get("metadata_json") or "{}")
                except (TypeError, ValueError):
                    metadata = {}
                delete_session_recording(metadata.get("audio_path"))
            self._refresh_history()

    def _export_history_session(self):
        item = self.history_list.currentItem()
        if item is None:
            self.history_status.setText("Select one session before exporting.")
            return
        from datetime import datetime
        from pathlib import Path
        from session_export import (
            SessionExportDialog,
            copy_audio_export,
            write_bundle,
            write_text_export,
        )
        from src.segment_api import SegmentAPI

        session_id = item.data(Qt.ItemDataRole.UserRole)
        repo = self._open_history_repository()
        api = SegmentAPI(repo)
        try:
            snapshot = api.get_session_snapshot(session_id)
            display_mode = self.history_player.current_display_mode()
            text = (
                api.export_transcript(
                    session_id,
                    format="txt",
                    display_mode=display_mode,
                )
                if snapshot is not None else ""
            )
        finally:
            repo.close()
        if snapshot is None:
            self.history_status.setText("The selected session is no longer available.")
            return

        from session_recording import inspect_session_recording

        metadata = snapshot.session.metadata or {}
        recording = inspect_session_recording(metadata.get("audio_path") or "")
        audio_path = recording.path if metadata.get("record_audio") and recording.playable else None
        dialog = SessionExportDialog(
            display_mode=display_mode,
            has_audio=bool(audio_path and audio_path.is_file()),
            parent=self,
        )
        apply_language(dialog, self.ui_language)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        stamp = datetime.fromtimestamp(snapshot.session.created_at).strftime("%Y-%m-%d %H-%M")
        stem = f"Realtime Subtitle {stamp}"
        choice = dialog.export_choice()
        try:
            if choice == "text":
                path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Export transcript",
                    f"{stem}.txt",
                    "Text files (*.txt)",
                )
                if not path:
                    return
                if not path.lower().endswith(".txt"):
                    path += ".txt"
                result = write_text_export(path, text)
                exported_to = result.text_path
            elif choice == "audio":
                path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Export recording",
                    f"{stem}.wav",
                    "Wave audio (*.wav)",
                )
                if not path:
                    return
                if not path.lower().endswith(".wav"):
                    path += ".wav"
                result = copy_audio_export(audio_path, path)
                exported_to = result.audio_path
            else:
                directory = QFileDialog.getExistingDirectory(self, "Export transcript and recording")
                if not directory:
                    return
                result = write_bundle(directory, stem, text, audio_path)
                exported_to = result.text_path.parent
            self.history_status.setText(f"Exported selected session to {exported_to}")
        except Exception as exc:
            self.history_status.setText(f"Export failed: {exc}")

    def init_audio_tab(self):
        tab = QWidget()
        form_host = QWidget()
        form_host.setMaximumWidth(900)
        layout = QGridLayout(form_host)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(15)

        layout.addWidget(QLabel("Input Source:"), 0, 0)
        self.input_source_combo = QComboBox()
        self.input_source_combo.addItem("Microphone", "microphone")
        self.input_source_combo.addItem("System audio (built in)", "system_audio")
        source_index = self.input_source_combo.findData(
            getattr(config, "input_source", "microphone")
        )
        self.input_source_combo.setCurrentIndex(max(0, source_index))
        self.input_source_combo.currentIndexChanged.connect(self._on_input_source_changed)
        layout.addWidget(self.input_source_combo, 0, 1, 1, 2)

        self.system_audio_hint = QLabel(
            "Uses macOS ScreenCaptureKit. No BlackHole or virtual audio device is required."
        )
        self.system_audio_hint.setObjectName("Muted")
        self.system_audio_hint.setWordWrap(True)
        layout.addWidget(self.system_audio_hint, 1, 1, 1, 2)

        # Device Selection
        self.device_label = QLabel("Input Device:")
        layout.addWidget(self.device_label, 2, 0)
        self.device_combo = QComboBox()
        self.device_combo.setMaximumWidth(620)
        self.populate_devices()
        layout.addWidget(self.device_combo, 2, 1)
        
        # Refresh Button
        self.audio_refresh_btn = QPushButton("Refresh")
        self.audio_refresh_btn.setObjectName("SecondaryButton")
        self.audio_refresh_btn.setFixedWidth(90)
        self.audio_refresh_btn.clicked.connect(self.populate_devices)
        layout.addWidget(self.audio_refresh_btn, 2, 2)
        
        # Sample Rate
        layout.addWidget(QLabel("Sample Rate:"), 3, 0)
        self.sample_rate = QSpinBox()
        self.sample_rate.setMaximumWidth(260)
        self.sample_rate.setRange(8000, 48000)
        self.sample_rate.setValue(config.sample_rate)
        layout.addWidget(self.sample_rate, 3, 1)

        # Silence Threshold
        layout.addWidget(QLabel("Silence Threshold:"), 4, 0)
        self.silence_thresh = QDoubleSpinBox()
        self.silence_thresh.setMaximumWidth(260)
        self.silence_thresh.setRange(0.001, 1.0)
        self.silence_thresh.setSingleStep(0.001)
        self.silence_thresh.setDecimals(3)
        self.silence_thresh.setValue(config.silence_threshold)
        layout.addWidget(self.silence_thresh, 4, 1)
        
        layout.addWidget(QLabel("Silence Duration (s):"), 5, 0)
        self.silence_dur = QDoubleSpinBox()
        self.silence_dur.setRange(0.4, 2.0)
        self.silence_dur.setSingleStep(0.1)
        self.silence_dur.setDecimals(1)
        self.silence_dur.setMaximumWidth(260)
        self.silence_dur.setValue(config.silence_duration)
        layout.addWidget(self.silence_dur, 5, 1)
        
        layout.setRowStretch(6, 1)
        
        outer = QHBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()
        outer.addWidget(form_host, 1)
        outer.addStretch()
        self.tabs.addTab(tab, "Audio")
        self._on_input_source_changed()

    def _on_input_source_changed(self):
        system_audio = self.input_source_combo.currentData() == "system_audio"
        self.device_label.setEnabled(not system_audio)
        self.device_combo.setEnabled(not system_audio)
        self.audio_refresh_btn.setEnabled(not system_audio)
        self.system_audio_hint.setVisible(system_audio)

    def init_device_manager_tab(self):
        """Audio Device Manager - Create/Manage Multi-Output Devices"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Header
        header = QLabel("Audio Device Manager")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #fab387;")
        layout.addWidget(header)
        
        info = QLabel("Create multi-output devices to capture system audio + hear it through speakers")
        info.setStyleSheet("color: #6c7086; font-size: 12px; font-style: italic;")
        layout.addWidget(info)
        
        # Available Devices List
        devices_label = QLabel("Available Output Devices:")
        layout.addWidget(devices_label)
        
        self.output_devices_list = QComboBox()
        self.output_devices_list.setMinimumHeight(30)
        layout.addWidget(self.output_devices_list)
        
        # Virtual Device List
        virtual_label = QLabel("Virtual/BlackHole Devices:")
        layout.addWidget(virtual_label)
        
        self.virtual_devices_list = QComboBox()
        self.virtual_devices_list.setMinimumHeight(30)
        layout.addWidget(self.virtual_devices_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.refresh_devices_btn = QPushButton("Refresh Devices")
        self.refresh_devices_btn.clicked.connect(self.refresh_audio_devices)
        btn_layout.addWidget(self.refresh_devices_btn)
        
        self.create_multi_output_btn = QPushButton("Create Multi-Output Device")
        self.create_multi_output_btn.setStyleSheet("""
            background-color: #a6e3a1; color: #1e1e2e; font-weight: bold;
        """)
        self.create_multi_output_btn.clicked.connect(self.create_multi_output_device)
        btn_layout.addWidget(self.create_multi_output_btn)
        
        layout.addLayout(btn_layout)
        
        # Set as Default Button
        self.set_default_btn = QPushButton("Set Selected as Default Output")
        self.set_default_btn.clicked.connect(self.set_default_output_device)
        layout.addWidget(self.set_default_btn)
        
        # Status
        self.device_status = QLabel("Ready")
        self.device_status.setStyleSheet("color: #a6e3a1; font-style: italic; padding: 10px;")
        layout.addWidget(self.device_status)
        
        # Help text
        help_text = QLabel(
            "<b>How to use:</b><br>"
            "1. Select your speakers from 'Available Output Devices'<br>"
            "2. Select BlackHole from 'Virtual Devices'<br>"
            "3. Click 'Create Multi-Output Device'<br>"
            "   • Audio MIDI Setup will open with instructions<br>"
            "   • Follow the step-by-step guide in the terminal/console<br>"
            "4. The new device lets you hear audio AND capture it!<br>"
            "<br><i>Note: Accessibility permissions may be required for automation.<br>"
            "Without permissions, you'll see manual instructions (very easy!).</i>"
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("background-color: #313244; padding: 10px; border-radius: 5px; font-size: 12px;")
        layout.addWidget(help_text)
        
        layout.addStretch()
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Devices")
        self.tabs.setTabToolTip(self.tabs.count() - 1, "Devices — multi-output setup")
        
        # Initial population
        self.refresh_audio_devices()

    def refresh_audio_devices(self):
        """Refresh the list of audio devices"""
        try:
            import platform
            if platform.system() != "Darwin":
                self.device_status.setText("⚠️ Device Manager only available on macOS")
                self.device_status.setStyleSheet("color: #fab387;")
                return
            
            from audio_device_manager import AudioDeviceManager
            manager = AudioDeviceManager()
            
            # Get output devices
            output_devices = manager.get_output_devices()
            self.output_devices_list.clear()
            for device in output_devices:
                self.output_devices_list.addItem(f"{device['name']}", device['id'])
            
            # Get virtual/BlackHole devices
            virtual_devices = manager.get_virtual_devices()
            self.virtual_devices_list.clear()
            if not virtual_devices:
                self.virtual_devices_list.addItem("No BlackHole device found - Please install it")
                self.device_status.setText("⚠️ BlackHole not found. Install: brew install blackhole-2ch")
                self.device_status.setStyleSheet("color: #fab387;")
            else:
                for device in virtual_devices:
                    self.virtual_devices_list.addItem(f"{device['name']}", device['id'])
                self.device_status.setText("✅ Devices loaded successfully")
                self.device_status.setStyleSheet("color: #a6e3a1;")
                
        except ImportError:
            self.device_status.setText("⚠️ Audio device management requires PyObjC (pip install pyobjc-framework-CoreAudio)")
            self.device_status.setStyleSheet("color: #f38ba8;")
        except Exception as e:
            self.device_status.setText(f"❌ Error: {str(e)}")
            self.device_status.setStyleSheet("color: #f38ba8;")
    
    def create_multi_output_device(self):
        """Create a multi-output device combining speakers + BlackHole"""
        try:
            from audio_device_manager import AudioDeviceManager
            manager = AudioDeviceManager()
            
            output_device_id = self.output_devices_list.currentData()
            virtual_device_id = self.virtual_devices_list.currentData()
            
            if not output_device_id or not virtual_device_id:
                self.device_status.setText("⚠️ Please select both devices")
                self.device_status.setStyleSheet("color: #fab387;")
                return
            
            # Show instruction dialog
            self._show_multi_output_instructions()
            
            # Call the audio device manager to open Audio MIDI Setup
            device_name = f"Translator Multi-Output"
            success = manager.create_multi_output_device(
                device_name,
                [output_device_id, virtual_device_id],
                silent=True  # Suppress console output, show GUI dialog instead
            )
            
            if success:
                self.device_status.setText(f"✅ Audio MIDI Setup opened - Follow the instructions!")
                self.device_status.setStyleSheet("color: #a6e3a1;")
                # Refresh after user has time to create the device
                QTimer = __import__('PyQt6.QtCore', fromlist=['QTimer']).QTimer
                QTimer.singleShot(3000, self.refresh_audio_devices)
            else:
                self.device_status.setText("❌ Failed to open Audio MIDI Setup")
                self.device_status.setStyleSheet("color: #f38ba8;")
                
        except Exception as e:
            self.device_status.setText(f"❌ Error: {str(e)}")
            self.device_status.setStyleSheet("color: #f38ba8;")
    
    def _show_multi_output_instructions(self):
        """Show a dialog with step-by-step instructions"""
        dialog = QDialog(self)
        dialog.setWindowTitle("🎵 Create Multi-Output Device - Instructions")
        dialog.setMinimumSize(600, 500)
        dialog.setStyleSheet(STYLESHEET)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Step-by-Step Guide")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #89b4fa; padding: 10px;")
        layout.addWidget(title)
        
        # Instructions text
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 15px;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        
        output_device = self.output_devices_list.currentText()
        virtual_device = self.virtual_devices_list.currentText()
        
        instructions_html = f"""
        <div style='font-family: Arial;'>
        <h3 style='color: #fab387;'>✨ Audio MIDI Setup is opening...</h3>
        
        <p style='color: #a6adc8;'><b>Follow these simple steps:</b></p>
        
        <div style='background: #313244; padding: 12px; border-radius: 6px; margin: 10px 0;'>
        <p style='color: #89b4fa; font-weight: bold;'>👉 Step 1: Find the Plus Button</p>
        <p>In the Audio MIDI Setup window, look at the <b>bottom-left corner</b>.<br>
        Click the <span style='background: #45475a; padding: 2px 8px; border-radius: 3px;'>[+]</span> button.</p>
        </div>
        
        <div style='background: #313244; padding: 12px; border-radius: 6px; margin: 10px 0;'>
        <p style='color: #89b4fa; font-weight: bold;'>👉 Step 2: Create Multi-Output</p>
        <p>From the menu that appears, select:<br>
        <span style='color: #a6e3a1; font-weight: bold;'>“Create Multi-Output Device”</span></p>
        </div>
        
        <div style='background: #313244; padding: 12px; border-radius: 6px; margin: 10px 0;'>
        <p style='color: #89b4fa; font-weight: bold;'>👉 Step 3: Select Devices</p>
        <p>Check the boxes for these devices:<br>
        ✅ <span style='color: #f9e2af;'>{output_device}</span> (your speakers)<br>
        ✅ <span style='color: #f9e2af;'>{virtual_device}</span> (for capturing)</p>
        </div>
        
        <div style='background: #313244; padding: 12px; border-radius: 6px; margin: 10px 0;'>
        <p style='color: #89b4fa; font-weight: bold;'>👉 Step 4: Configure Drift Correction</p>
        <p><b style='color: #f38ba8;'>IMPORTANT:</b> Uncheck <b>“Drift Correction”</b> for <span style='color: #f9e2af;'>{output_device}</span><br>
        (This allows you to hear the audio through your speakers)</p>
        </div>
        
        <div style='background: #313244; padding: 12px; border-radius: 6px; margin: 10px 0;'>
        <p style='color: #89b4fa; font-weight: bold;'>👉 Step 5: Set as Default Output</p>
        <p>Go to <b>System Settings → Sound</b><br>
        Set the new <span style='color: #a6e3a1;'>Multi-Output Device</span> as your output device.</p>
        </div>
        
        <hr style='border: 1px solid #45475a; margin: 15px 0;'>
        
        <p style='color: #6c7086; font-style: italic;'>
        💡 <b>Tip:</b> You only need to do this once! The device will persist across reboots.<br>
        After setup, you'll hear audio normally while the translator captures it in real-time.
        </p>
        </div>
        """
        
        instructions.setHtml(instructions_html)
        layout.addWidget(instructions)
        
        # Close button
        close_btn = QPushButton("Got it")
        close_btn.setFixedHeight(40)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e2e;
                font-weight: bold;
                font-size: 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #b4e4b4;
            }
        """)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def set_default_output_device(self):
        """Set the selected device as system default output"""
        try:
            from audio_device_manager import AudioDeviceManager
            manager = AudioDeviceManager()
            
            device_id = self.output_devices_list.currentData()
            if not device_id:
                self.device_status.setText("⚠️ Please select a device")
                self.device_status.setStyleSheet("color: #fab387;")
                return
            
            device_name = self.output_devices_list.currentText()
            success = manager.set_default_output_device(device_id)
            
            if success:
                self.device_status.setText(f"✅ Set '{device_name}' as default output")
                self.device_status.setStyleSheet("color: #a6e3a1;")
            else:
                self.device_status.setText("❌ Failed to set default device")
                self.device_status.setStyleSheet("color: #f38ba8;")
                
        except Exception as e:
            self.device_status.setText(f"❌ Error: {str(e)}")
            self.device_status.setStyleSheet("color: #f38ba8;")

    def refresh_model_list(self):
        """Fetch available models from the API and populate the model dropdown"""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        api_key = self.api_key.text().strip()
        base_url = self.base_url.text().strip()
        mode = self.translation_mode.currentData() or "off"

        if mode in ("off", "fast"):
            self.status_label.setText("ℹ️ This translation mode has no model endpoint")
            self.status_label.setStyleSheet("font-size: 18px; color: #89b4fa;")
            return
        
        # Guard: don't call API with placeholder keys
        if mode == "online" and (
            not api_key or api_key in ("sk-...", "", "dummy-key-for-local", "dummy-key")
        ):
            log.warning("refresh_model_list: no valid API key, skipping")
            self.status_label.setText("⚠️ Enter API key to fetch models")
            self.status_label.setStyleSheet("font-size: 18px; color: #fab387;")
            return
        
        if mode == "local" and not base_url:
            base_url = "http://localhost:1234/v1"
            self.base_url.setText(base_url)
        if mode == "custom" and not base_url:
            self.status_label.setText("⚠️ Configure an API to fetch models")
            self.status_label.setStyleSheet("font-size: 18px; color: #fab387;")
            return

        if base_url and not base_url.startswith(("http://", "https://")):
            base_url = "http://" + base_url
            self.base_url.setText(base_url)

        self.refresh_models_btn.setEnabled(False)
        self.refresh_models_btn.setText("...")
        current_model = self.model.currentText()

        def _fetch():
            try:
                from openai import OpenAI
                import httpx
                from translation_engine import OnlineAPITranslator

                timeout = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
                if OnlineAPITranslator._is_local_endpoint(base_url):
                    http_client = httpx.Client(
                        verify=False, timeout=timeout, trust_env=False,
                    )
                else:
                    http_client = httpx.Client(timeout=timeout)
                client = OpenAI(
                    api_key=api_key or "not-needed",
                    base_url=base_url or None,
                    http_client=http_client,
                    max_retries=0,
                )
                response = client.models.list(timeout=10.0)
                model_ids = sorted(model.id for model in response.data)
                self.model_list_finished.emit(True, model_ids, current_model)
            except Exception as exc:
                self.model_list_finished.emit(
                    False, [], f"{type(exc).__name__}: {str(exc)[:160]}"
                )

        import threading
        threading.Thread(target=_fetch, daemon=True, name="model-list-fetch").start()

    def _on_model_list_finished(self, ok: bool, model_ids, detail: str):
        self.refresh_models_btn.setEnabled(True)
        self.refresh_models_btn.setText("Load Models")
        if ok:
            current_model = detail
            self.model.clear()
            if model_ids:
                self.model.addItems(model_ids)
                index = self.model.findText(current_model)
                if index >= 0:
                    self.model.setCurrentIndex(index)
                self.status_label.setText(f"✅ Loaded {len(model_ids)} models")
                self.status_label.setStyleSheet("font-size: 18px; color: #a6e3a1;")
            else:
                self.model.addItem(current_model)
                self.status_label.setText("⚠️ No models found")
                self.status_label.setStyleSheet("font-size: 18px; color: #fab387;")
            return

        if not self.model.currentText():
            self.model.addItem(config.model)
        self.status_label.setText(f"❌ Failed to fetch models: {detail[:80]}")
        self.status_label.setStyleSheet("font-size: 18px; color: #f38ba8;")

    def init_transcription_tab(self):
        tab = QWidget()
        form_host = QWidget()
        form_host.setMaximumWidth(940)
        layout = QFormLayout(form_host)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(14)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        
        # ASR Backend Selection
        self.asr_backend = QComboBox()
        self.asr_backend.addItems(["whisper", "mlx", "funasr"])
        self.asr_backend.setCurrentText(config.asr_backend)
        self.asr_backend.setToolTip(
            "whisper: CPU/CUDA (faster-whisper)\n"
            "mlx: Apple Silicon GPU (mlx-whisper)\n"
            "funasr: Alibaba ASR (excellent for Chinese)"
        )
        self.asr_backend.currentTextChanged.connect(self._on_backend_changed)
        layout.addRow("ASR Backend:", self.asr_backend)
        
        # Whisper Model
        self.whisper_model = QComboBox()
        self.whisper_model.setEditable(True)
        self.whisper_model.addItems(["tiny", "tiny.en", "base", "base.en", "small", "small.en", "medium", "medium.en", "large-v3", "turbo"])
        try:
            from model_manager import model_manager
            for installed in model_manager.get_models("whisper"):
                model_id = installed["id"]
                if installed.get("downloaded") and self.whisper_model.findText(model_id) < 0:
                    self.whisper_model.addItem(model_id)
        except Exception:
            pass
        self.whisper_model.setCurrentText(config.whisper_model)
        layout.addRow("Whisper Model:", self.whisper_model)
        quality_row = QWidget()
        quality_layout = QHBoxLayout(quality_row)
        quality_layout.setContentsMargins(0, 0, 0, 0)
        quality_layout.setSpacing(10)
        self.recognition_quality_hint = QLabel("")
        self.recognition_quality_hint.setObjectName("Muted")
        self.recognition_quality_hint.setWordWrap(True)
        quality_layout.addWidget(self.recognition_quality_hint, 1)
        self.open_recognition_models_btn = QPushButton("Open Recognition Models")
        self.open_recognition_models_btn.setObjectName("SecondaryButton")
        self.open_recognition_models_btn.clicked.connect(
            lambda: self.tabs.showRoute("Settings", "Recognition Models")
        )
        quality_layout.addWidget(self.open_recognition_models_btn)
        layout.addRow(quality_row)
        self.whisper_model.currentTextChanged.connect(self._update_recognition_quality_hint)
        self._update_recognition_quality_hint(self.whisper_model.currentText())

        self.enhanced_accuracy_mode = SegmentedControl()
        self.enhanced_accuracy_mode.addItem("Standard", False)
        self.enhanced_accuracy_mode.addItem("Enhanced", True)
        enhanced_index = self.enhanced_accuracy_mode.findData(
            bool(getattr(config, "enhanced_accuracy", False))
        )
        self.enhanced_accuracy_mode.setCurrentIndex(max(0, enhanced_index))
        layout.addRow("Accuracy enhancement:", self.enhanced_accuracy_mode)

        self.accuracy_profile = QComboBox()
        self.accuracy_profile.addItem("Auto (recommended)", "auto")
        self.accuracy_profile.addItem("Fast", "fast")
        self.accuracy_profile.addItem("Balanced", "balanced")
        self.accuracy_profile.addItem("Accurate", "accurate")
        accuracy_index = self.accuracy_profile.findData(
            getattr(config, "accuracy_profile", "auto")
        )
        self.accuracy_profile.setCurrentIndex(max(0, accuracy_index))
        layout.addRow("Hardware profile:", self.accuracy_profile)

        accuracy_status_row = QWidget()
        accuracy_status_layout = QHBoxLayout(accuracy_status_row)
        accuracy_status_layout.setContentsMargins(0, 0, 0, 0)
        accuracy_status_layout.setSpacing(10)
        self.accuracy_plan_label = QLabel("")
        self.accuracy_plan_label.setObjectName("Muted")
        self.accuracy_plan_label.setWordWrap(True)
        accuracy_status_layout.addWidget(self.accuracy_plan_label, 1)
        self.accuracy_download_btn = QPushButton("Download accuracy model")
        self.accuracy_download_btn.setObjectName("SecondaryButton")
        self.accuracy_download_btn.clicked.connect(self._download_accuracy_model)
        accuracy_status_layout.addWidget(self.accuracy_download_btn)
        layout.addRow(accuracy_status_row)
        self.enhanced_accuracy_mode.currentIndexChanged.connect(self._update_accuracy_plan_ui)
        self.accuracy_profile.currentIndexChanged.connect(self._update_accuracy_plan_ui)
        self._update_accuracy_plan_ui()
        
        # FunASR Model
        self.funasr_model = QComboBox()
        self.funasr_model.setEditable(True)
        self.funasr_model.addItems([
            "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
            "iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
            "iic/speech_paraformer_asr_nat-zh-cn-16k-common-vocab8404-online",
            "iic/speech_UniASR_asr_2pass-vi-16k-common-vocab1001-pytorch-online",
            "iic/speech_UniASR_asr_2pass-en-16k-common-vocab1080-tensorflow1-online",
            "iic/SenseVoiceSmall",
            "FunAudioLLM/SenseVoiceSmall",
            "FunAudioLLM/Fun-ASR-Nano-2512",
            "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
        ])
        self.funasr_model.setCurrentText(config.funasr_model)
        self.funasr_model.setToolTip(
            "Chinese (Offline): iic/speech_paraformer-large...\n"
            "Chinese (Streaming): iic/speech_paraformer_asr_nat...online\n"
            "English (Streaming): iic/speech_UniASR_asr_2pass-en...\n"
            "Multi-language: iic/SenseVoiceSmall\n"
            "Latest 31-lang model: FunAudioLLM/Fun-ASR-Nano-2512"
        )
        layout.addRow("FunASR Model:", self.funasr_model)
        
        self.device_type = QComboBox()
        self.device_type.addItems(["cpu", "cuda", "mps", "auto"])
        self.device_type.setCurrentText(config.whisper_device)
        self.device_type.currentTextChanged.connect(self._on_device_changed)
        layout.addRow("Compute Device:", self.device_type)
        
        self.compute_type = QComboBox()
        self.compute_type.addItems(["int8", "float16", "float32"])
        self.compute_type.setCurrentText(config.whisper_compute_type)
        self.compute_type.currentTextChanged.connect(self._on_quantization_changed)
        layout.addRow("Quantization:", self.compute_type)
        
        # Source Language Configuration
        self.source_language = QComboBox()
        self.source_language.setEditable(False)
        for language_name, language_code in (
            ("Automatic", "auto"),
            ("English", "en"),
            ("简体中文", "zh"),
            ("Tiếng Việt", "vi"),
            ("日本語", "ja"),
            ("한국어", "ko"),
            ("Español", "es"),
            ("Français", "fr"),
            ("Deutsch", "de"),
            ("Русский", "ru"),
            ("العربية", "ar"),
            ("Português", "pt"),
            ("Italiano", "it"),
        ):
            self.source_language.addItem(language_name, language_code)
        source_lang = config.source_language if config.source_language else "auto"
        source_index = self.source_language.findData(source_lang)
        if source_index >= 0:
            self.source_language.setCurrentIndex(source_index)
        else:
            self.source_language.setCurrentText(source_lang)
        layout.addRow("Source Language:", self.source_language)
        
        # Update UI based on initial backend
        self._on_backend_changed(config.asr_backend)
        
        outer = QHBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()
        outer.addWidget(form_host, 1)
        outer.addStretch()
        self.tabs.addTab(tab, "Transcript")
        self.tabs.setTabToolTip(self.tabs.count() - 1, "Transcript — ASR backend & model")
    
    def _on_backend_changed(self, backend):
        """Show/hide model selectors based on backend and warn about device compatibility"""
        is_whisper_or_mlx = backend in ["whisper", "mlx"]
        is_funasr = backend == "funasr"
        
        # Enable/disable appropriate widgets
        self.whisper_model.setEnabled(is_whisper_or_mlx)
        self.funasr_model.setEnabled(is_funasr)
        
        # Visual feedback - dim disabled widgets
        if is_whisper_or_mlx:
            self.whisper_model.setStyleSheet("")
            self.funasr_model.setStyleSheet("color: #6c7086;")
        else:
            self.whisper_model.setStyleSheet("color: #6c7086;")
            self.funasr_model.setStyleSheet("")
        
        # Check MPS + FunASR quantization compatibility
        if is_funasr:
            self._check_funasr_mps_compatibility()

    def _update_recognition_quality_hint(self, model_name):
        if not hasattr(self, "recognition_quality_hint"):
            return
        normalized = str(model_name or "").lower()
        if normalized.startswith(("tiny", "base")):
            source = (
                "Tiny/Base prioritizes speed and often splits or mishears natural speech. "
                "Use Small for everyday accuracy or Turbo on a capable Mac."
            )
            self.recognition_quality_hint.setStyleSheet("color: #e9a36f; font-size: 12px;")
            self.open_recognition_models_btn.show()
        else:
            source = "A fixed source language usually improves recognition accuracy and stability."
            self.recognition_quality_hint.setStyleSheet("color: #9a958c; font-size: 12px;")
            self.open_recognition_models_btn.hide()
        self._set_localized_text(self.recognition_quality_hint, source)

    def _selected_accuracy_plan(self):
        from recognition_quality import detect_hardware, resolve_accuracy_plan
        hardware = detect_hardware()
        profile = str(self.accuracy_profile.currentData() or "auto")
        return hardware, resolve_accuracy_plan(profile, hardware)

    def _update_accuracy_plan_ui(self, *_):
        if not hasattr(self, "accuracy_plan_label"):
            return
        from model_manager import model_manager
        enabled = bool(self.enhanced_accuracy_mode.currentData())
        self.accuracy_profile.setEnabled(enabled)
        hardware, plan = self._selected_accuracy_plan()
        installed = model_manager.is_downloaded(plan.model_id, "whisper")
        downloading = plan.model_id in self._active_downloads
        if not enabled:
            text = (
                "Enhanced mode shows a fast draft first, then corrects the same subtitle line "
                "with a larger local model."
            )
            self._set_localized_text(self.accuracy_plan_label, text)
            self.accuracy_download_btn.hide()
            return
        if self.ui_language == "zh-Hans":
            state = "已安装" if installed else ("正在下载" if downloading else "需要下载")
            hardware_label = (
                f"Apple Silicon · {hardware.memory_gb:.0f} GB 内存"
                if hardware.apple_silicon else
                f"Intel / 兼容架构 · {hardware.memory_gb:.0f} GB 内存"
            )
            text = (
                f"检测到 {hardware_label} · 推荐 {plan.model_id}（{plan.size_label}）· {state}。"
                "当前模型负责即时显示，推荐模型随后原位置修正。"
            )
        else:
            state = "installed" if installed else ("downloading" if downloading else "download required")
            text = (
                f"Detected {hardware.label} · {plan.model_id} ({plan.size_label}) · {state}. "
                "Your current model stays responsive; this model corrects the same line afterward."
            )
        if self._accuracy_download_error and not installed and not downloading:
            text += (
                f" 上次下载未完成：{self._accuracy_download_error[:100]}"
                if self.ui_language == "zh-Hans" else
                f" Last download did not finish: {self._accuracy_download_error[:100]}"
            )
        self.accuracy_plan_label.setText(text)
        self.accuracy_download_btn.setProperty("i18n_source_text", "Download accuracy model")
        self.accuracy_download_btn.setText(
            ui_translate("Accuracy model ready", self.ui_language)
            if installed else
            (
                (f"正在下载 {plan.model_id}…" if self.ui_language == "zh-Hans" else f"Downloading {plan.model_id}…")
                if downloading else
                f"{ui_translate('Download', self.ui_language)} {plan.model_id} · {plan.size_label}"
            )
        )
        self.accuracy_download_btn.setEnabled(not installed and not downloading)
        self.accuracy_download_btn.show()

    def _download_accuracy_model(self):
        _, plan = self._selected_accuracy_plan()
        if self._active_downloads and plan.model_id not in self._active_downloads:
            self._pending_start_after_accuracy_download = False
            self._set_localized_text(self.status_label, "Wait…")
            self.model_mgmt_status.setText(
                "请等待当前模型下载完成" if self.ui_language == "zh-Hans"
                else "Wait for the current model download to finish"
            )
            return
        self._accuracy_download_model_id = plan.model_id
        self._accuracy_download_error = None
        self._download_model(plan.model_id, "whisper")
        self._update_accuracy_plan_ui()
    
    def _check_funasr_mps_compatibility(self):
        """Check if MPS device is used with FunASR and enforce float32"""
        current_device = self.device_type.currentText()
        current_quantization = self.compute_type.currentText()
        
        if current_device == "mps" and current_quantization != "float32":
            self._show_mps_float32_warning()
            # Auto-switch to float32
            float32_index = self.compute_type.findText("float32")
            if float32_index >= 0:
                self.compute_type.setCurrentIndex(float32_index)
    
    def _show_mps_float32_warning(self):
        """Show warning about MPS requiring float32 with FunASR"""
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Quantization Compatibility")
        msg.setText("MPS device requires float32 quantization with FunASR")
        msg.setInformativeText(
            "Apple's MPS (Metal Performance Shaders) does not support float64 operations.\n\n"
            "When using FunASR with MPS device, quantization must be set to 'float32'.\n\n"
            "The quantization has been automatically switched to float32."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
    
    def _on_device_changed(self, device):
        """Check device compatibility when user changes device selection"""
        # Check MPS + FunASR quantization compatibility
        if self.asr_backend.currentText() == "funasr":
            self._check_funasr_mps_compatibility()
    
    def _on_quantization_changed(self, quantization):
        """Check quantization compatibility when user changes quantization"""
        # Check MPS + FunASR quantization compatibility
        if self.asr_backend.currentText() == "funasr":
            self._check_funasr_mps_compatibility()

    def init_translation_tab(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        content = QWidget()
        content.setMinimumWidth(520)
        content.setMaximumWidth(940)
        layout = QFormLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(14)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        title = QLabel("Translation Provider")
        title.setObjectName("HeroTitle")
        layout.addRow(title)
        intro = QLabel("Choose a provider, then test it here. The same settings are used when Live starts.")
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        layout.addRow(intro)

        self.translation_mode = ProviderSelector()
        self.translation_mode.addItem("No translation", "off")
        self.translation_mode.addItem("Apple Translation", "fast")
        self.translation_mode.addItem("Agnes AI", "online")
        self.translation_mode.addItem("LM Studio / local server", "local")
        self.translation_mode.addItem("Custom API", "custom")
        mode_index = self.translation_mode.findData(config.translation_mode)
        self.translation_mode.setCurrentIndex(max(0, mode_index))
        self.translation_mode.currentIndexChanged.connect(self._on_provider_changed)
        layout.addRow("Provider:", self.translation_mode)
        
        self.api_key = QLineEdit(config.api_key)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("sk-...")
        self.api_key.textChanged.connect(self._on_translation_settings_changed)
        layout.addRow("API Key:", self.api_key)
        
        self.base_url = QLineEdit(config.api_base_url or "")
        self.base_url.setPlaceholderText("https://api.openai.com/v1")
        self.base_url.setToolTip("Must start with http:// or https://. Example: http://localhost:1234/v1")
        self.base_url.textChanged.connect(self._on_translation_settings_changed)
        layout.addRow("Base URL:", self.base_url)
        
        # Model selection with refresh button
        model_layout = QHBoxLayout()
        model_layout.setSpacing(10)
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItem(config.model)
        self.model.setToolTip("Model name. Use 'Fetch' to pull from server.")
        self.model.currentTextChanged.connect(self._on_translation_settings_changed)
        model_layout.addWidget(self.model)
        
        self.refresh_models_btn = QPushButton("Load Models")
        self.refresh_models_btn.setMinimumWidth(112)
        self.refresh_models_btn.setToolTip("Load translation models from the selected service")
        self.refresh_models_btn.clicked.connect(self.refresh_model_list)
        model_layout.addWidget(self.refresh_models_btn)
        
        layout.addRow("Translation Model:", model_layout)
        self.translation_model_hint = QLabel(
            "Translation models come from the selected service. LM Studio models are downloaded and loaded in LM Studio, then selected here."
        )
        self.translation_model_hint.setObjectName("Muted")
        self.translation_model_hint.setWordWrap(True)
        layout.addRow(self.translation_model_hint)
        
        self.target_lang = QComboBox()
        for language in ("Chinese", "English", "Japanese", "French", "Spanish", "German", "Korean"):
            self.target_lang.addItem(language, language)
        # Destination languages are a finite product choice.  Keeping this
        # non-editable makes the whole field open immediately on click.
        self.target_lang.setEditable(False)
        target_index = self.target_lang.findData(config.target_lang)
        if target_index >= 0:
            self.target_lang.setCurrentIndex(target_index)
        else:
            self.target_lang.addItem(str(config.target_lang), str(config.target_lang))
            self.target_lang.setCurrentIndex(self.target_lang.count() - 1)
        self.target_lang.currentTextChanged.connect(self._on_translation_settings_changed)
        layout.addRow("Translate into:", self.target_lang)
        
        # Test Translation button
        test_layout = QHBoxLayout()
        self.test_trans_btn = QPushButton("Test Connection")
        self.test_trans_btn.clicked.connect(self._test_translation)
        test_layout.addWidget(self.test_trans_btn)
        test_layout.addStretch()
        layout.addRow(test_layout)
        
        # Test result label
        self.trans_test_result = QLabel("")
        self.trans_test_result.setWordWrap(True)
        self.trans_test_result.setStyleSheet("color: #6c7086; font-size: 12px; padding-top: 5px;")
        layout.addRow(self.trans_test_result)

        self.apple_translation_help = QPushButton("?  Install Apple languages")
        self.apple_translation_help.setObjectName("SecondaryButton")
        self.apple_translation_help.clicked.connect(self._show_apple_translation_help)
        self.apple_translation_help.hide()
        layout.addRow(self.apple_translation_help)

        self.trans_mode_label = QLabel("")
        self.trans_mode_label.setStyleSheet("color: #6c7086; font-size: 12px; padding: 5px 0;")
        self.trans_mode_label.setWordWrap(True)
        layout.addRow(self.trans_mode_label)
        self.update_translation_mode_label()
        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addStretch()
        wrapper_layout.addWidget(content)
        wrapper_layout.addStretch()
        scroll.setWidget(wrapper)
        self.tabs.addTab(tab, "Translate")
        self.tabs.setTabToolTip(self.tabs.count() - 1, "Translate — API, model, test connection")

    def _use_agnes_preset(self):
        """Apply the provider's documented OpenAI-compatible defaults."""
        index = self.translation_mode.findData("online")
        self.translation_mode.setCurrentIndex(index)
        self.base_url.setText("https://apihub.agnes-ai.com/v1")
        self.model.setCurrentText("agnes-2.0-flash")
        self.api_key.setFocus()
        self.update_translation_mode_label()

    def _use_lm_studio_preset(self):
        """Apply a local endpoint without touching the API-key field."""
        index = self.translation_mode.findData("local")
        self.translation_mode.setCurrentIndex(index)
        self.base_url.setText("http://127.0.0.1:1234/v1")
        self.model.setCurrentText("qwen2.5-coder-14b-instruct-mlx")
        self.update_translation_mode_label()

    def _on_provider_changed(self, *_):
        self._invalidate_translation_test()
        mode = self.translation_mode.currentData() or "off"
        if mode == "online":
            if not self.base_url.text().strip() or "127.0.0.1" in self.base_url.text() or "localhost" in self.base_url.text():
                self.base_url.setText("https://apihub.agnes-ai.com/v1")
            if not self.model.currentText().strip() or "qwen" in self.model.currentText().lower():
                self.model.setCurrentText("agnes-2.0-flash")
        elif mode == "local":
            if not self.base_url.text().strip() or "agnes-ai.com" in self.base_url.text():
                self.base_url.setText("http://127.0.0.1:1234/v1")
            if not self.model.currentText().strip() or self.model.currentText() == "agnes-2.0-flash":
                self.model.setCurrentText("qwen2.5-coder-14b-instruct-mlx")
        self.update_translation_mode_label()

    def _show_apple_translation_help(self):
        zh = self.ui_language == "zh-Hans"
        message = QMessageBox(self)
        message.setWindowTitle("安装 Apple 翻译语言" if zh else "Install Apple translation languages")
        message.setIcon(QMessageBox.Icon.Information)
        message.setText(
            "需要先在 macOS 下载原语言和译入语言。" if zh
            else "macOS needs both the source and destination languages before on-device translation can run."
        )
        message.setInformativeText(
            (
                "打开“系统设置 → 通用 → 语言与地区 → 翻译语言”，下载两种语言后回到这里再次测试。"
                "如果希望完全离线，可在同一页面开启设备端模式。"
            ) if zh else (
                "Open System Settings → General → Language & Region → Translation Languages, "
                "download both languages, then return and test again. You can also enable On-Device Mode there."
            )
        )
        open_settings = message.addButton(
            "打开语言与地区" if zh else "Open Language & Region",
            QMessageBox.ButtonRole.AcceptRole,
        )
        apple_help = message.addButton(
            "查看 Apple 帮助" if zh else "View Apple Help",
            QMessageBox.ButtonRole.ActionRole,
        )
        message.addButton(QMessageBox.StandardButton.Close)
        message.exec()
        if message.clickedButton() is open_settings:
            QDesktopServices.openUrl(QUrl("x-apple.systempreferences:com.apple.Localization-Settings.extension"))
        elif message.clickedButton() is apple_help:
            QDesktopServices.openUrl(QUrl("https://support.apple.com/guide/mac-help/mchldd8b3c15/mac"))

    def _translation_settings_snapshot(self):
        """Return the exact settings identity covered by a connection test."""
        return (
            self.translation_mode.currentData() or "off",
            self.api_key.text().strip(),
            self.base_url.text().strip().rstrip("/"),
            self.model.currentText().strip(),
            str(self.target_lang.currentData() or self.target_lang.currentText()).strip(),
        )

    def _on_translation_settings_changed(self, *_):
        self._invalidate_translation_test()
        self.update_translation_mode_label()

    def _invalidate_translation_test(self, *, show_message=True):
        """Invalidate both visible and in-flight results after any setting change."""
        self._translation_test_generation += 1
        self._translation_test_fingerprint = None
        if hasattr(self, "trans_test_result"):
            if show_message:
                self.trans_test_result.setText(
                    "尚未测试当前设置" if self.ui_language == "zh-Hans"
                    else "Current settings have not been tested"
                )
            else:
                self.trans_test_result.clear()
            self.trans_test_result.setStyleSheet(
                "color: #8f8a82; font-size: 12px; padding-top: 5px;"
            )
        if hasattr(self, "test_trans_btn"):
            testable_mode = (self.translation_mode.currentData() or "off") in {
                "fast", "online", "local", "custom",
            }
            self.test_trans_btn.setEnabled(testable_mode)
            self._set_localized_text(self.test_trans_btn, "Test Connection")
        if hasattr(self, "apple_translation_help"):
            self.apple_translation_help.setVisible(
                (self.translation_mode.currentData() or "off") == "fast"
            )
        
    def update_translation_mode_label(self, *_):
        mode = self.translation_mode.currentData() or "off"
        endpoint_mode = mode in {"online", "local", "custom"}
        self.api_key.setEnabled(mode in {"online", "custom"})
        self.base_url.setEnabled(endpoint_mode)
        self.model.setEnabled(endpoint_mode)
        self.refresh_models_btn.setEnabled(endpoint_mode)
        self.target_lang.setEnabled(mode != "off")
        self.test_trans_btn.setEnabled(mode != "off")
        if hasattr(self, "apple_translation_help"):
            self.apple_translation_help.setVisible(mode == "fast")
        api_key = self.api_key.text().strip()
        base_url = self.base_url.text().strip()
        model = self.model.currentText().strip()
        zh = self.ui_language == "zh-Hans"
        if mode == "off":
            self.trans_mode_label.setText(
                "翻译：关闭 · 仅显示原文" if zh else "Translation: Off · original subtitles only"
            )
        elif mode == "online" and (not api_key or api_key == "sk-..."):
            self.trans_mode_label.setText(
                "翻译：关闭 · 请先填写 API 密钥" if zh else "Translation: Off · API key required"
            )
        elif mode == "fast":
            self.trans_mode_label.setText(
                "翻译：Apple 本地翻译 · 需 macOS 26 与已下载语言包" if zh
                else "Translation: Apple on-device · macOS 26 and installed language assets required"
            )
        elif mode == "online":
            endpoint = base_url or "OpenAI default endpoint"
            self.trans_mode_label.setText(
                f"翻译：在线 · {model} · {endpoint}" if zh
                else f"Translation: Online · {model} · {endpoint}"
            )
        elif mode == "local":
            endpoint = base_url or "http://localhost:1234/v1"
            self.trans_mode_label.setText(
                f"翻译：本地 · {model} · {endpoint}" if zh
                else f"Translation: Local · {model} · {endpoint}"
            )
        elif mode == "custom":
            endpoint = base_url or ("请填写接口地址" if zh else "endpoint required")
            self.trans_mode_label.setText(
                f"翻译：自定义 · {model} · {endpoint}" if zh
                else f"Translation: Custom · {model} · {endpoint}"
            )
        else:
            self.trans_mode_label.setText("翻译：关闭" if zh else "Translation: Off")
    
    def _test_translation(self):
        """Test translation backend with current settings"""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        
        api_key = self.api_key.text().strip()
        mode = self.translation_mode.currentData() or "off"
        from translation_engine import normalize_base_url
        base_url = normalize_base_url(self.base_url.text(), mode)
        if base_url != self.base_url.text().strip():
            self.base_url.setText(base_url)
        model = self.model.currentText().strip()
        target_lang = self.target_lang.currentData() or self.target_lang.currentText()
        self._translation_test_generation += 1
        request_generation = self._translation_test_generation
        self._translation_test_fingerprint = self._translation_settings_snapshot()

        if mode == "off":
            self.trans_test_result.setText(
                "ℹ️ 翻译已关闭，无需测试连接" if self.ui_language == "zh-Hans"
                else "ℹ️ Translation is disabled; no connection is needed"
            )
            self.trans_test_result.setStyleSheet("color: #89b4fa; font-size: 12px;")
            return
        
        # Guard: empty API key or placeholder
        if mode == "online" and (
            not api_key or api_key in ("sk-...", "", "dummy-key-for-local")
        ):
            self.trans_test_result.setText(
                "❌ 请先填写 API 密钥" if self.ui_language == "zh-Hans"
                else "❌ No API key configured — enter a key to test"
            )
            self.trans_test_result.setStyleSheet("color: #f38ba8; font-size: 12px;")
            return
        
        if base_url and not base_url.startswith(("http://", "https://")):
            base_url = "http://" + base_url
            self.base_url.setText(base_url)
        
        if mode == "local" and not base_url:
            base_url = "http://localhost:1234/v1"
            self.base_url.setText(base_url)

        # Custom endpoints must be explicit. Online mode may use the SDK's
        # official default endpoint when the field is blank.
        if mode == "custom" and not base_url:
            self.trans_test_result.setText(
                "❌ 请先填写接口地址" if self.ui_language == "zh-Hans"
                else "❌ No API endpoint configured"
            )
            self.trans_test_result.setStyleSheet("color: #f38ba8; font-size: 12px;")
            return
        
        is_local = any(h in base_url for h in ("localhost", "127.0.0.1", "::1"))
        
        endpoint_label = (
            "Apple Translation"
            if mode == "fast"
            else (base_url or "OpenAI default endpoint")
        )
        self.trans_test_result.setText(
            f"正在测试 {endpoint_label}…" if self.ui_language == "zh-Hans"
            else f"Testing {endpoint_label}…"
        )
        self.trans_test_result.setStyleSheet("color: #fab387; font-size: 12px;")
        self.test_trans_btn.setEnabled(False)
        
        def _do_test():
            from translation_engine import TranslationEngine
            from mac_translation import normalize_language_code
            
            try:
                # Never test Apple Translation with the same source and target
                # language.  That checks an unsupported no-op pair rather than
                # the installed translation assets.
                target_code = normalize_language_code(target_lang, default="zh-Hans")
                if mode == "fast" and target_code.lower().startswith("en"):
                    sample_text = "连接测试正常。"
                    sample_source = "Chinese"
                else:
                    sample_text = "The connection is working."
                    sample_source = "English"
                engine = TranslationEngine()
                engine.target_lang = target_lang
                engine.set_mode(
                    mode,
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    source_language=sample_source if mode == "fast" else "auto",
                )
                sample = engine.translate(sample_text)
                if sample and not sample.startswith("[Translation Failed:"):
                    prefix = "连接成功" if self.ui_language == "zh-Hans" else "Connected"
                    provider_label = "Apple Translation" if mode == "fast" else model
                    self.translation_test_finished.emit(
                        request_generation, True, f"{prefix} · {provider_label}\n{sample[:120]}"
                    )
                else:
                    hint = ""
                    if is_local:
                        hint = "\nCheck that the local server and selected model are running."
                    self.translation_test_finished.emit(
                        request_generation, False, f"{sample or 'Empty response'}{hint}"
                    )
            except Exception as e:
                log.error(f"Translation test: {e}")
                self.translation_test_finished.emit(
                    request_generation, False, f"{type(e).__name__}: {str(e)[:160]}"
                )
        
        import threading
        threading.Thread(target=_do_test, daemon=True).start()

    def _on_translation_test_finished(self, generation: int, ok: bool, message: str):
        if generation != self._translation_test_generation:
            return
        if self._translation_test_fingerprint != self._translation_settings_snapshot():
            return
        if not ok and (self.translation_mode.currentData() or "off") == "fast":
            raw = str(message or "")
            if "language assets are not installed" in raw:
                pair = raw.rsplit(":", 1)[-1].strip()
                message = (
                    f"缺少 Apple 翻译语言包（{pair}）。请下载原语言和译入语言后重试。"
                    if self.ui_language == "zh-Hans" else
                    f"Apple translation languages are missing ({pair}). Download both languages, then test again."
                )
            elif "language pair is unsupported" in raw:
                pair = raw.rsplit(":", 1)[-1].strip()
                message = (
                    f"Apple 翻译不支持这个语言组合（{pair}）。"
                    if self.ui_language == "zh-Hans" else
                    f"Apple Translation does not support this language pair ({pair})."
                )
        self.trans_test_result.setText(("✅ " if ok else "❌ ") + message)
        color = "#a6e3a1" if ok else "#f38ba8"
        self.trans_test_result.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.test_trans_btn.setEnabled(True)
        self.test_trans_btn.setText(
            "测试连接" if self.ui_language == "zh-Hans" else "Test Connection"
        )
        self.apple_translation_help.setVisible(
            (self.translation_mode.currentData() or "off") == "fast" and not ok
        )

    def init_model_tab(self):
        """Model Management tab - download/delete/switch ASR models"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(28, 22, 28, 24)
        layout.setSpacing(14)
        
        header = QLabel("Speech Recognition Models")
        header.setObjectName("HeroTitle")
        layout.addWidget(header)
        model_copy = QLabel(
            "These downloads are only for speech recognition. Translation models are selected on the Translation page and are managed by that service."
        )
        model_copy.setObjectName("Muted")
        model_copy.setWordWrap(True)
        layout.addWidget(model_copy)
        
        # Backend filter
        filter_card = QFrame()
        filter_card.setObjectName("SettingsCard")
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(16, 12, 16, 12)
        filter_layout.addWidget(QLabel("Backend:"))
        self.model_backend_combo = QComboBox()
        self.model_backend_combo.setMinimumWidth(170)
        self.model_backend_combo.addItems(["whisper", "mlx"])
        self.model_backend_combo.currentTextChanged.connect(self._refresh_model_list)
        filter_layout.addWidget(self.model_backend_combo)
        filter_layout.addStretch()
        
        self.refresh_model_btn = QPushButton("Refresh")
        self.refresh_model_btn.setObjectName("SecondaryButton")
        self.refresh_model_btn.clicked.connect(self._refresh_model_list)
        filter_layout.addWidget(self.refresh_model_btn)
        layout.addWidget(filter_card)

        discover = QFrame()
        discover.setObjectName("SettingsCard")
        discover_layout = QVBoxLayout(discover)
        discover_layout.setContentsMargins(16, 14, 16, 14)
        discover_layout.setSpacing(9)
        discover_title = QLabel("Find a community model")
        discover_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        discover_layout.addWidget(discover_title)
        discover_copy = QLabel(
            "Search Hugging Face or paste an organization/model URL. Only faster-whisper compatible models can be installed."
        )
        discover_copy.setObjectName("Muted")
        discover_copy.setWordWrap(True)
        discover_layout.addWidget(discover_copy)
        search_row = QHBoxLayout()
        self.model_search_input = QLineEdit()
        self.model_search_input.setPlaceholderText("e.g. large-v3 Chinese or organization/model")
        self.model_search_input.returnPressed.connect(self._search_model_catalog)
        search_row.addWidget(self.model_search_input, 1)
        self.model_search_btn = QPushButton("Search")
        self.model_search_btn.setObjectName("SecondaryButton")
        self.model_search_btn.clicked.connect(self._search_model_catalog)
        search_row.addWidget(self.model_search_btn)
        discover_layout.addLayout(search_row)
        result_row = QHBoxLayout()
        self.model_search_results = QComboBox()
        self.model_search_results.setPlaceholderText("Search results")
        result_row.addWidget(self.model_search_results, 1)
        self.model_search_download = QPushButton("Download selected")
        self.model_search_download.setEnabled(False)
        self.model_search_download.clicked.connect(self._download_selected_search_model)
        result_row.addWidget(self.model_search_download)
        discover_layout.addLayout(result_row)
        layout.addWidget(discover)
        
        # Model list
        self.model_list_widget = QWidget()
        self.model_list_layout = QVBoxLayout()
        self.model_list_layout.setContentsMargins(0, 0, 0, 0)
        self.model_list_layout.setSpacing(10)
        self.model_list_widget.setLayout(self.model_list_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.model_list_widget)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll)
        
        # Status
        self.model_mgmt_status = QLabel("")
        self.model_mgmt_status.setWordWrap(True)
        self.model_mgmt_status.setObjectName("Muted")
        layout.addWidget(self.model_mgmt_status)
        
        # Clear all button
        clear_layout = QHBoxLayout()
        clear_layout.addStretch()
        self.clear_models_btn = QPushButton("Delete All Models")
        self.clear_models_btn.setObjectName("DangerButton")
        self.clear_models_btn.clicked.connect(self._clear_all_models)
        clear_layout.addWidget(self.clear_models_btn)
        layout.addLayout(clear_layout)
        
        self.tabs.addTab(tab, "Recognition Models")
        
        layout.addWidget(self.progress_panel)
        
        self._refresh_model_list()

    def _search_model_catalog(self):
        query = self.model_search_input.text().strip()
        if not query:
            self.model_mgmt_status.setText("Enter a model name or Hugging Face URL")
            return
        if self.model_backend_combo.currentText() != "whisper":
            self.model_backend_combo.setCurrentText("whisper")
        self.model_search_btn.setEnabled(False)
        self.model_search_download.setEnabled(False)
        self.model_search_results.clear()
        self.model_mgmt_status.setText("Searching Hugging Face…")

        def work():
            try:
                from model_catalog import search_faster_whisper
                results = search_faster_whisper(query, limit=10)
                self.model_search_finished.emit(True, results, "")
            except Exception as exc:
                self.model_search_finished.emit(False, [], str(exc))

        import threading
        threading.Thread(target=work, daemon=True, name="model-search").start()

    def _on_model_search_finished(self, ok, results, error):
        self.model_search_btn.setEnabled(True)
        self.model_search_results.clear()
        if not ok:
            self.model_mgmt_status.setText(f"Search failed: {error}")
            return
        for model_id in results:
            self.model_search_results.addItem(model_id, model_id)
        self.model_search_download.setEnabled(bool(results))
        self.model_mgmt_status.setText(
            f"Found {len(results)} compatible model(s)" if results
            else "No compatible faster-whisper models found"
        )

    def _download_selected_search_model(self):
        model_id = self.model_search_results.currentData()
        if model_id:
            self._download_model(str(model_id), "whisper")
    
    def _refresh_model_list(self):
        """Refresh model list display"""
        from model_manager import model_manager
        
        backend = self.model_backend_combo.currentText()
        models = model_manager.get_models(backend)
        disk = model_manager.get_disk_usage()
        
        # Clear existing
        while self.model_list_layout.count():
            child = self.model_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        for m in models:
            card = self._create_model_card(m, backend)
            self.model_list_layout.addWidget(card)
        
        self.model_list_layout.addStretch()
        
        if self.ui_language == "zh-Hans":
            self.model_mgmt_status.setText(
                f"本地模型共占用 {disk['total_mb']} MB · {disk['model_count']} 个模型"
            )
        else:
            self.model_mgmt_status.setText(
                f"{disk['model_count']} local model(s) · {disk['total_mb']} MB"
            )
    
    def _create_model_card(self, model_info, backend):
        """Create a card widget for a single model"""
        card = QFrame()
        card.setObjectName("ModelCard")
        card.setMinimumHeight(92)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(18, 14, 16, 14)
        layout.setSpacing(14)
        card.setLayout(layout)
        
        # Model info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        name_label = QLabel(f"{model_info['name']}")
        name_label.setObjectName("ModelName")
        info_layout.addWidget(name_label)
        
        speed = ui_translate(model_info['speed'], self.ui_language)
        accuracy = ui_translate(model_info['accuracy'], self.ui_language)
        detail = f"{speed} · {accuracy} · {model_info['size_mb']} MB"
        detail_label = QLabel(detail)
        detail_label.setObjectName("ModelMeta")
        info_layout.addWidget(detail_label)
        
        best_for = QLabel(ui_translate(model_info['best_for'], self.ui_language))
        best_for.setObjectName("ModelBestFor")
        info_layout.addWidget(best_for)
        
        layout.addLayout(info_layout, 1)
        
        # Action button
        downloaded = model_info['downloaded']
        mid = model_info['id']
        be = backend
        is_downloading = hasattr(self, '_active_downloads') and mid in self._active_downloads
        
        if downloaded:
            btn = QPushButton(ui_translate("Installed", self.ui_language))
            btn.setObjectName("ModelInstalled")
            btn.setToolTip("Installed locally · click to remove")
            btn.clicked.connect(lambda checked, mid=mid, be=be: self._delete_model(mid, be))
        elif is_downloading:
            btn = QPushButton(ui_translate("Cancel", self.ui_language))
            btn.setObjectName("DangerButton")
            btn.clicked.connect(lambda checked, mid=mid: self._cancel_download(mid))
        else:
            btn = QPushButton(ui_translate("Download", self.ui_language))
            btn.setObjectName("ModelDownload")
            btn.clicked.connect(lambda checked, mid=mid, be=be: self._download_model(mid, be))
        btn.setMinimumWidth(104)
        
        if model_info.get('recommended'):
            rec_label = QLabel(ui_translate("Recommended", self.ui_language))
            rec_label.setObjectName("RecommendedPill")
            rec_label.setToolTip("Recommended")
            layout.addWidget(rec_label)
        
        layout.addWidget(btn)
        
        return card
    
    def _download_model(self, model_id, backend):
        """Start download via DownloadTask, receive status via Qt signals."""
        from model_download_task import DownloadTask
        from model_manager import model_manager
        import logging, threading
        log = logging.getLogger("RealtimeSubtitle")
        
        if hasattr(self, '_active_downloads') and model_id in self._active_downloads:
            log.info(f"Model download already active: {model_id}")
            return
        
        if self._active_downloads:
            log.info("Another model is already downloading — ignoring")
            return
        
        self.model_mgmt_status.setText(
            f"{model_id} · 正在准备下载…" if self.ui_language == "zh-Hans"
            else f"{model_id} · preparing download…"
        )
        self.model_mgmt_status.setStyleSheet("color: #fab387; font-size: 12px;")
        
        # Use SYNCHRONOUS download — DownloadTask handles retries, not nested threads
        def do_download(ctx):
            model_manager.download_model_sync(model_id, backend)
            return True  # success — exception would be caught by DownloadTask
        
        task = DownloadTask(model_id, backend, do_download, max_attempts=3)
        self._active_downloads[model_id] = task
        # Immediately refresh card to show Cancel button
        self._refresh_model_list()
        
        # Wire progress channel to the associated ProgressPanel
        from model_progress_channel import ModelProgressChannel
        channel = ModelProgressChannel(model_id, max_attempts=3, language=self.ui_language)
        self._progress_model_id = model_id
        self._progress_backend = backend
        self.progress_event.emit(channel.on_start())
        self.progress_panel.setVisible(True)
        task._progress_channel = channel  # store for cleanup
        
        task.on_status(lambda s, a: (
            self.model_download_status.emit(model_id, s, a),
            self._emit_channel_status(channel, s, a, None)
        ))
        task.on_done(lambda ts, err, a: (
            self._active_downloads.pop(model_id, None),
            self._emit_channel_done(channel, ts, err, a),
            self.model_download_done.emit(model_id, ts, err, a)
        ))
        task.on_cleanup(lambda: None)
        
        threading.Thread(target=task.start, daemon=True, name=f"dl-{model_id}").start()
    
    def _on_model_status(self, model_id, status, attempt):
        """Qt-safe status callback — queued to main thread."""
        if status == "downloading":
            self.model_mgmt_status.setText(
                f"{model_id} · 正在下载（第 {attempt} 次）" if self.ui_language == "zh-Hans"
                else f"{model_id} · downloading (attempt {attempt})"
            )
            self.model_mgmt_status.setStyleSheet("color: #fab387; font-size: 12px;")
        elif status == "retrying":
            self.model_mgmt_status.setText(
                f"{model_id} · 正在重试（第 {attempt} 次）" if self.ui_language == "zh-Hans"
                else f"{model_id} · retrying (attempt {attempt})"
            )
            self.model_mgmt_status.setStyleSheet("color: #f9e2af; font-size: 12px;")
        elif status == "cancelled":
            self.model_mgmt_status.setText(
                f"{model_id} · 已取消" if self.ui_language == "zh-Hans"
                else f"{model_id} · cancelled"
            )
            self.model_mgmt_status.setStyleSheet("color: #6c7086; font-size: 12px;")
        if model_id == self._accuracy_download_model_id:
            self._update_accuracy_plan_ui()
    
    def _on_model_done(self, model_id, terminal_state, error, attempt):
        """Qt-safe done callback — queued to main thread."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        from model_download_task import SUCCEEDED, CANCELLED
        if terminal_state == SUCCEEDED:
            log.info(f"Model {model_id} downloaded")
            self.model_mgmt_status.setText(
                f"{model_id} · 已安装" if self.ui_language == "zh-Hans"
                else f"{model_id} · installed"
            )
            self.model_mgmt_status.setStyleSheet("color: #a6e3a1; font-size: 12px;")
            is_accuracy_download = model_id == self._accuracy_download_model_id
            if is_accuracy_download:
                self._accuracy_download_error = None
            if self.model_backend_combo.currentText() == "whisper" and not is_accuracy_download:
                if self.whisper_model.findText(model_id) < 0:
                    self.whisper_model.addItem(model_id)
                self.whisper_model.setCurrentText(model_id)
            QTimer.singleShot(
                1200,
                lambda mid=model_id: self._dismiss_completed_progress(mid),
            )
        elif terminal_state == CANCELLED:
            log.info(f"Model download cancelled: {model_id}")
            self.model_mgmt_status.setText(
                f"{model_id} · 已取消" if self.ui_language == "zh-Hans"
                else f"{model_id} · cancelled"
            )
            self.model_mgmt_status.setStyleSheet("color: #6c7086; font-size: 12px;")
            if model_id == self._accuracy_download_model_id:
                self._accuracy_download_error = (
                    "已取消" if self.ui_language == "zh-Hans" else "cancelled"
                )
        else:
            log.error(f"Model {model_id} failed: {error}")
            self.model_mgmt_status.setText(
                (f"{model_id} · 下载失败（已尝试 {attempt} 次）" if self.ui_language == "zh-Hans"
                 else f"{model_id} · failed after {attempt} attempts")
            )
            self.model_mgmt_status.setStyleSheet("color: #f38ba8; font-size: 12px;")
            if model_id == self._accuracy_download_model_id:
                self._accuracy_download_error = str(error or "download failed")
        if hasattr(self, '_active_downloads'):
            self._active_downloads.pop(model_id, None)
        self._refresh_model_list()
        if hasattr(self, "accuracy_plan_label"):
            self._update_accuracy_plan_ui()
        if model_id == self._accuracy_download_model_id:
            should_start = terminal_state == SUCCEEDED and self._pending_start_after_accuracy_download
            self._accuracy_download_model_id = None
            self._pending_start_after_accuracy_download = False
            if should_start:
                QTimer.singleShot(250, self.on_start)

    def _dismiss_completed_progress(self, model_id):
        """Remove a completed progress surface unless another task replaced it."""
        if self._progress_model_id == model_id and model_id not in self._active_downloads:
            self._dismiss_progress_panel()
    
    def _emit_channel_status(self, channel, status, attempt, error):
        """Translate DownloadTask status string to ProgressEvent and emit."""
        if status == "downloading":
            evt = channel.on_start() if attempt <= 1 else channel.on_retry(attempt)
        elif status == "retrying":
            evt = channel.on_retry(attempt)
        elif status == "completed":
            evt = channel.on_success(attempt)
        elif status == "cancelled":
            evt = channel.on_cancel(attempt)
        elif status == "failed":
            evt = channel.on_fail(error, attempt)
        else:
            return
        self.progress_event.emit(evt)

    def _emit_channel_done(self, channel, terminal_state, error, attempt):
        """Final event for progress panel — uses terminal_state, not ok bool."""
        from model_download_task import SUCCEEDED, FAILED, CANCELLED
        if terminal_state == SUCCEEDED:
            self.progress_event.emit(channel.on_success(attempt))
        elif terminal_state == CANCELLED:
            self.progress_event.emit(channel.on_cancel(attempt))
        else:
            self.progress_event.emit(channel.on_fail(error, attempt))

    def _dismiss_progress_panel(self):
        """Dismiss progress panel — hide and clear tracking."""
        self.progress_panel.hide()
        self._progress_model_id = None
        self._progress_backend = None
    
    def _retry_progress_model(self):
        """Retry the model currently shown in progress panel."""
        if self._progress_model_id and self._progress_backend:
            self._retry_download(self._progress_model_id, self._progress_backend)
    
    def _cancel_progress_model(self):
        """Cancel the model currently shown in progress panel."""
        if self._progress_model_id:
            self._cancel_download(self._progress_model_id)
    
    def _retry_download(self, model_id, backend):
        """Retry a failed download."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.info(f"Retry download: {model_id}")
        self._download_model(model_id, backend)
    
    def _cancel_download(self, model_id):
        """Cancel an active download."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        if hasattr(self, '_active_downloads') and model_id in self._active_downloads:
            task = self._active_downloads[model_id]
            task.cancel()
            log.info(f"Download cancelled: {model_id}")
            self.model_mgmt_status.setText(
                f"{model_id} · 正在取消…" if self.ui_language == "zh-Hans"
                else f"{model_id} · cancelling…"
            )
            self.model_mgmt_status.setStyleSheet("color: #fab387; font-size: 12px;")
    
    def _delete_model(self, model_id, backend):
        """Delete a model with confirmation"""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self, "Delete Model",
            f"Delete model '{model_id}'?\nThis will free up disk space.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        from model_manager import model_manager
        success = model_manager.delete_model(model_id, backend)
        
        if success:
            self.model_mgmt_status.setText(f"✅ Deleted {model_id}")
            self.model_mgmt_status.setStyleSheet("color: #a6e3a1; font-size: 12px;")
        else:
            self.model_mgmt_status.setText(f"❌ Failed to delete {model_id}")
            self.model_mgmt_status.setStyleSheet("color: #f38ba8; font-size: 12px;")
        
        self._refresh_model_list()
    
    def _clear_all_models(self):
        """Delete all downloaded models"""
        from PyQt6.QtWidgets import QMessageBox
        from model_manager import model_manager
        
        reply = QMessageBox.question(
            self, "Delete All Models",
            "Are you sure you want to delete ALL downloaded models?\n\n"
            "You will need to download them again to use the app.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        success = model_manager.clear_all_models()
        if success:
            self.model_mgmt_status.setText("✅ All models deleted")
        else:
            self.model_mgmt_status.setText("❌ Error deleting models")
        
        self._refresh_model_list()

    def init_style_tab(self):
        """Subtitle appearance editor with a live, transparent preview."""
        tab = QWidget()
        root = QVBoxLayout(tab)
        root.setContentsMargins(18, 20, 18, 20)
        root.setSpacing(14)

        header = QLabel("Subtitle appearance")
        header.setObjectName("HeroTitle")
        root.addWidget(header)
        intro = QLabel("Adjust the floating subtitle window and see every change before applying it.")
        intro.setObjectName("Muted")
        root.addWidget(intro)

        editor = QHBoxLayout()
        editor.setSpacing(16)
        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        controls_scroll.setMinimumWidth(320)
        controls_scroll.setMaximumWidth(370)
        controls = QFrame()
        controls.setObjectName("SettingsCard")
        layout = QFormLayout(controls)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(14)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        
        # Font size
        self.original_font_size = QSpinBox()
        self.original_font_size.setRange(8, 48)
        self.original_font_size.setValue(getattr(config, "original_font_size", 20))
        self.original_font_size.setSuffix(" px")
        layout.addRow("Original Font Size:", self.original_font_size)
        
        self.translation_font_size = QSpinBox()
        self.translation_font_size.setRange(8, 48)
        self.translation_font_size.setValue(getattr(config, "translation_font_size", 17))
        self.translation_font_size.setSuffix(" px")
        layout.addRow("Translation Font Size:", self.translation_font_size)
        
        # Colors
        self.original_color = ColorButton(getattr(config, "original_color", "#ffffff"))
        layout.addRow("Original Text Color:", self.original_color)
        
        self.translation_color = ColorButton(getattr(config, "translation_color", "#d99a69"))
        layout.addRow("Translation Color:", self.translation_color)
        
        # Background opacity — deliberately independent from text colors.
        opacity_row = QHBoxLayout()
        self.window_opacity = QSlider(Qt.Orientation.Horizontal)
        self.window_opacity.setRange(30, 100)
        self.window_opacity.setValue(round(getattr(config, "window_opacity", 0.94) * 100))
        self.opacity_value = QLabel(f"{self.window_opacity.value()}%")
        self.window_opacity.valueChanged.connect(lambda value: self.opacity_value.setText(f"{value}%"))
        opacity_row.addWidget(self.window_opacity, 1)
        opacity_row.addWidget(self.opacity_value)
        layout.addRow("Background Opacity:", opacity_row)
        
        # Window width
        self.window_width = QSpinBox()
        self.window_width.setRange(200, 1200)
        self.window_width.setValue(getattr(config, "window_width", 620))
        self.window_width.setSuffix(" px")
        layout.addRow("Window Width:", self.window_width)

        self.visible_subtitles = QSpinBox()
        self.visible_subtitles.setRange(1, 8)
        self.visible_subtitles.setValue(getattr(config, "visible_subtitles", 3))
        self.visible_subtitles.setToolTip(
            "Controls the overlay height. Older subtitles remain available by scrolling up."
        )
        layout.addRow("Visible Subtitle Rows:", self.visible_subtitles)
        
        # Display mode
        self.display_mode = SegmentedControl()
        self.display_mode.addItem("Both", "bilingual")
        self.display_mode.addItem("Original", "original_only")
        self.display_mode.addItem("Translation", "translation_only")
        mode_index = self.display_mode.findData(getattr(config, "display_mode", "bilingual"))
        self.display_mode.setCurrentIndex(max(0, mode_index))
        display_mode_group = QWidget()
        display_mode_layout = QVBoxLayout(display_mode_group)
        display_mode_layout.setContentsMargins(0, 2, 0, 0)
        display_mode_layout.setSpacing(7)
        display_mode_layout.addWidget(QLabel("Display Mode"))
        display_mode_layout.addWidget(self.display_mode)
        layout.addRow(display_mode_group)

        controls_scroll.setWidget(controls)
        editor.addWidget(controls_scroll, 4)

        preview_column = QVBoxLayout()
        preview_label = QLabel("LIVE PREVIEW")
        preview_label.setObjectName("SummaryLabel")
        preview_column.addWidget(preview_label)
        self.appearance_preview = SubtitlePreview()
        preview_column.addWidget(self.appearance_preview, 1)
        preview_hint = QLabel("Drag the subtitle between the dark and light sides to check contrast anywhere.")
        preview_hint.setObjectName("Muted")
        preview_hint.setWordWrap(True)
        preview_column.addWidget(preview_hint)
        editor.addLayout(preview_column, 6)
        root.addLayout(editor, 1)

        footer = QHBoxLayout()
        self.appearance_feedback = QLabel("")
        self.appearance_feedback.setObjectName("StatusPill")
        self.appearance_feedback.hide()
        footer.addWidget(self.appearance_feedback)
        footer.addStretch()
        self.apply_style_btn = QPushButton("Apply Style")
        self.apply_style_btn.setMinimumWidth(150)
        self.apply_style_btn.clicked.connect(self._apply_style)
        footer.addWidget(self.apply_style_btn)
        root.addLayout(footer)

        for signal in (
            self.original_font_size.valueChanged,
            self.translation_font_size.valueChanged,
            self.original_color.colorChanged,
            self.translation_color.colorChanged,
            self.window_opacity.valueChanged,
            self.window_width.valueChanged,
            self.visible_subtitles.valueChanged,
            self.display_mode.currentIndexChanged,
        ):
            signal.connect(self._update_appearance_preview)
        self._update_appearance_preview()
        self.tabs.addTab(tab, "Style")

    def _appearance_style_from_controls(self):
        return {
            "original_font_size": self.original_font_size.value(),
            "translation_font_size": self.translation_font_size.value(),
            "original_color": self.original_color.currentText(),
            "translation_color": self.translation_color.currentText(),
            "window_opacity": self.window_opacity.value() / 100.0,
            "window_width": self.window_width.value(),
            "visible_subtitles": self.visible_subtitles.value(),
            "display_mode": self.display_mode.currentData() or "bilingual",
        }

    def _update_appearance_preview(self, *_):
        if hasattr(self, "appearance_preview"):
            self.appearance_preview.set_preview_style(self._appearance_style_from_controls())

    def _apply_style(self):
        """Apply subtitle style to overlay window"""
        style = self._appearance_style_from_controls()
        if hasattr(self, 'overlay_window') and self.overlay_window:
            self.overlay_window.set_style(style)
        self._save_display_preferences(style)
        if hasattr(self, "live_preview"):
            self.live_preview.set_preview_style(style)
        self._set_localized_text(self.status_label, "Appearance applied")
        self._set_localized_text(
            self.appearance_feedback,
            "Applied — the subtitle window is updated",
        )
        self.appearance_feedback.show()
        self._set_localized_text(self.apply_style_btn, "Applied")
        QTimer.singleShot(1800, self._reset_appearance_feedback)

    def _reset_appearance_feedback(self):
        self.appearance_feedback.hide()
        self._set_localized_text(self.apply_style_btn, "Apply Style")

    def _save_display_preferences(self, style):
        import configparser
        from app_paths import write_config

        parser = configparser.ConfigParser()
        parser.read(config.config_path)
        if not parser.has_section("display"):
            parser.add_section("display")
        for key, value in style.items():
            parser.set("display", key, str(value))
            setattr(config, key, value)
        parser.set("display", "history_limit", str(getattr(config, "subtitle_history_limit", 250)))
        write_config(parser, config.config_path)
    
    def init_diagnostics_tab(self):
        """Product-facing system preferences with optional technical detail."""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tab_layout.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(26, 22, 26, 26)
        layout.setSpacing(14)

        language_card = QFrame()
        language_card.setObjectName("SettingsCard")
        self.language_card = language_card
        language_layout = QVBoxLayout(language_card)
        language_layout.setContentsMargins(18, 16, 18, 16)
        language_layout.setSpacing(10)
        language_title = QLabel("App Language")
        language_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        language_layout.addWidget(language_title)
        language_row = QHBoxLayout()
        language_row.addWidget(QLabel("Interface Language:"))
        self.ui_language_combo = SegmentedControl()
        self.ui_language_combo.addItem("English", "en")
        self.ui_language_combo.addItem("简体中文", "zh-Hans")
        self.ui_language_combo.setMaximumWidth(300)
        language_index = self.ui_language_combo.findData(self.ui_language)
        self.ui_language_combo.setCurrentIndex(max(0, language_index))
        language_row.addWidget(self.ui_language_combo)
        language_row.addStretch()
        language_layout.addLayout(language_row)
        language_hint = QLabel("Changes apply immediately across the app.")
        language_hint.setObjectName("Muted")
        language_layout.addWidget(language_hint)
        self.ui_language_combo.currentIndexChanged.connect(self._change_ui_language)
        layout.addWidget(language_card)

        about_card = QFrame()
        about_card.setObjectName("SettingsCard")
        about_layout = QVBoxLayout(about_card)
        about_layout.setContentsMargins(18, 16, 18, 16)
        about_title = QLabel("About")
        about_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        about_layout.addWidget(about_title)
        try:
            from version import BUILD_VERSION
            version_text = str(BUILD_VERSION)
        except ImportError:
            version_text = "Development"
        about_layout.addWidget(QLabel(f"Realtime Subtitle · {version_text}"))
        privacy_note = QLabel("Audio and settings stay on this Mac.")
        privacy_note.setObjectName("Muted")
        about_layout.addWidget(privacy_note)
        layout.addWidget(about_card)

        action_row = QHBoxLayout()
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self.save_config)
        action_row.addWidget(self.save_btn)
        self.run_diag_btn = QPushButton("Run Quick Check")
        self.run_diag_btn.setObjectName("SecondaryButton")
        self.run_diag_btn.clicked.connect(self._run_diagnostics)
        action_row.addWidget(self.run_diag_btn)
        self.view_logs_btn = QPushButton("View Logs")
        self.view_logs_btn.setObjectName("SecondaryButton")
        self.view_logs_btn.clicked.connect(self._view_logs)
        action_row.addWidget(self.view_logs_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.details_toggle = QPushButton("Technical Details")
        self.details_toggle.setObjectName("SecondaryButton")
        self.details_toggle.setCheckable(True)
        self.details_toggle.setChecked(False)
        self.details_toggle.toggled.connect(self._toggle_technical_details)
        layout.addWidget(self.details_toggle)

        self.technical_details = QFrame()
        details_layout = QVBoxLayout(self.technical_details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(10)

        # Architecture status (v2.4)
        self._arch_status = QLabel("")
        self._arch_status.setWordWrap(True)
        self._arch_status.setStyleSheet(
            "color: #bac2de; background: #181825; border: 1px solid #313244; "
            "border-radius: 4px; padding: 8px; font-size: 11px;"
        )
        details_layout.addWidget(self._arch_status)
        self._refresh_arch_status()

        # Runtime decision (v2.4)
        self._runtime_decision_status = QLabel("")
        self._runtime_decision_status.setTextFormat(Qt.TextFormat.RichText)
        self._runtime_decision_status.setWordWrap(True)
        self._runtime_decision_status.setStyleSheet(
            "color: #bac2de; background: #181825; border: 1px solid #313244; "
            "border-radius: 4px; padding: 8px; font-size: 11px;"
        )
        details_layout.addWidget(self._runtime_decision_status)
        self._refresh_runtime_decision_status()

        # Transcript history (v2.4)
        self._history_status = QLabel("")
        self._history_status.setTextFormat(Qt.TextFormat.RichText)
        self._history_status.setWordWrap(True)
        self._history_status.setStyleSheet(
            "color: #bac2de; background: #181825; border: 1px solid #313244; "
            "border-radius: 4px; padding: 8px; font-size: 11px;"
        )
        details_layout.addWidget(self._history_status)
        self._refresh_history_status()
        
        # Results area
        self.diag_results = QTextEdit()
        self.diag_results.setReadOnly(True)
        self.diag_results.setMinimumHeight(150)
        self.diag_results.setMaximumHeight(260)
        details_layout.addWidget(self.diag_results)
        self.technical_details.setVisible(False)
        layout.addWidget(self.technical_details)
        layout.addStretch()

        scroll.setWidget(content)
        self.tabs.addTab(tab, "Diag")
        self.tabs.setTabToolTip(self.tabs.count() - 1, "Diagnostics — check system, view logs")

    def _change_ui_language(self, *_):
        self.ui_language = normalize_language(self.ui_language_combo.currentData())
        config.ui_language = self.ui_language
        self._save_ui_language()
        apply_language(self, self.ui_language)
        if hasattr(self, "history_player"):
            self.history_player.set_language(self.ui_language)
            self._refresh_history()
        if hasattr(self, "model_list_layout"):
            self._refresh_model_list()
        if hasattr(self, "trans_mode_label"):
            self._invalidate_translation_test()
            self.update_translation_mode_label()
        if hasattr(self, "accuracy_plan_label"):
            self._update_accuracy_plan_ui()

    def _save_ui_language(self):
        import configparser
        from app_paths import write_config

        parser = configparser.ConfigParser()
        parser.read(config.config_path)
        if not parser.has_section("app"):
            parser.add_section("app")
        parser.set("app", "language", self.ui_language)
        write_config(parser, config.config_path)

    def _toggle_technical_details(self, visible):
        self.technical_details.setVisible(visible)
        self.details_toggle.setText(
            ("收起技术详情" if visible else "技术详情")
            if self.ui_language == "zh-Hans"
            else ("Hide Technical Details" if visible else "Technical Details")
        )
    
    def _refresh_runtime_decision_status(self):
        """Update runtime decision label using guard + formatter."""
        try:
            from src.dashboard_runtime_decision_adapter import build_runtime_decision_html
            html = build_runtime_decision_html(config)
            self._runtime_decision_status.setText(html)
        except Exception as e:
            self._runtime_decision_status.setText(
                f"<h3>Runtime Decision</h3><p><i>Unavailable: {e}</i></p>"
            )

    def _refresh_arch_status(self):
        """Update architecture status label from current config + SettingsDependencyEngine."""
        try:
            from src.settings_validation_viewmodel import build_settings_validation_viewmodel
            settings = {
                "use_translation_scheduler": getattr(config, "use_translation_scheduler", False),
                "use_sqlite_session_repository": getattr(config, "use_sqlite_session_repository", False),
            }
            vm = build_settings_validation_viewmodel(settings)
            lines = [f"<b>Architecture:</b> {vm.mode_label}"]
            lines.append(f"<b>Summary:</b> {vm.summary}")
            if vm.messages:
                lines.append("<b>Issues:</b>")
                for m in vm.messages:
                    tag = m.severity.upper()
                    color = "#f38ba8" if tag == "ERROR" else "#f9e2af" if tag == "WARNING" else "#89b4fa"
                    lines.append(f'  <span style="color:{color};">[{tag}]</span> {m.message}')
            if vm.recommended_changes:
                lines.append("<b>Recommended:</b>")
                for k, v in vm.recommended_changes.items():
                    lines.append(f"  {k} = {v}")
            self._arch_status.setText("<br>".join(lines))
        except Exception as e:
            self._arch_status.setText(f"<i>Architecture check unavailable: {e}</i>")

    def _refresh_history_status(self):
        """Refresh transcript history preview from SQLite repository.
        Only opens the database if use_sqlite_session_repository is True."""
        try:
            from src.dashboard_history_adapter import build_history_viewmodel_for_dashboard
            from src.history_dashboard_formatter import format_history_viewmodel_html
            vm = build_history_viewmodel_for_dashboard(config)
            html = format_history_viewmodel_html(vm)
            self._history_status.setText(html)
        except Exception as e:
            self._history_status.setText(
                f"<h3>Transcript History</h3><p><i>Unavailable: {e}</i></p>"
            )

    def _run_diagnostics(self):
        """Run and display system diagnostics with pipeline state"""
        from diagnostics import diagnostics
        import logging
        
        self.run_diag_btn.setEnabled(False)
        self.details_toggle.setChecked(True)
        self._set_localized_text(self.run_diag_btn, "Running Quick Check…")
        
        report = diagnostics.get_status_text()
        
        # Add pipeline runtime state
        try:
            from version import BUILD_VERSION, BUILD_COMMIT, BUILD_TIME
            version_label = BUILD_VERSION if str(BUILD_VERSION).startswith("v") else f"v{BUILD_VERSION}"
            report += f"\n\nApp: {version_label} (commit {BUILD_COMMIT})"
        except ImportError:
            report += f"\n\nApp: dev build"
        
        log_dir = os.path.expanduser("~/Library/Logs/RealtimeSubtitle")
        report += f"\nLogs: {log_dir}"
        
        # Pipeline state
        if hasattr(self, 'pipeline') and self.pipeline:
            pp = self.pipeline
            report += f"\nPipeline state: {'RUNNING' if pp.running else 'STOPPING'}"
            if hasattr(pp, 'thread') and pp.thread:
                report += f"\nPipelineLoop alive: {pp.thread.is_alive()}"
            if hasattr(pp, '_failed') and pp._failed:
                report += f"\nPipeline failed: YES"
            if hasattr(pp, '_cleanup_in_progress') and pp._cleanup_in_progress:
                report += f"\nCleanup in progress: YES"
            # ASR worker status
            if hasattr(pp, 'running') and pp.running:
                report += "\nASR worker: (checking via PipelineLoop only)"
            else:
                report += "\nASR worker: stopped (PipelineLoop not running)"
        else:
            report += "\nPipeline: NOT STARTED"
        
        # Last error
        if hasattr(self, 'last_pipeline_error') and self.last_pipeline_error:
            report += f"\n\nLast Pipeline Error:\n{self.last_pipeline_error[:300]}"
        
        self.diag_results.setText(report)
        self.run_diag_btn.setEnabled(True)
        self._set_localized_text(self.run_diag_btn, "Run Quick Check")
    
    def _view_logs(self):
        """View recent log entries"""
        from diagnostics import logger

        self.details_toggle.setChecked(True)
        
        logs = logger.get_logs(50)
        if logs:
            text = "Recent Logs:\n" + "=" * 40 + "\n"
            for line in logs[-30:]:
                text += line
            self.diag_results.setText(text)
        else:
            self.diag_results.setText("No logs available yet.")

    def populate_devices(self):
        self.device_combo.clear()
        self.device_combo.addItem("Auto (Default)", "auto")
        
        try:
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d['max_input_channels'] > 0:
                    name = f"[{i}] {d['name']}"
                    self.device_combo.addItem(name, i) # Store index as data
            
            # Select current
            if config.device_index is not None:
                index = self.device_combo.findData(config.device_index)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)
        except Exception as e:
            self.device_combo.addItem(f"Error: {e}")

    def save_config(self):
        import configparser
        from app_paths import write_config
        
        cp = configparser.ConfigParser()
        config_path = config.config_path
        cp.read(config_path)
        
        if not cp.has_section("audio"): cp.add_section("audio")
        if not cp.has_section("api"): cp.add_section("api")
        if not cp.has_section("translation"): cp.add_section("translation")
        if not cp.has_section("transcription"): cp.add_section("transcription")
        if not cp.has_section("display"): cp.add_section("display")
        if not cp.has_section("app"): cp.add_section("app")
        
        # Audio
        idx = self.device_combo.currentData()
        input_source = str(self.input_source_combo.currentData() or "microphone")
        cp.set("audio", "input_source", input_source)
        cp.set("audio", "device_index", str(idx) if idx is not None else "auto")
        cp.set("audio", "sample_rate", str(self.sample_rate.value()))
        cp.set("audio", "silence_threshold", str(self.silence_thresh.value()))
        cp.set("audio", "silence_duration", str(self.silence_dur.value()))
        
        # Transcription
        cp.set("transcription", "backend", self.asr_backend.currentText())
        cp.set("transcription", "whisper_model", self.whisper_model.currentText())
        cp.set("transcription", "funasr_model", self.funasr_model.currentText())
        cp.set("transcription", "device", self.device_type.currentText())
        cp.set("transcription", "compute_type", self.compute_type.currentText())
        enhanced_accuracy = bool(self.enhanced_accuracy_mode.currentData())
        accuracy_profile = str(self.accuracy_profile.currentData() or "auto")
        cp.set("transcription", "enhanced_accuracy", str(enhanced_accuracy).lower())
        cp.set("transcription", "accuracy_profile", accuracy_profile)
        source_language = str(
            self.source_language.currentData() or self.source_language.currentText()
        )
        cp.set("transcription", "source_language", source_language)
        
        # Translation — normalize exactly once so Test and Live share it.
        from translation_engine import normalize_base_url
        translation_mode = str(self.translation_mode.currentData() or "off")
        normalized_url = normalize_base_url(self.base_url.text(), translation_mode)
        self.base_url.setText(normalized_url)
        cp.set("api", "api_key", self.api_key.text())
        cp.set("api", "base_url", normalized_url)
        cp.set("translation", "model", self.model.currentText())
        cp.set("translation", "target_lang", str(self.target_lang.currentData() or self.target_lang.currentText()))
        cp.set("translation", "mode", translation_mode)

        # App and overlay appearance
        cp.set("app", "language", self.ui_language)
        session_choice = str(self.session_mode_combo.currentData() or "temporary")
        session_mode = "temporary" if session_choice == "temporary" else "saved"
        cp.set("app", "session_mode", session_mode)
        record_session_audio = session_choice == "saved_recording"
        cp.set("app", "record_session_audio", str(record_session_audio).lower())
        cp.set("display", "window_width", str(self.window_width.value()))
        cp.set("display", "visible_subtitles", str(self.visible_subtitles.value()))
        cp.set("display", "history_limit", str(getattr(config, "subtitle_history_limit", 250)))
        cp.set("display", "original_font_size", str(self.original_font_size.value()))
        cp.set("display", "translation_font_size", str(self.translation_font_size.value()))
        cp.set("display", "original_color", self.original_color.currentText())
        cp.set("display", "translation_color", self.translation_color.currentText())
        cp.set("display", "window_opacity", str(self.window_opacity.value() / 100.0))
        cp.set("display", "display_mode", str(self.display_mode.currentData() or "bilingual"))
        
        write_config(cp, config_path)

        # Keep the singleton used by create_pipeline in sync with what is on
        # screen.  Previously this only updated disk, causing Live to launch
        # with stale provider/model values after a successful connection test.
        config.device_index = idx
        config.input_source = input_source
        config.sample_rate = self.sample_rate.value()
        config.silence_threshold = self.silence_thresh.value()
        config.silence_duration = self.silence_dur.value()
        config.asr_backend = self.asr_backend.currentText()
        config.whisper_model = self.whisper_model.currentText()
        config.funasr_model = self.funasr_model.currentText()
        config.whisper_device = self.device_type.currentText()
        config.whisper_compute_type = self.compute_type.currentText()
        config.enhanced_accuracy = enhanced_accuracy
        config.accuracy_profile = accuracy_profile
        source = source_language
        config.source_language = None if source == "auto" else source
        config.api_key = self.api_key.text().strip()
        config.api_base_url = normalized_url
        config.model = self.model.currentText().strip()
        config.target_lang = str(self.target_lang.currentData() or self.target_lang.currentText())
        config.translation_mode = translation_mode
        config.session_mode = session_mode
        config.record_session_audio = record_session_audio
        config.use_translation_scheduler = session_mode == "saved"
        config.use_sqlite_session_repository = session_mode == "saved"
        config.use_segment_api_for_history = session_mode == "saved"
        config.use_segment_api_for_export = session_mode == "saved"
        config.original_font_size = self.original_font_size.value()
        config.translation_font_size = self.translation_font_size.value()
        config.original_color = self.original_color.currentText()
        config.translation_color = self.translation_color.currentText()
        config.window_opacity = self.window_opacity.value() / 100.0
        config.window_width = self.window_width.value()
        config.visible_subtitles = self.visible_subtitles.value()
        config.display_mode = self.display_mode.currentData() or "bilingual"
        
        # Visual feedback
        self._set_localized_text(self.save_btn, "Saved")
        self._set_localized_text(self.status_label, "Settings saved")
        # Restore after 2s
        QTimer.singleShot(
            2000,
            lambda: self._set_localized_text(self.save_btn, "Save Changes"),
        )

    def on_start(self):
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.info("Launch Translator clicked")
        self.save_config()

        if bool(getattr(config, "enhanced_accuracy", False)):
            from model_manager import model_manager
            _, plan = self._selected_accuracy_plan()
            if not model_manager.is_downloaded(plan.model_id, "whisper"):
                title = ui_translate("Download enhanced model?", self.ui_language)
                detail = ui_translate(
                    "Enhanced accuracy needs the recommended local model before this session can start.",
                    self.ui_language,
                )
                reply = QMessageBox.question(
                    self,
                    title,
                    f"{detail}\n\n{plan.model_id} · {plan.size_label}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._pending_start_after_accuracy_download = True
                    self._download_accuracy_model()
                return
        
        # Update UI to Loading State
        self._set_localized_text(self.status_label, "Initializing…")
        self.status_label.setStyleSheet("font-size: 18px; color: #fab387;")
        self.start_btn.setEnabled(False)
        self._set_localized_text(self.start_btn, "Loading…")
        
        # Start worker thread for NON-UI preparation
        self.startup_worker = StartupWorker()
        self.startup_worker.ready.connect(self._on_startup_ready)
        self.startup_worker.failed.connect(self._on_startup_failed)
        log.info("StartupWorker started")
        self.startup_worker.start()

    def _on_startup_ready(self, result):
        """Called on MAIN THREAD when startup preparation is done.
        Creates overlay window HERE — never in background thread."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.info("StartupWorker finished, creating overlay on main thread")
        
        pipeline, signals = result
        
        try:
            # Create overlay ON MAIN THREAD
            from main import create_and_show_overlay
            log.info("Creating overlay on main thread...")
            style = {
                "original_font_size": self.original_font_size.value(),
                "translation_font_size": self.translation_font_size.value(),
                "original_color": self.original_color.currentText(),
                "translation_color": self.translation_color.currentText(),
                "window_opacity": self.window_opacity.value() / 100.0,
                "window_width": self.window_width.value(),
                "visible_subtitles": self.visible_subtitles.value(),
                "history_limit": getattr(config, "subtitle_history_limit", 250),
                "display_mode": self.display_mode.currentData() or "bilingual",
                "ui_language": self.ui_language,
            }
            self.overlay_window = create_and_show_overlay(
                pipeline, signals, start_pipeline=False, subtitle_style=style
            )
            log.info("Overlay shown")
            
            self.pipeline = pipeline
            
            # Connect overlay signals
            if hasattr(self.overlay_window, 'stop_requested'):
                self.overlay_window.stop_requested.connect(self.on_stop)
            if hasattr(self.overlay_window, 'style_changed'):
                self.overlay_window.style_changed.connect(self._on_style_changed)
            if hasattr(self.overlay_window, 'control_center_requested'):
                self.overlay_window.control_center_requested.connect(self._toggle_control_center)
            
            # Connect lifecycle signals BEFORE pipeline.start()
            if hasattr(signals, 'pipeline_failed'):
                signals.pipeline_failed.connect(self._on_pipeline_failed)
            if hasattr(signals, 'pipeline_cleanup_finished'):
                signals.pipeline_cleanup_finished.connect(self._on_pipeline_cleanup_finished)
            if hasattr(signals, 'pipeline_started'):
                signals.pipeline_started.connect(self._on_pipeline_started)
            if hasattr(signals, 'audio_failed'):
                signals.audio_failed.connect(self._on_audio_failed)
            
            # Set a 10s startup timeout
            self._startup_timeout = QTimer()
            self._startup_timeout.setSingleShot(True)
            self._startup_timeout.timeout.connect(self._on_startup_timeout)
            self._startup_timeout.start(10000)
            
            # Now safe to start
            self._set_localized_text(self.status_label, "Starting…")
            self.status_label.setStyleSheet("font-size: 18px; color: #fab387;")
            pipeline.start()
            
            log.info("Translator launched, waiting for pipeline_started signal...")
            
            log.info("Translator launched successfully")
        except Exception:
            log.exception("Failed to create overlay")
            self._on_startup_failed(f"Failed to create overlay:\n{__import__('traceback').format_exc()}")

    def _on_startup_failed(self, error):
        """Called on MAIN THREAD when startup fails."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.error(f"Startup failed: {error}")
        
        self._set_localized_text(self.status_label, "Initialization Failed")
        self.status_label.setStyleSheet("font-size: 18px; color: #f38ba8;")
        self.start_btn.setEnabled(True)
        self._set_localized_text(self.start_btn, "Start Live Subtitles")
        self._show_control_center()
        
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Launch Failed",
                           f"Failed to launch translator:\n\n{str(error)[:500]}")
    
    def _on_pipeline_failed(self, error):
        """Pipeline thread crashed. Disable Launch until cleanup completes."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.error(f"Pipeline failed: {error}")
        self.last_pipeline_error = error
        self._set_localized_text(self.status_label, "Pipeline Error — cleaning up…")
        self.status_label.setStyleSheet("font-size: 18px; color: #fab387;")
        self.stop_btn.hide()
        self.start_btn.show()
        self.start_btn.setEnabled(False)
        self._set_localized_text(self.start_btn, "Cleaning up…")
        self._show_control_center()
    
    def _on_pipeline_cleanup_finished(self, success, message):
        """ASR worker and executors have shut down (or not). Safe to clean UI only if success."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.info(f"Pipeline cleanup finished: success={success} {message}")
        if not success:
            self._set_localized_text(self.status_label, "Cleanup failed — retry or force quit")
            self.status_label.setStyleSheet("font-size: 18px; color: #f38ba8;")
            self.start_btn.setEnabled(False)
            self._set_localized_text(self.start_btn, "Retry Stop")
            return
        if hasattr(self, 'overlay_window') and self.overlay_window:
            self.overlay_window.close()
            self.overlay_window = None
        self.pipeline = None
        self._set_localized_text(self.status_label, "Pipeline Error — ready to retry")
        self.status_label.setStyleSheet("font-size: 18px; color: #f38ba8;")
        self.start_btn.setEnabled(True)
        self._set_localized_text(self.start_btn, "Retry Start")
    
    def _on_pipeline_started(self):
        """Pipeline confirmed started — transition to Running."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.info("Pipeline started confirmed")
        if hasattr(self, '_startup_timeout'):
            self._startup_timeout.stop()
        self.start_btn.hide()
        self._set_localized_text(self.status_label, "Running…")
        self.status_label.setStyleSheet("font-size: 18px; color: #a6e3a1;")
        self.stop_btn.show()
        self.stop_btn.setEnabled(True)
        self._hide_control_center_for_session()

    def _hide_control_center_for_session(self):
        """Keep the caption overlay running without a minimized main window."""
        self._control_center_hidden_for_session = True
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.hide()
        if getattr(self, "overlay_window", None):
            self.overlay_window.set_control_center_visible(False)

    def _toggle_control_center(self):
        """The overlay control is a true show/hide toggle."""
        if self.isVisible():
            self._hide_control_center_for_session()
        else:
            self._show_control_center()

    def _show_control_center(self):
        """Explicit user path back from the overlay to the main controls."""
        self._control_center_hidden_for_session = False
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if getattr(self, "overlay_window", None):
            self.overlay_window.set_control_center_visible(True)
    
    def _on_audio_failed(self, message):
        """Audio device failure. Show error, disable Retry until cleanup."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.error(f"Audio device failed: {message}")
        self._set_localized_text(self.status_label, "Audio Device Error")
        self.status_label.setStyleSheet("font-size: 18px; color: #f38ba8;")
        self.last_pipeline_error = f"Audio: {message[:200]}"
        self.stop_btn.hide()
        self.start_btn.show()
        self.start_btn.setEnabled(False)  # disabled until cleanup_finished
        self._set_localized_text(self.start_btn, "Wait…")
        self._show_control_center()
    
    def _on_startup_timeout(self):
        """Pipeline never confirmed start."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.error("Pipeline start timeout")
        if hasattr(self, 'pipeline') and self.pipeline:
            self.pipeline.stop()
        self._set_localized_text(self.status_label, "Start failed — timeout")
        self.status_label.setStyleSheet("font-size: 18px; color: #f38ba8;")
        self.start_btn.show()
        self.start_btn.setEnabled(True)
        self._set_localized_text(self.start_btn, "Retry Start")
        self._show_control_center()
    
    def _on_style_changed(self, style):
        """Sync style changes back to the style tab"""
        if hasattr(self, 'original_font_size'):
            self.original_font_size.blockSignals(True)
            self.original_font_size.setValue(style.get('original_font_size', 18))
            self.original_font_size.blockSignals(False)
        if hasattr(self, 'translation_font_size'):
            self.translation_font_size.blockSignals(True)
            self.translation_font_size.setValue(style.get('translation_font_size', 16))
            self.translation_font_size.blockSignals(False)
        if hasattr(self, 'window_opacity'):
            self.window_opacity.blockSignals(True)
            self.window_opacity.setValue(round(float(style.get('window_opacity', 0.85)) * 100))
            self.window_opacity.blockSignals(False)
        if hasattr(self, 'display_mode'):
            self.display_mode.blockSignals(True)
            idx = self.display_mode.findData(style.get('display_mode', 'bilingual'))
            if idx >= 0:
                self.display_mode.setCurrentIndex(idx)
            self.display_mode.blockSignals(False)
        if hasattr(self, 'visible_subtitles'):
            self.visible_subtitles.blockSignals(True)
            self.visible_subtitles.setValue(style.get('visible_subtitles', 3))
            self.visible_subtitles.blockSignals(False)

    def on_stop(self):
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        
        self.stop_btn.setEnabled(False)
        self._set_localized_text(self.stop_btn, "Stopping…")
        
        if hasattr(self, 'pipeline') and self.pipeline:
            try:
                ok = self.pipeline.stop()
            except Exception:
                log.exception("Pipeline stop failed — forcing cleanup")
                ok = False
            if not ok:
                log.error("Pipeline stop timed out")
                self._set_localized_text(self.status_label, "Stop timed out — Retry or Force Quit")
                self.status_label.setStyleSheet("font-size: 18px; color: #f38ba8;")
                self.stop_btn.setEnabled(True)
                self._set_localized_text(self.stop_btn, "Retry Stop")
                return False
            self.pipeline = None
            
        if hasattr(self, 'overlay_window') and self.overlay_window:
            self.overlay_window.close()
            self.overlay_window = None
        
        log.info("Translator stopped")
        
        self._set_localized_text(self.status_label, "Stopped")
        self.status_label.setStyleSheet("font-size: 18px; color: #6c7086;")
        self.stop_btn.hide()
        self.start_btn.show()
        self.start_btn.setEnabled(True)
        self._set_localized_text(self.start_btn, "Start Live Subtitles")
        self._show_control_center()
        if hasattr(self, "history_list"):
            self._refresh_history()
        return True

class StartupWorker(QThread):
    ready = pyqtSignal(object)    # emits (pipeline, signals) tuple
    failed = pyqtSignal(str)     # emits error message

    def run(self):
        """NON-UI preparation only. NEVER create windows or widgets here."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.info("StartupWorker: beginning non-UI preparation")
        
        try:
            from main import create_pipeline
            pipeline, signals = create_pipeline()
            log.info("StartupWorker: pipeline created")
            self.ready.emit((pipeline, signals))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            log.error(f"StartupWorker: failed\n{tb}")
            self.failed.emit(tb)

if __name__ == "__main__":
    def exception_hook(exctype, value, traceback_obj):
        import traceback
        traceback_str = ''.join(traceback.format_tb(traceback_obj))
        error_msg = f"Unhandled Exception: {value}\n\n{traceback_str}"
        print(error_msg)
        from PyQt6.QtWidgets import QMessageBox
        if QApplication.instance():
            QMessageBox.critical(None, "Crash", error_msg)
        else:
            # If no app, just print (already done)
            pass
        sys.exit(1)

    sys.excepthook = exception_hook

    app = QApplication(sys.argv)
    w = Dashboard()
    w.show()
    sys.exit(app.exec())
