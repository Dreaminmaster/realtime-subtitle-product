import logging
log = logging.getLogger("RealtimeSubtitle")

_transcriber_singleton = None
_transcriber_config_hash = None


def _model_name_for_backend(settings):
    return (
        settings.whisper_model
        if settings.asr_backend in ("whisper", "mlx")
        else settings.funasr_model
    )

def _config_hash():
    from config import config
    from runtime_performance import resolve_hardware_runtime_plan
    plan = resolve_hardware_runtime_plan(config.performance_profile)
    return hash((config.asr_backend, config.whisper_model, config.funasr_model,
                 config.whisper_device, config.whisper_compute_type, config.source_language,
                 plan.cpu_threads, plan.num_workers))

def get_or_create_transcriber():
    global _transcriber_singleton, _transcriber_config_hash
    current = _config_hash()
    if _transcriber_singleton is not None and _transcriber_config_hash == current:
        return _transcriber_singleton
    
    from transcriber import Transcriber
    from config import config
    from runtime_performance import resolve_hardware_runtime_plan
    
    asr_backend = config.asr_backend
    model_name = _model_name_for_backend(config)
    runtime_plan = resolve_hardware_runtime_plan(config.performance_profile)
    
    # Resolve model to local path if available — critical for offline first-launch
    resolved_model = model_name
    if asr_backend == "whisper":
        try:
            from model_manager import model_manager as mm
            path = mm.get_model_path(model_name, "whisper")
            if path:
                resolved_model = path
                log.info(f"Resolved whisper model path: {model_name} → {path}")
            else:
                log.warning(f"No local path for model '{model_name}', will use as-is (may trigger HF download)")
        except Exception as e:
            log.warning(f"model_manager resolution skipped: {e}")
    
    log.info(f"Creating Transcriber: {asr_backend}/{model_name} (resolved={resolved_model})")
    _transcriber_singleton = Transcriber(
        backend=asr_backend,
        model_size=resolved_model,
        device=config.whisper_device,
        compute_type=config.whisper_compute_type,
        language=config.source_language,
        cpu_threads=runtime_plan.cpu_threads,
        num_workers=runtime_plan.num_workers,
    )
    _transcriber_singleton.warmup()
    _transcriber_config_hash = current
    return _transcriber_singleton
