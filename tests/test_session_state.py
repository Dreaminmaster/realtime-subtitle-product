"""Unit tests for SessionState machine."""
import pytest
import time
from src.session_state import (
    SessionState, SessionStateEnum, InvalidStateTransition,
)


class TestInitialState:
    def test_default_is_idle(self):
        s = SessionState()
        assert s.state == SessionStateEnum.IDLE
        assert s.is_active is True
        assert s.is_terminal is False

    def test_session_id_unique(self):
        s1 = SessionState()
        s2 = SessionState()
        assert s1.session_id != s2.session_id

    def test_created_at_set(self):
        s = SessionState()
        now = time.time()
        assert abs(s.created_at - now) < 2.0


class TestValidTransitions:
    def test_full_lifecycle(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        assert s.state == SessionStateEnum.STARTING
        assert s.started_at is not None

        s = s.transition(SessionStateEnum.RUNNING)
        assert s.state == SessionStateEnum.RUNNING

        s = s.transition(SessionStateEnum.STOPPING)
        assert s.state == SessionStateEnum.STOPPING

        s = s.transition(SessionStateEnum.COMPLETED)
        assert s.state == SessionStateEnum.COMPLETED
        assert s.is_terminal is True
        assert s.stopped_at is not None

    def test_running_to_pause_and_back(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        s = s.transition(SessionStateEnum.RUNNING)
        s = s.transition(SessionStateEnum.PAUSED)
        assert s.state == SessionStateEnum.PAUSED
        s = s.transition(SessionStateEnum.RUNNING)
        assert s.state == SessionStateEnum.RUNNING

    def test_idle_to_starting(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        assert s.state == SessionStateEnum.STARTING

    def test_starting_to_error(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        s = s.transition(SessionStateEnum.ERROR)
        assert s.state == SessionStateEnum.ERROR
        assert s.is_terminal is True

    def test_running_to_error(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        s = s.transition(SessionStateEnum.RUNNING)
        s = s.transition(SessionStateEnum.ERROR)
        assert s.state == SessionStateEnum.ERROR


class TestInvalidTransitions:
    def test_idle_to_completed_raises(self):
        s = SessionState()
        with pytest.raises(InvalidStateTransition):
            s.transition(SessionStateEnum.COMPLETED)

    def test_idle_to_running_raises(self):
        s = SessionState()
        with pytest.raises(InvalidStateTransition):
            s.transition(SessionStateEnum.RUNNING)

    def test_completed_to_running_raises(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        s = s.transition(SessionStateEnum.RUNNING)
        s = s.transition(SessionStateEnum.STOPPING)
        s = s.transition(SessionStateEnum.COMPLETED)
        with pytest.raises(InvalidStateTransition):
            s.transition(SessionStateEnum.RUNNING)

    def test_error_to_running_raises(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        s = s.transition(SessionStateEnum.ERROR)
        with pytest.raises(InvalidStateTransition):
            s.transition(SessionStateEnum.RUNNING)

    def test_error_to_idle_raises(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        s = s.transition(SessionStateEnum.ERROR)
        with pytest.raises(InvalidStateTransition):
            s.transition(SessionStateEnum.IDLE)

    def test_paused_to_starting_raises(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        s = s.transition(SessionStateEnum.RUNNING)
        s = s.transition(SessionStateEnum.PAUSED)
        with pytest.raises(InvalidStateTransition):
            s.transition(SessionStateEnum.STARTING)


class TestTerminalStates:
    def test_completed_is_terminal(self):
        assert SessionStateEnum.COMPLETED.is_terminal is True

    def test_error_is_terminal(self):
        assert SessionStateEnum.ERROR.is_terminal is True

    def test_running_is_not_terminal(self):
        assert SessionStateEnum.RUNNING.is_terminal is False

    def test_cannot_transition_from_completed(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        s = s.transition(SessionStateEnum.RUNNING)
        s = s.transition(SessionStateEnum.STOPPING)
        s = s.transition(SessionStateEnum.COMPLETED)
        assert s.can_transition(SessionStateEnum.RUNNING) is False
        assert s.can_transition(SessionStateEnum.ERROR) is False
        assert s.can_transition(SessionStateEnum.IDLE) is False

    def test_cannot_transition_from_error(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        s = s.transition(SessionStateEnum.ERROR)
        assert s.can_transition(SessionStateEnum.RUNNING) is False
        assert s.can_transition(SessionStateEnum.COMPLETED) is False


class TestErrorHandling:
    def test_set_error_message(self):
        s = SessionState()
        s2 = s.set_error("disk full")
        assert s2.error == "disk full"
        assert s2.state == SessionStateEnum.IDLE  # set_error does NOT change state

    def test_transition_to_error_sets_default_message(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        s = s.transition(SessionStateEnum.ERROR)
        assert s.error is not None

    def test_transition_to_error_keeps_existing_message(self):
        s = SessionState()
        s = s.set_error("already known")
        s = s.transition(SessionStateEnum.STARTING)
        s = s.transition(SessionStateEnum.ERROR)
        assert s.error == "already known"


class TestStartedStopped:
    def test_started_at_on_starting(self):
        s = SessionState()
        assert s.started_at is None
        s = s.transition(SessionStateEnum.STARTING)
        assert s.started_at is not None

    def test_stopped_at_on_completed(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        s = s.transition(SessionStateEnum.RUNNING)
        s = s.transition(SessionStateEnum.STOPPING)
        s = s.transition(SessionStateEnum.COMPLETED)
        assert s.stopped_at is not None

    def test_stopped_at_on_error(self):
        s = SessionState()
        s = s.transition(SessionStateEnum.STARTING)
        s = s.transition(SessionStateEnum.ERROR)
        assert s.stopped_at is not None
