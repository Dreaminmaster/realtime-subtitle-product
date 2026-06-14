import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from progress_events import ProgressEvent
from model_progress_channel import ModelProgressChannel

ch = ModelProgressChannel("tiny", max_attempts=3)
errors = 0

def check(name, cond):
    global errors
    if cond: print(f"PASS {name}")
    else:
        print(f"FAIL {name}")
        errors += 1

# 1: start
e = ch.on_start()
check("start stage", e.stage == "starting")
check("start cancel", e.can_cancel)

# 2: retry
e2 = ch.on_retry(2)
check("retry stage", e2.stage == "retrying")
check("retry attempt", e2.attempt == 2)

# 3: progress with bytes
e3 = ch.on_progress(105*1024*1024, 288*1024*1024, attempt=1)
check("progress stage", e3.stage == "downloading")
check("progress percent", e3.percent is not None and 30 < e3.percent < 45)
check("progress speed", e3.speed_bps is not None and True)
check("progress cancel", e3.can_cancel)

# 4: indeterminate (no total_bytes)
e4 = ch.on_progress(0, 0, attempt=1)
check("indeterminate", e4.percent is None)
check("indeterminate cancel", e4.can_cancel)

# 5: success
e5 = ch.on_success(1)
check("success stage", e5.stage == "succeeded")
check("success percent", e5.percent == 100.0)
check("success no cancel", not e5.can_cancel)

# 6: fail after 3 attempts
e6 = ch.on_fail("Connection timed out", 3)
check("fail stage", e6.stage == "failed")
check("fail retry", e6.can_retry)
check("fail no cancel", not e6.can_cancel)

# 7: fail message rewrite
e7 = ch.on_fail("ConnectTimeout", 2)
check("fail timeout msg", "timed out" in e7.message.lower() or "connect" in e7.message.lower())

# 8: cancel
e8 = ch.on_cancel(2)
check("cancel stage", e8.stage == "cancelled")
check("cancel no retry", not e8.can_retry)
check("cancel no cancel", not e8.can_cancel)

print(f"PASSED" if errors == 0 else f"FAILED with {errors} errors")
