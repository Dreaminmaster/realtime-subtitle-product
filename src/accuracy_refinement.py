"""Thread-safe bookkeeping for same-position ASR corrections."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from src.contextual_phrase_composer import ContextualPhraseComposer, PhraseDecision


@dataclass
class _Component:
    source_chunk_id: int
    text: str
    start_offset: float | None = None
    end_offset: float | None = None


@dataclass
class _DisplayRecord:
    components: list[_Component] = field(default_factory=list)
    revision: int = 1


@dataclass(frozen=True)
class RefinementUpdate:
    display_chunk_id: int
    text: str
    revision: int
    start_offset: float | None
    end_offset: float | None


class AccuracyRefinementCoordinator:
    """Maps utterance-level refinements back to the visible composed line."""

    def __init__(self, composer: ContextualPhraseComposer, session_generation: int):
        self._composer = composer
        self._session_generation = int(session_generation)
        self._records: dict[int, _DisplayRecord] = {}
        self._source_to_display: dict[int, int] = {}
        self._lock = RLock()

    def register(
        self,
        decision: PhraseDecision,
        component_text: str,
        *,
        start_offset: float | None = None,
        end_offset: float | None = None,
    ) -> None:
        component = _Component(
            source_chunk_id=int(decision.source_chunk_id),
            text=" ".join((component_text or "").strip().split()),
            start_offset=start_offset,
            end_offset=end_offset,
        )
        with self._lock:
            display_id = int(decision.chunk_id)
            if decision.merged and display_id in self._records:
                record = self._records[display_id]
                record.components.append(component)
                record.revision = max(record.revision + 1, int(decision.revision))
            else:
                record = _DisplayRecord(
                    components=[component],
                    revision=max(1, int(decision.revision)),
                )
                self._records[display_id] = record
            self._source_to_display[component.source_chunk_id] = display_id
            while len(self._records) > 300:
                oldest_display = next(iter(self._records))
                removed = self._records.pop(oldest_display)
                for item in removed.components:
                    self._source_to_display.pop(item.source_chunk_id, None)

    def apply(
        self,
        source_chunk_id: int,
        corrected_text: str,
        *,
        session_generation: int,
    ) -> RefinementUpdate | None:
        clean = " ".join((corrected_text or "").strip().split())
        if not clean or int(session_generation) != self._session_generation:
            return None
        with self._lock:
            display_id = self._source_to_display.get(int(source_chunk_id))
            record = self._records.get(display_id) if display_id is not None else None
            if record is None:
                return None
            component = next(
                (item for item in record.components if item.source_chunk_id == int(source_chunk_id)),
                None,
            )
            if component is None or component.text == clean:
                return None
            component.text = clean
            full_text = ContextualPhraseComposer.join_parts(
                item.text for item in record.components
            )
            record.revision += 1
            self._composer.revise_current(display_id, full_text)
            starts = [item.start_offset for item in record.components if item.start_offset is not None]
            ends = [item.end_offset for item in record.components if item.end_offset is not None]
            return RefinementUpdate(
                display_chunk_id=display_id,
                text=full_text,
                revision=record.revision,
                start_offset=min(starts) if starts else None,
                end_offset=max(ends) if ends else None,
            )

    def reset(self, session_generation: int) -> None:
        with self._lock:
            self._session_generation = int(session_generation)
            self._records.clear()
            self._source_to_display.clear()
