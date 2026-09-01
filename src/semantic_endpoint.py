"""Deterministic multi-signal end-of-turn policy for streaming captions."""

from __future__ import annotations

from dataclasses import dataclass
import re


_STRONG_END_RE = re.compile(r"[.!?。！？][\"'”’）)】》]?$", re.UNICODE)
_EN_UNFINISHED = frozenset(
    {
        "a", "an", "and", "as", "at", "because", "but", "by", "for",
        "from", "if", "in", "into", "of", "on", "or", "so", "than",
        "that", "the", "then", "to", "until", "when", "where", "which",
        "while", "with", "without", "would", "could", "should",
    }
)
_CJK_UNFINISHED = tuple(
    "的了和与或但而因为所以如果虽然为了把被在从到对向比让给跟就才还又也"
)


def _word_count(text: str) -> int:
    latin = re.findall(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*", text)
    cjk = re.findall(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", text)
    return len(latin) + len(cjk)


def looks_incomplete(text: str, language: str | None = None) -> bool:
    text = str(text or "").strip()
    if not text or _STRONG_END_RE.search(text):
        return False
    language = str(language or "auto").lower()
    if language.startswith(("zh", "ja", "ko")) or re.search(
        r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", text
    ):
        return text.endswith(_CJK_UNFINISHED)
    words = re.findall(r"[A-Za-z]+(?:['’\-][A-Za-z]+)*", text.casefold())
    return bool(words and words[-1] in _EN_UNFINISHED)


@dataclass(frozen=True)
class EndpointSignals:
    duration: float
    silence: float
    text: str = ""
    language: str | None = None
    seconds_since_text_change: float | None = None
    word_count: int | None = None


@dataclass(frozen=True)
class EndpointDecision:
    should_finalize: bool
    reason: str
    required_silence: float
    incomplete: bool


class SemanticEndpointPolicy:
    """Combine audio and text cues without a heavyweight turn model.

    This policy is intentionally cheap enough to run for every audio chunk.  A
    future separately licensed semantic model can produce an additional cue,
    but the portable default remains deterministic and testable.
    """

    def __init__(
        self,
        *,
        base_silence: float = 0.95,
        min_duration: float = 0.45,
        max_duration: float = 12.0,
        max_words: int = 42,
    ):
        self.base_silence = max(0.35, min(float(base_silence), 2.5))
        self.min_duration = max(0.2, float(min_duration))
        self.max_duration = max(self.min_duration, float(max_duration))
        self.max_words = max(8, int(max_words))

    def decide(self, signals: EndpointSignals) -> EndpointDecision:
        duration = max(0.0, float(signals.duration))
        silence = max(0.0, float(signals.silence))
        text = str(signals.text or "").strip()
        count = signals.word_count if signals.word_count is not None else _word_count(text)
        incomplete = looks_incomplete(text, signals.language)

        if duration >= self.max_duration:
            return EndpointDecision(True, "hard_duration", 0.0, incomplete)
        if count >= self.max_words and silence >= 0.30:
            return EndpointDecision(True, "content_limit", 0.30, incomplete)
        if duration < self.min_duration:
            return EndpointDecision(False, "too_short", self.base_silence, incomplete)

        required = self.base_silence
        reason = "semantic_pause"
        if _STRONG_END_RE.search(text) and count >= 2:
            required = max(0.35, self.base_silence * 0.52)
            reason = "punctuated_pause"
        elif incomplete:
            required = min(2.25, self.base_silence * 1.70)
            reason = "unfinished_phrase"
        elif count <= 2:
            # A two-word answer may be complete, but a little extra evidence
            # avoids converting normal hesitation into separate caption rows.
            required = min(1.65, self.base_silence * 1.30)
            reason = "short_phrase"

        changed = signals.seconds_since_text_change
        if changed is not None and changed < 0.30:
            required += 0.20
            reason = f"{reason}_still_changing"

        return EndpointDecision(silence >= required, reason, required, incomplete)
