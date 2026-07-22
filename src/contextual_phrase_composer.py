"""Compose nearby ASR finals into sentence-level subtitle revisions."""

from __future__ import annotations

from dataclasses import dataclass
import re
import time


_CJK_RE = re.compile(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]")
_NO_SPACE_SCRIPT_RE = re.compile(r"[\u3400-\u9fff\u3040-\u30ff]")
_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_CONTINUATION_WORDS = {
    "a", "an", "and", "are", "as", "at", "because", "but", "by",
    "can", "could", "did", "do", "does", "for", "from", "had", "has",
    "have", "if", "in", "is", "my", "of", "on", "or", "should", "so",
    "than", "that", "the", "their", "then", "to", "was", "were", "when",
    "which", "who", "will", "with", "would", "your",
}
_COMPLETE_SHORT_PHRASES = {
    "thank you", "thanks", "goodbye", "hello", "hi", "okay", "ok",
    "yes", "no", "good morning", "good night", "see you",
}
_CJK_CONTINUATION_SUFFIXES = (
    "因为", "所以", "但是", "不过", "而且", "然后", "如果", "假如", "虽然",
    "就是", "比如", "例如", "我想", "我觉得", "我希望", "能不能", "可不可以",
    "关于", "对于", "以及", "或者", "还有", "为了", "当", "在", "从", "把", "被",
    "から", "ので", "けど", "でも", "そして", "もし", "について",
    "그리고", "하지만", "때문에", "만약", "그래서", "대해서",
)


@dataclass(frozen=True)
class PhraseDecision:
    chunk_id: int
    source_chunk_id: int
    text: str
    merged: bool
    complete: bool
    revision: int


class ContextualPhraseComposer:
    """Join a likely unfinished phrase with the next nearby ASR final."""

    def __init__(self, *, join_window: float = 4.0, max_words: int = 42, max_chars: int = 280):
        self.join_window = float(join_window)
        self.max_words = int(max_words)
        self.max_chars = int(max_chars)
        self._chunk_id: int | None = None
        self._text = ""
        self._complete = True
        self._updated_at = 0.0
        self._revision = 0

    def compose(self, chunk_id: int, text: str, *, now: float | None = None) -> PhraseDecision:
        now = time.monotonic() if now is None else float(now)
        clean = " ".join((text or "").strip().split())
        if not clean:
            raise ValueError("text must not be empty")

        can_join = (
            self._chunk_id is not None
            and not self._complete
            and now - self._updated_at <= self.join_window
            and self._fits(self._text, clean)
        )
        if can_join:
            self._text = self._join(self._text, clean)
            self._revision += 1
            merged = True
        else:
            self._chunk_id = int(chunk_id)
            self._text = clean
            self._revision = 1
            merged = False

        self._complete = self.looks_complete(self._text)
        self._updated_at = now
        return PhraseDecision(
            chunk_id=int(self._chunk_id),
            source_chunk_id=int(chunk_id),
            text=self._text,
            merged=merged,
            complete=self._complete,
            revision=self._revision,
        )

    def _fits(self, first: str, second: str) -> bool:
        combined = self._join(first, second)
        return len(combined) <= self.max_chars and len(_WORD_RE.findall(combined)) <= self.max_words

    @staticmethod
    def _join(first: str, second: str) -> str:
        first = first.rstrip()
        second = second.lstrip()
        # Remove artificial sentence punctuation before a continuation while
        # retaining question/exclamation marks that convey real intent.
        if first.endswith((".", "。")):
            first = first[:-1].rstrip()
        # Chinese/Japanese join without an inserted space; Korean retains its
        # normal inter-word spacing even though it shares the CJK branch.
        no_space = bool(
            _NO_SPACE_SCRIPT_RE.search(first[-1:])
            and _NO_SPACE_SCRIPT_RE.search(second[:1])
        )
        return first + ("" if no_space else " ") + second

    @staticmethod
    def looks_complete(text: str) -> bool:
        clean = (text or "").strip()
        if not clean:
            return True
        if clean.endswith(("?", "!", "？", "！", "…")):
            return True
        if _CJK_RE.search(clean):
            compact = re.sub(r"\s+", "", clean)
            if compact.rstrip(".。").endswith(_CJK_CONTINUATION_SUFFIXES):
                return False
            # CJK has no reliable whitespace-based word count.  Avoid joining
            # every ordinary short sentence merely because ASR omitted a full
            # stop; only explicit connective endings remain open.
            return True
        words = [word.lower() for word in _WORD_RE.findall(clean)]
        if words:
            normalized = " ".join(words)
            if normalized in _COMPLETE_SHORT_PHRASES:
                return True
            if words[-1] in _CONTINUATION_WORDS:
                return False
        if clean.endswith((".", "。")):
            return True
        # ASR without punctuation is usually a phrase boundary caused by a
        # pause, not necessarily a semantic sentence boundary.
        # A two-word fragment is frequently a pause inside a phrase ("I was",
        # "the new").  At three or more words, a non-connective ending is much
        # more likely to be a legitimate caption boundary.
        return len(words) >= 3 or len(clean) >= 150
