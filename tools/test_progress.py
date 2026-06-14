import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from progress_events import ProgressEvent

# 1: known bytes
e1 = ProgressEvent("m1", "downloading", "36% done", current_bytes=105, total_bytes=288,
                   percent=36.0, speed_bps=2_400_000, eta_seconds=60, attempt=1,
                   max_attempts=3, can_cancel=True)
assert e1.percent == 36.0
assert e1.can_cancel == True
assert e1.can_retry == False
print("PASS 1: known bytes")

# 2: indeterminate
e2 = ProgressEvent("m1", "connecting", "Connecting to server...", attempt=1,
                   max_attempts=3, can_cancel=True)
assert e2.percent is None
assert e2.total_bytes is None
print("PASS 2: indeterminate")

# 3: retry state
e3 = ProgressEvent("m1", "failed", "Connection timed out", attempt=3,
                   max_attempts=3, can_retry=True, can_cancel=False)
assert e3.can_retry
assert not e3.can_cancel
print("PASS 3: retry state")

# 4: cancelled
e4 = ProgressEvent("m1", "cancelled", "Download cancelled", can_cancel=False,
                   can_retry=False)
assert not e4.can_cancel and not e4.can_retry
print("PASS 4: cancelled")

# 5: completed
e5 = ProgressEvent("m1", "completed", "Download complete", percent=100.0,
                   can_cancel=False, can_retry=False)
assert e5.percent == 100.0
print("PASS 5: completed")

# 6: stages (first-launch)
for i in range(3):
    e = ProgressEvent("setup", f"step_{i}", f"Step {i+1} of 3",
                      stage_index=i, total_stages=3, attempt=1, max_attempts=1,
                      can_cancel=True)
    assert e.stage_index == i and e.total_stages == 3
print("PASS 6: stages")

# 7: retry after failure preserves stage_index
e7 = ProgressEvent("setup", "failed", "Step 1 failed", stage_index=0,
                   total_stages=3, can_retry=True, can_cancel=False)
assert e7.stage_index == 0 and e7.can_retry
print("PASS 7: retry preserves stage")

# 8: default values
e8 = ProgressEvent("test", "idle", "")
assert e8.attempt == 1 and e8.max_attempts == 3
assert e8.percent is None and e8.total_bytes is None
print("PASS 8: defaults")

print("ALL 8 PASSED")
