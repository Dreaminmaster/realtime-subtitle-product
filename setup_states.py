#!/usr/bin/env python3
"""First-launch setup state machine — drives ProgressEvent pipeline."""
from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Optional
from progress_events import ProgressEvent


class SetupStage(IntEnum):
    CHECK_SYSTEM = 0
    CREATE_ENV = auto()
    INSTALL_DEPENDENCIES = auto()
    DOWNLOAD_MODEL = auto()
    VERIFY = auto()
    READY = auto()
    FAILED = auto()
    CANCELLED = auto()


STAGE_LABELS = {
    SetupStage.CHECK_SYSTEM: "Check system",
    SetupStage.CREATE_ENV: "Create environment",
    SetupStage.INSTALL_DEPENDENCIES: "Install dependencies",
    SetupStage.DOWNLOAD_MODEL: "Download model",
    SetupStage.VERIFY: "Verify installation",
    SetupStage.READY: "Ready",
}

TOTAL_STAGES = len(STAGE_LABELS)


class SetupStateMachine:
    """Track first-launch progress with retry and cancel support."""

    def __init__(self, model_id: str = "tiny"):
        self.current_stage: Optional[SetupStage] = None
        self.model_id = model_id
        self.completed: set[SetupStage] = set()
        self.error: Optional[str] = None
        self.cancelled = False

    def begin_stage(self, stage: SetupStage) -> ProgressEvent:
        self.current_stage = stage
        label = STAGE_LABELS.get(stage, str(stage))
        idx = stage.value
        return ProgressEvent(task_id="setup", stage=label,
                             message=f"{label}…",
                             stage_index=idx, total_stages=TOTAL_STAGES,
                             attempt=1, max_attempts=1, can_cancel=True)

    def complete_stage(self, stage: SetupStage) -> ProgressEvent:
        self.completed.add(stage)
        return ProgressEvent(task_id="setup",
                             stage=STAGE_LABELS.get(stage, str(stage)),
                             message=f"{STAGE_LABELS.get(stage, '')} ✓",
                             stage_index=stage.value + 1,
                             total_stages=TOTAL_STAGES, percent=100.0,
                             can_cancel=True)

    def fail_stage(self, msg: str) -> ProgressEvent:
        return ProgressEvent(task_id="setup", stage="failed",
                             message=msg, can_retry=True, can_cancel=False)

    def cancel(self) -> ProgressEvent:
        self.cancelled = True
        return ProgressEvent(task_id="setup", stage="cancelled",
                             message="Setup cancelled",
                             can_cancel=False, can_retry=False)

    def ready(self) -> ProgressEvent:
        self.current_stage = SetupStage.READY
        return ProgressEvent(task_id="setup", stage="Ready",
                             message="Ready", stage_index=TOTAL_STAGES,
                             total_stages=TOTAL_STAGES, percent=100.0,
                             can_cancel=False)
