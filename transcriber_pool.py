import logging
log = logging.getLogger("RealtimeSubtitle")

_transcriber_singleton = None
_transcriber_config_hash = None

def _config_hash():
    from config import config
    return hash((config.asr_backend, config.whisper_model, config.funasr_model,
                 config.whisper_device, config.whisper_compute_type, config.source_language))

def get_or_create_transcriber():
    global _transcriber_singleton, _transcriber_config_hash
    current = _config_hash()
    if _transcriber_singleton is not None and _transcriber_config_hash == current:
        return _transcriber_singleton
    
    from transcriber import Transcriber
    from config import config
    
    asr_backend = config.asr_backend
    model_size = config.whisper_model if asr_backend == "whisper" else config.funasr_model
    
    log.info(f"Creating Transcriber: {asr_backend}/{model_size}")
    _transcriber_singleton = Transcriber(
        backend=asr_backend,
        model_size=model_size,
        device=config.whisper_device,
        compute_type=config.whisper_compute_type,
        language=config.source_language
    )
    _transcriber_singleton.warmup()
    _transcriber_config_hash = current
    return _transcriber_singleton
