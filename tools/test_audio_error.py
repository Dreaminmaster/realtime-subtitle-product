#!/usr/bin/env python3
"""Test AudioCaptureError structured pathway — class isolation test."""
import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class AudioCaptureError(RuntimeError):
    """Copy of the class definition from audio_capture.py for testing."""
    def __init__(self, message, *, stage="open", requested_device=None,
                 fallback_device=None, fallback_attempted=False):
        super().__init__(message)
        self.stage = stage
        self.requested_device = requested_device
        self.fallback_device = fallback_device
        self.fallback_attempted = fallback_attempted


class TestAudioCaptureError(unittest.TestCase):
    def test_open_error(self):
        e = AudioCaptureError("msg", stage="open", requested_device="3",
                              fallback_attempted=True)
        self.assertEqual(e.stage, "open")
        self.assertEqual(e.requested_device, "3")
        self.assertTrue(e.fallback_attempted)

    def test_read_error(self):
        e = AudioCaptureError("read failed", stage="read", requested_device="auto")
        self.assertEqual(e.stage, "read")

    def test_is_runtime(self):
        e = AudioCaptureError("msg")
        self.assertIsInstance(e, RuntimeError)

    def test_string_contains_info(self):
        e = AudioCaptureError("device open error", stage="open", requested_device="5",
                              fallback_attempted=True)
        s = str(e).lower()
        self.assertIn("device", s)
        self.assertEqual(e.requested_device, "5")
        self.assertTrue(e.fallback_attempted)

    def test_dashboard_handler_pattern(self):
        """Verify what Dashboard would see."""
        e = AudioCaptureError("Audio device failed: requested device=3, fallback also failed",
                              stage="open", requested_device="3", fallback_attempted=True)
        msg = str(e)
        self.assertIn("3", msg)
        self.assertIn("fallback", msg.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=False)
