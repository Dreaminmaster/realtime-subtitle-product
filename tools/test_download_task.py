#!/usr/bin/env python3
"""Test DownloadTask — deadlock detection, timeout, cancel."""
import sys, os, unittest, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from model_download_task import DownloadTask, IDLE, SUCCEEDED, FAILED, CANCELLED


class TestDownloadTask(unittest.TestCase):
    def test_success_no_deadlock(self):
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
        self.assertFalse(thr.is_alive(), "DEADLOCK: thread still alive after 2s")
        self.assertEqual(t.state, SUCCEEDED)
        self.assertEqual(len(called), 1, "download_fn was never called")
        self.assertEqual(len(r), 1)

    def test_fail_then_success(self):
        def flaky(ctx):
            return ctx.attempt >= 2
        r = []
        t = DownloadTask("m", "w", flaky, max_attempts=3, retry_delays=(0.01, 0.01))
        t.on_done(lambda ok, e, a: r.append((ok, e, a)))
        thr = threading.Thread(target=t.start, daemon=True)
        thr.start()
        thr.join(timeout=2.0)
        self.assertFalse(thr.is_alive())
        self.assertEqual(t.state, SUCCEEDED, f"State: {t.state}")
        self.assertEqual(t.attempt, 2)

    def test_fail_all(self):
        def fail(ctx):
            raise RuntimeError("fail")
        r = []
        t = DownloadTask("m", "w", fail, max_attempts=2, retry_delays=(0.01,))
        t.on_done(lambda ok, e, a: r.append((ok, e, a)))
        thr = threading.Thread(target=t.start, daemon=True)
        thr.start()
        thr.join(timeout=2.0)
        self.assertFalse(thr.is_alive())
        self.assertEqual(t.state, FAILED)
        self.assertFalse(r[0][0])

    def test_cancel_async(self):
        # download_fn IS the slow part (simulates real HF download)
        def slow(ctx):
            for i in range(50):
                time.sleep(0.1)
                if ctx._cancel.is_set():
                    return False
            return True
        r = []
        t = DownloadTask("m", "w", slow, max_attempts=1, retry_delays=(0.1,))
        t.on_done(lambda ok, e, a: r.append((ok, e, a)))
        thr = threading.Thread(target=t.start, daemon=True)
        thr.start()
        time.sleep(0.5)  # let it enter slow download loop
        t.cancel()
        thr.join(timeout=8.0)
        self.assertIn(t.state, (CANCELLED, FAILED))
        self.assertEqual(len(r), 1)

    def test_done_called_once(self):
        called = []
        t = DownloadTask("m", "w", lambda c: True, max_attempts=3)
        t.on_done(lambda ok, e, a: called.append(1))
        thr = threading.Thread(target=t.start, daemon=True)
        thr.start()
        thr.join(timeout=2.0)
        self.assertEqual(len(called), 1)

    def test_cleanup(self):
        cleaned = []
        t = DownloadTask("m", "w", lambda c: 1/0, max_attempts=1)
        t.on_cleanup(lambda: cleaned.append(True))
        thr = threading.Thread(target=t.start, daemon=True)
        thr.start()
        thr.join(timeout=2.0)
        self.assertEqual(len(cleaned), 1)

    def test_active_task_cleared(self):
        active = {}
        def fn(ctx):
            active["running"] = True
            return True
        t = DownloadTask("m", "w", fn, max_attempts=3)
        t.on_done(lambda ok, e, a: active.pop("running", None))
        thr = threading.Thread(target=t.start, daemon=True)
        thr.start()
        thr.join(timeout=2.0)
        self.assertNotIn("running", active, "active task not cleared")


if __name__ == "__main__":
    unittest.main(verbosity=2)
