"""Construction boundary for the optional high-quality ASR second pass."""

from __future__ import annotations

import logging

from recognition_quality import AccuracyPlan, resolve_accuracy_plan


log = logging.getLogger("RealtimeSubtitle")


def create_accuracy_transcriber() -> tuple[AccuracyPlan, object] | None:
    """Create a local refiner, or safely disable enhancement when unavailable."""
    from config import config

    if not bool(getattr(config, "enhanced_accuracy", False)):
        return None

    plan = resolve_accuracy_plan(getattr(config, "accuracy_profile", "auto"))
    if (
        getattr(config, "asr_backend", "whisper") == "whisper"
        and getattr(config, "whisper_model", "") == plan.model_id
    ):
        log.info(
            "Enhanced ASR second pass skipped: live model already matches %s",
            plan.model_id,
        )
        return None

    from model_manager import model_manager

    model_path = model_manager.get_model_path(plan.model_id, "whisper")
    if not model_path:
        log.warning(
            "Enhanced ASR disabled for this session: local model %s is missing",
            plan.model_id,
        )
        return None

    from transcriber import Transcriber

    log.info(
        "Loading enhanced ASR refiner: profile=%s model=%s device=%s compute=%s",
        plan.resolved_profile,
        plan.model_id,
        plan.device,
        plan.compute_type,
    )
    transcriber = Transcriber(
        backend="whisper",
        model_size=model_path,
        device=plan.device,
        compute_type=plan.compute_type,
        language=getattr(config, "source_language", None),
    )
    transcriber.warmup()
    return plan, transcriber

