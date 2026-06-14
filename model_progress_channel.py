#!/usr/bin/env python3
"""Bridge: DownloadTask callbacks -> ProgressPanel via ProgressEvent."""
import time
from progress_events import ProgressEvent


class ModelProgressChannel:
    def __init__(self, model_id, max_attempts=3):
        self.model_id = model_id
        self.max_attempts = max_attempts
        self._start_time = 0
        self._last_bytes = 0
        self._last_time = 0

    def on_start(self):
        self._start_time = time.time()
        self._last_bytes = 0
        self._last_time = self._start_time
        return ProgressEvent(self.model_id, "starting", f"Connecting to HuggingFace...",
                             attempt=1, max_attempts=self.max_attempts, can_cancel=True)

    def on_retry(self, attempt):
        return ProgressEvent(self.model_id, "retrying", f"Retrying in a moment...",
                             attempt=attempt, max_attempts=self.max_attempts, can_cancel=True)

    def on_progress(self, current_bytes, total_bytes, attempt=1):
        now = time.time()
        speed = 0
        if self._last_bytes and (now - self._last_time) > 0:
            speed = (current_bytes - self._last_bytes) / (now - self._last_time)
        self._last_bytes = current_bytes
        self._last_time = now
        percent = (current_bytes / total_bytes * 100) if total_bytes else None
        mb_cur = current_bytes / (1024*1024) if current_bytes else 0
        mb_tot = total_bytes / (1024*1024) if total_bytes else 0
        eta = int((total_bytes - current_bytes) / speed) if speed > 0 else None
        msg = f"Downloading... {mb_cur:.0f} MB / {mb_tot:.0f} MB"
        if speed > 0: msg += f"  {speed/1e6:.1f} MB/s"
        if eta: msg += f"  About {eta}s remaining"
        return ProgressEvent(self.model_id, "downloading", msg, current_bytes=current_bytes,
                             total_bytes=total_bytes, percent=percent, speed_bps=speed,
                             eta_seconds=eta, attempt=attempt, max_attempts=self.max_attempts,
                             can_cancel=True)

    def on_success(self, attempt):
        return ProgressEvent(self.model_id, "succeeded", "Download complete", percent=100.0,
                             attempt=attempt, max_attempts=self.max_attempts, can_cancel=False)

    def on_fail(self, error_msg, attempt):
        msg = error_msg or "Download failed"
        if "timeout" in msg.lower() or "connect" in msg.lower():
            msg = "Connection timed out. Check your network and try again."
        return ProgressEvent(self.model_id, "failed", msg, attempt=attempt,
                             max_attempts=self.max_attempts, can_retry=True, can_cancel=False)

    def on_cancel(self, attempt):
        return ProgressEvent(self.model_id, "cancelled", "Download cancelled",
                             attempt=attempt, max_attempts=self.max_attempts, can_cancel=False)
