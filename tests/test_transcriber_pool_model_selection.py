from types import SimpleNamespace

from transcriber_pool import _model_name_for_backend


def settings(backend):
    return SimpleNamespace(
        asr_backend=backend,
        whisper_model="small",
        funasr_model="sensevoice",
    )


def test_whisper_and_mlx_use_the_whisper_model_selection():
    assert _model_name_for_backend(settings("whisper")) == "small"
    assert _model_name_for_backend(settings("mlx")) == "small"


def test_funasr_uses_the_funasr_model_selection():
    assert _model_name_for_backend(settings("funasr")) == "sensevoice"
