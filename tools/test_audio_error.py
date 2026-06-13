#!/usr/bin/env python3
"""Test AudioCaptureError — validate real class from source + import when possible."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Try importing directly (won't work in iSH, but works on Mac with sounddevice installed)
AudioCaptureError = None
try:
    from audio_capture import AudioCaptureError
    print("Imported AudioCaptureError from audio_capture.py")
except ImportError:
    # Fallback: parse the class from source and validate it matches spec
    src = open('audio_capture.py').read()
    assert 'class AudioCaptureError(RuntimeError)' in src, "Missing class definition"
    assert "self.stage = stage" in src, "Missing stage attribute"
    assert "self.requested_device = requested_device" in src, "Missing requested_device"
    assert "self.fallback_device = fallback_device" in src, "Missing fallback_device"
    assert "self.fallback_attempted = fallback_attempted" in src, "Missing fallback_attempted"
    print("AudioCaptureError validated from source (no sounddevice in this env)")

print("=== PASSED ===")
