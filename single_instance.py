"""Single-instance coordination for the macOS desktop application."""

from __future__ import annotations

import os
import signal

from PyQt6.QtCore import QObject, QLockFile, QTimer, pyqtSignal


class SingleInstance(QObject):
    """Keep one caption process and route repeat launches to its controls."""

    message_received = pyqtSignal(str)

    def __init__(self, name: str = "com.realtimesubtitle.app", parent=None):
        super().__init__(parent)
        safe_name = name.replace("/", "-")
        self.name = f"/tmp/{safe_name}.{os.getuid()}.lock"
        self.lock = QLockFile(self.name)
        self.lock.setStaleLockTime(0)
        self._pending_show = False
        self._poll_timer = None
        self.is_primary = self.lock.tryLock(100)

        if self.is_primary:
            self._install_signal_handler()
        else:
            self._notify_primary()

    def _install_signal_handler(self):
        if not hasattr(signal, "SIGUSR1"):
            return

        def request_show(_signum, _frame):
            self._pending_show = True

        signal.signal(signal.SIGUSR1, request_show)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(80)
        self._poll_timer.timeout.connect(self._deliver_pending_message)
        self._poll_timer.start()

    def _notify_primary(self):
        ok, pid, _host, _application = self.lock.getLockInfo()
        if not ok or not pid or not hasattr(signal, "SIGUSR1"):
            return
        try:
            os.kill(int(pid), signal.SIGUSR1)
        except (OSError, ValueError):
            pass

    def _deliver_pending_message(self):
        if self._pending_show:
            self._pending_show = False
            self.message_received.emit("show-controls")

    def release(self):
        if self.is_primary:
            self.lock.unlock()
            self.is_primary = False

