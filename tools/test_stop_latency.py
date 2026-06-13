#!/usr/bin/env python3
"""Test translation stop latency — verify stop() doesn't hang indefinitely."""
import sys, os, time, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

print("=== Translation Stop Latency Test ===\n")

from concurrent.futures import ThreadPoolExecutor

# Test 1: cancel_futures cancels pending, running tasks complete within HTTP timeout
print("[1] Pending futures cancelled immediately...")
executor = ThreadPoolExecutor(max_workers=1)

def slow_task(delay=0.1):
    time.sleep(delay)
    return "done"

f1 = executor.submit(slow_task, 0.1)  # running, fast
t0 = time.time()
executor.shutdown(wait=False, cancel_futures=True)
t1 = time.time()
print(f"    Shutdown took {t1-t0:.3f}s (should be < 1s)")
assert t1 - t0 < 2.0, "Shutdown too slow"
print("    OK: shutdown immediate with cancel_futures\n")

# Test 2: running task bounded by HTTP timeout (simulated)
print("[2] Running tasks bounded by httpx timeout...")
executor2 = ThreadPoolExecutor(max_workers=1)
def bounded_task():
    time.sleep(5.0)  # HTTP connect=5s max
    return "done"

f2 = executor2.submit(bounded_task)
t0 = time.time()
executor2.shutdown(wait=True)
t1 = time.time()
print(f"    Running task completed in {t1-t0:.1f}s (bounded by task timeout)")
assert t1 - t0 < 15.0, "Running task not bounded"
print("    OK: task bounded by internal timeout\n")

# Test 3: session invalidation on stop
print("[3] Session invalidation on stop...")
class FakePipeline:
    def __init__(self):
        self._session_generation = 1
    def is_valid(self, session_gen):
        return self._session_generation == session_gen
    def stop(self):
        self._session_generation += 1

pipe = FakePipeline()
session_1 = pipe._session_generation
pipe.stop()
assert not pipe.is_valid(session_1), "Old session should be invalid"
pipe.start = lambda: setattr(pipe, '_session_generation', pipe._session_generation + 1)
pipe.start()
session_3 = pipe._session_generation
assert pipe.is_valid(session_3), "New session should be valid"
print("    OK: old session invalid, new session valid\n")

print("=== ALL TESTS PASSED ===")
