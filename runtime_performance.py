"""Small, deterministic runtime budgets for live caption workloads.

The product exposes quality choices separately from this performance budget:
users may still select a larger recognition model, while the runtime controls
how aggressively draft ASR, draft translation, and second-pass correction are
allowed to consume the machine.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import platform


@dataclass(frozen=True)
class HardwareRuntimePlan:
    profile: str
    machine: str
    memory_gb: float
    cpu_count: int
    cpu_threads: int
    num_workers: int
    compute_type: str
    partial_window_seconds: float


def resolve_hardware_runtime_plan(
    profile: str = "balanced",
    *,
    machine: str | None = None,
    memory_gb: float | None = None,
    cpu_count: int | None = None,
) -> HardwareRuntimePlan:
    """Resolve conservative sustained-inference budgets for one desktop."""
    normalized = str(profile or "balanced").lower()
    if normalized not in RuntimePerformancePolicy.PROFILES:
        normalized = "balanced"
    machine = str(machine or platform.machine()).lower()
    if memory_gb is None:
        try:
            from recognition_quality import detect_memory_gb

            memory_gb = detect_memory_gb()
        except Exception:
            memory_gb = 8.0
    cores = max(1, int(cpu_count or os.cpu_count() or 4))

    if normalized == "efficient":
        threads = max(1, min(4, cores // 2 or 1))
        workers = 1
        window = 7.5
    elif normalized == "maximum":
        threads = max(2, min(10, cores - 1 if cores > 2 else cores))
        workers = 2 if memory_gb >= 16 else 1
        window = 12.0
    else:
        threads = max(2, min(6, cores // 2 or 2))
        workers = 1
        window = 9.0

    return HardwareRuntimePlan(
        profile=normalized,
        machine=machine,
        memory_gb=float(memory_gb),
        cpu_count=cores,
        cpu_threads=threads,
        num_workers=workers,
        # The portable desktop packages use CPU int8. MLX remains a separate
        # Apple-Silicon backend selected by the user.
        compute_type="int8",
        partial_window_seconds=window,
    )


@dataclass(frozen=True)
class RuntimePerformancePolicy:
    profile: str = "balanced"

    PROFILES = {"efficient", "balanced", "maximum"}

    def __post_init__(self):
        normalized = str(self.profile or "balanced").lower()
        if normalized not in self.PROFILES:
            normalized = "balanced"
        object.__setattr__(self, "profile", normalized)

    def partial_interval(self, configured: float) -> float:
        """Return the minimum spacing between whole-buffer draft ASR passes."""
        requested = max(0.4, min(float(configured), 1.8))
        if self.profile == "efficient":
            return max(1.15, requested)
        if self.profile == "maximum":
            return max(0.55, min(requested, 0.75))
        return max(0.78, requested)

    def caption_segment_limit(self, configured: float) -> float:
        """Bound one acoustic segment so a timed caption stays scannable."""
        requested = max(4.0, min(float(configured), 30.0))
        if self.profile == "efficient":
            return min(requested, 7.5)
        if self.profile == "maximum":
            return min(requested, 12.0)
        return min(requested, 9.0)

    def draft_translation_interval(self, translation_mode: str, live_mode: str) -> float | None:
        """Provider-aware interval for non-final translation previews."""
        live_mode = str(live_mode or "balanced").lower()
        if live_mode == "final_only":
            return None

        provider = str(translation_mode or "off").lower()
        if provider == "off":
            return None

        # Apple Translation is local and very quick.  Hosted and local LLMs
        # need wider spacing to avoid request/token churn while the sentence
        # is still changing.
        base = 1.15 if provider == "fast" else 1.80
        if provider == "offline":
            base = 1.35
        if provider in {"local", "custom"}:
            base = 2.20
        if live_mode == "realtime":
            base *= 0.62

        if self.profile == "efficient":
            base *= 1.45
        elif self.profile == "maximum":
            base *= 0.72
        return max(0.65, min(base, 3.2))

    def draft_min_growth(self, live_mode: str) -> int:
        if str(live_mode or "balanced").lower() == "realtime":
            return 5 if self.profile == "maximum" else 7
        return 14 if self.profile == "efficient" else 10

    def translation_workers(self, configured: int) -> int:
        """Bound concurrent translation calls for a sustained live session."""
        requested = max(1, min(int(configured or 1), 8))
        if self.profile == "efficient":
            return 1
        if self.profile == "maximum":
            return min(requested, 4)
        return min(requested, 2)

    def accuracy_cooldown(self, elapsed_seconds: float, model_id: str) -> float:
        """Cooling pause after one optional second-pass recognition job.

        Maximum deliberately preserves continuous correction for powerful or
        externally cooled machines.  Balanced and Efficient convert a slow
        CPU-bound refiner into a bounded duty cycle while the latest-only slot
        continues to keep the newest phrase.
        """
        elapsed = max(0.0, float(elapsed_seconds))
        if self.profile == "maximum" or elapsed < 2.0:
            return 0.0
        large = str(model_id or "").lower() in {"large", "large-v2", "large-v3"}
        ratio = 1.0 if self.profile == "efficient" else 0.55
        floor = 6.0 if (large and self.profile == "efficient") else (3.5 if large else 1.5)
        ceiling = 18.0 if self.profile == "efficient" else 10.0
        return min(ceiling, max(floor, elapsed * ratio))
