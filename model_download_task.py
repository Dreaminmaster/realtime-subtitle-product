#!/usr/bin/env python3
"""Model download state machine — async, thread-safe, single-fire callbacks."""
import threading, time

IDLE, DOWNLOADING, RETRY_WAIT, SUCCEEDED, FAILED, CANCELLED = range(6)
STATES = {IDLE: "idle", DOWNLOADING: "downloading", RETRY_WAIT: "retrying",
          SUCCEEDED: "succeeded", FAILED: "failed", CANCELLED: "cancelled"}


class DownloadTask:
    def __init__(self, model_id, backend, download_fn, max_attempts=3,
                 retry_delays=(1.0, 2.0, 3.0)):
        self.model_id = model_id
        self.backend = backend
        self.download_fn = download_fn
        self.max_attempts = max_attempts
        self.retry_delays = retry_delays
        self.state = IDLE
        self.attempt = 0
        self.last_error = None
        self._cancel = threading.Event()
        self._done_callback = None
        self._status_callback = None
        self._cleanup_fn = None
        self._lock = threading.Lock()
        self._finished = False

    def on_status(self, cb):
        self._status_callback = cb
        return self

    def on_done(self, cb):
        self._done_callback = cb
        return self

    def on_cleanup(self, cb):
        self._cleanup_fn = cb
        return self

    def cancel(self):
        with self._lock:
            if self._finished:
                return
            self._cancel.set()

    def start(self):
        with self._lock:
            if self._finished:
                return
            self._cancel.clear()
            self.attempt = 0
            self.last_error = None
            self.state = DOWNLOADING
        self._run()  # release lock before entering run loop

    def _finalize(self, ok, error, attempt):
        with self._lock:
            if self._finished:
                return
            self._finished = True
        if self._cleanup_fn and not ok:
            self._cleanup_fn()
        if self._done_callback:
            self._done_callback(ok, error, attempt)

    def _run(self):
        while self.attempt < self.max_attempts:
            self.attempt += 1
            self._set_state(DOWNLOADING)
            self._emit_status("downloading", self.attempt)
            try:
                ok = self.download_fn(self)
                if ok:
                    self._set_state(SUCCEEDED)
                    self._emit_status("completed", self.attempt)
                    self._finalize(True, None, self.attempt)
                    return
                self.last_error = "Download returned False"
            except Exception as e:
                self.last_error = str(e)

            if self._cancel.is_set():
                self._set_state(CANCELLED)
                self._emit_status("cancelled", self.attempt)
                self._finalize(False, "Cancelled", self.attempt)
                return

            if self.attempt < self.max_attempts:
                delay = self.retry_delays[min(self.attempt - 1, len(self.retry_delays) - 1)]
                self._set_state(RETRY_WAIT)
                self._emit_status("retrying", self.attempt)
                if self._cancel.wait(delay):
                    self._set_state(CANCELLED)
                    self._emit_status("cancelled", self.attempt)
                    self._finalize(False, "Cancelled", self.attempt)
                    return

        self._set_state(FAILED)
        self._emit_status("failed", self.attempt)
        self._finalize(False, self.last_error or "Failed after attempts", self.attempt)

    def _set_state(self, s):
        with self._lock:
            self.state = s

    def _emit_status(self, status, attempt):
        cb = self._status_callback
        if cb:
            cb(status, attempt)
