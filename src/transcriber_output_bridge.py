"""Transcriber output bridge for v2.4.0 architecture.

Connects raw transcriber outputs to the ASRResultAdapter and
TranslationAdapter.  Never calls real Whisper, real microphone,
or real API.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
from src.asr_result_adapter import (
    ASRResultAdapter,
    NormalizedASRResult,
    forward_normalized_asr_to_translation_adapter,
)


@dataclass(frozen=True)
class TranscriberBridgeStats:
    received: int = 0
    normalized: int = 0
    forwarded_final: int = 0
    ignored_partial: int = 0
    ignored_stable: int = 0
    invalid: int = 0
    errors: int = 0


@dataclass
class TranscriberBridgeResult:
    ok: bool = True
    normalized: NormalizedASRResult | None = None
    forwarded: bool = False
    message: str = ""


class TranscriberOutputBridge:
    """Bridges raw transcriber output → ASRResultAdapter → TranslationAdapter."""

    def __init__(
        self,
        *,
        session_id: str,
        translation_adapter=None,
        asr_adapter: ASRResultAdapter | None = None,
    ):
        self.session_id = session_id
        self.translation_adapter = translation_adapter
        self.asr_adapter = asr_adapter or ASRResultAdapter(session_id=session_id)
        self._stats = TranscriberBridgeStats()

    def handle_raw_output(self, raw_output: Any) -> TranscriberBridgeResult:
        stats = self._stats
        new_stats = TranscriberBridgeStats(
            received=stats.received + 1,
            normalized=stats.normalized,
            forwarded_final=stats.forwarded_final,
            ignored_partial=stats.ignored_partial,
            ignored_stable=stats.ignored_stable,
            invalid=stats.invalid,
            errors=stats.errors,
        )

        try:
            normalized = self.asr_adapter.normalize(raw_output)
        except Exception as e:
            new_stats = TranscriberBridgeStats(**{
                **asdict(new_stats), "invalid": new_stats.invalid + 1,
            })
            self._stats = new_stats
            return TranscriberBridgeResult(ok=False, message=f"Normalize failed: {e}")

        if normalized is None:
            new_stats = TranscriberBridgeStats(**{
                **asdict(new_stats), "invalid": new_stats.invalid + 1,
            })
            self._stats = new_stats
            return TranscriberBridgeResult(ok=False, message="Invalid output (empty or unknown)")

        new_stats = TranscriberBridgeStats(**{
            **asdict(new_stats), "normalized": new_stats.normalized + 1,
        })

        if normalized.status == "PARTIAL":
            new_stats = TranscriberBridgeStats(**{
                **asdict(new_stats), "ignored_partial": new_stats.ignored_partial + 1,
            })
            self._stats = new_stats
            return TranscriberBridgeResult(
                ok=True, normalized=normalized, forwarded=False,
                message="PARTIAL — not forwarded",
            )

        if normalized.status == "STABLE":
            new_stats = TranscriberBridgeStats(**{
                **asdict(new_stats), "ignored_stable": new_stats.ignored_stable + 1,
            })
            self._stats = new_stats
            return TranscriberBridgeResult(
                ok=True, normalized=normalized, forwarded=False,
                message="STABLE — not forwarded",
            )

        # FINAL
        if self.translation_adapter is None:
            new_stats = TranscriberBridgeStats(**{
                **asdict(new_stats), "ignored_stable": new_stats.ignored_stable + 1,
            })
            self._stats = new_stats
            return TranscriberBridgeResult(
                ok=True, normalized=normalized, forwarded=False,
                message="FINAL but no TranslationAdapter available",
            )

        try:
            fwd = forward_normalized_asr_to_translation_adapter(normalized, self.translation_adapter)
        except Exception as e:
            new_stats = TranscriberBridgeStats(**{
                **asdict(new_stats), "errors": new_stats.errors + 1,
            })
            self._stats = new_stats
            return TranscriberBridgeResult(
                ok=False, normalized=normalized, forwarded=False,
                message=f"Forward error: {e}",
            )

        if fwd:
            new_stats = TranscriberBridgeStats(**{
                **asdict(new_stats), "forwarded_final": new_stats.forwarded_final + 1,
            })
            self._stats = new_stats
            return TranscriberBridgeResult(
                ok=True, normalized=normalized, forwarded=True,
                message="FINAL forwarded to TranslationAdapter",
            )
        else:
            new_stats = TranscriberBridgeStats(**{
                **asdict(new_stats), "ignored_stable": new_stats.ignored_stable + 1,
            })
            self._stats = new_stats
            return TranscriberBridgeResult(
                ok=True, normalized=normalized, forwarded=False,
                message="FINAL but forward returned False",
            )

    def handle_many(self, raw_outputs: list[Any]) -> list[TranscriberBridgeResult]:
        return [self.handle_raw_output(r) for r in raw_outputs]

    def get_stats(self) -> TranscriberBridgeStats:
        return self._stats
