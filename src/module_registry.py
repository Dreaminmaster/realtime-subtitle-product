"""Module status registry for v2.4.0 architecture.

Each subsystem (audio, asr, translation, overlay, storage) reports
its status independently.  A DEGRADED or ERROR module does NOT
automatically change the session state — that decision belongs to
the session controller.
"""

from __future__ import annotations
from enum import Enum, auto
from dataclasses import dataclass, field
import threading
import time


class ModuleStatus(Enum):
    UNINITIALIZED = auto()
    STARTING = auto()
    RUNNING = auto()
    DEGRADED = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()

    @property
    def is_ok(self) -> bool:
        return self in (ModuleStatus.RUNNING, ModuleStatus.DEGRADED)

    @property
    def is_error(self) -> bool:
        return self == ModuleStatus.ERROR

    @property
    def is_terminal(self) -> bool:
        return self in (ModuleStatus.STOPPED, ModuleStatus.ERROR)


DEFAULT_MODULES = ("audio", "asr", "translation", "overlay", "storage")


@dataclass
class ModuleInfo:
    status: ModuleStatus = ModuleStatus.UNINITIALIZED
    message: str | None = None
    updated_at: float = field(default_factory=time.time)


class ModuleStatusRegistry:
    """Thread-safe registry for module statuses."""

    def __init__(self, modules: list[str] | None = None):
        self._lock = threading.Lock()
        self._modules: dict[str, ModuleInfo] = {}
        for name in (modules or list(DEFAULT_MODULES)):
            self._modules[name] = ModuleInfo()

    # ── basic ops ──────────────────────────────────────────────────
    def register(self, name: str) -> None:
        with self._lock:
            if name not in self._modules:
                self._modules[name] = ModuleInfo()

    def set_status(self, name: str, status: ModuleStatus, message: str | None = None) -> None:
        with self._lock:
            if name not in self._modules:
                self._modules[name] = ModuleInfo()
            self._modules[name] = ModuleInfo(status=status, message=message, updated_at=time.time())

    def get_status(self, name: str) -> ModuleStatus:
        with self._lock:
            info = self._modules.get(name)
            return info.status if info else ModuleStatus.UNINITIALIZED

    def get_info(self, name: str) -> ModuleInfo | None:
        with self._lock:
            return self._modules.get(name)

    # ── queries ────────────────────────────────────────────────────
    def is_ready(self, name: str) -> bool:
        """A module is ready when it is RUNNING or DEGRADED."""
        return self.get_status(name).is_ok

    def health_check(self) -> dict[str, ModuleStatus]:
        """Return a snapshot of every known module's status."""
        with self._lock:
            return {name: info.status for name, info in self._modules.items()}

    def has_errors(self) -> bool:
        """True if any module is in ERROR state."""
        with self._lock:
            return any(info.status.is_error for info in self._modules.values())

    def all_ready(self) -> bool:
        """True when every registered module is RUNNING or DEGRADED.

        UNINITIALIZED / STARTING / STOPPING / STOPPED / ERROR all
        count as NOT ready.  DEGRADED counts as ready (translation off
        should not block the session).
        """
        with self._lock:
            if not self._modules:
                return False
            return all(info.status.is_ok for info in self._modules.values())

    def wait_for_ready(self, names: list[str], timeout: float = 10.0) -> bool:
        """Block until every named module is ready or timeout expires."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                ok = all(
                    self._modules.get(n, ModuleInfo()).status.is_ok
                    for n in names
                )
            if ok:
                return True
            time.sleep(0.1)
        return False

    # ── convenience ────────────────────────────────────────────────
    def mark_running(self, name: str) -> None:
        self.set_status(name, ModuleStatus.RUNNING)

    def mark_error(self, name: str, message: str | None = None) -> None:
        self.set_status(name, ModuleStatus.ERROR, message=message)

    def mark_degraded(self, name: str, message: str | None = None) -> None:
        self.set_status(name, ModuleStatus.DEGRADED, message=message)
