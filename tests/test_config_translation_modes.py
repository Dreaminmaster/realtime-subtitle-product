from config import Config
from translation_engine import TranslationEngine


def _config(monkeypatch, tmp_path, text: str | None = None) -> Config:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setattr(Config, "_find_blackhole_device", lambda self: None)
    path = tmp_path / "config.ini"
    if text is not None:
        path.write_text(text, encoding="utf-8")
    return Config(path)


def test_clean_install_defaults_match_bundled_model(monkeypatch, tmp_path):
    cfg = _config(monkeypatch, tmp_path)
    assert cfg.whisper_model == "tiny"
    assert cfg.source_language is None
    assert cfg.translation_mode == "off"


def test_legacy_config_with_key_keeps_online_mode(monkeypatch, tmp_path):
    cfg = _config(
        monkeypatch,
        tmp_path,
        "[api]\napi_key = test-key\n[translation]\nmodel = test-model\n",
    )
    assert cfg.translation_mode == "online"


def test_local_mode_does_not_require_api_key(monkeypatch, tmp_path):
    cfg = _config(
        monkeypatch,
        tmp_path,
        "[translation]\nmode = local\nmodel = local-model\n",
    )
    assert cfg.translation_mode == "local"


def test_scheduler_can_call_translation_engine_with_target_language():
    engine = TranslationEngine()
    engine.set_mode("off")
    assert engine.translate("hello", "Chinese") == ""


def test_local_mode_uses_default_endpoint_when_field_is_blank():
    engine = TranslationEngine()
    translator = engine.set_mode("local", base_url="", model="local-model")
    assert translator.base_url == "http://localhost:1234/v1"
