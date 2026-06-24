"""Test NoneType not subscriptable fix in OnlineAPITranslator."""
import pytest, sys
from unittest.mock import MagicMock

@pytest.fixture
def translator():
    sys.path.insert(0, '.')
    from translation_engine import OnlineAPITranslator
    t = OnlineAPITranslator(target_lang="Chinese", base_url="http://test.local/v1",
        api_key="fake-key", model="test-model", timeout=5.0)
    return t

class MockChoice:
    def __init__(self, content):
        self.message = MagicMock()
        self.message.content = content

class MockResponse:
    def __init__(self, choices=None):
        self.choices = choices or []

class TestNoneResponse:
    def test_empty_choices(self, translator):
        resp = MockResponse(choices=[])
        translator._ensure_client = MagicMock()
        translator._ensure_client.return_value.chat.completions.create.return_value = resp
        result = translator.translate("hello")
        assert "empty response" in result.lower() or "translation failed" in result.lower()
        assert "NoneType" not in result

    def test_none_content(self, translator):
        resp = MockResponse(choices=[MockChoice(None)])
        translator._ensure_client = MagicMock()
        translator._ensure_client.return_value.chat.completions.create.return_value = resp
        result = translator.translate("hello")
        assert "empty content" in result.lower() or "translation failed" in result.lower()

    def test_no_choices_attr(self, translator):
        class BadResp:
            pass
        translator._ensure_client = MagicMock()
        translator._ensure_client.return_value.chat.completions.create.return_value = BadResp()
        result = translator.translate("hello")
        assert "translation failed" in result.lower()

    def test_none_response(self, translator):
        translator._ensure_client = MagicMock()
        translator._ensure_client.return_value.chat.completions.create.return_value = None
        result = translator.translate("hello")
        assert "translation failed" in result.lower()

class TestNormalSuccess:
    def test_valid(self, translator):
        resp = MockResponse(choices=[MockChoice("Chinese translation")])
        translator._ensure_client = MagicMock()
        translator._ensure_client.return_value.chat.completions.create.return_value = resp
        result = translator.translate("hello")
        assert result == "Chinese translation"

    def test_think_tags_stripped(self, translator):
        resp = MockResponse(choices=[MockChoice("<think>ignore</think>Chinese text")])
        translator._ensure_client = MagicMock()
        translator._ensure_client.return_value.chat.completions.create.return_value = resp
        result = translator.translate("hello")
        assert result == "Chinese text"

class TestEmptyInput:
    def test_empty_string(self, translator):
        result = translator.translate("")
        assert result == ""

    def test_whitespace(self, translator):
        result = translator.translate("   ")
        assert result == ""

class TestNoAPIKeyLeak:
    def test_no_key_in_error(self, translator):
        translator._ensure_client = MagicMock(side_effect=ConnectionError("connect fail"))
        result = translator.translate("hello")
        assert "fake-key" not in result
        assert "test.local" not in result
        assert "Translation Failed" in result
