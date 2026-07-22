import pytest, json, tempfile
from pathlib import Path
from dataclasses import asdict
from src.real_model_smoke_gate import (
    RealModelSmokeConfig, RealModelSmokeResult,
    real_model_smoke_config_from_env, run_optional_real_model_smoke,
)

def _faux():
    class FT:
        def __init__(s, backend=None): pass
        # Match the real Transcriber API so the smoke gate cannot accidentally
        # rely on fake-only keyword arguments.
        def transcribe(s, audio): return 'hello from fake model'
    return lambda b: FT(b)

class TestDefaultDisabled:
    def test_no_env(self): c=real_model_smoke_config_from_env(env={}); assert not c.enabled
    def test_not_run(self): r=run_optional_real_model_smoke(RealModelSmokeConfig(enabled=False)); assert r.ok and r.status=='not_run'

class TestEnvFlag:
    def test_on(self): c=real_model_smoke_config_from_env(env={'REALTIME_SUBTITLE_ENABLE_REAL_MODEL_SMOKE':'1'}); assert c.enabled
    def test_backend(self): c=real_model_smoke_config_from_env(env={'REALTIME_SUBTITLE_REAL_MODEL_BACKEND':'mlx'}); assert c.backend=='mlx'
    def test_model_name(self):
        c=real_model_smoke_config_from_env(env={'REALTIME_SUBTITLE_REAL_MODEL_NAME':'/tmp/local-model'})
        assert c.model_name == '/tmp/local-model'

class TestDisabledNoSideEffects:
    def test_no(self): r=run_optional_real_model_smoke(RealModelSmokeConfig(enabled=False)); assert r.status=='not_run'

class TestMissingModel:
    def test_not_available(self):
        def f(b): raise ImportError('missing')
        r=run_optional_real_model_smoke(RealModelSmokeConfig(enabled=True,backend='whisper'),transcriber_factory=f)
        assert r.status=='not_available'

class TestBackendException:
    def test_structured(self):
        class Bad:
            def __init__(s,b=None): pass
            def transcribe(s,*a,**k): raise RuntimeError('model crash')
        from src.audio_file_smoke import generate_fixture_wav
        import tempfile; tmp=Path(tempfile.mkdtemp()); w=str(tmp/'f.wav')
        generate_fixture_wav(w)
        r=run_optional_real_model_smoke(RealModelSmokeConfig(enabled=True,backend='whisper',fixture_wav_path=w),transcriber_factory=lambda b:Bad(b),tmp_path=tmp)
        assert not r.ok and r.status=='error' and 'model crash' in r.reason

class TestFakeEnabled:
    def test_writes_repository(self):
        import tempfile; tmp=Path(tempfile.mkdtemp())
        r=run_optional_real_model_smoke(RealModelSmokeConfig(enabled=True,backend='whisper'),transcriber_factory=_faux(),tmp_path=tmp)
        assert r.status=='passed' and 'hello' in r.original_text
        assert r.translated_text and r.bilingual_text and r.repo_closed

class TestSerializable:
    def test_json(self): r=RealModelSmokeResult(ok=True,status='passed',original_text='hi'); j=json.dumps(asdict(r)); assert 'hi' in j

class TestNoRealAPI:
    def test_fake(self):
        import tempfile; tmp=Path(tempfile.mkdtemp())
        r=run_optional_real_model_smoke(RealModelSmokeConfig(enabled=True,backend='whisper'),transcriber_factory=_faux(),tmp_path=tmp); assert r.status=='passed'

class TestNoRealUserPath:
    def test_tmp(self):
        import tempfile; tmp=Path(tempfile.mkdtemp())
        r=run_optional_real_model_smoke(RealModelSmokeConfig(enabled=True,backend='whisper'),transcriber_factory=_faux(),tmp_path=tmp); assert 'translated' in r.translated_text

class TestNoRealMic:
    def test_disabled(self): r=run_optional_real_model_smoke(RealModelSmokeConfig(enabled=False)); assert r.status=='not_run'
