"""Settings validation ViewModel for v2.4.0 architecture.

Translates SettingsDependencyEngine results into human-readable
dashboard display data.  No Qt dependency.  No side effects.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
from src.settings_dependency_engine import SettingsDependencyEngine


@dataclass(frozen=True)
class SettingsValidationMessage:
    code: str
    severity: str
    message: str
    setting: str | None = None
    recommended_changes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SettingsValidationViewModel:
    ok: bool
    title: str
    summary: str
    mode_label: str
    messages: list[SettingsValidationMessage]
    effective_settings: dict[str, Any]
    recommended_changes: dict[str, Any]
    can_use_new_architecture: bool
    can_use_history: bool
    can_use_export: bool


def build_settings_validation_viewmodel(
    settings: dict[str, Any],
    *,
    engine: SettingsDependencyEngine | None = None,
) -> SettingsValidationViewModel:
    """Pure function: settings dict → ViewModel. Never mutates input."""
    eng = engine or SettingsDependencyEngine()
    result = eng.validate(settings)

    messages = [
        SettingsValidationMessage(
            code=iss.code,
            severity=iss.severity,
            message=iss.message,
            setting=iss.setting,
            recommended_changes=iss.recommended_changes,
        )
        for iss in result.issues
    ]

    # Infer capabilities from effective settings
    eff = result.effective_settings
    can_new_arch = bool(eff.get("use_translation_scheduler"))
    can_history = bool(eff.get("use_sqlite_session_repository")) and can_new_arch
    can_export = can_history

    # Override if dependency errors block them
    if result.has_errors:
        can_new_arch = False
        can_history = False
        can_export = False

    if not result.ok:
        title = "Invalid settings"
        summary = "One or more settings have dependency conflicts."
        mode_label = "Invalid configuration"
    elif can_history:
        title = "New architecture ready"
        summary = "Scheduler and SQLite repository are enabled."
        mode_label = "Scheduler + persistent transcript"
    elif can_new_arch:
        title = "Scheduler mode"
        summary = "Translation scheduler is enabled, but persistent transcript history is disabled."
        mode_label = "Scheduler without history"
    else:
        title = "Legacy mode"
        summary = "Current settings use the stable legacy runtime."
        mode_label = "Legacy runtime"

    return SettingsValidationViewModel(
        ok=result.ok,
        title=title,
        summary=summary,
        mode_label=mode_label,
        messages=messages,
        effective_settings=eff,
        recommended_changes=dict(result.recommended_changes),
        can_use_new_architecture=can_new_arch,
        can_use_history=can_history,
        can_use_export=can_export,
    )
