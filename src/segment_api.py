"""Segment API for v2.4.0 architecture — stable read-only access over repository.

Provides SessionView, SegmentView, TranscriptSnapshot on top of
SQLiteSessionRepository, and transcript assembly / export helpers.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import json
import time
from src.session_repository import SQLiteSessionRepository


# ── View types ──────────────────────────────────────────────────
@dataclass(frozen=True)
class SessionView:
    session_id: str
    status: str
    created_at: float
    updated_at: float
    closed_at: float | None = None
    source_language: str | None = None
    target_language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SegmentView:
    session_id: str
    segment_id: str
    revision: int
    status: str
    original_text: str
    translated_text: str | None = None
    translation_status: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0
    finalized_at: float | None = None
    translated_at: float | None = None


@dataclass(frozen=True)
class TranscriptSnapshot:
    session: SessionView
    segments: list[SegmentView]
    original_text: str
    translated_text: str
    bilingual_text: str


# ── helpers ──────────────────────────────────────────────────────
def _parse_metadata(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _session_view(row: dict) -> SessionView:
    return SessionView(
        session_id=row.get("session_id", ""),
        status=row.get("status", "ACTIVE"),
        created_at=row.get("created_at", 0.0),
        updated_at=row.get("updated_at", 0.0),
        closed_at=row.get("closed_at"),
        source_language=row.get("source_language"),
        target_language=row.get("target_language"),
        metadata=_parse_metadata(row.get("metadata_json") or row.get("metadata")),
    )


def _segment_view(row: dict) -> SegmentView:
    return SegmentView(
        session_id=row.get("session_id", ""),
        segment_id=row.get("segment_id", ""),
        revision=row.get("revision", 1),
        status=row.get("status", "FINAL"),
        original_text=row.get("original_text", ""),
        translated_text=row.get("translated_text"),
        translation_status=row.get("translation_status"),
        created_at=row.get("created_at", 0.0),
        updated_at=row.get("updated_at", 0.0),
        finalized_at=row.get("finalized_at"),
        translated_at=row.get("translated_at"),
    )


# ── Segment API ──────────────────────────────────────────────────
class SegmentAPI:
    """Read-only access layer over SQLiteSessionRepository."""

    def __init__(self, repository: SQLiteSessionRepository):
        self.repository = repository

    # ── sessions ─────────────────────────────────────────────
    def list_sessions(self, *, limit: int = 50) -> list[SessionView]:
        rows = self.repository.list_sessions(limit=limit)
        return [_session_view(r) for r in rows]

    def get_session(self, session_id: str) -> SessionView | None:
        row = self.repository.get_session(session_id)
        return _session_view(row) if row else None

    def get_active_session(self) -> SessionView | None:
        sessions = self.repository.list_sessions(limit=200)
        for row in sessions:
            if row.get("status") == "ACTIVE":
                return _session_view(row)
        return None

    def recover_last_session(self) -> SessionView | None:
        active = self.get_active_session()
        if active is not None:
            return active
        sessions = self.repository.list_sessions(limit=1)
        if sessions:
            return _session_view(sessions[0])
        return None

    # ── segments ─────────────────────────────────────────────
    def list_segments(self, session_id: str, *, limit: int = 200) -> list[SegmentView]:
        rows = self.repository.list_segments(session_id=session_id, limit=limit)
        return [_segment_view(r) for r in rows]

    def get_latest_segment(self, session_id: str, segment_id: str) -> SegmentView | None:
        row = self.repository.get_latest_segment(session_id=session_id, segment_id=segment_id)
        return _segment_view(row) if row else None

    def _latest_segments_map(self, session_id: str) -> dict[str, SegmentView]:
        rows = self.repository.list_segments(session_id=session_id, limit=2000)
        latest: dict[str, SegmentView] = {}
        for row in rows:
            seg = _segment_view(row)
            if seg.original_text and seg.original_text.strip():
                existing = latest.get(seg.segment_id)
                if existing is None or seg.revision > existing.revision:
                    latest[seg.segment_id] = seg
        return latest

    # ── transcripts ──────────────────────────────────────────
    def get_latest_transcript(self, session_id: str) -> str:
        latest = self._latest_segments_map(session_id)
        ordered = sorted(latest.values(), key=lambda s: (s.updated_at, s.segment_id))
        return "\n".join(s.original_text for s in ordered if s.original_text.strip())

    def get_translated_transcript(self, session_id: str) -> str:
        latest = self._latest_segments_map(session_id)
        ordered = sorted(latest.values(), key=lambda s: (s.updated_at, s.segment_id))
        lines = []
        for s in ordered:
            if s.translated_text and s.translation_status == "DONE":
                lines.append(s.translated_text)
            elif s.translated_text and s.translation_status == "FAILED":
                lines.append(s.original_text)  # fallback to original
            else:
                lines.append(s.original_text)
        return "\n".join(l for l in lines if l.strip())

    def get_session_snapshot(self, session_id: str) -> TranscriptSnapshot | None:
        session = self.get_session(session_id)
        if session is None:
            return None
        latest = self._latest_segments_map(session_id)
        ordered = sorted(latest.values(), key=lambda s: (s.updated_at, s.segment_id))

        original_lines = [s.original_text for s in ordered if s.original_text.strip()]
        translated_lines = []
        bilingual_lines = []
        for s in ordered:
            txt = s.original_text.strip()
            if not txt:
                continue
            bilingual_lines.append(txt)
            if s.translated_text and s.translation_status == "DONE":
                translated_lines.append(s.translated_text)
                bilingual_lines.append(s.translated_text)
            elif s.translated_text and s.translation_status == "FAILED":
                translated_lines.append(txt)
                bilingual_lines.append("[translation failed]")

        return TranscriptSnapshot(
            session=session,
            segments=list(ordered),
            original_text="\n".join(original_lines),
            translated_text="\n".join(translated_lines),
            bilingual_text="\n".join(bilingual_lines),
        )

    # ── export ───────────────────────────────────────────────
    def export_transcript(
        self,
        session_id: str,
        *,
        format: str = "txt",
    ) -> str:
        snap = self.get_session_snapshot(session_id)
        if snap is None:
            raise ValueError(f"Session not found: {session_id}")

        if format == "json":
            return json.dumps({
                "session": {
                    "session_id": snap.session.session_id,
                    "status": snap.session.status,
                    "created_at": snap.session.created_at,
                    "updated_at": snap.session.updated_at,
                    "closed_at": snap.session.closed_at,
                    "source_language": snap.session.source_language,
                    "target_language": snap.session.target_language,
                    "metadata": snap.session.metadata,
                },
                "segments": [
                    {
                        "segment_id": s.segment_id,
                        "revision": s.revision,
                        "original_text": s.original_text,
                        "translated_text": s.translated_text,
                        "translation_status": s.translation_status,
                    }
                    for s in snap.segments
                ],
                "original_text": snap.original_text,
                "translated_text": snap.translated_text,
                "bilingual_text": snap.bilingual_text,
            }, ensure_ascii=False, indent=2)

        # txt format
        lines = [f"Session: {snap.session.session_id}"]
        lines.append(f"Status: {snap.session.status}")
        lines.append(f"Created: {snap.session.created_at}")
        lines.append("")
        lines.append(snap.bilingual_text)
        return "\n".join(lines)
