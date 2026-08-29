from pathlib import Path
from types import SimpleNamespace

import mac_translation
from translation_engine import OfflineTranslator


def test_language_name_mapping():
    assert mac_translation.normalize_language_code("Chinese", default="en") == "zh-Hans"
    assert mac_translation.normalize_language_code("ja-JP", default="en") == "ja-JP"
    assert mac_translation.normalize_language_code(None, default="auto") == "auto"


def test_translate_invokes_native_helper(monkeypatch, tmp_path):
    helper = tmp_path / "mac-translation"
    helper.write_text("binary")
    monkeypatch.setattr(mac_translation, "availability", lambda: (True, "ready"))
    monkeypatch.setattr(mac_translation, "helper_path", lambda: helper)
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="早上好\n", stderr="")

    monkeypatch.setattr(mac_translation.subprocess, "run", fake_run)
    result = mac_translation.translate(
        "Good morning.", source_language="English", target_language="Chinese"
    )
    assert result == "早上好"
    assert calls[0][0][1:] == ["en", "zh-Hans", "Good morning."]


def test_offline_translator_returns_user_safe_error(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("language assets are not installed")

    monkeypatch.setattr(mac_translation, "translate", fail)
    result = OfflineTranslator(target_lang="Chinese").translate("hello")
    assert result == "[Translation Failed: language assets are not installed]"
