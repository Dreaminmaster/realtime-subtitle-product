"""Construction boundary for the optional high-quality ASR second pass."""

from __future__ import annotations

import logging

from recognition_quality import AccuracyPlan, resolve_accuracy_plan


log = logging.getLogger("RealtimeSubtitle")


def resolve_accuracy_runtime() -> tuple[AccuracyPlan, str] | None:
    """Resolve the installed refiner without loading a model.

    This deliberately stays cheap so live captions can start before a larger
    optional model is initialized in the background.
    """
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

    return plan, model_path


def load_accuracy_transcriber(plan: AccuracyPlan, model_path: str):
    """Load and warm an already-resolved local refinement model."""
    from config import config
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
    return transcriber


def create_accuracy_transcriber() -> tuple[AccuracyPlan, object] | None:
    """Backward-compatible eager factory used by diagnostics and tests."""
    runtime = resolve_accuracy_runtime()
    if runtime is None:
        return None
    plan, model_path = runtime
    return plan, load_accuracy_transcriber(plan, model_path)
