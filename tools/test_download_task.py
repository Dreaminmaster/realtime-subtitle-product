#!/usr/bin/env python3
"""Test DownloadTask — atomic callbacks, cancel, concurrent."""
import sys, os, unittest, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from model_download_task import DownloadTask, IDLE, SUCCEEDED, FAILED, CANCELLED


class TestDownloadTask(unittest.TestCase):
    def test_success_first(self):
        r = []
        t = DownloadTask("m", "w", lambda c: True, max_attempts=3)
        t.on_done(lambda ok, e, a: r.append((ok, e, a)))
        t.start()
        self.assertEqual(t.state, SUCCEEDED)
        self.assertEqual(len(r), 1)
        self.assertTrue(r[0][0])

    def test_fail_then_success(self):
        def flaky(c):
            return c.attempt >= 2
        r = []
        t = DownloadTask("m", "w", flaky, max_attempts=3, retry_delays=(0.01, 0.01))
        t.on_done(lambda ok, e, a: r.append((ok, e, a)))
        t.start()
        self.assertEqual(t.state, SUCCEEDED)
        self.assertEqual(t.attempt, 2)

    def test_fail_all(self):
        def fail(c):
            raise RuntimeError("fail")
        r = []
        t = DownloadTask("m", "w", fail, max_attempts=2, retry_delays=(0.01,))
        t.on_done(lambda ok, e, a: r.append((ok, e, a)))
        t.start()
        self.assertEqual(t.state, FAILED)
        self.assertFalse(r[0][0])

    def test_cancel_async(self):
        def slow_fail(c):
            time.sleep(2.0)
            return False
        r = []
        t = DownloadTask("m", "w", slow_fail, max_attempts=5, retry_delays=(1.0, 2.0))
        t.on_done(lambda ok, e, a: r.append((ok, e, a)))
        thr = threading.Thread(target=t.start, daemon=True)
        thr.start()
        time.sleep(0.2)  # let it enter download_fn sleep
        t.cancel()
        thr.join(timeout=5)
        self.assertEqual(t.state, CANCELLED)
        self.assertEqual(len(r), 1)

    def test_done_called_exactly_once(self):
        called = []
        def flaky(c):
            return c.attempt >= 2
        t = DownloadTask("m", "w", flaky, max_attempts=3, retry_delays=(0.01, 0.01))
        t.on_done(lambda ok, e, a: called.append(1))
        t.start()
        self.assertEqual(len(called), 1)

    def test_cleanup_on_failure(self):
        cleaned = []
        t = DownloadTask("m", "w", lambda c: 1/0, max_attempts=1)
        t.on_cleanup(lambda: cleaned.append(True))
        t.start()
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(t.state, FAILED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
