import threading, time, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from model_download_task import DownloadTask, CANCELLED, FAILED, SUCCEEDED

errors = 0

def ok(ctx): return True
def fail(ctx): return False
def exc(ctx): raise Exception("test exc")

# 1: success
t = DownloadTask("m", "w", ok, max_attempts=1)
results = []
t.on_done(lambda ts,e,a: results.append((ts,e,a)))
thr = threading.Thread(target=t.start, daemon=True)
thr.start()
thr.join(5)
assert t.state == SUCCEEDED and len(results) == 1 and results[0][0] == SUCCEEDED
print("PASS 1: success")

# 2: fail all
t2 = DownloadTask("m", "w", fail, max_attempts=2, retry_delays=(0.05,0.05))
r2 = []
t2.on_done(lambda ok,e,a: r2.append((ok,e,a)))
thr2 = threading.Thread(target=t2.start, daemon=True)
thr2.start()
thr2.join(5)
assert t2.state == FAILED and len(r2) == 1 and r2[0][0] == FAILED
assert t2.attempt == 2
print("PASS 2: fail all")

# 3: exception
t3 = DownloadTask("m", "w", exc, max_attempts=2, retry_delays=(0.05,0.05))
r3 = []
t3.on_done(lambda ok,e,a: r3.append((ok,e,a)))
thr3 = threading.Thread(target=t3.start, daemon=True)
thr3.start()
thr3.join(5)
assert t3.state == FAILED and len(r3) == 1 and r3[0][0] == FAILED
print("PASS 3: exception")

# 4: cancel
def slow(ctx):
    ctx._cancel.wait(5.0)
    return False
t4 = DownloadTask("m", "w", slow, max_attempts=1)
r4 = []
t4.on_done(lambda ts,e,a: r4.append((ts,e,a)))
thr4 = threading.Thread(target=t4.start, daemon=True)
thr4.start()
time.sleep(0.2)
t4.cancel()
thr4.join(5)
assert t4.state == CANCELLED or t4.state == FAILED
assert len(r4) == 1
print("PASS 4: cancel, state={}".format(t4.state))

# 5: done_once
t5 = DownloadTask("m", "w", ok, max_attempts=1)
cnt = [0]
t5.on_done(lambda ts,e,a: cnt.__setitem__(0, cnt[0]+1))
thr5 = threading.Thread(target=t5.start, daemon=True)
thr5.start()
thr5.join(5)
assert cnt[0] == 1
print("PASS 5: done_once")

# 6: active_task_cleared (simulate Dashboard pattern)
active = {}
def done_cb(ts, err, att):
    active.pop("m", None)
t6 = DownloadTask("m", "w", ok, max_attempts=1)
active["m"] = t6
t6.on_done(done_cb)
thr6 = threading.Thread(target=t6.start, daemon=True)
thr6.start()
thr6.join(5)
assert "m" not in active
assert t6.state == SUCCEEDED
print("PASS 6: active cleared")

print("ALL 6 PASSED")
