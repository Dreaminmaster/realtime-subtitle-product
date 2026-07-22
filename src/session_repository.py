"""SQLite-backed session repository for v2.4.0 architecture.

Phase 1f: provides persistence for sessions, segments, translations.
Does NOT replace runtime state unless feature flag is enabled.
Default: false.

Schema version: 1
"""

from __future__ import annotations
import sqlite3
import json
import time
import os
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


def get_default_database_path() -> Path:
    return Path.home() / "Library" / "Application Support" / "RealtimeSubtitle" / "realtime_subtitle.sqlite3"


class RepositoryError(RuntimeError):
    """Raised when the repository is in an invalid state."""
    pass


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    closed_at REAL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    source_language TEXT,
    target_language TEXT,
    metadata_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS segments (
    session_id TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    status TEXT NOT NULL,
    original_text TEXT NOT NULL,
    translated_text TEXT,
    translation_status TEXT DEFAULT 'PENDING',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    finalized_at REAL,
    translated_at REAL,
    PRIMARY KEY (session_id, segment_id, revision),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_segments_session_updated
ON segments(session_id, updated_at);

CREATE INDEX IF NOT EXISTS idx_segments_session_segment
ON segments(session_id, segment_id);
"""


class SQLiteSessionRepository:
    """Thread-safe SQLite repository for session and segment persistence."""

    def __init__(self, db_path: str | Path, *, timeout: float = 5.0):
        self._db_path = str(db_path)
        self._timeout = timeout
        self._conn: sqlite3.Connection | None = None
        self._closed = False
        # sqlite3.Connection.close() must never race with a read or write on
        # another thread.  RLock lets _ensure() initialize lazily while a
        # repository operation already owns the lifecycle lock.
        self._lock = threading.RLock()

    # ── lifecycle ────────────────────────────────────────────────
    def initialize(self) -> None:
        with self._lock:
            if self._closed:
                raise RepositoryError("Repository is closed")
            if self._conn is not None:
                return  # already initialized

            parent = os.path.dirname(self._db_path)
            if parent and self._db_path != ":memory:" and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)

            self._conn = sqlite3.connect(
                self._db_path,
                timeout=self._timeout,
                check_same_thread=False,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA_SQL)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except Exception:
                    pass
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
            self._closed = True

    def _ensure(self) -> sqlite3.Connection:
        if self._closed:
            raise RepositoryError("Repository is closed")
        if self._conn is None:
            self.initialize()
        return self._conn

    # ── sessions ─────────────────────────────────────────────────
    def create_session(
        self,
        session_id: str,
        *,
        source_language: str | None = None,
        target_language: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        now = time.time()
        with self._lock:
            conn = self._ensure()
            conn.execute(
                """INSERT OR IGNORE INTO sessions
                   (session_id, created_at, updated_at, status, source_language, target_language, metadata_json)
                   VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?)""",
                (
                    session_id, now, now,
                    source_language, target_language,
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()

    def close_session(self, session_id: str) -> None:
        now = time.time()
        with self._lock:
            conn = self._ensure()
            conn.execute(
                "UPDATE sessions SET closed_at = ?, updated_at = ?, status = 'CLOSED' WHERE session_id = ?",
                (now, now, session_id),
            )
            conn.commit()

    def get_session(self, session_id: str) -> dict | None:
        with self._lock:
            conn = self._ensure()
            cur = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            )
            row = cur.fetchone()
            if row is None:
                return None
            return _row_to_dict(row, cur)

    def list_sessions(self, *, limit: int = 50) -> list[dict]:
        with self._lock:
            conn = self._ensure()
            cur = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            )
            rows = cur.fetchall()
            return [_row_to_dict(r, cur) for r in rows]

    # ── segments ─────────────────────────────────────────────────
    def upsert_original_segment(
        self,
        *,
        session_id: str,
        segment_id: str,
        revision: int,
        status: str,
        original_text: str,
        translation_status: str = "PENDING",
    ) -> None:
        now = time.time()
        with self._lock:
            conn = self._ensure()
            conn.execute(
                """INSERT OR REPLACE INTO segments
                   (session_id, segment_id, revision, status, original_text,
                    translation_status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    segment_id,
                    revision,
                    status,
                    original_text,
                    translation_status,
                    now,
                    now,
                ),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            conn.commit()

    def apply_translation(
        self,
        *,
        session_id: str,
        segment_id: str,
        revision: int,
        translated_text: str,
        translation_status: str = "DONE",
    ) -> bool:
        with self._lock:
            conn = self._ensure()
            now = time.time()
            latest = conn.execute(
                "SELECT MAX(revision) FROM segments WHERE session_id = ? AND segment_id = ?",
                (session_id, segment_id),
            ).fetchone()
            if latest is None or latest[0] is None:
                return False
            if revision != latest[0]:
                return False
            conn.execute(
                """UPDATE segments SET
                   translated_text = ?, translation_status = ?,
                   translated_at = ?, updated_at = ?
                   WHERE session_id = ? AND segment_id = ? AND revision = ?""",
                (translated_text, translation_status, now, now,
                 session_id, segment_id, revision),
            )
            conn.commit()
        return True

    def mark_translation_failed(
        self,
        *,
        session_id: str,
        segment_id: str,
        revision: int,
        error: str | None = None,
    ) -> bool:
        with self._lock:
            conn = self._ensure()
            now = time.time()
            latest = conn.execute(
                "SELECT MAX(revision) FROM segments WHERE session_id = ? AND segment_id = ?",
                (session_id, segment_id),
            ).fetchone()
            if latest is None or latest[0] is None:
                return False
            if revision != latest[0]:
                return False
            conn.execute(
                """UPDATE segments SET
                   translation_status = 'FAILED',
                   translated_text = ?,
                   updated_at = ?
                   WHERE session_id = ? AND segment_id = ? AND revision = ?""",
                (error or "FAILED", now, session_id, segment_id, revision),
            )
            conn.commit()
        return True

    def get_latest_segment(
        self,
        *,
        session_id: str,
        segment_id: str,
    ) -> dict | None:
        with self._lock:
            conn = self._ensure()
            cur = conn.execute(
                """SELECT * FROM segments
                   WHERE session_id = ? AND segment_id = ?
                   ORDER BY revision DESC LIMIT 1""",
                (session_id, segment_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return _row_to_dict(row, cur)

    def list_segments(
        self,
        *,
        session_id: str,
        limit: int = 200,
    ) -> list[dict]:
        with self._lock:
            conn = self._ensure()
            cur = conn.execute(
                """SELECT * FROM segments
                   WHERE session_id = ?
                   ORDER BY updated_at DESC, revision DESC
                   LIMIT ?""",
                (session_id, limit),
            )
            rows = cur.fetchall()
            return [_row_to_dict(r, cur) for r in rows]


def _row_to_dict(row: tuple, cursor: sqlite3.Cursor) -> dict:
    cols = [desc[0] for desc in cursor.description]
    d = dict(zip(cols, row))
    # Parse metadata_json if present
    if "metadata_json" in d and isinstance(d["metadata_json"], str):
        try:
            d["metadata"] = json.loads(d["metadata_json"])
        except (json.JSONDecodeError, TypeError):
            d["metadata"] = {}
    return d
