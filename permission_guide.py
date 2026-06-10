#!/usr/bin/env python3
"""
Permission Guide - First-launch permission setup wizard.

Guides users through granting necessary macOS permissions:
  - Microphone access
  - Accessibility (for global keyboard shortcuts)
  - Screen Recording (for system audio capture, future)
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QFrame, QScrollArea, QWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
import subprocess
import platform


class PermissionGuide(QDialog):
    """First-launch permission setup wizard"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Permission Setup - Realtime Subtitle")
        self.setMinimumSize(550, 500)
        self.setModal(True)
        
        self.permissions_granted = {
            "microphone": False,
            "accessibility": False,
            "screen_recording": False
        }
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        self.setLayout(layout)
        
        # Header
        title = QLabel("🔐 Permission Setup")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(title)
        
        subtitle = QLabel(
            "Realtime Subtitle needs the following permissions to work properly. "
            "You can change these later in System Settings."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #6c7086; font-size: 13px; margin-bottom: 10px;")
        layout.addWidget(subtitle)
        
        # Permission cards
        # 1. Microphone
        mic_card = self._create_permission_card(
            "🎤 Microphone Access",
            "Required for real-time speech recognition.",
            "Used to capture audio from your microphone for transcription.",
            "System Settings → Privacy & Security → Microphone",
            "permission_microphone",
            critical=True
        )
        layout.addWidget(mic_card)
        
        # 2. Accessibility
        acc_card = self._create_permission_card(
            "⌨️ Accessibility Access",
            "Optional - needed for global keyboard shortcuts.",
            "Allows the app to show/hide the subtitle window via hotkeys.",
            "System Settings → Privacy & Security → Accessibility",
            "permission_accessibility",
            critical=False
        )
        layout.addWidget(acc_card)
        
        # 3. Screen Recording
        screen_card = self._create_permission_card(
            "🖥 Screen Recording",
            "Optional - needed for system audio capture (future).",
            "If you want to capture audio from other apps or the system.",
            "System Settings → Privacy & Security → Screen Recording",
            "permission_screen_recording",
            critical=False
        )
        layout.addWidget(screen_card)
        
        # Bottom buttons
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        
        self.skip_btn = QPushButton("Skip for now")
        self.skip_btn.setStyleSheet(
            "QPushButton { background: #45475a; color: #cdd6f4; padding: 10px 20px; "
            "border-radius: 6px; border: none; } "
            "QPushButton:hover { background: #585b70; }"
        )
        self.skip_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.skip_btn)
        
        btn_layout.addStretch()
        
        self.check_btn = QPushButton("Check Permissions")
        self.check_btn.setStyleSheet(
            "QPushButton { background: #89b4fa; color: #1e1e2e; padding: 10px 20px; "
            "border-radius: 6px; border: none; font-weight: bold; } "
            "QPushButton:hover { background: #b4befe; }"
        )
        self.check_btn.clicked.connect(self._check_permissions)
        btn_layout.addWidget(self.check_btn)
        
        self.continue_btn = QPushButton("Continue →")
        self.continue_btn.setStyleSheet(
            "QPushButton { background: #a6e3a1; color: #1e1e2e; padding: 10px 20px; "
            "border-radius: 6px; border: none; font-weight: bold; } "
            "QPushButton:hover { background: #94e2d5; }"
        )
        self.continue_btn.clicked.connect(self.accept)
        self.continue_btn.hide()
        btn_layout.addWidget(self.continue_btn)
        
        layout.addLayout(btn_layout)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 12px; color: #a6adc8; margin-top: 10px;")
        layout.addWidget(self.status_label)
    
    def _create_permission_card(self, title, reason, description, setting_path, 
                                 perm_key, critical=False):
        card = QFrame()
        border_color = "#f38ba8" if critical else "#45475a"
        card.setStyleSheet(
            f"QFrame {{ background: #313244; border: 1px solid {border_color}; "
            f"border-radius: 8px; padding: 15px; }}"
        )
        
        layout = QVBoxLayout()
        layout.setSpacing(5)
        card.setLayout(layout)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(title_label)
        
        reason_label = QLabel(reason)
        reason_label.setStyleSheet("color: #fab387; font-size: 12px;")
        reason_label.setWordWrap(True)
        layout.addWidget(reason_label)
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Open settings button
        open_btn = QPushButton(f"📂 Open {setting_path.split('→')[-1].strip()}")
        open_btn.setStyleSheet(
            "QPushButton { background: #45475a; color: #cdd6f4; padding: 6px 12px; "
            "border-radius: 4px; border: none; font-size: 12px; } "
            "QPushButton:hover { background: #585b70; }"
        )
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda checked, p=perm_key: self._open_settings(p))
        layout.addWidget(open_btn)
        
        return card
    
    def _open_settings(self, perm_key):
        """Open System Settings for the given permission"""
        if platform.system() != "Darwin":
            self.status_label.setText("⚠️ This guide is for macOS only.")
            return
        
        urls = {
            "permission_microphone": "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
            "permission_accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            "permission_screen_recording": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
        }
        
        url = urls.get(perm_key, "")
        if url:
            try:
                subprocess.run(["open", url], timeout=3)
                self.status_label.setText(f"✅ System Settings opened. Grant permission, then click 'Check Permissions'.")
                self.status_label.setStyleSheet("color: #a6e3a1; font-size: 12px; margin-top: 10px;")
            except Exception as e:
                self.status_label.setText(f"❌ Could not open settings: {e}")
                self.status_label.setStyleSheet("color: #f38ba8; font-size: 12px;")
    
    def _check_permissions(self):
        """Check which permissions are granted"""
        if platform.system() != "Darwin":
            self.status_label.setText("⚠️ Permission check is for macOS only. Continue anyway.")
            self.status_label.setStyleSheet("color: #fab387; font-size: 12px;")
            self.continue_btn.show()
            self.check_btn.hide()
            return
        
        # Check microphone via tccutil or direct check
        # For now, we'll guide the user - real checking requires native code
        mic_ok = self._check_microphone()
        acc_ok = self._check_accessibility()
        
        msg = "Permission Status:\n"
        msg += f"  Microphone: {'✅ Granted' if mic_ok else '❌ Not granted'}\n"
        msg += f"  Accessibility: {'✅ Granted' if acc_ok else '❌ Not granted (optional)'}\n"
        
        self.status_label.setText(msg)
        
        if mic_ok:
            self.status_label.setStyleSheet("color: #a6e3a1; font-size: 12px; margin-top: 10px;")
            self.continue_btn.show()
            self.check_btn.hide()
        else:
            self.status_label.setStyleSheet("color: #fab387; font-size: 12px; margin-top: 10px;")
            self.continue_btn.show()  # Still allow continue
    
    def _check_microphone(self):
        """Check microphone permission status"""
        try:
            import objc
            from AVFoundation import AVCaptureDevice
            status = AVCaptureDevice.authorizationStatusForMediaType_("soun")
            # 3 = AVAuthorizationStatusAuthorized
            return status == 3
        except Exception:
            pass
        
        # Fallback: try to query with tccutil
        try:
            result = subprocess.run(
                ["tccutil", "status", "kTCCServiceMicrophone"],
                capture_output=True, text=True, timeout=3
            )
            return "allowed" in result.stdout.lower()
        except Exception:
            pass
        
        return None  # Unknown
    
    def _check_accessibility(self):
        """Check accessibility permission status"""
        try:
            result = subprocess.run(
                ["tccutil", "status", "kTCCServiceAccessibility"],
                capture_output=True, text=True, timeout=3
            )
            return "allowed" in result.stdout.lower()
        except Exception:
            pass
        return None
    
    @staticmethod
    def should_show() -> bool:
        """Check if this is the first launch (no config exists)"""
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "config.ini"
        )
        # Show if no config exists (first launch)
        if not os.path.exists(config_path):
            return True
        
        # Also check if permissions are missing
        try:
            guide = PermissionGuide.__new__(PermissionGuide)
            mic_ok = guide._check_microphone()
            if mic_ok is False:
                return True
        except Exception:
            pass
        
        return False
