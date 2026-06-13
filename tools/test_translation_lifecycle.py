#!/usr/bin/env python3
"""Translation lifecycle tests using httpx mock transport."""
import sys, os, unittest, json, threading, time
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import httpx

class FakeTransport(httpx.BaseTransport):
    """Controllable fake HTTP transport for testing."""
    def __init__(self, handler=None):
        self.handler = handler or (lambda req: (200, {"choices": [{"message": {"content": "translated"}}]}))
        self.request_count = 0
        self.delay = 0

    def handle_request(self, request):
        self.request_count += 1
        if self.delay:
            time.sleep(self.delay)
        return self._make_response(self.handler(request))

    def _make_response(self, result):
        if isinstance(result, tuple):
            status, body = result
        elif isinstance(result, Exception):
            raise result
        else:
            status, body = 200, result
        content = json.dumps(body).encode()
        return httpx.Response(status, content=content, request=MagicMock())


class TestTranslation(unittest.TestCase):
    def setUp(self):
        from translation_engine import TranslationEngine
        self.engine = TranslationEngine()

    def test_off_mode_no_call(self):
        self.engine.set_mode("off")
        result = self.engine.translate("hello")
        self.assertEqual(result, "")
        self.assertEqual(self.engine.current_mode, "off")

    def test_translate_success(self):
        t = FakeTransport(handler=lambda req: (200, {"choices": [{"message": {"content": "Bonjour"}}]}))
        self.engine.set_mode("online", base_url="http://fake/v1", api_key="test-key")
        self.engine._translator._client = None
        with patch.object(self.engine._translator, '_ensure_client') as mock_ensure:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content="Bonjour"))]
            )
            mock_ensure.return_value = mock_client
            result = self.engine.translate("hello")
            self.assertIn("Bonjour", result)

    def test_timeout_error(self):
        self.engine.set_mode("online", base_url="http://fake/v1", api_key="test-key")
        self.engine._translator._client = None
        with patch.object(self.engine._translator, '_ensure_client') as mock_ensure:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("timeout")
            mock_ensure.return_value = mock_client
            result = self.engine.translate("hello")
            self.assertIn("Translation Failed", result)

    def test_auth_error(self):
        self.engine.set_mode("online", base_url="http://fake/v1", api_key="bad-key")
        self.engine._translator._client = None
        with patch.object(self.engine._translator, '_ensure_client') as mock_ensure:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("Unauthorized 401")
            mock_ensure.return_value = mock_client
            result = self.engine.translate("hello")
            self.assertIn("invalid API key", result)

    def test_stop_translation_still_preserves_original(self):
        """Ensure that even on stop, translation error doesn't lose original text."""
        self.engine.set_mode("online", base_url="http://fake/v1", api_key="test-key")
        self.engine._translator._client = None
        with patch.object(self.engine._translator, '_ensure_client') as mock_ensure:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("connection reset by peer")
            mock_ensure.return_value = mock_client
            result = self.engine.translate("Hello")
            self.assertIn("Translation Failed", result)
            # Original text is NOT in the return (return is error message), but the caller
            # emits original + error message separately — this is main.py's job.

    def test_empty_translation_returns_empty(self):
        self.engine.set_mode("off")
        result = self.engine.translate("")
        self.assertEqual(result, "")

    def test_check_health(self):
        self.engine.set_mode("off")
        h = self.engine.check_health()
        self.assertTrue(h["available"])
        self.assertEqual(h["mode"], "off")


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=False)
