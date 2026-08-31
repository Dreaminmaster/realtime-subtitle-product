from pathlib import Path
from types import SimpleNamespace

import mac_translation
from translation_engine import OfflineTranslator


def test_language_name_mapping():
    assert mac_translation.normalize_language_code("Chinese", default="en") == "zh-Hans"
    assert mac_translation.normalize_language_code("ja-JP", default="en") == "ja-JP"
    assert mac_translation.normalize_language_code(None, default="auto") == "auto"


def test_fixed_language_translation_uses_persistent_service(monkeypatch, tmp_path):
    helper = tmp_path / "mac-translation"
    helper.write_text("binary")
    monkeypatch.setattr(mac_translation, "availability", lambda: (True, "ready"))
    monkeypatch.setattr(mac_translation, "helper_path", lambda: helper)
    calls = []

    def fake_translate(path, source, target, text, timeout, *, wait_if_busy):
        calls.append((path, source, target, text, timeout, wait_if_busy))
        return "早上好"

    monkeypatch.setattr(mac_translation._SERVICE, "translate", fake_translate)
    result = mac_translation.translate(
        "Good morning.", source_language="English", target_language="Chinese"
    )
    assert result == "早上好"
    assert calls[0][1:4] == ("en", "zh-Hans", "Good morning.")
    assert calls[0][-1] is True


def test_auto_language_translation_keeps_one_shot_helper(monkeypatch, tmp_path):
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
        "Good morning.", source_language="auto", target_language="Chinese"
    )
    assert result == "早上好"
    assert calls[0][0][1:] == ["auto", "zh-Hans", "Good morning."]


def test_same_language_translation_is_a_noop_without_helper(monkeypatch):
    monkeypatch.setattr(mac_translation, "availability", lambda: (True, "ready"))
    monkeypatch.setattr(
        mac_translation.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("helper should not run")),
    )
    assert mac_translation.translate(
        "Already English.", source_language="English", target_language="English"
    ) == "Already English."


def test_offline_translator_returns_user_safe_error(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("language assets are not installed")

    monkeypatch.setattr(mac_translation, "translate", fail)
    result = OfflineTranslator(target_lang="Chinese").translate("hello")
    assert result == "[Translation Failed: language assets are not installed]"


def test_offline_draft_never_waits_behind_final_translation(monkeypatch):
    calls = []

    def fake_translate(*args, **kwargs):
        calls.append(kwargs)
        return "草稿"

    monkeypatch.setattr(mac_translation, "translate", fake_translate)
    result = OfflineTranslator(target_lang="Chinese", source_lang="en").translate_draft(
        "draft words"
    )
    assert result == "草稿"
    assert calls[0]["wait_if_busy"] is False
