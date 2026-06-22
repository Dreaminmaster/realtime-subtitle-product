"""Runtime Transcriber Bridge Adapter for v2.4.0 architecture.

Factory is pure: decision + translation_adapter → TranscriberOutputBridge or None.
No filesystem, no network, no scheduler creation, no repository.
"""

from __future__ import annotations
from src.runtime_settings_guard import RuntimeSettingsDecision
from src.transcriber_output_bridge import TranscriberOutputBridge


def build_transcriber_output_bridge_for_runtime(
    decision: RuntimeSettingsDecision,
    *,
    session_id: str,
    translation_adapter=None,
) -> TranscriberOutputBridge | None:
    """Return a TranscriberOutputBridge if the runtime decision permits,
    or None if not allowed, adapter missing, or decision invalid.
    """
    if not decision.allow_transcriber_output_bridge:
        return None
    if translation_adapter is None:
        return None
    return TranscriberOutputBridge(
        session_id=session_id,
        translation_adapter=translation_adapter,
    )
