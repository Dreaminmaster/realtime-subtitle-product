"""Latest-only translation previews for an utterance that is still changing."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass


log = logging.getLogger("RealtimeSubtitle")


@dataclass(frozen=True)
class _Draft:
    session_generation: int
    chunk_id: int
    revision: int
    source_text: str
    translation_text: str
    due_at: float


class LiveTranslationDrafts:
    """Translate only the newest partial without persisting draft text.

    One worker and one pending slot keep local LLMs and online APIs bounded.
    A completed prefix is still useful while a longer phrase is being spoken,
    so the callback receives the latest original text together with that
    prefix translation.  Finalization invalidates all draft results for the
    chunk before the regular FINAL scheduler takes over.
    """

    def __init__(
        self,
        translator,
        on_result,
        *,
        interval: float,
        min_growth: int = 10,
        clock=time.monotonic,
    ):
        self._translator = translator
        self._on_result = on_result
        self._interval = max(0.25, float(interval))
        self._min_growth = max(1, int(min_growth))
        self._clock = clock
        self._condition = threading.Condition()
        self._session_generation: int | None = None
        self._pending: _Draft | None = None
        self._latest_revision: dict[int, int] = {}
        self._latest_text: dict[int, str] = {}
        self._finalized: set[int] = set()
        self._last_submitted_text: dict[int, str] = {}
        self._last_started_at = 0.0
        self._running = True
        self._thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="LiveTranslationDrafts",
        )
        self._thread.start()

    def start_session(self, session_generation: int) -> None:
        with self._condition:
            self._session_generation = int(session_generation)
            self._pending = None
            self._latest_revision.clear()
            self._latest_text.clear()
            self._finalized.clear()
            self._last_submitted_text.clear()
            self._last_started_at = 0.0
            self._condition.notify_all()

    def submit(
        self,
        session_generation: int,
        chunk_id: int,
        text: str,
        *,
        stable_text: str | None = None,
        source_revision: int | None = None,
    ) -> bool:
        """Queue the newest useful stable prefix for bounded retranslation.

        ``text`` is the latest full source shown by the overlay.  When supplied,
        ``stable_text`` is the smaller monotonic prefix sent to the translator.
        The optional source revision lets the transcript state machine and this
        worker share one stale-result identity.
        """
        text = str(text or "").strip()
        translation_text = str(stable_text or text).strip()
        if len(translation_text) < 6:
            return False
        with self._condition:
            if not self._running or self._session_generation != session_generation:
                return False
            if chunk_id in self._finalized:
                return False
            previous = self._last_submitted_text.get(chunk_id, "")
            if previous and translation_text == previous:
                self._latest_text[chunk_id] = text
                return False
            if (
                previous
                and translation_text.startswith(previous)
                and len(translation_text) - len(previous) < self._min_growth
            ):
                self._latest_text[chunk_id] = text
                return False

            current_revision = self._latest_revision.get(chunk_id, 0)
            revision = max(
                current_revision + 1,
                int(source_revision or 0),
            )
            self._latest_revision[chunk_id] = revision
            self._latest_text[chunk_id] = text
            self._last_submitted_text[chunk_id] = translation_text
            due_at = max(self._clock(), self._last_started_at + self._interval)
            replaced = self._pending is not None
            self._pending = _Draft(
                session_generation=session_generation,
                chunk_id=chunk_id,
                revision=revision,
                source_text=text,
                translation_text=translation_text,
                due_at=due_at,
            )
            self._condition.notify_all()
        if replaced:
            log.debug("Draft translation replaced an older pending preview")
        return True

    def finalize(self, chunk_id: int) -> None:
        with self._condition:
            self._finalized.add(chunk_id)
            self._latest_revision[chunk_id] = self._latest_revision.get(chunk_id, 0) + 1
            if self._pending is not None and self._pending.chunk_id == chunk_id:
                self._pending = None
            self._condition.notify_all()

    def stop(self) -> None:
        with self._condition:
            self._session_generation = None
            self._pending = None
            self._latest_revision.clear()
            self._latest_text.clear()
            self._finalized.clear()
            self._condition.notify_all()

    def shutdown(self, wait: bool = False) -> None:
        with self._condition:
            self._running = False
            self._pending = None
            self._condition.notify_all()
        if wait and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                while self._running and self._pending is None:
                    self._condition.wait(timeout=0.75)
                if not self._running:
                    return
                draft = self._pending
                if draft is None:
                    continue
                remaining = draft.due_at - self._clock()
                if remaining > 0:
                    self._condition.wait(timeout=min(remaining, 0.75))
                    continue
                self._pending = None
                self._last_started_at = self._clock()

            started = self._clock()
            try:
                translated = self._translator(draft.translation_text)
            except Exception:
                log.exception("Draft translation failed for chunk %s", draft.chunk_id)
                continue
            elapsed = self._clock() - started
            if isinstance(translated, str) and translated.startswith("[Translation Failed:"):
                log.warning(
                    "Draft translation[%s] failed; keeping the original preview",
                    draft.chunk_id,
                )
                continue

            with self._condition:
                valid = (
                    self._running
                    and self._session_generation == draft.session_generation
                    and draft.chunk_id not in self._finalized
                )
                current_text = self._latest_text.get(draft.chunk_id, draft.source_text)
                current_revision = self._latest_revision.get(draft.chunk_id, 0)
                # A translation for a recent prefix is useful, but never show
                # text from an unrelated replacement hypothesis.
                compatible = (
                    current_revision >= draft.revision
                    and (
                        current_text.startswith(draft.translation_text)
                        or draft.translation_text.startswith(current_text)
                    )
                )
            if valid and compatible and translated:
                log.info(
                    "Draft translation[%s] chars=%s latency_ms=%.0f",
                    draft.chunk_id,
                    len(draft.translation_text),
                    elapsed * 1000,
                )
                try:
                    self._on_result(draft.chunk_id, current_text, translated)
                except Exception:
                    log.exception("Draft translation callback failed")
