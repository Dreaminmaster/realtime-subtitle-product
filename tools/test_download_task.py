#!/usr/bin/env python3
"""Test DownloadTask state machine."""
import sys, os, unittest, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from model_download_task import DownloadTask, IDLE, DOWNLOADING, SUCCEEDED, FAILED, CANCELLED


class TestDownloadTask(unittest.TestCase):
    def test_success_first_try(self):
        results = []
        task = DownloadTask("test", "whisper", lambda ctx: True, max_retries=3)
        task.on_done(lambda ok, err, attempts: results.append((ok, err, attempts)))
        task.start()
        # task runs synchronously — no threading for success path
        self.assertEqual(task.state, SUCCEEDED)
        self.assertEqual(task.attempt, 1)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0][0])

    def test_fail_then_success(self):
        attempts_made = []
        def flaky(ctx):
            attempts_made.append(ctx.attempt)
            return ctx.attempt >= 2
        results = []
        task = DownloadTask("test", "whisper", flaky, max_retries=3, retry_delays=(0.01, 0.01))
        task.on_done(lambda ok, err, attempts: results.append((ok, err, attempts)))
        task.start()
        self.assertEqual(task.state, SUCCEEDED)
        self.assertEqual(task.attempt, 2)
        self.assertEqual(attempts_made, [1, 2])

    def test_fail_all_retries(self):
        def always_fail(ctx):
            raise RuntimeError("fail")
        results = []
        task = DownloadTask("test", "whisper", always_fail, max_retries=2, retry_delays=(0.01, 0.01))
        task.on_done(lambda ok, err, attempts: results.append((ok, err, attempts)))
        task.start()
        self.assertEqual(task.state, FAILED)
        self.assertEqual(task.attempt, 2)
        self.assertFalse(results[0][0])

    def test_cancel_during_retry(self):
        def slow_fail(ctx):
            time.sleep(0.1)
            return False
        results = []
        task = DownloadTask("test", "whisper", slow_fail, max_retries=5, retry_delays=(1.0, 1.0))
        task.on_done(lambda ok, err, attempts: results.append((ok, err, attempts)))
        task.start()
        time.sleep(0.15)
        task.cancel()
        # After cancel, state should be CANCELLED or FAILED (not SUCCEEDED)
        self.assertIn(task.state, (CANCELLED, FAILED))

    def test_status_callbacks(self):
        statuses = []
        task = DownloadTask("test", "whisper", lambda ctx: True)
        task.on_status(lambda s, a: statuses.append((s, a)))
        task.start()
        self.assertIn(("downloading", 1), statuses)

    def test_cleanup_called_on_failure(self):
        cleaned = []
        def always_fail(ctx):
            raise RuntimeError("fail")
        task = DownloadTask("test", "whisper", always_fail, max_retries=1)
        task.on_cleanup(lambda: cleaned.append(True))
        task.start()
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(task.state, FAILED)

    def test_success_is_not_retried(self):
        task = DownloadTask("test", "whisper", lambda ctx: True)
        task.start()
        self.assertEqual(task.state, SUCCEEDED)
        task.start()  # restart from SUCCEEDED — should work
        self.assertEqual(task.state, SUCCEEDED)

    def test_done_called_exactly_once(self):
        called = []
        def flaky(ctx):
            return ctx.attempt >= 2
        task = DownloadTask("test", "whisper", flaky, max_retries=3, retry_delays=(0.01, 0.01))
        task.on_done(lambda ok, e, a: called.append(1))
        task.start()
        self.assertEqual(len(called), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
