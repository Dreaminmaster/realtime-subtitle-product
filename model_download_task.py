#!/usr/bin/env python3
"""Model download state machine: IDLE → DOWNLOADING → RETRY → SUCCEEDED/FAILED."""
import threading, time

# States
(IDLE, DOWNLOADING, RETRY_WAIT, SUCCEEDED, FAILED, CANCELLED) = range(6)
_STATE_NAMES = {0: "IDLE", 1: "DOWNLOADING", 2: "RETRY_WAIT", 3: "SUCCEEDED", 4: "FAILED", 5: "CANCELLED"}


class DownloadTask:
    """Controls a model download with retries, cancellation, and cleanup."""
    def __init__(self, model_id, backend, download_fn, max_retries=3, retry_delays=(1.0, 2.0, 3.0)):
        self.model_id = model_id
        self.backend = backend
        self.download_fn = download_fn       # callable(ctx) → True/False
        self.max_retries = max_retries
        self.retry_delays = retry_delays
        self.state = IDLE
        self.attempt = 0
        self.last_error = None
        self._cancel = threading.Event()
        self._done_callback = None
        self._status_callback = None
        self._cleanup_fn = None              # callable to remove incomplete model

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
        if self.state in (IDLE, DOWNLOADING, RETRY_WAIT):
            self._cancel.set()
            self.state = CANCELLED
            if self._cleanup_fn:
                self._cleanup_fn()
            if self._done_callback:
                self._done_callback(False, "Cancelled", self.attempt)

    def start(self):
        if self.state not in (IDLE, FAILED, CANCELLED):
            return
        self._cancel.clear()
        self.attempt = 0
        self.last_error = None
        self._run()

    def _run(self):
        while self.attempt < self.max_retries and not self._cancel.is_set():
            self.attempt += 1
            self.state = DOWNLOADING
            self._emit_status("downloading", self.attempt)
            try:
                ok = self.download_fn(self)
                if ok:
                    self.state = SUCCEEDED
                    self._emit_status("completed", self.attempt)
                    if self._done_callback:
                        self._done_callback(True, None, self.attempt)
                    return
                self.last_error = "Download failed"
            except Exception as e:
                self.last_error = str(e)
            if self._cancel.is_set():
                self.state = CANCELLED
                if self._cleanup_fn:
                    self._cleanup_fn()
                if self._done_callback:
                    self._done_callback(False, "Cancelled", self.attempt)
                return
            if self.attempt < self.max_retries:
                delay = self.retry_delays[min(self.attempt - 1, len(self.retry_delays) - 1)]
                self.state = RETRY_WAIT
                self._emit_status("retrying", self.attempt)
                self._cancel.wait(delay)
        if not self._cancel.is_set():
            self.state = FAILED
            self._emit_status("failed", self.attempt)
            if self._cleanup_fn:
                self._cleanup_fn()
            if self._done_callback:
                self._done_callback(False, self.last_error or "Failed after retries", self.attempt)

    def _emit_status(self, status, attempt):
        if self._status_callback:
            self._status_callback(status, attempt)
