"""Dashboard adapter: builds HistoryDashboardViewModel for the UI.

Encapsulates config flag check, repository construction, SegmentAPI
creation, and ViewModel building.  Dashboard.py only calls one function.
"""

from __future__ import annotations
from src.history_viewmodel import HistoryViewModelBuilder, HistoryDashboardViewModel


def build_history_viewmodel_for_dashboard(
    config=None,
    *,
    repo_factory=None,
    api_builder=None,
) -> HistoryDashboardViewModel:
    """Build a history viewmodel for dashboard display.

    If use_sqlite_session_repository is False, returns unavailable.
    Otherwise opens the repository, builds SegmentAPI, and returns
    the view.  Repository is always closed within this call.
    """
    if config is None:
        from config import config as _cfg
        config = _cfg

    if not getattr(config, "use_sqlite_session_repository", False):
        return HistoryViewModelBuilder(segment_api=None).build()

    repo = None
    try:
        if repo_factory is not None:
            repo = repo_factory()
        else:
            from src.session_repository import SQLiteSessionRepository, get_default_database_path
            repo = SQLiteSessionRepository(get_default_database_path())
            repo.initialize()

        if api_builder is not None:
            api = api_builder(repo)
        else:
            from src.segment_api import SegmentAPI
            api = SegmentAPI(repo)

        return HistoryViewModelBuilder(api).build()

    except Exception as exc:
        return HistoryDashboardViewModel(
            available=False,
            title="Transcript history unavailable",
            summary="Transcript history could not be loaded.",
            messages=[f"History unavailable: {exc}"],
        )

    finally:
        if repo is not None:
            try:
                repo.close()
            except Exception:
                pass
