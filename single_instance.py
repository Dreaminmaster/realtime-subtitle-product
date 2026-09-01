"""Cross-platform single-instance coordination for the desktop application."""

from __future__ import annotations

import os
from pathlib import Path
import weakref

from PyQt6.QtCore import QObject, QLockFile, QStandardPaths, QTimer, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


_IN_PROCESS_PRIMARIES: dict[str, weakref.ReferenceType] = {}


class SingleInstance(QObject):
    """Keep one caption process and route repeat launches to its controls.

    A local Qt socket works on Windows and macOS and avoids platform signals.
    QLockFile remains the ownership authority so a crashed process can be
    recovered without leaving the product permanently unlaunchable.
    """

    message_received = pyqtSignal(str)

    def __init__(self, name: str = "com.realtimesubtitle.app", parent=None):
        super().__init__(parent)
        safe_name = "".join(ch if ch.isalnum() or ch in ".-_" else "-" for ch in name)
        temp_root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation))
        user_suffix = os.getenv("USERNAME") or os.getenv("USER") or "user"
        self.server_name = f"{safe_name}-{user_suffix}"
        self.name = os.fspath(temp_root / f"{self.server_name}.lock")
        self.lock = QLockFile(self.name)
        self.lock.setStaleLockTime(0)
        self.server: QLocalServer | None = None
        self.is_primary = self.lock.tryLock(150)

        if self.is_primary:
            _IN_PROCESS_PRIMARIES[self.server_name] = weakref.ref(self)
            self._start_server()
        else:
            self._notify_primary()

    def _start_server(self):
        QLocalServer.removeServer(self.server_name)
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._read_pending_connections)
        if not self.server.listen(self.server_name):
            # The lock still prevents duplicate caption pipelines. A missing
            # notification channel is recoverable on the next launch.
            self.server = None

    def _notify_primary(self):
        local_primary = _IN_PROCESS_PRIMARIES.get(self.server_name)
        target = local_primary() if local_primary is not None else None
        if target is not None:
            QTimer.singleShot(0, lambda: target.message_received.emit("show-controls"))
            return
        socket = QLocalSocket(self)
        socket.connectToServer(self.server_name)
        if socket.waitForConnected(350):
            socket.write(b"show-controls\n")
            socket.flush()
            socket.waitForBytesWritten(350)
            socket.disconnectFromServer()

    def _read_pending_connections(self):
        server = self.server
        if server is None:
            return
        while server.hasPendingConnections():
            socket = server.nextPendingConnection()
            if socket is None:
                continue
            socket.setParent(self)

            def consume(sock=socket):
                message = bytes(sock.readAll()).decode("utf-8", errors="replace").strip()
                if message:
                    self.message_received.emit(message)

            socket.readyRead.connect(consume)
            socket.disconnected.connect(consume)
            socket.disconnected.connect(socket.deleteLater)
            # The client can write and disconnect before newConnection is
            # delivered. Process any bytes already queued on the local socket.
            QTimer.singleShot(0, consume)

    def release(self):
        if self.server is not None:
            self.server.close()
            QLocalServer.removeServer(self.server_name)
            self.server = None
        if self.is_primary:
            self.lock.unlock()
            self.is_primary = False
        current = _IN_PROCESS_PRIMARIES.get(self.server_name)
        if current is not None and current() is self:
            _IN_PROCESS_PRIMARIES.pop(self.server_name, None)
