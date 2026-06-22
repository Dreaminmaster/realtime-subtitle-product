"""Runtime Settings Guard for v2.4.0 architecture.

Evaluates feature flag combinations at runtime startup using
SettingsDependencyEngine, and produces a RuntimeSettingsDecision
that main.py uses to construct (or skip) new-architecture paths.

Never mutates config.  Never creates repository or scheduler.
Never touches filesystem or network.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
from src.settings_dependency_engine import SettingsDependencyEngine


@dataclass(frozen=True)
class RuntimeSettingsIssue:
    code: str
    severity: str
    message: str
    setting: str | None = None
    recommended_changes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeSettingsDecision:
    ok: bool
    mode: str
    effective_settings: dict[str, Any]
    issues: list[RuntimeSettingsIssue]
    recommended_changes: dict[str, Any]

    allow_translation_scheduler: bool = False
    allow_sqlite_repository: bool = False
    allow_segment_history: bool = False
    allow_segment_export: bool = False
    allow_segment_overlay: bool = False
    allow_transcriber_output_bridge: bool = False

    should_fallback_to_legacy: bool = False
    reason: str = ""


class RuntimeSettingsGuard:
    """Validates runtime settings and returns a decision."""

    def __init__(self, *, engine: SettingsDependencyEngine | None = None):
        self._engine = engine or SettingsDependencyEngine()

    def evaluate(self, settings: dict[str, Any]) -> RuntimeSettingsDecision:
        result = self._engine.validate(settings)
        eff = result.effective_settings

        scheduler = bool(eff.get("use_translation_scheduler"))
        repo = bool(eff.get("use_sqlite_session_repository"))

        # Compute allow_ booleans
        allow_scheduler = result.ok and scheduler
        allow_repo = result.ok and repo and scheduler  # repo requires scheduler
        allow_history = allow_repo and bool(eff.get("use_segment_api_for_history"))
        allow_export = allow_repo and bool(eff.get("use_segment_api_for_export"))
        allow_overlay = bool(eff.get("use_segment_api_for_overlay")) and repo
        allow_bridge = result.ok and scheduler and bool(eff.get("use_transcriber_output_bridge"))  # fallback to legacy if repo off

        # Mode
        if not result.ok:
            mode = "invalid"
        elif scheduler and repo:
            mode = "scheduler_repository"
        elif scheduler:
            mode = "scheduler"
        else:
            mode = "legacy"

        # Fallback
        fallback = not result.ok
        reason = ""
        if fallback:
            errors = [i for i in result.issues if i.severity == "error"]
            if errors:
                reason = "; ".join(i.message for i in errors)
            else:
                reason = "dependency validation failed"

        issues = [
            RuntimeSettingsIssue(
                code=i.code,
                severity=i.severity,
                message=i.message,
                setting=i.setting,
                recommended_changes=i.recommended_changes,
            )
            for i in result.issues
        ]

        return RuntimeSettingsDecision(
            ok=result.ok,
            mode=mode,
            effective_settings=eff,
            issues=issues,
            recommended_changes=dict(result.recommended_changes),
            allow_translation_scheduler=allow_scheduler,
            allow_sqlite_repository=allow_repo,
            allow_segment_history=allow_history,
            allow_segment_export=allow_export,
            allow_segment_overlay=allow_overlay,
            allow_transcriber_output_bridge=allow_bridge,
            should_fallback_to_legacy=fallback,
            reason=reason,
        )


def settings_from_config(config_module_or_object: Any) -> dict[str, Any]:
    """Extract v2.4 feature flags from a config object.
    Reads attributes via getattr; never mutates the source.
    """
    keys = [
        "use_translation_scheduler",
        "use_sqlite_session_repository",
        "use_segment_api_for_history",
        "use_segment_api_for_export",
        "use_segment_api_for_overlay",
        "use_transcriber_output_bridge",
    ]
    result: dict[str, Any] = {}
    for k in keys:
        val = getattr(config_module_or_object, k, None)
        if val is not None:
            result[k] = val
    return result
