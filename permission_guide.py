#!/usr/bin/env python3
"""
Permission Guide - First-launch permission setup wizard.

This module can be imported without PyQt6 installed.
"""

import subprocess
import platform
import os


def _check_microphone_raw():
    if platform.system() != "Darwin":
        return None
    try:
        import objc
        from AVFoundation import AVCaptureDevice
        status = AVCaptureDevice.authorizationStatusForMediaType_("soun")
        return status == 3
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
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")
    if not os.path.exists(config_path):
        return True
    mic_ok = _check_microphone_raw()
    if mic_ok is False:
        return True
    return False


def create_permission_guide(parent=None):
    try:
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
            QFrame, QSizePolicy
        )
        from PyQt6.QtCore import Qt
    except ImportError:
        return None
    
    class _PermissionGuide(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Permission Setup - Realtime Subtitle")
            self.setMinimumSize(550, 520)
            self.setModal(True)
            # Force opaque dark background independent of system palette
            self.setStyleSheet("""
                _PermissionGuide, QDialog {
                    background-color: #1e1e2e;
                    color: #cdd6f4;
                }
                _PermissionGuide QLabel {
                    color: #cdd6f4;
                    background: transparent;
                }
                _PermissionGuide QPushButton {
                    background-color: #89b4fa;
                    color: #1e1e2e;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
            """)
            self.setAutoFillBackground(True)
            self.init_ui()
        
        def init_ui(self):
            layout = QVBoxLayout()
            layout.setSpacing(12)
            layout.setContentsMargins(25, 25, 25, 25)
            self.setLayout(layout)
            
            title = QLabel("Permission Setup")
            title.setStyleSheet("font-size: 22px; font-weight: bold; color: #89b4fa; padding: 0; margin: 0;")
            title.setFixedHeight(32)
            layout.addWidget(title)
            
            subtitle = QLabel(
                "Realtime Subtitle needs these permissions to work."
            )
            subtitle.setWordWrap(True)
            subtitle.setStyleSheet("color: #cdd6f4; font-size: 13px; padding: 0; margin: 0;")
            subtitle.setFixedHeight(20)
            layout.addWidget(subtitle)
            
            mic_card = self._create_card(
                "Microphone Access",
                "Required",
                "Grabs audio from the selected input device for speech recognition.",
                "Microphone",
            )
            layout.addWidget(mic_card)
            
            acc_card = self._create_card(
                "Accessibility Access",
                "Optional",
                "Allows global keyboard shortcuts for controlling the app.",
                "Accessibility",
            )
            layout.addWidget(acc_card)
            
            screen_card = self._create_card(
                "Screen Recording",
                "Optional (future)",
                "Would enable system audio capture for translating other apps.",
                "ScreenCapture",
            )
            layout.addWidget(screen_card)
            
            layout.addStretch()
            
            btn_layout = QHBoxLayout()
            self.skip_btn = QPushButton("Skip for now")
            self.skip_btn.setFixedHeight(36)
            self.skip_btn.setStyleSheet(
                "QPushButton { background: #45475a; color: #cdd6f4; "
                "border-radius: 6px; border: none; font-size: 13px; font-weight: normal; }"
                "QPushButton:hover { background: #585b70; }"
            )
            self.skip_btn.clicked.connect(self.accept)
            btn_layout.addWidget(self.skip_btn)
            btn_layout.addStretch()
            
            self.continue_btn = QPushButton("Continue")
            self.continue_btn.setFixedHeight(36)
            self.continue_btn.setStyleSheet(
                "QPushButton { background: #a6e3a1; color: #1e1e2e; "
                "border-radius: 6px; border: none; font-size: 13px; font-weight: bold; }"
                "QPushButton:hover { background: #94e2d5; }"
            )
            self.continue_btn.clicked.connect(self.accept)
            btn_layout.addWidget(self.continue_btn)
            
            layout.addLayout(btn_layout)
            
            self.status_label = QLabel("")
            self.status_label.setWordWrap(True)
            self.status_label.setStyleSheet("font-size: 12px; color: #a6adc8; padding: 0; margin: 0;")
            layout.addWidget(self.status_label)
        
        def _create_card(self, title, subtitle, description, section_name):
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background: #313244; border: 1px solid #45475a; border-radius: 8px; }}"
            )
            card.setFixedHeight(96)
            card_layout = QHBoxLayout()
            card_layout.setContentsMargins(15, 12, 15, 12)
            card_layout.setSpacing(12)
            card.setLayout(card_layout)
            
            # Left: text block
            text_block = QVBoxLayout()
            text_block.setSpacing(2)
            
            title_label = QLabel(title)
            title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #cdd6f4; padding: 0; margin: 0; background: transparent;")
            title_label.setFixedHeight(20)
            text_block.addWidget(title_label)
            
            subtitle_label = QLabel(subtitle)
            subtitle_label.setStyleSheet("font-size: 11px; color: #f9e2af; padding: 0; margin: 0; background: transparent;")
            subtitle_label.setFixedHeight(16)
            text_block.addWidget(subtitle_label)
            
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("font-size: 11px; color: #bac2de; padding: 0; margin: 0; background: transparent;")
            desc_label.setFixedHeight(36)
            text_block.addWidget(desc_label)
            
            card_layout.addLayout(text_block, 1)
            
            # Right: button
            open_btn = QPushButton("Open")
            open_btn.setFixedSize(70, 28)
            open_btn.setStyleSheet(
                "QPushButton { background: #45475a; color: #cdd6f4; "
                "border-radius: 4px; border: none; font-size: 11px; font-weight: normal; }"
                "QPushButton:hover { background: #585b70; }"
            )
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.clicked.connect(lambda checked, t=title: self._open_settings(t))
            card_layout.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignVCenter)
            
            return card
        
        def _open_settings(self, title):
            url_map = {
                "Microphone": "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
                "Accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
                "Screen": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
            }
            for key, url in url_map.items():
                if key in title:
                    subprocess.run(["open", url], timeout=3)
                    self.status_label.setText("System Settings opened. Grant permission, then click Continue.")
                    self.status_label.setStyleSheet("font-size: 12px; color: #a6e3a1;")
                    return
            self.status_label.setText("Please open System Settings manually.")
    
    return _PermissionGuide(parent)


class PermissionGuide:
    @staticmethod
    def should_show():
        return should_show_permission_guide()
    
    def __new__(cls, parent=None):
        return create_permission_guide(parent)
