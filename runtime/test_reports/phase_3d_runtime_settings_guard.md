# Phase 3d — Runtime Settings Guard

Phase: 3d
Branch: v2.4.0-architecture
Commit before: a1faebd
Commit after: (pending)

Files changed: 4
  - src/runtime_settings_guard.py (NEW)
  - tests/test_runtime_settings_guard.py (NEW)
  - main.py (minimal: RuntimeSettingsGuard)
  - runtime/test_reports/phase_3d_*.md

SettingsDependencyEngine file: src/settings_dependency_engine.py
Existing runtime config flags: use_translation_scheduler, use_sqlite_session_repository
Existing main.py scheduler construction restructured to use guard decision
Existing repository construction restructured to use guard decision
Runtime enforcement gap: CLOSED

Runtime guard design:
  - settings_from_config → dict
  - SettingsDependencyEngine.validate → DependencyValidationResult
  - RuntimeSettingsGuard.evaluate → RuntimeSettingsDecision
  - allow_translation_scheduler / allow_sqlite_repository / allow_segment_*
  - should_fallback_to_legacy: true if errors
  - mode: legacy | scheduler | scheduler_repository | invalid

Tests added: 14
Total: 366 (+14 from Phase 3c)
