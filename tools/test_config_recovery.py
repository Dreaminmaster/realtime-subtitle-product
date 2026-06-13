#!/usr/bin/env python3
"""Test config corruption recovery."""
import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
tmp = tempfile.mkdtemp()
os.chdir(tmp)

# Test 1: corrupt file
corrupt_path = os.path.join(tmp, "config.ini")
with open(corrupt_path, 'w') as f:
    f.write("this is not valid ini = [[[[broken\n")

try:
    print("=== Test 1: corrupt config.ini ===")
    from config import Config
    c = Config(config_path=corrupt_path)
    assert c.sample_rate == 16000, f"default sample_rate failed: {c.sample_rate}"
    assert c.silence_threshold == 0.01, f"default silence_threshold failed"
    assert c.translation_mode == "off", f"default translation_mode failed"
    assert c.asr_backend == "whisper", f"default asr_backend failed"
    print("  OK: all defaults loaded after corrupt parse")
except Exception as e:
    print(f"  FAIL: {e}")
    sys.exit(1)

# Test 2: missing file
print("=== Test 2: missing config.ini ===")
missing_path = os.path.join(tmp, "nonexistent.ini")
try:
    c2 = Config(config_path=missing_path)
    assert c2.sample_rate == 16000
    assert c2.translation_mode == "off"
    print("  OK: defaults loaded when file missing")
except Exception as e:
    print(f"  FAIL: {e}")
    sys.exit(1)

# Cleanup
import shutil
shutil.rmtree(tmp)
print("=== ALL TESTS PASSED ===")
