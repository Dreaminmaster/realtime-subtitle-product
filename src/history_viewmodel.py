"""Dashboard history ViewModel for v2.4.0 architecture.

Pure read-only layer over SegmentAPI.  Never writes.
No Qt dependency.  No side effects.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class HistorySessionItem:
    session_id: str
    status: str
    created_at: float
    updated_at: float
    closed_at: float | None = None
    label: str = ""


@dataclass(frozen=True)
class HistorySegmentItem:
    session_id: str
    segment_id: str
    revision: int
    status: str
    original_text: str
    translated_text: str | None = None
    translation_status: str | None = None


@dataclass(frozen=True)
class HistoryDashboardViewModel:
    available: bool
    title: str
    summary: str
    sessions: list[HistorySessionItem] = field(default_factory=list)
    selected_session_id: str | None = None
    segments: list[HistorySegmentItem] = field(default_factory=list)
    original_text: str = ""
    translated_text: str = ""
    bilingual_text: str = ""
    export_preview_txt: str = ""
    export_preview_json: str = ""
    messages: list[str] = field(default_factory=list)


class HistoryViewModelBuilder:
    """Builds HistoryDashboardViewModel from SegmentAPI. Pure — no side effects."""

    def __init__(self, segment_api=None):
        self.segment_api = segment_api

    def build(self, selected_session_id: str | None = None) -> HistoryDashboardViewModel:
        api = self.segment_api
        if api is None:
            return HistoryDashboardViewModel(
                available=False,
                title="Transcript history",
                summary="Transcript history is not available. "
                        "Enable SQLite session repository to persist sessions.",
                messages=["SegmentAPI is not available."],
            )

        try:
            sessions_raw = api.list_sessions(limit=20)
        except Exception as e:
            return HistoryDashboardViewModel(
                available=False,
                title="Transcript history",
                summary=f"Unable to read session list: {e}",
                messages=[str(e)],
            )

        sessions = [
            HistorySessionItem(
                session_id=s.get("session_id", ""),
                status=s.get("status", ""),
                created_at=s.get("created_at", 0),
                updated_at=s.get("updated_at", 0),
                closed_at=s.get("closed_at"),
                label=f"{s.get('session_id','')[:8]} ({s.get('status','')})",
            )
            for s in sessions_raw
        ]

        if not sessions:
            return HistoryDashboardViewModel(
                available=True,
                title="Transcript history",
                summary="No transcript sessions found.",
                sessions=[],
                messages=[],
            )

        # Select session
        if selected_session_id is None:
            try:
                recovered = api.recover_last_session()
                if recovered is not None:
                    selected_session_id = recovered.session_id
            except Exception:
                pass
        if selected_session_id is None and sessions:
            selected_session_id = sessions[0].session_id

        vm = HistoryDashboardViewModel(
            available=True,
            title="Transcript history",
            summary=f"{len(sessions)} session(s) available.",
            sessions=sessions,
            selected_session_id=selected_session_id,
        )

        if selected_session_id:
            self._fill_snapshot(api, selected_session_id, vm)
        return vm

    @staticmethod
    def _fill_snapshot(api, session_id: str, vm: HistoryDashboardViewModel) -> None:
        messages = list(vm.messages)
        snap = None
        try:
            snap = api.get_session_snapshot(session_id)
        except ValueError as e:
            messages.append(f"Session not found: {session_id} ({e})")
        except Exception as e:
            messages.append(f"Error reading session: {e}")

        if snap is None:
            if messages != list(vm.messages):
                object.__setattr__(vm, "messages", messages)
            return

        object.__setattr__(vm, "original_text", snap.original_text)
        object.__setattr__(vm, "translated_text", snap.translated_text)
        object.__setattr__(vm, "bilingual_text", snap.bilingual_text)
        object.__setattr__(vm, "segments", [
            HistorySegmentItem(
                session_id=s.session_id,
                segment_id=s.segment_id,
                revision=s.revision,
                status=s.status,
                original_text=s.original_text,
                translated_text=s.translated_text,
                translation_status=s.translation_status,
            )
            for s in snap.segments
        ])

        try:
            txt = api.export_transcript(session_id, format="txt")
            object.__setattr__(vm, "export_preview_txt", txt[:2000])
        except Exception as e:
            messages.append(f"TXT export error: {e}")

        try:
            j = api.export_transcript(session_id, format="json")
            object.__setattr__(vm, "export_preview_json", j[:2000])
        except Exception as e:
            messages.append(f"JSON export error: {e}")

        if messages != list(vm.messages):
            object.__setattr__(vm, "messages", messages)
