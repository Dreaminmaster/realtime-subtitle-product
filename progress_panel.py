#!/usr/bin/env python3
"""Reusable progress panel — model download + first-launch setup."""
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel,
                              QProgressBar, QPushButton, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal


class ProgressPanel(QFrame):
    retry_clicked = pyqtSignal()
    cancel_clicked = pyqtSignal()
    dismiss_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("progressPanel")
        self.setStyleSheet("""
            QFrame#progressPanel {
                background: #313244; border-radius: 10px; padding: 12px;
                border: 1px solid #45475a;
            }
            QProgressBar {
                border: 1px solid #585b70; border-radius: 3px; height: 12px;
                text-align: center; background: #1e1e2e;
            }
            QProgressBar::chunk { background: #89b4fa; border-radius: 2px; }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.title = QLabel("Progress")
        self.title.setStyleSheet("font-weight: bold; color: #cdd6f4;")
        layout.addWidget(self.title)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #a6adc8; font-size: 12px;")
        layout.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setStyleSheet(self._btn("#a6e3a1"))
        self.retry_btn.clicked.connect(self.retry_clicked.emit)
        self.retry_btn.hide()
        btn_layout.addWidget(self.retry_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(self._btn("#f38ba8"))
        self.cancel_btn.clicked.connect(self.cancel_clicked.emit)
        btn_layout.addWidget(self.cancel_btn)
        self.dismiss_btn = QPushButton("Close")
        self.dismiss_btn.setStyleSheet(self._btn("#6c7086"))
        self.dismiss_btn.clicked.connect(self.dismiss_clicked.emit)
        self.dismiss_btn.hide()
        btn_layout.addWidget(self.dismiss_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    @staticmethod
    def _btn(color):
        return (f"QPushButton {{ background: {color}; color: #1e1e2e; "
                f"padding: 6px 14px; border-radius: 4px; font-weight: bold; }}"
                f"QPushButton:hover {{ opacity: 0.8; }}")

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
            self.dismiss_btn.hide()
