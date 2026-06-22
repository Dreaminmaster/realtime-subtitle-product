"""ASR result normalization adapter for v2.4.0 architecture.

Converts heterogeneous ASR outputs (dict, object, str, segments lists)
into a stable NormalizedASRResult for use by the rest of the pipeline.

No real audio device, no real Whisper, no side effects.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Literal

ASRStatus = Literal["PARTIAL", "STABLE", "FINAL"]


_STATUS_MAP: dict[str, ASRStatus] = {
    "partial": "PARTIAL",
    "interim": "PARTIAL",
    "unstable": "PARTIAL",
    "stable": "STABLE",
    "confirmed": "STABLE",
    "final": "FINAL",
    "done": "FINAL",
    "completed": "FINAL",
}


def _parse_status(raw: Any) -> ASRStatus | None:
    """Map any raw status value to ASRStatus, or None."""
    # 1. attribute or dict access on status field
    val = _get_field(raw, "status")
    if isinstance(val, str):
        return _STATUS_MAP.get(val.strip().lower())
    # 2. is_final / final flags
    if _get_field(raw, "is_final"):
        return "FINAL"
    if _get_field(raw, "final"):
        return "FINAL"
    # 3. if only plain text → default FINAL
    if isinstance(raw, str):
        return "FINAL"
    # 4. unknown
    return None


def _parse_text(raw: Any) -> str | None:
    """Extract text from raw ASR output."""
    # 1. segments list
    segs = _get_field(raw, "segments")
    if isinstance(segs, list) and segs:
        parts = []
        for s in segs:
            t = _parse_text(s)
            if t:
                parts.append(t)
        if parts:
            return " ".join(parts)
        return None

    # 2. plain string
    if isinstance(raw, str):
        return raw.strip() or None

    # 3. known text field names
    for field in ("text", "transcript", "result", "content"):
        val = _get_field(raw, field)
        if isinstance(val, str) and val.strip():
            return val.strip()

    return None


def _get_field(obj: Any, field: str) -> Any:
    """Try attribute access, then dict lookup."""
    try:
        return getattr(obj, field)
    except AttributeError:
        pass
    try:
        return obj.get(field)
    except (AttributeError, TypeError):
        pass
    try:
        return obj[field]
    except (KeyError, TypeError):
        return None


@dataclass(frozen=True)
class NormalizedASRResult:
    session_id: str
    segment_id: str
    revision: int
    status: ASRStatus
    text: str
    start_time: float | None = None
    end_time: float | None = None
    confidence: float | None = None
    language: str | None = None
    raw: Any = None


class ASRResultAdapter:
    """Normalize heterogeneous ASR outputs to stable internal format."""

    def __init__(self, *, session_id: str):
        self.session_id = session_id
        self._seq = 0
        self._rev_by_segment: dict[str, int] = {}

    def normalize(self, raw_result: Any) -> NormalizedASRResult | None:
        text = _parse_text(raw_result)
        if not text:
            return None
        status = _parse_status(raw_result)
        if status is None:
            return None

        # segment_id
        seg_id = _get_field(raw_result, "segment_id") or _get_field(raw_result, "chunk_id") or _get_field(raw_result, "id")
        if not seg_id or not isinstance(seg_id, str) or not seg_id.strip():
            self._seq += 1
            seg_id = f"seg-{self._seq:06d}"
        else:
            seg_id = seg_id.strip()

        # revision
        rev = _get_field(raw_result, "revision") or _get_field(raw_result, "rev") or _get_field(raw_result, "version")
        if isinstance(rev, (int, float)):
            rev = int(rev)
        else:
            rev = self._rev_by_segment.get(seg_id, 0) + 1
        self._rev_by_segment[seg_id] = rev

        return NormalizedASRResult(
            session_id=self.session_id,
            segment_id=seg_id,
            revision=rev,
            status=status,
            text=text,
            start_time=_get_field(raw_result, "start_time"),
            end_time=_get_field(raw_result, "end_time"),
            confidence=_get_field(raw_result, "confidence"),
            language=_get_field(raw_result, "language"),
            raw=raw_result,
        )

    def normalize_many(self, raw_results: list[Any]) -> list[NormalizedASRResult]:
        return [r for r in (self.normalize(x) for x in raw_results) if r is not None]


def forward_normalized_asr_to_translation_adapter(
    result: NormalizedASRResult,
    translation_adapter,
) -> bool:
    """Bridge: FINAL → adapter.on_final_text. PARTIAL/STABLE → noop.

    Does NOT catch exceptions — let the caller decide error handling.
    """
    if result is None:
        return False
    if result.status != "FINAL":
        return False
    # Compute chunk_id from segment_id
    if result.segment_id.startswith("seg-"):
        chunk_id = int(result.segment_id.rsplit("-", 1)[-1])
    else:
        chunk_id = hash(result.segment_id) % 100000
    translation_adapter.on_final_text(result.text, chunk_id)
    return True
