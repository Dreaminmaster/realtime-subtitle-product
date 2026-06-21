"""Session state machine for v2.4.0 architecture.

Session-level states:
    IDLE       → initial state, no session active
    STARTING   → setup in progress (venv, model warmup)
    RUNNING    → audio capture + ASR + overlay all active
    PAUSED     → audio capture paused, overlay frozen
    STOPPING   → graceful shutdown in progress
    COMPLETED  → clean shutdown finished (terminal)
    ERROR      → unrecoverable error (terminal)

Module-level status is handled by ModuleStatusRegistry, NOT here.
"""

from __future__ import annotations
from dataclasses import dataclass, field, replace
from enum import Enum, auto
import time
import uuid


class SessionStateEnum(Enum):
    IDLE = auto()
    STARTING = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    COMPLETED = auto()
    ERROR = auto()

    @property
    def is_terminal(self) -> bool:
        return self in (SessionStateEnum.COMPLETED, SessionStateEnum.ERROR)

    @property
    def is_active(self) -> bool:
        return self in (SessionStateEnum.IDLE, SessionStateEnum.STARTING,
                        SessionStateEnum.RUNNING, SessionStateEnum.PAUSED, SessionStateEnum.STOPPING)


# Valid transitions: each state → set of allowed next states
_TRANSITIONS: dict[SessionStateEnum, set[SessionStateEnum]] = {
    SessionStateEnum.IDLE:      {SessionStateEnum.STARTING, SessionStateEnum.ERROR},
    SessionStateEnum.STARTING:  {SessionStateEnum.RUNNING, SessionStateEnum.ERROR, SessionStateEnum.STOPPING},
    SessionStateEnum.RUNNING:   {SessionStateEnum.PAUSED, SessionStateEnum.STOPPING, SessionStateEnum.ERROR},
    SessionStateEnum.PAUSED:    {SessionStateEnum.RUNNING, SessionStateEnum.STOPPING, SessionStateEnum.ERROR},
    SessionStateEnum.STOPPING:  {SessionStateEnum.COMPLETED, SessionStateEnum.ERROR},
    SessionStateEnum.COMPLETED: set(),   # terminal
    SessionStateEnum.ERROR:     set(),   # terminal
}


class InvalidStateTransition(Exception):
    """Raised when a state transition is not allowed."""
    pass


@dataclass
class SessionState:
    """Lightweight session state holder.

    Module-level status is managed by ModuleStatusRegistry separately.
    Translation / ASR / overlay failures do NOT change session state
    unless the session itself becomes unrecoverable.
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: SessionStateEnum = SessionStateEnum.IDLE
    model_id: str = "tiny"
    translation_mode: str = "off"
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: float | None = None
    stopped_at: float | None = None

    @property
    def is_active(self) -> bool:
        return self.state.is_active

    @property
    def is_terminal(self) -> bool:
        return self.state.is_terminal

    def can_transition(self, target: SessionStateEnum) -> bool:
        return target in _TRANSITIONS.get(self.state, set())

    def transition(self, target: SessionStateEnum) -> "SessionState":
        """Transition to target state. Raises InvalidStateTransition if not allowed.

        Returns self for chaining.
        """
        if not self.can_transition(target):
            raise InvalidStateTransition(
                f"Cannot transition from {self.state.name} to {target.name}"
            )

        now = time.time()
        updates: dict = {"state": target, "updated_at": now}

        if target == SessionStateEnum.STARTING and self.started_at is None:
            updates["started_at"] = now
        if target in (SessionStateEnum.COMPLETED, SessionStateEnum.ERROR):
            updates["stopped_at"] = now
        if target == SessionStateEnum.ERROR and self.error is None:
            updates["error"] = "unspecified error"

        return replace(self, **updates)

    def set_error(self, message: str) -> "SessionState":
        """Convenience: set error message without changing state."""
        return replace(self, error=message, updated_at=time.time())
