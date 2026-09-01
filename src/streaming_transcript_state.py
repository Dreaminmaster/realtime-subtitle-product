"""Monotonic partial/stable/final transcript state.

The implementation borrows the *idea* of LocalAgreement without depending on
or copying WhisperStreaming.  Consecutive hypotheses confirm a common token
prefix while a small suffix stays volatile.  The state is deliberately model
agnostic so faster-whisper, MLX, FunASR, and future native Apple adapters share
the same UI and translation contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import threading
from typing import Hashable

from src.transcript_event import TranscriptPhase


_TOKEN_RE = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]|"
    r"[\u3040-\u30ff\uac00-\ud7af]|"
    r"[\w]+(?:['’\-][\w]+)*|"
    r"[^\w\s]",
    re.UNICODE,
)
_STRONG_ENDINGS = frozenset(".!?。！？")


@dataclass(frozen=True)
class _Token:
    value: str
    start: int
    end: int


def _tokens(text: str) -> list[_Token]:
    return [
        _Token(match.group(0).casefold(), match.start(), match.end())
        for match in _TOKEN_RE.finditer(text)
    ]


def _common_prefix_length(left: list[_Token], right: list[_Token]) -> int:
    length = 0
    for left_token, right_token in zip(left, right):
        if left_token.value != right_token.value:
            break
        length += 1
    return length


def _prefix_for_token_count(text: str, tokens: list[_Token], count: int) -> str:
    if count <= 0 or not tokens:
        return ""
    return text[: tokens[min(count, len(tokens)) - 1].end].strip()


@dataclass(frozen=True)
class StreamingTranscriptUpdate:
    segment_id: Hashable
    revision: int
    phase: TranscriptPhase
    display_text: str
    stable_text: str
    volatile_text: str
    agreement_tokens: int
    final_conflicted_with_stable: bool = False

    @property
    def is_final(self) -> bool:
        return self.phase is TranscriptPhase.FINAL


@dataclass
class _SegmentState:
    revision: int = 0
    previous_text: str = ""
    stable_text: str = ""
    final: bool = False


class StreamingTranscriptState:
    """Track streaming hypotheses with a non-regressing stable prefix.

    ``unsafe_tail_tokens`` is kept volatile even when two hypotheses agree.
    A strongly punctuated hypothesis may confirm its entire common prefix,
    because endpointing can then finalize it quickly.  ``finalize`` is the only
    operation that may replace a previously stable token; that exceptional
    conflict is exposed to diagnostics rather than producing duplicated text.
    """

    def __init__(self, *, unsafe_tail_tokens: int = 2, min_stable_tokens: int = 1):
        self._unsafe_tail_tokens = max(0, int(unsafe_tail_tokens))
        self._min_stable_tokens = max(1, int(min_stable_tokens))
        self._segments: dict[Hashable, _SegmentState] = {}
        self._lock = threading.RLock()

    def observe(self, segment_id: Hashable, text: str) -> StreamingTranscriptUpdate | None:
        text = str(text or "").strip()
        if not text:
            return None

        with self._lock:
            state = self._segments.setdefault(segment_id, _SegmentState())
            if state.final:
                return None

            state.revision += 1
            current_tokens = _tokens(text)
            previous_tokens = _tokens(state.previous_text)
            agreement = _common_prefix_length(previous_tokens, current_tokens)
            unsafe_tail = (
                0 if text[-1:] in _STRONG_ENDINGS else self._unsafe_tail_tokens
            )
            confirmed_count = max(0, agreement - unsafe_tail)
            candidate = _prefix_for_token_count(text, current_tokens, confirmed_count)

            # Stable content is monotonic.  A recognizer rewrite that conflicts
            # with it is kept inside the volatile suffix until FINAL.
            if candidate and len(_tokens(candidate)) >= self._min_stable_tokens:
                if not state.stable_text:
                    state.stable_text = candidate
                elif candidate.casefold().startswith(state.stable_text.casefold()):
                    state.stable_text = candidate

            display_text, volatile_text = self._compose_display(state.stable_text, text)
            state.previous_text = text
            phase = TranscriptPhase.STABLE if state.stable_text else TranscriptPhase.PARTIAL
            return StreamingTranscriptUpdate(
                segment_id=segment_id,
                revision=state.revision,
                phase=phase,
                display_text=display_text,
                stable_text=state.stable_text,
                volatile_text=volatile_text,
                agreement_tokens=agreement,
            )

    def finalize(self, segment_id: Hashable, text: str) -> StreamingTranscriptUpdate | None:
        text = str(text or "").strip()
        if not text:
            return None

        with self._lock:
            state = self._segments.setdefault(segment_id, _SegmentState())
            if state.final:
                return None
            state.revision += 1
            conflicted = bool(
                state.stable_text
                and not text.casefold().startswith(state.stable_text.casefold())
            )
            state.stable_text = text
            state.previous_text = text
            state.final = True
            return StreamingTranscriptUpdate(
                segment_id=segment_id,
                revision=state.revision,
                phase=TranscriptPhase.FINAL,
                display_text=text,
                stable_text=text,
                volatile_text="",
                agreement_tokens=len(_tokens(text)),
                final_conflicted_with_stable=conflicted,
            )

    def discard(self, segment_id: Hashable) -> None:
        with self._lock:
            self._segments.pop(segment_id, None)

    def reset(self) -> None:
        with self._lock:
            self._segments.clear()

    def snapshot(self, segment_id: Hashable) -> StreamingTranscriptUpdate | None:
        with self._lock:
            state = self._segments.get(segment_id)
            if state is None or not state.previous_text:
                return None
            display, volatile = self._compose_display(
                state.stable_text, state.previous_text
            )
            return StreamingTranscriptUpdate(
                segment_id=segment_id,
                revision=state.revision,
                phase=(
                    TranscriptPhase.FINAL
                    if state.final
                    else TranscriptPhase.STABLE
                    if state.stable_text
                    else TranscriptPhase.PARTIAL
                ),
                display_text=display,
                stable_text=state.stable_text,
                volatile_text="" if state.final else volatile,
                agreement_tokens=len(_tokens(state.stable_text)),
            )

    @staticmethod
    def _compose_display(stable: str, latest: str) -> tuple[str, str]:
        if not stable:
            return latest, latest
        if latest.casefold().startswith(stable.casefold()):
            volatile = latest[len(stable) :].lstrip()
            return latest, volatile
        # Preserve the committed prefix in the UI while the recognizer's
        # conflicting rewrite remains volatile.  FINAL can resolve the conflict.
        separator = "" if stable[-1:].isspace() else " "
        return f"{stable}{separator}{latest}", latest
