#!/usr/bin/env python3
"""Lifecycle simulation test for v2.3.0-rc1. Verifies state machine, stop idempotency, and no AttributeErrors."""
import sys, os, threading, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

print("=== v2.3.0-rc1 Lifecycle Test ===")

# Test 1: Pipeline init
print("\n[1] Pipeline __init__ completeness...")
from main import create_pipeline
pipeline, signals = create_pipeline()
attrs = ['_stopping', '_failed', '_cleanup_in_progress', '_session_generation',
         '_lifecycle_lock', '_utt_lifecycle', '_finalizing_uids', '_finalized_uids',
         '_latest_partial_seq', 'last_final_text']
for attr in attrs:
    assert hasattr(pipeline, attr), f"MISSING: {attr}"
print(f"  OK: all {len(attrs)} fields present")

# Test 2: Lifecycle transitions
print("\n[2] Lifecycle transitions...")

# Start
pipeline.start()
time.sleep(0.5)  # let pipeline loop spin up
assert pipeline._stopping == False, "new session should not be stopping"
print("  OK: _stopping=False on start")

# Stop
ok = pipeline.stop()
assert ok == True, "stop should succeed"
print(f"  OK: stop() returned {ok}")

# Test 3: Stop idempotency
print("\n[3] Stop idempotency...")
ok2 = pipeline.stop()
assert ok2 == True, "second stop should also return True"
print("  OK: duplicate stop handled")

# Test 4: Relaunch reset
print("\n[4] Relaunch state reset...")
pipeline.start()
time.sleep(0.3)
assert pipeline._stopping == False, "relaunch should reset _stopping"
ok3 = pipeline.stop()
assert ok3 == True
print("  OK: relaunch stop works")

# Test 5: Session isolation
print("\n[5] Session isolation...")
gen1 = pipeline._session_generation
pipeline.start()
time.sleep(0.3)
ok4 = pipeline.stop()
gen2 = pipeline._session_generation
assert gen2 > gen1, f"session gen should increment: {gen1} -> {gen2}"
print(f"  OK: generation {gen1} -> {gen2}")

# Done
print("\n=== ALL TESTS PASSED ===")
