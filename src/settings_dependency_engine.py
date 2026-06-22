"""Settings dependency engine for v2.4.0 architecture.

Validates feature flag combinations without side-effects.
Never creates repositories, schedulers, or touches the filesystem.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Literal, Dict, List

Severity = Literal["info", "warning", "error"]

KNOWN_KEYS = {
    "use_translation_scheduler",
    "use_sqlite_session_repository",
    "use_segment_api_for_history",
    "use_segment_api_for_export",
    "use_segment_api_for_overlay",
    "use_transcriber_output_bridge",
}


@dataclass(frozen=True)
class DependencyIssue:
    code: str
    severity: Severity
    message: str
    setting: str | None = None
    depends_on: list[str] = field(default_factory=list)
    recommended_changes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DependencyValidationResult:
    ok: bool
    issues: list[DependencyIssue] = field(default_factory=list)
    effective_settings: dict[str, Any] = field(default_factory=dict)
    recommended_changes: dict[str, Any] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return any(iss.severity == "error" for iss in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(iss.severity == "warning" for iss in self.issues)


class SettingsDependencyEngine:
    """Pure-logic validator for feature flag combinations."""

    def validate(self, settings: dict[str, Any]) -> DependencyValidationResult:
        """Validate settings dict. Does NOT modify input."""
        issues: list[DependencyIssue] = []
        effective: dict[str, Any] = {}
        recommended: dict[str, Any] = {}

        # ── normalize booleans ──────────────────────────────────
        scheduler = self._normalize_bool(settings.get("use_translation_scheduler"))
        repo = self._normalize_bool(settings.get("use_sqlite_session_repository"))
        seg_history = self._normalize_bool(settings.get("use_segment_api_for_history"))
        seg_export = self._normalize_bool(settings.get("use_segment_api_for_export"))
        seg_overlay = self._normalize_bool(settings.get("use_segment_api_for_overlay"))

        effective.update({
            "use_translation_scheduler": scheduler,
            "use_sqlite_session_repository": repo,
            "use_segment_api_for_history": seg_history,
            "use_segment_api_for_export": seg_export,
            "use_segment_api_for_overlay": seg_overlay,
        })

        for key, raw in settings.items():
            if key in KNOWN_KEYS:
                continue
            issues.append(DependencyIssue(
                code="unknown_setting",
                severity="info",
                message=f"Ignored unknown setting: {key}",
                setting=key,
            ))

        # Non-bool warnings
        for key in KNOWN_KEYS:
            raw = settings.get(key)
            if raw is None:
                continue
            if isinstance(raw, bool):
                continue
            if isinstance(raw, str) and raw.lower() not in ("true", "false"):
                issues.append(DependencyIssue(
                    code="non_bool_value",
                    severity="warning",
                    message=f"{key} value '{raw}' is not a boolean — defaulting to False",
                    setting=key,
                ))

        # ── rules ───────────────────────────────────────────────
        # 1-2. scheduler on + repo off → valid
        # (no issue needed)

        # 3. repo requires scheduler
        if repo and not scheduler:
            issues.append(DependencyIssue(
                code="repository_requires_scheduler",
                severity="error",
                message="SQLite repository requires translation scheduler to be active.",
                setting="use_sqlite_session_repository",
                depends_on=["use_translation_scheduler"],
                recommended_changes={"use_translation_scheduler": True},
            ))

        # 5. history requires repository (and thus scheduler)
        if seg_history and not repo:
            issues.append(DependencyIssue(
                code="history_requires_repository",
                severity="error",
                message="Segment history requires SQLite repository (and scheduler).",
                setting="use_segment_api_for_history",
                depends_on=["use_sqlite_session_repository", "use_translation_scheduler"],
                recommended_changes={
                    "use_sqlite_session_repository": True,
                    "use_translation_scheduler": True,
                },
            ))

        # 6. export requires repository
        if seg_export and not repo:
            issues.append(DependencyIssue(
                code="export_requires_repository",
                severity="error",
                message="Transcript export requires SQLite repository.",
                setting="use_segment_api_for_export",
                depends_on=["use_sqlite_session_repository", "use_translation_scheduler"],
                recommended_changes={
                    "use_sqlite_session_repository": True,
                    "use_translation_scheduler": True,
                },
            ))

        # 7. overlay segment api without repo → warning (not error)
        if seg_overlay and not repo:
            issues.append(DependencyIssue(
                code="overlay_segment_api_requires_repository",
                severity="warning",
                message="Overlay segment API is enabled but SQLite repository is off. "
                        "Overlay will fall back to legacy signals.",
                setting="use_segment_api_for_overlay",
                depends_on=["use_sqlite_session_repository"],
            ))

        # 8. transcriber bridge requires scheduler
        bridge = self._normalize_bool(settings.get("use_transcriber_output_bridge"))
        effective["use_transcriber_output_bridge"] = bridge
        if bridge and not scheduler:
            issues.append(DependencyIssue(
                code="transcriber_bridge_requires_scheduler",
                severity="error",
                message="Transcriber output bridge requires translation scheduler to be active.",
                setting="use_transcriber_output_bridge",
                depends_on=["use_translation_scheduler"],
                recommended_changes={"use_translation_scheduler": True},
            ))

        # Build recommended_changes from errors only
        for iss in issues:
            if iss.severity == "error" and iss.recommended_changes:
                recommended.update(iss.recommended_changes)

        ok = not any(iss.severity == "error" for iss in issues)
        return DependencyValidationResult(
            ok=ok,
            issues=issues,
            effective_settings=effective,
            recommended_changes=recommended,
        )

    @staticmethod
    def _normalize_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        if isinstance(value, (int, float)):
            return bool(value)
        return False
