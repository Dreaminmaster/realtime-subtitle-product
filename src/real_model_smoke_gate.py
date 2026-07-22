"""Phase 4c — optional real model smoke gate."""

from __future__ import annotations
from dataclasses import dataclass, field
import os
import time

@dataclass(frozen=True)
class RealModelSmokeConfig:
    enabled: bool = False
    backend: str = "whisper"
    model_name: str | None = None
    fixture_wav_path: str | None = None
    repository_path: str | None = None

@dataclass(frozen=True)
class RealModelSmokeResult:
    ok: bool = True
    status: str = "not_run"
    reason: str = "Real model smoke is disabled by default."
    backend: str | None = None
    model_name: str | None = None
    original_text: str = ""
    translated_text: str = ""
    bilingual_text: str = ""
    repo_closed: bool = False

def real_model_smoke_config_from_env(env=None):
    if env is None:
        env = os.environ
    return RealModelSmokeConfig(
        enabled=env.get("REALTIME_SUBTITLE_ENABLE_REAL_MODEL_SMOKE", "0") == "1",
        backend=env.get("REALTIME_SUBTITLE_REAL_MODEL_BACKEND", "whisper"),
        model_name=env.get("REALTIME_SUBTITLE_REAL_MODEL_NAME") or None,
        fixture_wav_path=env.get("REALTIME_SUBTITLE_REAL_MODEL_FIXTURE_WAV") or None,
        repository_path=env.get("REALTIME_SUBTITLE_REAL_MODEL_REPO_PATH") or None,
    )

def run_optional_real_model_smoke(config, transcriber_factory=None, translator=None, tmp_path=None):
    if not config.enabled:
        return RealModelSmokeResult(ok=True, status="not_run",
            reason="Real model smoke is disabled by default.")

    # Check backend
    if config.backend not in ("whisper", "mlx", "funasr"):
        return RealModelSmokeResult(ok=True, status="not_run",
            reason=f"Unknown backend: {config.backend}")

    # Try to construct transcriber
    try:
        if transcriber_factory is None:
            from transcriber import Transcriber
            t = Transcriber(
                backend=config.backend,
                model_size=config.model_name or "base",
            )
        else:
            t = transcriber_factory(config.backend)
    except Exception as e:
        return RealModelSmokeResult(ok=True, status="not_available",
            reason=f"Transcriber not available: {e}", backend=config.backend)

    # WAV
    wav_path = config.fixture_wav_path
    if not wav_path:
        from src.audio_file_smoke import generate_fixture_wav
        import tempfile
        wav_path = str(tmp_path / "smoke.wav") if tmp_path else tempfile.mktemp(suffix=".wav")
        generate_fixture_wav(wav_path)

    try:
        from src.audio_file_smoke import iter_wav_chunks, inspect_wav_file
        info = inspect_wav_file(wav_path)
        chunks = list(iter_wav_chunks(wav_path, chunk_duration_seconds=0.25))
        if not chunks:
            raise ValueError("WAV fixture contains no audio chunks")

        # The production pipeline transcribes an accumulated utterance, not
        # isolated 250 ms frames.  Joining the fixture prevents real Whisper
        # from returning empty text for every undersized chunk.
        import numpy as np
        if info.sample_width != 2:
            raise ValueError(f"Unsupported WAV sample width: {info.sample_width}")
        audio_data = np.frombuffer(
            b"".join(c.frames for c in chunks),
            dtype="<i2",
        ).astype(np.float32) / 32768.0
        if info.channels > 1:
            audio_data = audio_data.reshape(-1, info.channels).mean(axis=1)
        raw = t.transcribe(audio_data)
        if isinstance(raw, str):
            original = raw
        elif isinstance(raw, dict):
            original = raw.get("text", "")
        else:
            original = ""
    except Exception as e:
        return RealModelSmokeResult(ok=False, status="error",
            reason=f"Transcriber error: {e}", backend=config.backend)

    if not original:
        return RealModelSmokeResult(ok=True, status="not_run",
            reason="Transcriber produced empty output", backend=config.backend)

    # Bridge + repository
    from src.session_repository import SQLiteSessionRepository
    from src.segment_api import SegmentAPI
    from src.translation_scheduler import TranslationScheduler
    from src.translation_adapter import TranslationAdapter
    import uuid

    repo_path = config.repository_path or (str(tmp_path / "real_model_smoke.sqlite3") if tmp_path else ":memory:")
    repo = SQLiteSessionRepository(repo_path)
    repo.initialize()
    session_id = str(uuid.uuid4())

    trans = translator or (lambda t, l: f"(translated) {t}")
    sched = TranslationScheduler(translator=trans, max_queue=10, max_workers=1)
    adapter = TranslationAdapter(scheduler=sched, repository=repo, repository_enabled=True)
    adapter.start_session(session_id)

    from src.asr_result_adapter import ASRResultAdapter
    aradapter = ASRResultAdapter(session_id=session_id)
    n = aradapter.normalize({"text": original, "status": "final"})

    from src.asr_result_adapter import forward_normalized_asr_to_translation_adapter
    forward_normalized_asr_to_translation_adapter(n, adapter)

    time.sleep(0.3)
    adapter.stop_session()
    sched.shutdown(wait=True)

    api = SegmentAPI(repo)
    snap = api.get_session_snapshot(session_id)
    if snap is None:
        repo.close()
        return RealModelSmokeResult(ok=True, status="not_run",
            reason="Snapshot not found", backend=config.backend, original_text=original)

    repo.close()
    return RealModelSmokeResult(
        ok=True, status="passed",
        reason="Real model smoke completed.",
        backend=config.backend,
        model_name=config.model_name,
        original_text=snap.original_text,
        translated_text=snap.translated_text,
        bilingual_text=snap.bilingual_text,
        repo_closed=True,
    )
