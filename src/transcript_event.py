"""Transcript event model for v2.4.0 architecture.

A TranscriptEvent represents one ASR output segment at a specific revision.
The same segment_id can have multiple revisions (original → edit → retranslate).

Design rules:
  - Objects are immutable via dataclass (frozen=False to allow replace/copy
    but convention is: methods return *new* objects, never mutate in place).
  - Revision / stale semantics are baked into the model.
  - Serialization is roundtrip-correct via to_dict/from_dict.
"""

from __future__ import annotations
from dataclasses import dataclass, field, replace
from enum import Enum, auto
import time
import uuid


class TranscriptPhase(Enum):
    PARTIAL = auto()   # real-time preview, may be superseded
    STABLE = auto()    # utterance may continue after short silence (reserved)
    FINAL = auto()     # utterance is complete, will not change


class InvalidTranscriptEvent(ValueError):
    """Raised when Event fields fail validation."""
    pass


@dataclass
class TranscriptEvent:
    """Immutable-in-convention transcript event.

    All mutation helpers (with_*) return new objects.
    """

    # ── identity ──
    session_id: str
    segment_id: str
    utterance_id: int
    revision: int = 1
    phase: TranscriptPhase = TranscriptPhase.PARTIAL
    seq: int = 0

    # ── text ──
    text_raw: str = ""
    text_normalized: str | None = None
    text_user_edited: str | None = None
    translated_text: str | None = None

    # ── language ──
    source_lang: str | None = None
    target_lang: str | None = None

    # ── timing ──
    start_time: float | None = None
    end_time: float | None = None
    created_at: float = field(default_factory=time.time)

    # ── lifecycle ──
    is_stale: bool = False

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if not self.session_id or not isinstance(self.session_id, str):
            raise InvalidTranscriptEvent("session_id must be a non-empty string")
        if not self.segment_id or not isinstance(self.segment_id, str):
            raise InvalidTranscriptEvent("segment_id must be a non-empty string")
        if not isinstance(self.utterance_id, int) or self.utterance_id < 0:
            raise InvalidTranscriptEvent("utterance_id must be int >= 0")
        if not isinstance(self.revision, int) or self.revision < 1:
            raise InvalidTranscriptEvent("revision must be int >= 1")
        if not isinstance(self.seq, int) or self.seq < 0:
            raise InvalidTranscriptEvent("seq must be int >= 0")
        if not isinstance(self.phase, TranscriptPhase):
            raise InvalidTranscriptEvent(f"phase must be TranscriptPhase, got {type(self.phase)}")
        if not self.text_raw and self.phase != TranscriptPhase.STABLE:
            raise InvalidTranscriptEvent("text_raw must not be empty")
        if self.start_time is not None and self.end_time is not None:
            if self.end_time < self.start_time:
                raise InvalidTranscriptEvent(
                    f"end_time ({self.end_time}) must be >= start_time ({self.start_time})"
                )

    # ── properties ──────────────────────────────────────────────────
    @property
    def is_final(self) -> bool:
        return self.phase == TranscriptPhase.FINAL

    @property
    def effective_text(self) -> str:
        """User-edit has top priority, then normalized, then raw."""
        if self.text_user_edited is not None:
            return self.text_user_edited
        if self.text_normalized is not None:
            return self.text_normalized
        return self.text_raw

    # ── mutation helpers (return NEW objects) ───────────────────────
    def mark_stale(self) -> "TranscriptEvent":
        return replace(self, is_stale=True)

    def with_revision(self, new_revision: int, new_text: str | None = None) -> "TranscriptEvent":
        """Create the next revision of this segment.

        new_text becomes text_user_edited if provided.
        """
        updates: dict = {
            "revision": new_revision,
            "is_stale": False,
            "created_at": time.time(),
        }
        if new_text is not None:
            updates["text_user_edited"] = new_text
        return replace(self, **updates)

    def with_translation(self, translated_text: str, target_lang: str | None = None) -> "TranscriptEvent":
        updates: dict = {"translated_text": translated_text}
        if target_lang is not None:
            updates["target_lang"] = target_lang
        return replace(self, **updates)

    # ── serialization ───────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "segment_id": self.segment_id,
            "utterance_id": self.utterance_id,
            "revision": self.revision,
            "phase": self.phase.name,
            "seq": self.seq,
            "text_raw": self.text_raw,
            "text_normalized": self.text_normalized,
            "text_user_edited": self.text_user_edited,
            "translated_text": self.translated_text,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "created_at": self.created_at,
            "is_stale": self.is_stale,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TranscriptEvent":
        return cls(
            session_id=d["session_id"],
            segment_id=d["segment_id"],
            utterance_id=d["utterance_id"],
            revision=d.get("revision", 1),
            phase=TranscriptPhase[d["phase"]] if isinstance(d["phase"], str) else d["phase"],
            seq=d.get("seq", 0),
            text_raw=d.get("text_raw", ""),
            text_normalized=d.get("text_normalized"),
            text_user_edited=d.get("text_user_edited"),
            translated_text=d.get("translated_text"),
            source_lang=d.get("source_lang"),
            target_lang=d.get("target_lang"),
            start_time=d.get("start_time"),
            end_time=d.get("end_time"),
            created_at=d.get("created_at", time.time()),
            is_stale=d.get("is_stale", False),
        )

    # ── factory ─────────────────────────────────────────────────────
    @classmethod
    def create(
        cls,
        session_id: str,
        utterance_id: int,
        text_raw: str,
        *,
        segment_id: str | None = None,
        revision: int = 1,
        phase: TranscriptPhase = TranscriptPhase.PARTIAL,
        seq: int = 0,
        text_normalized: str | None = None,
        source_lang: str | None = None,
        target_lang: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        translated_text: str | None = None,
    ) -> "TranscriptEvent":
        return cls(
            session_id=session_id,
            segment_id=segment_id or str(uuid.uuid4()),
            utterance_id=utterance_id,
            revision=revision,
            phase=phase,
            seq=seq,
            text_raw=text_raw,
            text_normalized=text_normalized,
            source_lang=source_lang,
            target_lang=target_lang,
            start_time=start_time,
            end_time=end_time,
            translated_text=translated_text,
        )
