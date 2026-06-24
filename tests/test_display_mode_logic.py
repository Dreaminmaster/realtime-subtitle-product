"""Test display mode (A/文/globe) logic without Qt."""
import pytest

MODE_BILINGUAL = "bilingual"
MODE_ORIGINAL = "original_only"
MODE_TRANSLATION = "translation_only"

MODES = [MODE_BILINGUAL, MODE_ORIGINAL, MODE_TRANSLATION]
LABELS = {MODE_BILINGUAL: "globe", MODE_ORIGINAL: "A", MODE_TRANSLATION: "文"}

def _toggle(current):
    try:
        idx = MODES.index(current)
        return MODES[(idx + 1) % len(MODES)]
    except ValueError:
        return MODE_BILINGUAL

def _state(mode):
    return {
        "show_original": mode in (MODE_BILINGUAL, MODE_ORIGINAL),
        "show_translation": mode in (MODE_BILINGUAL, MODE_TRANSLATION),
    }

def _render(source, translated, status, mode):
    s = _state(mode)
    lines = []
    if s["show_original"] and source:
        lines.append(source)
    if s["show_translation"]:
        if translated:
            lines.append(translated)
        elif status == "failed":
            lines.append(f"Translation failed: {status}")
        else:
            lines.append("Translating...")
    return "\n".join(lines)

class TestModeToggle:
    def test_rotation(self):
        assert _toggle(MODE_BILINGUAL) == MODE_ORIGINAL
        assert _toggle(MODE_ORIGINAL) == MODE_TRANSLATION
        assert _toggle(MODE_TRANSLATION) == MODE_BILINGUAL
    def test_invalid_fallback(self):
        assert _toggle("invalid") == MODE_BILINGUAL

class TestState:
    def test_bilingual_shows_both(self):
        assert _state(MODE_BILINGUAL) == {"show_original": True, "show_translation": True}
    def test_original_shows_source_only(self):
        assert _state(MODE_ORIGINAL) == {"show_original": True, "show_translation": False}
    def test_translation_shows_trans_only(self):
        assert _state(MODE_TRANSLATION) == {"show_original": False, "show_translation": True}

class TestRender:
    EN = "Hello, how are you?"
    ZH = "你好，你好吗？"

    def test_A_mode_shows_source_only(self):
        r = _render(self.EN, self.ZH, "done", MODE_ORIGINAL)
        assert self.EN in r and self.ZH not in r

    def test_wen_mode_shows_translation_only(self):
        r = _render(self.EN, self.ZH, "done", MODE_TRANSLATION)
        assert self.ZH in r and self.EN not in r

    def test_globe_mode_shows_both(self):
        r = _render(self.EN, self.ZH, "done", MODE_BILINGUAL)
        assert self.EN in r and self.ZH in r

    def test_translation_pending(self):
        r = _render(self.EN, "", "pending", MODE_BILINGUAL)
        assert self.EN in r
        assert "Translating..." in r

    def test_translation_failed_safe(self):
        r = _render(self.EN, "", "failed", MODE_TRANSLATION)
        assert "Translation failed:" in r
        assert self.EN not in r  # A mode off

    def test_translation_failed_bilingual(self):
        r = _render(self.EN, "", "failed", MODE_BILINGUAL)
        assert self.EN in r
        assert "Translation failed:" in r

    def test_translation_failed_no_key(self):
        r = _render(self.EN, "", "unauthorized", MODE_TRANSLATION)
        assert "api_key" not in r.lower()
        assert "key" not in r.lower()
