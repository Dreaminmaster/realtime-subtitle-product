"""Hardware-aware plans for optional second-pass speech recognition.

The live recognizer remains the user's selected model.  When enhanced accuracy
is enabled, this module chooses a locally installed refinement model that runs
after the fast result and revises the same subtitle line.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import platform
import subprocess


_MODEL_SIZES_MB = {
    "small": 488,
    "turbo": 1620,
    "large-v3": 3100,
}
_VALID_PROFILES = {"auto", "fast", "balanced", "accurate"}


@dataclass(frozen=True)
class HardwareProfile:
    machine: str
    memory_gb: float
    apple_silicon: bool

    @property
    def label(self) -> str:
        family = "Apple Silicon" if self.apple_silicon else "Intel / compatible"
        return f"{family} · {self.memory_gb:.0f} GB memory"


@dataclass(frozen=True)
class AccuracyPlan:
    requested_profile: str
    resolved_profile: str
    model_id: str
    size_mb: int
    device: str = "cpu"
    compute_type: str = "int8"

    @property
    def size_label(self) -> str:
        if self.size_mb >= 1000:
            return f"{self.size_mb / 1000:.1f} GB"
        return f"{self.size_mb} MB"


def detect_memory_gb() -> float:
    """Return physical memory without importing platform-specific frameworks."""
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["/usr/sbin/sysctl", "-n", "hw.memsize"],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
            return max(1.0, int(result.stdout.strip()) / (1024 ** 3))
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return max(1.0, float(pages * page_size) / (1024 ** 3))
    except (AttributeError, OSError, ValueError):
        return 8.0


def detect_hardware() -> HardwareProfile:
    machine = platform.machine().lower()
    return HardwareProfile(
        machine=machine,
        memory_gb=detect_memory_gb(),
        apple_silicon=machine in {"arm64", "aarch64"} and platform.system() == "Darwin",
    )


def resolve_accuracy_plan(
    requested_profile: str = "auto",
    hardware: HardwareProfile | None = None,
) -> AccuracyPlan:
    """Resolve a stable, universal faster-whisper refinement plan.

    CTranslate2's macOS build uses CPU execution, so both Apple Silicon and
    Intel packages use ``int8``.  Hardware matching selects model size rather
    than pretending an unsupported MPS path exists.
    """
    requested = str(requested_profile or "auto").lower()
    if requested not in _VALID_PROFILES:
        requested = "auto"
    hardware = hardware or detect_hardware()

    if requested == "fast":
        resolved, model_id = "fast", "small"
    elif requested == "balanced":
        resolved, model_id = "balanced", "turbo"
    elif requested == "accurate":
        resolved, model_id = "accurate", "large-v3"
    elif hardware.apple_silicon and hardware.memory_gb >= 8:
        # ``large-v3`` is intentionally never selected by Auto.  On the
        # packaged macOS runtime CTranslate2 executes this second pass on the
        # CPU; a 24 GB Mac can hold it, but sustained 15–25 second refinements
        # make the machine hot and delay later corrections.  Turbo is the
        # best default balance.  Users who explicitly choose Accurate still
        # get large-v3 on demand.
        resolved, model_id = "balanced", "turbo"
    else:
        resolved, model_id = "fast", "small"

    return AccuracyPlan(
        requested_profile=requested,
        resolved_profile=resolved,
        model_id=model_id,
        size_mb=_MODEL_SIZES_MB[model_id],
    )
