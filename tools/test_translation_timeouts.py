#!/usr/bin/env python3
"""Translation timeout tests — real exception type verification."""
import sys, os, unittest, time
from unittest.mock import patch, MagicMock
import httpx
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestTranslationTimeouts(unittest.TestCase):
    def setUp(self):
        from translation_engine import TranslationEngine
        self.engine = TranslationEngine()
        self.engine.set_mode("online", base_url="http://fake/v1", api_key="test-key")

    def test_connect_timeout(self):
        self.engine._translator._client = None
        t0 = time.time()
        with patch.object(self.engine._translator, '_ensure_client') as mock_ensure:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = httpx.ConnectTimeout("connect timed out")
            mock_ensure.return_value = mock_client
            result = self.engine.translate("hello")
        elapsed = time.time() - t0
        self.assertIn("Translation Failed", result)
        self.assertLess(elapsed, 5.0, f"connect timeout took {elapsed:.1f}s")

    def test_read_timeout(self):
        self.engine._translator._client = None
        t0 = time.time()
        with patch.object(self.engine._translator, '_ensure_client') as mock_ensure:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = httpx.ReadTimeout("read timed out")
            mock_ensure.return_value = mock_client
            result = self.engine.translate("hello")
        elapsed = time.time() - t0
        self.assertIn("Translation Failed", result)
        self.assertLess(elapsed, 5.0)

    def test_http_500(self):
        self.engine._translator._client = None
        with patch.object(self.engine._translator, '_ensure_client') as mock_ensure:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("HTTP 500 Internal Server Error")
            mock_ensure.return_value = mock_client
            result = self.engine.translate("hello")
        self.assertIn("Translation Failed", result)

    def test_unauthorized_401(self):
        self.engine._translator._client = None
        with patch.object(self.engine._translator, '_ensure_client') as mock_ensure:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("401 Unauthorized")
            mock_ensure.return_value = mock_client
            result = self.engine.translate("hello")
        self.assertIn("invalid API key", result)

    def test_normal_success(self):
        self.engine._translator._client = None
        with patch.object(self.engine._translator, '_ensure_client') as mock_ensure:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content="Good"))]
            )
            mock_ensure.return_value = mock_client
            result = self.engine.translate("hello")
        self.assertEqual(result, "Good")

    def test_off_mode(self):
        self.engine.set_mode("off")
        result = self.engine.translate("hello")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=False)
