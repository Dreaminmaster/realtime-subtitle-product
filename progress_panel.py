#!/usr/bin/env python3
"""Reusable progress panel — model download + first-launch setup."""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
)
from PyQt6.QtCore import pyqtSignal


class ProgressPanel(QFrame):
    retry_clicked = pyqtSignal()
    cancel_clicked = pyqtSignal()
    dismiss_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DownloadProgress")
        self.setStyleSheet("""
            QFrame#DownloadProgress {
                background: #22211f; border-radius: 12px;
                border: 1px solid #45413a;
            }
            QLabel#ProgressTitle { color: #f2eee6; font-size: 14px; font-weight: 700; }
            QLabel#ProgressStatus { color: #b6b0a6; font-size: 12px; }
            QProgressBar#DownloadBar {
                border: none; border-radius: 4px; height: 8px;
                text-align: center; background: #34312d; color: transparent;
            }
            QProgressBar#DownloadBar::chunk { background: #d98246; border-radius: 4px; }
            QPushButton { padding: 7px 14px; border-radius: 7px; font-weight: 650; }
            QPushButton#ProgressPrimary { background: #d98246; color: #1d1712; }
            QPushButton#ProgressSecondary { background: #2d2b27; color: #ddd8ce; border: 1px solid #48443d; }
            QPushButton#ProgressDanger { background: #4b2c29; color: #f1b7aa; border: 1px solid #6c3e37; }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(8)
        self.title = QLabel("Download Progress")
        self.title.setObjectName("ProgressTitle")
        layout.addWidget(self.title)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setObjectName("ProgressStatus")
        layout.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setObjectName("DownloadBar")
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setObjectName("ProgressPrimary")
        self.retry_btn.clicked.connect(self.retry_clicked.emit)
        self.retry_btn.hide()
        btn_layout.addWidget(self.retry_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("ProgressDanger")
        self.cancel_btn.clicked.connect(self.cancel_clicked.emit)
        btn_layout.addWidget(self.cancel_btn)
        self.dismiss_btn = QPushButton("Close")
        self.dismiss_btn.setObjectName("ProgressSecondary")
        self.dismiss_btn.clicked.connect(self.dismiss_clicked.emit)
        self.dismiss_btn.hide()
        btn_layout.addWidget(self.dismiss_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def set_progress(self, event):
        self.status.setText(event.message)
        if event.percent is not None:
            self.bar.setRange(0, 100)
            self.bar.setValue(int(event.percent))
        else:
            self.bar.setRange(0, 0)
        if event.can_retry:
            self.retry_btn.show()
            self.cancel_btn.hide()
            self.dismiss_btn.show()
        elif event.can_cancel:
            self.cancel_btn.show()
            self.retry_btn.hide()
            self.dismiss_btn.hide()
        else:
            self.cancel_btn.hide()
            self.retry_btn.hide()
            self.dismiss_btn.setVisible(event.stage in {"cancelled", "succeeded"})
