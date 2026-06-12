#!/usr/bin/env python3
"""
Permission Guide - First-launch permission setup wizard.

Guides users through granting necessary macOS permissions:
  - Microphone access
  - Accessibility (for global keyboard shortcuts)
  - Screen Recording (for system audio capture, future)

This module can be imported without PyQt6 installed (diagnostics mode).
The GUI class is only available when PyQt6 is present.
"""

import subprocess
import platform
import os


# ---- Module-level functions (no PyQt6 needed) ----

def _check_microphone_raw():
    """Check microphone permission status — no GUI needed"""
    if platform.system() != "Darwin":
        return None
    
    try:
        import objc
        from AVFoundation import AVCaptureDevice
        status = AVCaptureDevice.authorizationStatusForMediaType_("soun")
        return status == 3  # AVAuthorizationStatusAuthorized
    except Exception:
        pass
    
    try:
        result = subprocess.run(
            ["tccutil", "status", "kTCCServiceMicrophone"],
            capture_output=True, text=True, timeout=3
        )
        return "allowed" in result.stdout.lower()
    except Exception:
        return None


def should_show_permission_guide() -> bool:
    """Check if first-launch permission guide should be shown"""
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "config.ini"
    )
    if not os.path.exists(config_path):
        return True
    
    mic_ok = _check_microphone_raw()
    if mic_ok is False:
        return True
    
    return False


# ---- GUI class (requires PyQt6) ----

def create_permission_guide(parent=None):
    """Factory: create and return a PermissionGuide dialog.
    Returns None if PyQt6 is not available."""
    try:
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
            QFrame, QSizePolicy
        )
        from PyQt6.QtCore import Qt
    except ImportError:
        return None
    
    class _PermissionGuide(QDialog):
        """First-launch permission setup wizard"""
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Permission Setup - Realtime Subtitle")
            self.setMinimumSize(550, 500)
            self.setModal(True)
            # Force dark background — works in both light and dark macOS appearance
            self.setStyleSheet("QDialog { background-color: #1e1e2e; } "
                             "QLabel { color: #cdd6f4; }")
            self.setAutoFillBackground(True)
            self.init_ui()
        
        def init_ui(self):
            layout = QVBoxLayout()
            layout.setSpacing(15)
            layout.setContentsMargins(25, 25, 25, 25)
            self.setLayout(layout)
            
            title = QLabel("🔐 Permission Setup")
            title.setStyleSheet("font-size: 22px; font-weight: bold; color: #89b4fa;")
            layout.addWidget(title)
            
            subtitle = QLabel(
                "Realtime Subtitle needs the following permissions to work properly.\n"
                "You can change these later in System Settings."
            )
            subtitle.setWordWrap(True)
            subtitle.setStyleSheet("color: #cdd6f4; font-size: 13px; margin-bottom: 10px;")
            layout.addWidget(subtitle)
            
            # Microphone card
            mic_card = self._create_card(
                "🎤 Microphone Access",
                "Required for real-time speech recognition.",
                "Used to capture audio from your microphone.",
                "System Settings → Privacy & Security → Microphone",
                critical=True
            )
            layout.addWidget(mic_card)
            
            # Accessibility card
            acc_card = self._create_card(
                "⌨️ Accessibility Access",
                "Optional - needed for global keyboard shortcuts.",
                "Allows the app to use global hotkeys.",
                "System Settings → Privacy & Security → Accessibility",
                critical=False
            )
            layout.addWidget(acc_card)
            
            # Screen Recording card
            screen_card = self._create_card(
                "🖥 Screen Recording",
                "Optional - needed for system audio capture (future).",
                "Capture audio from other apps or the system.",
                "System Settings → Privacy & Security → Screen Recording",
                critical=False
            )
            layout.addWidget(screen_card)
            
            layout.addStretch()
            
            btn_layout = QHBoxLayout()
            
            self.skip_btn = QPushButton("Skip for now")
            self.skip_btn.setStyleSheet(
                "QPushButton { background: #45475a; color: #cdd6f4; padding: 10px 20px; "
                "border-radius: 6px; border: none; }"
            )
            self.skip_btn.clicked.connect(self.accept)
            btn_layout.addWidget(self.skip_btn)
            btn_layout.addStretch()
            
            self.continue_btn = QPushButton("Continue →")
            self.continue_btn.setStyleSheet(
                "QPushButton { background: #a6e3a1; color: #1e1e2e; padding: 10px 20px; "
                "border-radius: 6px; border: none; font-weight: bold; }"
            )
            self.continue_btn.clicked.connect(self.accept)
            btn_layout.addWidget(self.continue_btn)
            
            layout.addLayout(btn_layout)
            
            self.status_label = QLabel("")
            self.status_label.setWordWrap(True)
            self.status_label.setStyleSheet("font-size: 12px; color: #a6adc8;")
            layout.addWidget(self.status_label)
        
        def _create_card(self, title, reason, description, setting_path, critical=False):
            card = QFrame()
            border_color = "#f38ba8" if critical else "#45475a"
            card.setStyleSheet(
                f"QFrame {{ background: #45475a; border: 1px solid {border_color}; "
                f"border-radius: 8px; padding: 15px; }} "
                f"QLabel {{ color: #cdd6f4; }}"
            )
            card_layout = QVBoxLayout()
            card_layout.setSpacing(5)
            card.setLayout(card_layout)
            
            title_label = QLabel(title)
            title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #cdd6f4;")
            card_layout.addWidget(title_label)
            
            reason_label = QLabel(reason)
            reason_label.setStyleSheet("color: #f9e2af; font-size: 12px;")
            reason_label.setWordWrap(True)
            card_layout.addWidget(reason_label)
            
            desc_label = QLabel(description)
            desc_label.setStyleSheet("color: #bac2de; font-size: 12px;")
            desc_label.setWordWrap(True)
            card_layout.addWidget(desc_label)
            
            section_name = setting_path.split("→")[-1].strip()
            open_btn = QPushButton(f"📂 Open {section_name}")
            open_btn.setStyleSheet(
                "QPushButton { background: #45475a; color: #cdd6f4; padding: 6px 12px; "
                "border-radius: 4px; border: none; font-size: 12px; }"
            )
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.clicked.connect(lambda: self._open_settings_url(title))
            card_layout.addWidget(open_btn)
            
            return card
        
        def _open_settings_url(self, title):
            urls = {
                "Microphone": "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
                "Accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
                "Screen": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
            }
            for key, url in urls.items():
                if key in title:
                    subprocess.run(["open", url], timeout=3)
                    self.status_label.setText("✅ System Settings opened. Grant permission, then click Continue →")
                    self.status_label.setStyleSheet("color: #a6e3a1; font-size: 12px;")
                    return
            self.status_label.setText("⚠️ Please open System Settings manually.")
    
    return _PermissionGuide(parent)


# Keep backward compatibility with old API
class PermissionGuide:
    """Thin wrapper for backward compatibility"""
    @staticmethod
    def should_show():
        return should_show_permission_guide()
    
    def __new__(cls, parent=None):
        return create_permission_guide(parent)
