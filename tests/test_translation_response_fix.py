"""Test NoneType not subscriptable fix in OnlineAPITranslator."""
import pytest
from unittest.mock import MagicMock
from unittest.mock import patch
from translation_engine import OnlineAPITranslator

@pytest.fixture
def translator():
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

    def test_question_is_treated_as_quoted_speech(self, translator):
        create = translator._ensure_client = MagicMock()
        client = create.return_value
        client.chat.completions.create.return_value = MockResponse(
            choices=[MockChoice("你现在在做什么？")]
        )
        result = translator.translate("What are you doing now?")
        assert result == "你现在在做什么？"
        messages = client.chat.completions.create.call_args.kwargs["messages"]
        assert "not a chat assistant" in messages[0]["content"]
        assert messages[1]["content"] == "<source>What are you doing now?</source>"

    def test_assistant_reply_is_retried_as_translation(self, translator):
        translator._ensure_client = MagicMock()
        create = translator._ensure_client.return_value.chat.completions.create
        create.side_effect = [
            MockResponse(choices=[MockChoice("我正在处理您的请求，准备为您提供帮助。")]),
            MockResponse(choices=[MockChoice("你现在在做什么？")]),
        ]
        assert translator.translate("What are you doing now?") == "你现在在做什么？"
        assert create.call_count == 2

    def test_repeated_assistant_reply_is_never_shown_as_a_subtitle(self, translator):
        translator._ensure_client = MagicMock()
        create = translator._ensure_client.return_value.chat.completions.create
        create.return_value = MockResponse(
            choices=[MockChoice("我正在处理您的请求，准备为您提供帮助。")]
        )
        result = translator.translate("What are you doing now?")
        assert result == "[Translation Failed: model answered instead of translating]"
        assert create.call_count == 2

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


class TestTLSConfiguration:
    def test_remote_endpoint_keeps_certificate_verification(self):
        translator = OnlineAPITranslator(
            base_url="https://api.example.com/v1", api_key="test-key"
        )
        with patch("httpx.Client") as http_client, patch("openai.OpenAI"):
            translator._ensure_client()
        assert "verify" not in http_client.call_args.kwargs
        assert "trust_env" not in http_client.call_args.kwargs

    def test_local_endpoint_bypasses_proxy_only_for_localhost(self):
        translator = OnlineAPITranslator(
            base_url="http://127.0.0.1:1234/v1", api_key="not-needed"
        )
        with patch("httpx.Client") as http_client, patch("openai.OpenAI"):
            translator._ensure_client()
        assert http_client.call_args.kwargs["verify"] is False
        assert http_client.call_args.kwargs["trust_env"] is False

    def test_localhost_in_remote_path_is_not_treated_as_local(self):
        assert OnlineAPITranslator._is_local_endpoint(
            "https://api.example.com/localhost/v1"
        ) is False
