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
    """Thin bridge: pipeline events → scheduler → overlay signals.

    Optional repository: if provided and repository_enabled=True, FINAL
    original text and translation results are persisted via the repository.
    """

    def __init__(
        self,
        scheduler: TranslationScheduler,
        on_update_text: callable | None = None,
        *,
        repository=None,
        repository_enabled: bool = False,
    ):
        self.scheduler = scheduler
        self._on_update_text = on_update_text
        self._repository = repository
        self._repo_enabled = bool(repository_enabled and repository is not None)
        self._chunk_to_segment: dict[int, str] = {}
        self._revision_by_segment: dict[str, int] = {}

        scheduler._on_result = self._on_result
        scheduler._on_error = self._on_error

    def start_session(
        self,
        session_id: str,
        *,
        source_language: str | None = None,
        target_language: str | None = None,
    ) -> None:
        self.scheduler.start_session(session_id)
        self._chunk_to_segment.clear()
        self._revision_by_segment.clear()
        if self._repo_enabled:
            self._repository.create_session(
                session_id,
                source_language=source_language or "Auto",
                target_language=target_language,
            )

    def stop_session(self) -> None:
        self.scheduler.stop_session()

    def shutdown(self, wait: bool = True) -> None:
        self.scheduler.shutdown(wait=wait)

    # ── called from pipeline ───────────────────────────────────
    def on_final_text(self, text: str, chunk_id: int, *, translate: bool = True) -> None:
        """Persist a FINAL transcript and optionally schedule translation.

        ``translate=False`` is the normal path when the user selects the
        no-translation mode.  The original still belongs in session history,
        but no empty no-op translation job should be created.
        """
        session_id = self.scheduler._session_id
        if session_id is None:
            return
        if not (text and text.strip()):
            return

        segment_id = self._chunk_to_segment.get(chunk_id)
        if segment_id is None:
            segment_id = str(uuid.uuid4())
            self._chunk_to_segment[chunk_id] = segment_id
            self._revision_by_segment[segment_id] = 1

        revision = self._revision_by_segment.get(segment_id, 1)

        # ── repository write (before scheduler, best-effort) ──
        if self._repo_enabled:
            try:
                self._repository.create_session(session_id)
                self._repository.upsert_original_segment(
                    session_id=session_id,
                    segment_id=segment_id,
                    revision=revision,
                    status="FINAL",
                    original_text=text,
                    translation_status="PENDING" if translate else "NOT_REQUESTED",
                )
            except Exception:
                import logging
                log = logging.getLogger("RealtimeSubtitle")
                log.exception("Repository write error (original segment)")
                # Do NOT block — continue to scheduler + overlay

        if not translate:
            self._revision_by_segment[segment_id] = revision + 1
            return

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
        self._revision_by_segment[segment_id] = revision + 1

    # ── scheduler callbacks ────────────────────────────────────
    def _on_result(self, result: TranslationResult) -> None:
        # Repository write-back with stale guard
        if self._repo_enabled and result.status == TranslationStatus.COMPLETED:
            try:
                applied = self._repository.apply_translation(
                    session_id=result.session_id,
                    segment_id=result.segment_id,
                    revision=result.revision,
                    translated_text=result.translated_text or "",
                )
            except Exception:
                import logging
                log = logging.getLogger("RealtimeSubtitle")
                log.exception("Repository write error (translation)")
                applied = False
            if not applied:
                # Stale or rejected — do NOT update overlay
                return

        # Overlay update
        if self._on_update_text is None:
            return
        chunk_id = None
        for cid, sid in self._chunk_to_segment.items():
            if sid == result.segment_id:
                chunk_id = cid
                break
        if chunk_id is None:
            return
        self._on_update_text(chunk_id, result.original_text, result.translated_text)

    def _on_error(self, job, result: TranslationResult) -> None:
        if self._repo_enabled:
            try:
                self._repository.mark_translation_failed(
                    session_id=result.session_id,
                    segment_id=result.segment_id,
                    revision=result.revision,
                    error=result.error or "unknown",
                )
            except Exception:
                pass
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        log.warning(
            f"Translation[{result.segment_id}] failed: {result.error or 'unknown'}"
        )
