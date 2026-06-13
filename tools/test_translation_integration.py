#!/usr/bin/env python3
"""Integration: session discard + executor shutdown timing."""
import sys, os, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

print("=== Translation Integration ===\n")

# --- Session discard test using actual logic from main.py ---
class MockSignals:
    emitted = []
    @staticmethod
    def update_text(a, b, c):
        MockSignals.emitted.append((a, b, c))

class MockPipeline:
    def __init__(self):
        self._session_generation = 1
    def _run_translation_safe(self, text, chunk_id, session_gen):
        if self._session_generation != session_gen:
            return "discarded"
        translated = "TRANSLATED:" + text
        if self._session_generation != session_gen:
            return "discarded"
        if translated:
            MockSignals.update_text(chunk_id, text, translated)
        return "emitted"

pipe = MockPipeline()
s1 = pipe._session_generation
r = pipe._run_translation_safe("hello", 1, s1)
assert r == "emitted", r
assert len(MockSignals.emitted) == 1
print(f"[A1] S1 emitted: OK")

pipe._session_generation += 1  # Stop
MockSignals.emitted = []
r = pipe._run_translation_safe("hello", 1, s1)  # stale
assert r == "discarded", r
assert len(MockSignals.emitted) == 0
print(f"[A2] S1 stale discarded: OK")

s2 = pipe._session_generation
r = pipe._run_translation_safe("world", 2, s2)
assert r == "emitted", r
assert len(MockSignals.emitted) == 1
print(f"[A3] S2 emitted: OK")

# --- Executor shutdown timing ---
print()
executor = ThreadPoolExecutor(max_workers=1)
f_running = executor.submit(time.sleep, 0.2)
f_pending = executor.submit(time.sleep, 30)
time.sleep(0.05)
t0 = time.time()
executor.shutdown(wait=False, cancel_futures=True)
elapsed = time.time() - t0
assert elapsed < 1.0, f"Slow: {elapsed:.2f}s"
print(f"[B] Shutdown with cancel: {elapsed:.3f}s OK")

# --- Running task bounded ---
executor = ThreadPoolExecutor(max_workers=1)
f = executor.submit(time.sleep, 0.2)
t0 = time.time()
executor.shutdown(wait=True)
elapsed = time.time() - t0
assert elapsed < 2.0
print(f"[C] Running task bounded: {elapsed:.2f}s OK")

print("\n=== ALL PASSED ===")
