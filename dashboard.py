from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QComboBox, QLineEdit, 
                             QSpinBox, QDoubleSpinBox, QGridLayout,
                             QScrollArea, QSizePolicy, QSpacerItem, QFormLayout, QApplication,
                             QMessageBox, QTextEdit, QDialog)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor, QPixmap
import sys
import os
from pathlib import Path
import sounddevice as sd
from config import config
from product_navigation import ProductNavigation

# Modern QSS Styles
STYLESHEET = """
QWidget {
    background-color: #0b1020;
    color: #e8edff;
    font-family: 'Helvetica Neue', Arial;
    font-size: 13px;
}
QFrame#AppHeader { background: #0d1427; border-bottom: 1px solid #202b45; }
QLabel#BrandTitle { color: #f7f9ff; font-size: 22px; font-weight: 700; }
QLabel#BrandSubtitle { color: #8792ad; font-size: 12px; }
QLabel#BuildPill {
    color: #aebcff; background: #18213a; border: 1px solid #2a3b69;
    border-radius: 11px; padding: 4px 10px; font-size: 10px; font-weight: 600;
}
QFrame#Sidebar { background: #0d1427; border-right: 1px solid #202b45; }
QLabel#SidebarEyebrow { color: #596681; font-size: 9px; font-weight: 700; }
QLabel#PrivacyNote {
    color: #68748e; background: #111a30; border: 1px solid #202b45;
    border-radius: 10px; padding: 10px; font-size: 10px;
}
QPushButton#NavButton {
    text-align: left; color: #919cb6; background: transparent;
    border: none; border-radius: 9px; padding: 9px 13px; font-weight: 600;
}
QPushButton#NavButton:hover { background: #141e35; color: #dce4ff; }
QPushButton#NavButton:checked {
    background: #1c2948; color: #9bb5ff; border-left: 3px solid #7d9cff;
}
QStackedWidget#ProductStack { background: #0b1020; }
QTabWidget#SectionTabs::pane { border: none; background: #0b1020; top: -1px; }
QTabWidget#SectionTabs QTabBar::tab {
    background: transparent; color: #74809b; padding: 11px 18px;
    border: none; border-bottom: 2px solid transparent; font-weight: 600;
}
QTabWidget#SectionTabs QTabBar::tab:hover { color: #c7d2ee; }
QTabWidget#SectionTabs QTabBar::tab:selected { color: #9bb5ff; border-bottom-color: #7d9cff; }
QLabel { font-size: 13px; background: transparent; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #141d31; border: 1px solid #293550; border-radius: 8px;
    padding: 8px 10px; min-height: 20px; color: #e8edff;
    selection-background-color: #425a9c;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #7897ff;
}
QPushButton {
    background-color: #7d9cff; color: #091022; border: none;
    padding: 9px 16px; border-radius: 8px; font-weight: 700;
}
QPushButton:hover { background-color: #9eb4ff; }
QPushButton:disabled { background: #25304a; color: #66718a; }
QPushButton#SecondaryButton { background: #18233b; color: #c9d4ef; border: 1px solid #2b3957; }
QPushButton#SecondaryButton:hover { background: #22304d; }
QPushButton#DangerButton { background: #4a2537; color: #ffb1c4; border: 1px solid #744159; }
QFrame#HeroCard, QFrame#SummaryCard {
    background: #111a2e; border: 1px solid #23304b; border-radius: 16px;
}
QLabel#HeroEyebrow { color: #7d9cff; font-size: 10px; font-weight: 700; }
QLabel#HeroTitle { color: #f7f9ff; font-size: 27px; font-weight: 700; }
QLabel#HeroCopy { color: #8792ad; font-size: 13px; }
QLabel#StatusPill {
    color: #8fe7c0; background: #102b28; border: 1px solid #1e5147;
    border-radius: 12px; padding: 5px 12px; font-size: 11px; font-weight: 700;
}
QLabel#SummaryLabel { color: #68748e; font-size: 10px; font-weight: 700; }
QLabel#SummaryValue { color: #e8edff; font-size: 14px; font-weight: 600; }
QScrollArea { background: transparent; border: none; }
QTextEdit {
    background: #0a0f1d; color: #dfe6fb; border: 1px solid #293550;
    border-radius: 10px; padding: 10px;
}
QGroupBox { border: 1px solid #293550; border-radius: 10px; margin-top: 12px; padding-top: 12px; }
QGroupBox::title { subcontrol-origin: margin; padding: 0 7px; color: #9bb5ff; }
"""

class Dashboard(QWidget):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    model_download_status = pyqtSignal(str, str, int)
    model_download_done = pyqtSignal(str, int, object, int)  # (model_id, terminal_state, error, attempt)
    progress_event = pyqtSignal(object)  # ProgressEvent — update ProgressPanel
    translation_test_finished = pyqtSignal(bool, str)
    model_list_finished = pyqtSignal(bool, object, str)

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
        """Close window only after clean stop + cancel downloads."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")

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
        self.status_label.setText("Stopping...")
        if self._attempt_close_after_stop():
            log.info("Clean stop before close — quitting")
            event.accept()
            QApplication.quit()
        else:
            event.ignore()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Realtime Subtitle — Control Center")
        self.setMinimumSize(860, 600)
        self.resize(1080, 720)
        self.setStyleSheet(STYLESHEET)
        
        # Main Layout
        self.layout = QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        
        # ---- Create UI elements BEFORE any tab that needs them ----
        self._active_downloads = {}
        self._progress_model_id = None
        self._progress_backend = None
        
        from progress_panel import ProgressPanel
        self.progress_panel = ProgressPanel()
        self.progress_panel.setVisible(False)
        self.progress_panel.retry_clicked.connect(self._retry_progress_model)
        self.progress_panel.cancel_clicked.connect(self._cancel_progress_model)
        self.progress_panel.dismiss_clicked.connect(self._dismiss_progress_panel)
        
        # Product header
        header = QFrame()
        header.setObjectName("AppHeader")
        header.setFixedHeight(82)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 14, 24, 14)
        header_layout.setSpacing(13)

        icon_label = QLabel()
        icon_path = Path(__file__).resolve().parent / "assets" / "icon" / "realtime-subtitle-icon.png"
        if icon_path.exists():
            icon_label.setPixmap(
                QPixmap(str(icon_path)).scaled(
                    50,
                    50,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        icon_label.setFixedSize(52, 52)
        header_layout.addWidget(icon_label)

        brand = QVBoxLayout()
        brand.setSpacing(2)
        brand_title = QLabel("Realtime Subtitle")
        brand_title.setObjectName("BrandTitle")
        brand_subtitle = QLabel("Live captions, translated as you speak")
        brand_subtitle.setObjectName("BrandSubtitle")
        brand.addWidget(brand_title)
        brand.addWidget(brand_subtitle)
        header_layout.addLayout(brand)
        header_layout.addStretch()

        try:
            from version import BUILD_VERSION
            build_label = str(BUILD_VERSION).replace("-dev", "")
        except ImportError:
            build_label = "Development"
        build_pill = QLabel(f"LOCAL-FIRST  ·  {build_label}")
        build_pill.setObjectName("BuildPill")
        header_layout.addWidget(build_pill)
        self.layout.addWidget(header)
        
        # Five product sections; related settings are grouped internally.
        self.tabs = ProductNavigation()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.layout.addWidget(self.tabs)
        
        self.init_home_tab()
        self.init_audio_tab()
        self.init_device_manager_tab()
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

        # Persistent footer actions
        footer_frame = QFrame()
        footer_frame.setObjectName("AppHeader")
        footer = QHBoxLayout(footer_frame)
        footer.setContentsMargins(24, 11, 24, 11)
        footer_note = QLabel("Changes are stored locally on this Mac")
        footer_note.setObjectName("BrandSubtitle")
        footer.addWidget(footer_note)
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self.save_config)
        footer.addStretch()
        footer.addWidget(self.save_btn)
        self.layout.addWidget(footer_frame)

    def init_home_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(30, 28, 30, 28)
        hero_layout.setSpacing(12)

        eyebrow = QLabel("LIVE WORKSPACE")
        eyebrow.setObjectName("HeroEyebrow")
        hero_layout.addWidget(eyebrow)

        title = QLabel("Bring every word into view.")
        title.setObjectName("HeroTitle")
        hero_layout.addWidget(title)

        copy = QLabel(
            "Private on-device speech recognition with an always-on-top subtitle window. "
            "Add translation only when you need it."
        )
        copy.setObjectName("HeroCopy")
        copy.setWordWrap(True)
        hero_layout.addWidget(copy)

        action_row = QHBoxLayout()
        action_row.setSpacing(12)
        self.start_btn = QPushButton("Start Live Subtitles")
        self.start_btn.setFixedSize(210, 46)
        self.start_btn.clicked.connect(self.on_start)
        action_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Session")
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.setFixedSize(160, 46)
        self.stop_btn.clicked.connect(self.on_stop)
        self.stop_btn.hide()
        action_row.addWidget(self.stop_btn)

        self.status_label = QLabel("READY")
        self.status_label.setObjectName("StatusPill")
        action_row.addWidget(self.status_label)
        action_row.addStretch()
        hero_layout.addLayout(action_row)
        layout.addWidget(hero)

        summaries = QHBoxLayout()
        summaries.setSpacing(12)
        summary_values = (
            (
                "INPUT",
                "Default microphone"
                if config.device_index is None
                else str(config.device_index),
            ),
            ("RECOGNITION", f"Whisper · {config.whisper_model}"),
            (
                "TRANSLATION",
                "Off" if config.translation_mode == "off" else config.target_lang,
            ),
        )
        for label_text, value_text in summary_values:
            card = QFrame()
            card.setObjectName("SummaryCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 15, 18, 15)
            card_layout.setSpacing(5)
            label = QLabel(label_text)
            label.setObjectName("SummaryLabel")
            value = QLabel(value_text)
            value.setObjectName("SummaryValue")
            value.setWordWrap(True)
            card_layout.addWidget(label)
            card_layout.addWidget(value)
            summaries.addWidget(card, 1)
        layout.addLayout(summaries)

        tip = QLabel(
            "Tip: once started, the Control Center minimizes automatically. "
            "Drag the subtitle window anywhere on screen and use its compact controls on hover."
        )
        tip.setObjectName("BrandSubtitle")
        tip.setWordWrap(True)
        layout.addWidget(tip)
        layout.addStretch()

        tab.setLayout(layout)
        self.tabs.addTab(tab, "Home")

    def init_audio_tab(self):
        tab = QWidget()
        layout = QGridLayout() # Use Grid for organized form
        layout.setSpacing(15)
        
        # Device Selection
        layout.addWidget(QLabel("Input Device:"), 0, 0)
        self.device_combo = QComboBox()
        self.populate_devices()
        layout.addWidget(self.device_combo, 0, 1)
        
        # Refresh Button
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedWidth(40)
        refresh_btn.clicked.connect(self.populate_devices)
        layout.addWidget(refresh_btn, 0, 2)
        
        # Sample Rate
        layout.addWidget(QLabel("Sample Rate:"), 1, 0)
        self.sample_rate = QSpinBox()
        self.sample_rate.setRange(8000, 48000)
        self.sample_rate.setValue(config.sample_rate)
        layout.addWidget(self.sample_rate, 1, 1)

        # Silence Threshold
        layout.addWidget(QLabel("Silence Threshold:"), 2, 0)
        self.silence_thresh = QDoubleSpinBox()
        self.silence_thresh.setRange(0.001, 1.0)
        self.silence_thresh.setSingleStep(0.001)
        self.silence_thresh.setDecimals(3)
        self.silence_thresh.setValue(config.silence_threshold)
        layout.addWidget(self.silence_thresh, 2, 1)
        
        layout.addWidget(QLabel("Silence Duration (s):"), 3, 0)
        self.silence_dur = QDoubleSpinBox()
        self.silence_dur.setValue(config.silence_duration)
        layout.addWidget(self.silence_dur, 3, 1)
        
        layout.setRowStretch(4, 1) # Push to top
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "🎤 Audio")

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
        
        self.refresh_devices_btn = QPushButton("🔄 Refresh Devices")
        self.refresh_devices_btn.clicked.connect(self.refresh_audio_devices)
        btn_layout.addWidget(self.refresh_devices_btn)
        
        self.create_multi_output_btn = QPushButton("➕ Create Multi-Output Device")
        self.create_multi_output_btn.setStyleSheet("""
            background-color: #a6e3a1; color: #1e1e2e; font-weight: bold;
        """)
        self.create_multi_output_btn.clicked.connect(self.create_multi_output_device)
        btn_layout.addWidget(self.create_multi_output_btn)
        
        layout.addLayout(btn_layout)
        
        # Set as Default Button
        self.set_default_btn = QPushButton("🔊 Set Selected as Default Output")
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
        self.tabs.addTab(tab, "🔧 Devices")
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
        title = QLabel("📋 Step-by-Step Guide")
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
        close_btn = QPushButton("✅ Got it!")
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
        self.refresh_models_btn.setText("Fetch")
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
        layout = QFormLayout()
        
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
        self.whisper_model.addItems(["tiny", "tiny.en", "base", "base.en", "small", "small.en", "medium", "medium.en", "large-v3", "turbo"])
        self.whisper_model.setCurrentText(config.whisper_model)
        layout.addRow("Whisper Model:", self.whisper_model)
        
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
        self.source_language.setEditable(True)
        self.source_language.addItems(["auto", "en", "zh", "vi", "ja", "ko", "es", "fr", "de", "ru", "ar", "pt", "it"])
        source_lang = config.source_language if config.source_language else "auto"
        self.source_language.setCurrentText(source_lang)
        layout.addRow("Source Language:", self.source_language)
        
        # Update UI based on initial backend
        self._on_backend_changed(config.asr_backend)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "📝 Transcript")
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
        layout = QFormLayout()

        self.translation_mode = QComboBox()
        self.translation_mode.addItem("Off — original subtitles only", "off")
        self.translation_mode.addItem("Online API — hosted OpenAI-compatible", "online")
        self.translation_mode.addItem("Local LLM — LM Studio / Ollama", "local")
        self.translation_mode.addItem("Custom OpenAI-compatible API", "custom")
        self.translation_mode.addItem("macOS System Translation (experimental)", "fast")
        mode_index = self.translation_mode.findData(config.translation_mode)
        self.translation_mode.setCurrentIndex(max(0, mode_index))
        self.translation_mode.currentIndexChanged.connect(self.update_translation_mode_label)
        layout.addRow("Mode:", self.translation_mode)
        
        self.api_key = QLineEdit(config.api_key)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("sk-...")
        self.api_key.textChanged.connect(self.update_translation_mode_label)
        layout.addRow("API Key:", self.api_key)
        
        self.base_url = QLineEdit(config.api_base_url or "")
        self.base_url.setPlaceholderText("https://api.openai.com/v1")
        self.base_url.setToolTip("Must start with http:// or https://. Example: http://localhost:1234/v1")
        self.base_url.textChanged.connect(self.update_translation_mode_label)
        layout.addRow("Base URL:", self.base_url)
        
        # Model selection with refresh button
        model_layout = QHBoxLayout()
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItem(config.model)
        self.model.setToolTip("Model name. Use 'Fetch' to pull from server.")
        self.model.currentTextChanged.connect(self.update_translation_mode_label)
        model_layout.addWidget(self.model)
        
        self.refresh_models_btn = QPushButton("Fetch")
        self.refresh_models_btn.setFixedWidth(80)
        self.refresh_models_btn.setToolTip("Fetch models from API server")
        self.refresh_models_btn.clicked.connect(self.refresh_model_list)
        model_layout.addWidget(self.refresh_models_btn)
        
        layout.addRow("Model:", model_layout)
        
        self.target_lang = QComboBox()
        self.target_lang.addItems(["Chinese", "English", "Japanese", "French", "Spanish", "German", "Korean"])
        self.target_lang.setEditable(True)
        self.target_lang.setCurrentText(config.target_lang)
        layout.addRow("Target Language:", self.target_lang)
        
        # Test Translation button
        test_layout = QHBoxLayout()
        self.test_trans_btn = QPushButton("🔗 Test Connection")
        self.test_trans_btn.setStyleSheet(
            "QPushButton { background: #45475a; color: #cdd6f4; padding: 8px 16px; "
            "border-radius: 4px; font-weight: bold; } "
            "QPushButton:hover { background: #585b70; }"
        )
        self.test_trans_btn.clicked.connect(self._test_translation)
        test_layout.addWidget(self.test_trans_btn)
        test_layout.addStretch()
        layout.addRow(test_layout)
        
        # Test result label
        self.trans_test_result = QLabel("")
        self.trans_test_result.setWordWrap(True)
        self.trans_test_result.setStyleSheet("color: #6c7086; font-size: 12px; padding-top: 5px;")
        layout.addRow(self.trans_test_result)

        self.trans_mode_label = QLabel("")
        self.trans_mode_label.setStyleSheet("color: #6c7086; font-size: 12px; padding: 5px 0;")
        self.trans_mode_label.setWordWrap(True)
        layout.addRow(self.trans_mode_label)
        self.update_translation_mode_label()
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "🈵 Translate")
        self.tabs.setTabToolTip(self.tabs.count() - 1, "Translate — API, model, test connection")
        
    def update_translation_mode_label(self, *_):
        mode = self.translation_mode.currentData() or "off"
        api_key = self.api_key.text().strip()
        base_url = self.base_url.text().strip()
        model = self.model.currentText().strip()
        if mode == "off":
            self.trans_mode_label.setText("Translation: Off — original subtitles only")
        elif mode == "online" and (not api_key or api_key == "sk-..."):
            self.trans_mode_label.setText("Translation: Off (no API key)")
        elif mode == "online":
            endpoint = base_url or "OpenAI default endpoint"
            self.trans_mode_label.setText(f"Translation: Online — {model} via {endpoint}")
        elif mode == "local":
            endpoint = base_url or "http://localhost:1234/v1"
            self.trans_mode_label.setText(f"Translation: Local — {model} via {endpoint}")
        elif mode == "custom":
            self.trans_mode_label.setText(
                f"Translation: Custom — {model} via {base_url or '(endpoint required)'}"
            )
        else:
            self.trans_mode_label.setText("Translation: macOS System Translation (experimental)")
    
    def _test_translation(self):
        """Test translation backend with current settings"""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        
        api_key = self.api_key.text().strip()
        base_url = self.base_url.text().strip()
        model = self.model.currentText().strip()
        mode = self.translation_mode.currentData() or "off"
        target_lang = self.target_lang.currentText()

        if mode == "off":
            self.trans_test_result.setText("ℹ️ Translation is disabled; no connection is needed")
            self.trans_test_result.setStyleSheet("color: #89b4fa; font-size: 12px;")
            return
        
        # Guard: empty API key or placeholder
        if mode == "online" and (
            not api_key or api_key in ("sk-...", "", "dummy-key-for-local")
        ):
            self.trans_test_result.setText("❌ No API key configured — enter a key to test")
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
            self.trans_test_result.setText("❌ No API endpoint configured")
            self.trans_test_result.setStyleSheet("color: #f38ba8; font-size: 12px;")
            return
        
        is_local = any(h in base_url for h in ("localhost", "127.0.0.1", "::1"))
        
        endpoint_label = base_url or "OpenAI default endpoint"
        self.trans_test_result.setText(f"Testing {endpoint_label}...")
        self.trans_test_result.setStyleSheet("color: #fab387; font-size: 12px;")
        self.test_trans_btn.setEnabled(False)
        
        def _do_test():
            from translation_engine import TranslationEngine
            
            try:
                engine = TranslationEngine()
                engine.target_lang = target_lang
                engine.set_mode(mode, base_url=base_url, api_key=api_key, model=model)
                health = engine.check_health()
                if health.get("available"):
                    self.translation_test_finished.emit(True, f"Connected — {model}")
                else:
                    err = health.get("error", "Unknown error")
                    hint = ""
                    if is_local:
                        hint = "\nLocal endpoint may have been routed through system proxy. "
                    self.translation_test_finished.emit(False, f"{err}{hint}")
            except Exception as e:
                log.error(f"Translation test: {e}")
                self.translation_test_finished.emit(False, f"{type(e).__name__}: {str(e)[:160]}")
        
        import threading
        threading.Thread(target=_do_test, daemon=True).start()

    def _on_translation_test_finished(self, ok: bool, message: str):
        self.trans_test_result.setText(("✅ " if ok else "❌ ") + message)
        color = "#a6e3a1" if ok else "#f38ba8"
        self.trans_test_result.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.test_trans_btn.setEnabled(True)
        self.test_trans_btn.setText("🔗 Test Connection")

    def init_model_tab(self):
        """Model Management tab - download/delete/switch ASR models"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        header = QLabel("📦 Model Management")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #fab387;")
        layout.addWidget(header)
        
        # Backend filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Backend:"))
        self.model_backend_combo = QComboBox()
        self.model_backend_combo.addItems(["whisper", "mlx"])
        self.model_backend_combo.currentTextChanged.connect(self._refresh_model_list)
        filter_layout.addWidget(self.model_backend_combo)
        filter_layout.addStretch()
        
        self.refresh_model_btn = QPushButton("🔄 Refresh")
        self.refresh_model_btn.clicked.connect(self._refresh_model_list)
        filter_layout.addWidget(self.refresh_model_btn)
        layout.addLayout(filter_layout)
        
        # Model list
        self.model_list_widget = QWidget()
        self.model_list_layout = QVBoxLayout()
        self.model_list_layout.setSpacing(5)
        self.model_list_widget.setLayout(self.model_list_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.model_list_widget)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #45475a; border-radius: 6px; }")
        layout.addWidget(scroll)
        
        # Status
        self.model_mgmt_status = QLabel("")
        self.model_mgmt_status.setWordWrap(True)
        self.model_mgmt_status.setStyleSheet("color: #a6adc8; font-size: 12px;")
        layout.addWidget(self.model_mgmt_status)
        
        # Clear all button
        clear_layout = QHBoxLayout()
        clear_layout.addStretch()
        self.clear_models_btn = QPushButton("🗑 Delete All Models")
        self.clear_models_btn.setStyleSheet(
            "QPushButton { background: #f38ba8; color: #1e1e2e; padding: 5px 10px; border-radius: 4px; } "
            "QPushButton:hover { background: #eba0ac; }"
        )
        self.clear_models_btn.clicked.connect(self._clear_all_models)
        clear_layout.addWidget(self.clear_models_btn)
        layout.addLayout(clear_layout)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "📦 Models")
        
        layout.addWidget(self.progress_panel)
        self.progress_panel.title.setText("Download Progress")
        
        self._refresh_model_list()
    
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
        
        self.model_mgmt_status.setText(
            f"Total disk usage: {disk['total_mb']} MB across {disk['model_count']} models"
        )
    
    def _create_model_card(self, model_info, backend):
        """Create a card widget for a single model"""
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: #313244; border: 1px solid #45475a; "
            "border-radius: 6px; padding: 8px; margin: 2px; }"
        )
        
        layout = QHBoxLayout()
        layout.setSpacing(8)
        card.setLayout(layout)
        
        # Model info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        name_label = QLabel(f"{model_info['name']}")
        name_label.setStyleSheet("font-weight: bold; color: #cdd6f4; font-size: 13px;")
        info_layout.addWidget(name_label)
        
        detail = f"{model_info['speed']} | {model_info['accuracy']} | {model_info['size_mb']} MB"
        detail_label = QLabel(detail)
        detail_label.setStyleSheet("color: #6c7086; font-size: 11px;")
        info_layout.addWidget(detail_label)
        
        best_for = QLabel(model_info['best_for'])
        best_for.setStyleSheet("color: #a6adc8; font-size: 10px; font-style: italic;")
        info_layout.addWidget(best_for)
        
        layout.addLayout(info_layout, 1)
        
        # Action button
        downloaded = model_info['downloaded']
        mid = model_info['id']
        be = backend
        is_downloading = hasattr(self, '_active_downloads') and mid in self._active_downloads
        
        if downloaded:
            btn = QPushButton("✓ Downloaded")
            btn.setStyleSheet(
                "QPushButton { background: #a6e3a1; color: #1e1e2e; padding: 4px 8px; "
                "border-radius: 4px; font-size: 11px; } "
                "QPushButton:hover { background: #f38ba8; }"
            )
            btn.clicked.connect(lambda checked, mid=mid, be=be: self._delete_model(mid, be))
        elif is_downloading:
            btn = QPushButton("Cancel")
            btn.setStyleSheet(
                "QPushButton { background: #f38ba8; color: #1e1e2e; padding: 4px 8px; "
                "border-radius: 4px; font-size: 11px; } "
                "QPushButton:hover { background: #eba0ac; }"
            )
            btn.clicked.connect(lambda checked, mid=mid: self._cancel_download(mid))
        else:
            btn = QPushButton("Download")
            btn.setStyleSheet(
                "QPushButton { background: #89b4fa; color: #1e1e2e; padding: 4px 8px; "
                "border-radius: 4px; font-size: 11px; } "
                "QPushButton:hover { background: #b4befe; }"
            )
            btn.clicked.connect(lambda checked, mid=mid, be=be: self._download_model(mid, be))
        
        if model_info.get('recommended'):
            rec_label = QLabel("⭐")
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
        
        self.model_mgmt_status.setText(f"⏳ {model_id}: starting...")
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
        channel = ModelProgressChannel(model_id, max_attempts=3)
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
            self.model_mgmt_status.setText(f"⏳ {model_id}: attempt {attempt}...")
            self.model_mgmt_status.setStyleSheet("color: #fab387; font-size: 12px;")
        elif status == "retrying":
            self.model_mgmt_status.setText(f"🔄 {model_id}: retry {attempt}...")
            self.model_mgmt_status.setStyleSheet("color: #f9e2af; font-size: 12px;")
        elif status == "cancelled":
            self.model_mgmt_status.setText(f"⊘ {model_id}: cancelled")
            self.model_mgmt_status.setStyleSheet("color: #6c7086; font-size: 12px;")
    
    def _on_model_done(self, model_id, terminal_state, error, attempt):
        """Qt-safe done callback — queued to main thread."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        from model_download_task import SUCCEEDED, CANCELLED
        if terminal_state == SUCCEEDED:
            log.info(f"Model {model_id} downloaded")
            self.model_mgmt_status.setText(f"✅ {model_id} installed")
            self.model_mgmt_status.setStyleSheet("color: #a6e3a1; font-size: 12px;")
        elif terminal_state == CANCELLED:
            log.info(f"Model download cancelled: {model_id}")
            self.model_mgmt_status.setText(f"⊘ {model_id}: cancelled")
            self.model_mgmt_status.setStyleSheet("color: #6c7086; font-size: 12px;")
        else:
            log.error(f"Model {model_id} failed: {error}")
            self.model_mgmt_status.setText(f"❌ {model_id}: failed after {attempt} attempts — retry?")
            self.model_mgmt_status.setStyleSheet("color: #f38ba8; font-size: 12px;")
        if hasattr(self, '_active_downloads'):
            self._active_downloads.pop(model_id, None)
        self._refresh_model_list()
    
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
            self.model_mgmt_status.setText(f"⊘ {model_id}: cancelling...")
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
        """Subtitle style customization tab"""
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        content = QWidget()
        layout = QFormLayout()
        layout.setSpacing(10)
        content.setLayout(layout)
        
        header = QLabel("Subtitle Appearance")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #fab387;")
        layout.addRow(header)
        
        # Font size
        self.original_font_size = QSpinBox()
        self.original_font_size.setRange(8, 48)
        self.original_font_size.setValue(20)
        self.original_font_size.setSuffix(" px")
        layout.addRow("Original Font Size:", self.original_font_size)
        
        self.translation_font_size = QSpinBox()
        self.translation_font_size.setRange(8, 48)
        self.translation_font_size.setValue(17)
        self.translation_font_size.setSuffix(" px")
        layout.addRow("Translation Font Size:", self.translation_font_size)
        
        # Colors
        self.original_color = QComboBox()
        self.original_color.addItems(["#ffffff", "#cdd6f4", "#a6e3a1", "#fab387", "#f9e2af", "#89b4fa"])
        self.original_color.setCurrentText("#ffffff")
        layout.addRow("Original Text Color:", self.original_color)
        
        self.translation_color = QComboBox()
        self.translation_color.addItems(["#9db5ff", "#89b4fa", "#a6e3a1", "#fab387", "#f9e2af", "#ffffff", "#cdd6f4"])
        self.translation_color.setCurrentText("#9db5ff")
        layout.addRow("Translation Color:", self.translation_color)
        
        # Window opacity
        self.window_opacity = QDoubleSpinBox()
        self.window_opacity.setRange(0.3, 1.0)
        self.window_opacity.setSingleStep(0.05)
        self.window_opacity.setValue(0.94)
        layout.addRow("Window Opacity:", self.window_opacity)
        
        # Window width
        self.window_width = QSpinBox()
        self.window_width.setRange(200, 1200)
        self.window_width.setValue(620)
        self.window_width.setSuffix(" px")
        layout.addRow("Window Width:", self.window_width)
        
        # Display mode
        self.display_mode = QComboBox()
        self.display_mode.addItems(["bilingual", "original_only", "translation_only"])
        layout.addRow("Display Mode:", self.display_mode)
        
        # Apply button
        apply_btn = QPushButton("Apply Style")
        apply_btn.setStyleSheet(
            "QPushButton { background: #89b4fa; color: #1e1e2e; padding: 10px; "
            "border-radius: 6px; font-weight: bold; }"
        )
        apply_btn.clicked.connect(self._apply_style)
        layout.addRow(apply_btn)
        
        scroll.setWidget(content)
        
        tab_layout = QVBoxLayout()
        tab_layout.addWidget(scroll)
        tab.setLayout(tab_layout)
        
        self.tabs.addTab(tab, "🎨 Style")
    
    def _apply_style(self):
        """Apply subtitle style to overlay window"""
        if hasattr(self, 'overlay_window') and self.overlay_window:
            style = {
                "original_font_size": self.original_font_size.value(),
                "translation_font_size": self.translation_font_size.value(),
                "original_color": self.original_color.currentText(),
                "translation_color": self.translation_color.currentText(),
                "window_opacity": self.window_opacity.value(),
                "window_width": self.window_width.value(),
                "display_mode": self.display_mode.currentText(),
            }
            self.overlay_window.set_style(style)
            self.status_label.setText("✅ Style applied")
            self.status_label.setStyleSheet("font-size: 18px; color: #a6e3a1;")
    
    def init_diagnostics_tab(self):
        """System diagnostics tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        header = QLabel("System Diagnostics")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #fab387;")
        layout.addWidget(header)

        # Architecture status (v2.4)
        self._arch_status = QLabel("")
        self._arch_status.setWordWrap(True)
        self._arch_status.setStyleSheet(
            "color: #bac2de; background: #181825; border: 1px solid #313244; "
            "border-radius: 4px; padding: 8px; font-size: 11px;"
        )
        layout.addWidget(self._arch_status)
        self._refresh_arch_status()

        # Runtime decision (v2.4)
        self._runtime_decision_status = QLabel("")
        self._runtime_decision_status.setTextFormat(Qt.TextFormat.RichText)
        self._runtime_decision_status.setWordWrap(True)
        self._runtime_decision_status.setStyleSheet(
            "color: #bac2de; background: #181825; border: 1px solid #313244; "
            "border-radius: 4px; padding: 8px; font-size: 11px;"
        )
        layout.addWidget(self._runtime_decision_status)
        self._refresh_runtime_decision_status()

        # Transcript history (v2.4)
        self._history_status = QLabel("")
        self._history_status.setTextFormat(Qt.TextFormat.RichText)
        self._history_status.setWordWrap(True)
        self._history_status.setStyleSheet(
            "color: #bac2de; background: #181825; border: 1px solid #313244; "
            "border-radius: 4px; padding: 8px; font-size: 11px;"
        )
        layout.addWidget(self._history_status)
        self._refresh_history_status()

        # ─────────────────────────────────────────────────────
        
        # Run diagnostics button
        self.run_diag_btn = QPushButton("▶ Run Diagnostics")
        self.run_diag_btn.setStyleSheet(
            "QPushButton { background: #89b4fa; color: #1e1e2e; padding: 10px; "
            "border-radius: 6px; font-weight: bold; }"
        )
        self.run_diag_btn.clicked.connect(self._run_diagnostics)
        layout.addWidget(self.run_diag_btn)
        
        # Results area
        self.diag_results = QTextEdit()
        self.diag_results.setReadOnly(True)
        self.diag_results.setStyleSheet(
            "QTextEdit { background: #11111b; color: #cdd6f4; border: 1px solid #45475a; "
            "border-radius: 6px; padding: 10px; font-family: monospace; font-size: 12px; }"
        )
        layout.addWidget(self.diag_results)
        
        # Log viewer
        log_layout = QHBoxLayout()
        log_layout.addWidget(QLabel("Recent Logs:"))
        self.view_logs_btn = QPushButton("📄 View")
        self.view_logs_btn.clicked.connect(self._view_logs)
        log_layout.addWidget(self.view_logs_btn)
        log_layout.addStretch()
        layout.addLayout(log_layout)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "🔍 Diag")
        self.tabs.setTabToolTip(self.tabs.count() - 1, "Diagnostics — check system, view logs")
    
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
        self.run_diag_btn.setText("Running...")
        
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
        self.run_diag_btn.setText("▶ Run Diagnostics")
    
    def _view_logs(self):
        """View recent log entries"""
        from diagnostics import logger
        
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
        
        # Audio
        idx = self.device_combo.currentData()
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
        cp.set("transcription", "source_language", self.source_language.currentText())
        
        # Translation
        cp.set("api", "api_key", self.api_key.text())
        cp.set("api", "base_url", self.base_url.text())
        cp.set("translation", "model", self.model.currentText())
        cp.set("translation", "target_lang", self.target_lang.currentText())
        cp.set("translation", "mode", str(self.translation_mode.currentData() or "off"))
        
        write_config(cp, config_path)
        
        # Visual feedback
        original_text = self.save_btn.text()
        self.save_btn.setText("✓ Saved")
        self.status_label.setText("✅ Settings saved! Restart to apply.")
        self.status_label.setStyleSheet("font-size: 18px; color: #a6e3a1;")
        # Restore after 2s
        QTimer.singleShot(2000, lambda: self.save_btn.setText(original_text))

    def on_start(self):
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.info("Launch Translator clicked")
        
        # Update UI to Loading State
        self.status_label.setText("Initializing Pipeline... (This may take a moment)")
        self.status_label.setStyleSheet("font-size: 18px; color: #fab387;")
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Loading...")
        
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
            self.overlay_window = create_and_show_overlay(pipeline, signals, start_pipeline=False)
            log.info("Overlay shown")
            
            self.pipeline = pipeline
            
            # Connect overlay signals
            if hasattr(self.overlay_window, 'stop_requested'):
                self.overlay_window.stop_requested.connect(self.on_stop)
            if hasattr(self.overlay_window, 'style_changed'):
                self.overlay_window.style_changed.connect(self._on_style_changed)
            
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
            self.status_label.setText("Starting Pipeline...")
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
        
        self.status_label.setText("Initialization Failed")
        self.status_label.setStyleSheet("font-size: 18px; color: #f38ba8;")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Start Live Subtitles")
        
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Launch Failed",
                           f"Failed to launch translator:\n\n{str(error)[:500]}")
    
    def _on_pipeline_failed(self, error):
        """Pipeline thread crashed. Disable Launch until cleanup completes."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.error(f"Pipeline failed: {error}")
        self.last_pipeline_error = error
        self.status_label.setText("Pipeline Error — cleaning up...")
        self.status_label.setStyleSheet("font-size: 18px; color: #fab387;")
        self.stop_btn.hide()
        self.start_btn.show()
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Cleaning up...")
        self.showNormal()
    
    def _on_pipeline_cleanup_finished(self, success, message):
        """ASR worker and executors have shut down (or not). Safe to clean UI only if success."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.info(f"Pipeline cleanup finished: success={success} {message}")
        if not success:
            self.status_label.setText("Cleanup failed — retry or force quit")
            self.status_label.setStyleSheet("font-size: 18px; color: #f38ba8;")
            self.start_btn.setEnabled(False)
            self.start_btn.setText("Retry Stop")
            return
        if hasattr(self, 'overlay_window') and self.overlay_window:
            self.overlay_window.close()
            self.overlay_window = None
        self.pipeline = None
        self.status_label.setText("Pipeline Error — ready to retry")
        self.status_label.setStyleSheet("font-size: 18px; color: #f38ba8;")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Retry Start")
    
    def _on_pipeline_started(self):
        """Pipeline confirmed started — transition to Running."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.info("Pipeline started confirmed")
        if hasattr(self, '_startup_timeout'):
            self._startup_timeout.stop()
        self.start_btn.hide()
        self.status_label.setText("Running...")
        self.status_label.setStyleSheet("font-size: 18px; color: #a6e3a1;")
        self.stop_btn.show()
        self.stop_btn.setEnabled(True)
        self.showMinimized()
    
    def _on_audio_failed(self, message):
        """Audio device failure. Show error, disable Retry until cleanup."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.error(f"Audio device failed: {message}")
        self.status_label.setText("Audio Device Error")
        self.status_label.setStyleSheet("font-size: 18px; color: #f38ba8;")
        self.last_pipeline_error = f"Audio: {message[:200]}"
        self.stop_btn.hide()
        self.start_btn.show()
        self.start_btn.setEnabled(False)  # disabled until cleanup_finished
        self.start_btn.setText("Wait...")
        self.showNormal()
    
    def _on_startup_timeout(self):
        """Pipeline never confirmed start."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.error("Pipeline start timeout")
        if hasattr(self, 'pipeline') and self.pipeline:
            self.pipeline.stop()
        self.status_label.setText("Start failed — timeout")
        self.status_label.setStyleSheet("font-size: 18px; color: #f38ba8;")
        self.start_btn.show()
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Retry Start")
    
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
            self.window_opacity.setValue(style.get('window_opacity', 0.85))
            self.window_opacity.blockSignals(False)
        if hasattr(self, 'display_mode'):
            self.display_mode.blockSignals(True)
            idx = self.display_mode.findText(style.get('display_mode', 'bilingual'))
            if idx >= 0:
                self.display_mode.setCurrentIndex(idx)
            self.display_mode.blockSignals(False)

    def on_stop(self):
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText("Stopping...")
        
        if hasattr(self, 'pipeline') and self.pipeline:
            try:
                ok = self.pipeline.stop()
            except Exception:
                log.exception("Pipeline stop failed — forcing cleanup")
                ok = False
            if not ok:
                log.error("Pipeline stop timed out")
                self.status_label.setText("Stop timed out — Retry or Force Quit")
                self.status_label.setStyleSheet("font-size: 18px; color: #f38ba8;")
                self.stop_btn.setEnabled(True)
                self.stop_btn.setText("Retry Stop")
                return False
            self.pipeline = None
            
        if hasattr(self, 'overlay_window') and self.overlay_window:
            self.overlay_window.close()
            self.overlay_window = None
        
        log.info("Translator stopped")
        
        self.status_label.setText("Stopped")
        self.status_label.setStyleSheet("font-size: 18px; color: #6c7086;")
        self.stop_btn.hide()
        self.start_btn.show()
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Start Live Subtitles")
        self.showNormal()
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
