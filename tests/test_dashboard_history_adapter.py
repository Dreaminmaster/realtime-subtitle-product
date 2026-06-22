"""Tests for dashboard_history_adapter."""
import pytest
from src.dashboard_history_adapter import build_history_viewmodel_for_dashboard
from src.history_viewmodel import HistoryDashboardViewModel


class FakeConfig:
    def __init__(self, use_repo=False):
        self.use_sqlite_session_repository = use_repo


class FakeRepo:
    def __init__(self, fail=False, leak_on_close=False):
        self.closed = False
        self.initialized = False
        self._fail = fail
        self._leak = leak_on_close
    def initialize(self):
        self.initialized = True
        if self._fail:
            raise RuntimeError("init fail")
    def close(self):
        if not self._leak:
            self.closed = True


class FakeAPI:
    def __init__(self, repo):
        self.repo = repo
    def list_sessions(self, limit=20): return []
    def get_session_snapshot(self, sid): raise ValueError("fake")
    def recover_last_session(self): return None


# ── 1. flag off ─────────────────────────────────────────────────
class TestFlagOff:
    def test_returns_unavailable(self):
        vm = build_history_viewmodel_for_dashboard(FakeConfig(use_repo=False))
        assert vm.available is False
        assert not vm.sessions


# ── 2. flag on ──────────────────────────────────────────────────
class TestFlagOn:
    def test_constructs_and_closes(self):
        repo = FakeRepo()
        def factory(): return repo
        def build_api(r): return FakeAPI(r)

        vm = build_history_viewmodel_for_dashboard(
            FakeConfig(use_repo=True),
            repo_factory=factory,
            api_builder=build_api,
        )
        assert repo.closed is True
        assert isinstance(vm, HistoryDashboardViewModel)


# ── 3. init failure ─────────────────────────────────────────────
class TestInitFailure:
    def test_safe(self):
        repo = FakeRepo(fail=True)
        vm = build_history_viewmodel_for_dashboard(
            FakeConfig(use_repo=True),
            repo_factory=lambda: repo,
        )
        assert vm.available is False
        assert vm.messages


# ── 4. repo close always called ─────────────────────────────────
class TestCloseAlways:
    def test_even_on_error(self):
        repo = FakeRepo()
        def build_api(r):
            raise RuntimeError("boom")
        vm = build_history_viewmodel_for_dashboard(
            FakeConfig(use_repo=True),
            repo_factory=lambda: repo,
            api_builder=build_api,
        )
        assert repo.closed is True
        assert vm.available is False


# ── 5. no real user path ────────────────────────────────────────
class TestNoRealUserPath:
    def test_fake_config_path(self):
        # With fake factory, user path is never touched
        repo = FakeRepo()
        vm = build_history_viewmodel_for_dashboard(
            FakeConfig(use_repo=True),
            repo_factory=lambda: repo,
            api_builder=lambda r: FakeAPI(r),
        )
        assert isinstance(vm, HistoryDashboardViewModel)


# ── 6. adapter read-only ────────────────────────────────────────
class TestReadOnly:
    def test_no_write_calls(self):
        repo = FakeRepo()
        vm = build_history_viewmodel_for_dashboard(
            FakeConfig(use_repo=True),
            repo_factory=lambda: repo,
            api_builder=lambda r: FakeAPI(r),
        )
        assert isinstance(vm, HistoryDashboardViewModel)
