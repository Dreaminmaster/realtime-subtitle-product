"""
translation_adapter.py — Bridge between TranslationScheduler and the real pipeline.

This adapter is the SINGLE point of contact between the v2.4 scheduler
and the existing pipeline.  It does NOT touch internal pipeline logic.

Usage (in main.py Pipeline.__init__):

    from src.translation_adapter import TranslationAdapter
    self.translation_adapter = TranslationAdapter(
        scheduler=scheduler,
        on_update_text=signals.update_text.emit,
    )

Then in _process_final_v3:

    self.translation_adapter.on_final_text(text, chunk_id)

The adapter handles:
  - TranscriptEvent construction
  - submit() to TranslationScheduler
  - callback → PyQt signal emit
"""

from __future__ import annotations
import time
import uuid
from src.transcript_event import TranscriptEvent, TranscriptPhase
from src.translation_scheduler import TranslationScheduler, TranslationStatus, TranslationResult


class TranslationAdapter:
    """Thin bridge: pipeline events → scheduler → overlay signals."""

    def __init__(
        self,
        scheduler: TranslationScheduler,
        on_update_text: callable | None = None,
    ):
        self.scheduler = scheduler
        self._on_update_text = on_update_text
        self._chunk_to_segment: dict[int, str] = {}  # chunk_id → segment_id
        self._revision_by_segment: dict[str, int] = {}  # segment_id → next revision

        # Wire scheduler callbacks
        scheduler._on_result = self._on_result
        scheduler._on_error = self._on_error

    def start_session(self, session_id: str) -> None:
        self.scheduler.start_session(session_id)
        self._chunk_to_segment.clear()
        self._revision_by_segment.clear()

    def stop_session(self) -> None:
        self.scheduler.stop_session()

    def shutdown(self, wait: bool = True) -> None:
        self.scheduler.shutdown(wait=wait)

    # ── called from pipeline ───────────────────────────────────
    def on_final_text(self, text: str, chunk_id: int) -> None:
        """Pipeline calls this when a FINAL utterance is recognized.

        chunk_id is the utterance_id used by the existing pipeline.
        """
        session_id = self.scheduler._session_id
        if session_id is None:
            return
        if not (text and text.strip()):
            return

        # Maintain stable segment_id per chunk_id
        segment_id = self._chunk_to_segment.get(chunk_id)
        if segment_id is None:
            segment_id = str(uuid.uuid4())
            self._chunk_to_segment[chunk_id] = segment_id
            self._revision_by_segment[segment_id] = 1

        revision = self._revision_by_segment.get(segment_id, 1)

        event = TranscriptEvent(
            session_id=session_id,
            segment_id=segment_id,
            utterance_id=chunk_id,
            revision=revision,
            phase=TranscriptPhase.FINAL,
            seq=chunk_id,
            text_raw=text,
        )
        self.scheduler.submit(event)

        # Bump revision for the next FINAL on this segment
        self._revision_by_segment[segment_id] = revision + 1

    # ── scheduler callbacks ────────────────────────────────────
    def _on_result(self, result: TranslationResult) -> None:
        if self._on_update_text is None:
            return
        # Map back to chunk_id for the existing signal signature
        chunk_id = None
        for cid, sid in self._chunk_to_segment.items():
            if sid == result.segment_id:
                chunk_id = cid
                break
        if chunk_id is None:
            return

        self._on_update_text(chunk_id, result.original_text, result.translated_text)

    def _on_error(self, job, result: TranslationResult) -> None:
        # Phase 1e: log only, no UI change
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.warning(
            f"Translation[{result.segment_id}] failed: {result.error or 'unknown'}"
        )
