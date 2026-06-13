#!/usr/bin/env python3
"""Test DownloadTask — strict cancel, deadlock detection, identity check."""
import sys, os, unittest, threading, time, inspect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import model_download_task
from model_download_task import DownloadTask, SUCCEEDED, FAILED, CANCELLED

print(f"Module: {model_download_task.__file__}")
print("=== start() source ===")
print(inspect.getsource(DownloadTask.start))


class TestDownloadTask(unittest.TestCase):
    def test_no_deadlock(self):
        called = []
        def fn(ctx):
            called.append(1)
            return True
        r = []
        t = DownloadTask("m", "w", fn, max_attempts=3)
        t.on_done(lambda ok, e, a: r.append((ok, e, a)))
        thr = threading.Thread(target=t.start, daemon=True)
        thr.start()
        thr.join(timeout=2.0)
        self.assertFalse(thr.is_alive(), "DEADLOCK")
        self.assertEqual(t.state, SUCCEEDED)
        self.assertEqual(called, [1])
        self.assertEqual(len(r), 1)

    def test_strict_cancel(self):
        def slow(ctx):
            for i in range(100):
                time.sleep(0.05)
                if ctx._cancel.is_set():
                    return False
            return True
        r = []
        t = DownloadTask("m", "w", slow, max_attempts=1)
        t.on_done(lambda ok, e, a: r.append((ok, e, a)))
        thr = threading.Thread(target=t.start, daemon=True)
        thr.start()
        time.sleep(0.3)
        t.cancel()
        thr.join(timeout=5.0)
        self.assertEqual(t.state, CANCELLED, f"state={t.state}")
        self.assertEqual(len(r), 1)

    def test_cancel_no_retry(self):
        def slow(ctx):
            for i in range(100):
                time.sleep(0.05)
                if ctx._cancel.is_set():
                    return False
            return True
        r = []
        t = DownloadTask("m", "w", slow, max_attempts=5, retry_delays=(0.5,))
        t.on_done(lambda ok, e, a: r.append((ok, e, a)))
        thr = threading.Thread(target=t.start, daemon=True)
        thr.start()
        time.sleep(0.3)
        t.cancel()
        thr.join(timeout=5.0)
        self.assertEqual(t.state, CANCELLED)

    def test_done_once(self):
        called = []
        t = DownloadTask("m", "w", lambda c: True)
        t.on_done(lambda ok, e, a: called.append(1))
        thr = threading.Thread(target=t.start, daemon=True)
        thr.start()
        thr.join(timeout=2.0)
        self.assertEqual(len(called), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
