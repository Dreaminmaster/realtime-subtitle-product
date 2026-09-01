"""Low-overhead development metrics for the live pipeline.

Metrics stay in memory and are logged as a compact JSON summary at shutdown.
They are intentionally absent from the normal product UI and contain no audio
or transcript text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import sys
import threading
import time

try:
    import resource
except ImportError:  # Windows does not provide the POSIX resource module.
    resource = None


def _process_peak_rss_mb() -> float:
    """Return peak resident memory without adding a runtime dependency."""

    if resource is not None:
        max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # macOS reports bytes; Linux and the other POSIX builds report KiB.
        return max_rss / (1024 * 1024) if sys.platform == "darwin" else max_rss / 1024

    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                handle,
                ctypes.byref(counters),
                counters.cb,
            )
            if ok:
                return counters.PeakWorkingSetSize / (1024 * 1024)
        except (AttributeError, OSError):
            pass
    return 0.0


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
    return ordered[index]


@dataclass
class _SegmentTiming:
    speech_started: float
    first_partial: float | None = None
    first_stable: float | None = None
    final: float | None = None
    first_translation: float | None = None


@dataclass
class RuntimeMetrics:
    profile: str
    backend: str
    model: str
    clock: callable = time.monotonic
    _segments: dict[int, _SegmentTiming] = field(default_factory=dict, init=False)
    _partial_latency: list[float] = field(default_factory=list, init=False)
    _stable_latency: list[float] = field(default_factory=list, init=False)
    _final_latency: list[float] = field(default_factory=list, init=False)
    _translation_latency: list[float] = field(default_factory=list, init=False)
    _asr_rtf: list[float] = field(default_factory=list, init=False)
    _endpoint_reasons: dict[str, int] = field(default_factory=dict, init=False)
    _stable_conflicts: int = field(default=0, init=False)
    _started: float = field(default=0.0, init=False)
    _started_cpu: float = field(default=0.0, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    def start_session(self) -> None:
        with self._lock:
            self._segments.clear()
            self._partial_latency.clear()
            self._stable_latency.clear()
            self._final_latency.clear()
            self._translation_latency.clear()
            self._asr_rtf.clear()
            self._endpoint_reasons.clear()
            self._stable_conflicts = 0
            self._started = self.clock()
            self._started_cpu = time.process_time()

    def begin_segment(self, segment_id: int) -> None:
        with self._lock:
            self._segments.setdefault(segment_id, _SegmentTiming(self.clock()))

    def record_asr(
        self,
        segment_id: int,
        phase: str,
        *,
        inference_seconds: float,
        audio_seconds: float,
        stable_conflict: bool = False,
    ) -> None:
        now = self.clock()
        phase = str(phase).upper()
        with self._lock:
            timing = self._segments.setdefault(segment_id, _SegmentTiming(now))
            latency = max(0.0, now - timing.speech_started)
            if phase == "PARTIAL" and timing.first_partial is None:
                timing.first_partial = now
                self._partial_latency.append(latency)
            elif phase == "STABLE" and timing.first_stable is None:
                timing.first_stable = now
                self._stable_latency.append(latency)
            elif phase == "FINAL" and timing.final is None:
                timing.final = now
                self._final_latency.append(latency)
            if audio_seconds > 0:
                self._asr_rtf.append(max(0.0, inference_seconds) / audio_seconds)
            if stable_conflict:
                self._stable_conflicts += 1

    def record_translation(self, segment_id: int) -> None:
        now = self.clock()
        with self._lock:
            timing = self._segments.get(segment_id)
            if timing is None or timing.first_translation is not None:
                return
            timing.first_translation = now
            self._translation_latency.append(max(0.0, now - timing.speech_started))

    def record_endpoint(self, reason: str) -> None:
        with self._lock:
            reason = str(reason or "unknown")
            self._endpoint_reasons[reason] = self._endpoint_reasons.get(reason, 0) + 1

    def snapshot(self) -> dict:
        with self._lock:
            wall = max(0.001, self.clock() - self._started) if self._started else 0.0
            cpu = max(0.0, time.process_time() - self._started_cpu) if self._started else 0.0
            return {
                "profile": self.profile,
                "backend": self.backend,
                "model": self.model,
                "wall_seconds": round(wall, 3),
                "process_cpu_percent": round((cpu / wall) * 100, 2) if wall else 0.0,
                "max_rss_mb": round(_process_peak_rss_mb(), 2),
                "segments": len(self._segments),
                "first_partial_ms_p50": self._ms(_percentile(self._partial_latency, 0.50)),
                "first_stable_ms_p50": self._ms(_percentile(self._stable_latency, 0.50)),
                "final_ms_p50": self._ms(_percentile(self._final_latency, 0.50)),
                "translation_ms_p50": self._ms(_percentile(self._translation_latency, 0.50)),
                "asr_rtf_p50": self._rounded(_percentile(self._asr_rtf, 0.50)),
                "asr_rtf_p95": self._rounded(_percentile(self._asr_rtf, 0.95)),
                "stable_conflicts": self._stable_conflicts,
                "endpoint_reasons": dict(sorted(self._endpoint_reasons.items())),
            }

    def log_summary(self, logger) -> dict:
        summary = self.snapshot()
        logger.info("RuntimeMetrics %s", json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return summary

    @staticmethod
    def _ms(value: float | None) -> float | None:
        return round(value * 1000, 1) if value is not None else None

    @staticmethod
    def _rounded(value: float | None) -> float | None:
        return round(value, 3) if value is not None else None
