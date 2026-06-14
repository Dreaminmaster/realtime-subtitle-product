#!/usr/bin/env python3
"""Structured progress events for model download + first-launch setup.
Thread-safe: only emit via Qt signals, never update widgets directly."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProgressEvent:
    task_id: str
    stage: str
    message: str
    current_bytes: Optional[int] = None
    total_bytes: Optional[int] = None
    percent: Optional[float] = None
    speed_bps: Optional[float] = None
    eta_seconds: Optional[int] = None
    attempt: int = 1
    max_attempts: int = 3
    can_cancel: bool = True
    can_retry: bool = False
    stage_index: int = 0
    total_stages: int = 0
