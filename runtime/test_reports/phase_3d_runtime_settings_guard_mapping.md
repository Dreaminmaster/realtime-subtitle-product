# Phase 3d — Runtime Settings Guard Mapping

Phase: 3d
Branch: v2.4.0-architecture
Commit before: a1faebd

Existing SettingsDependencyEngine file: src/settings_dependency_engine.py
Existing runtime config flags in config.py: use_translation_scheduler, use_sqlite_session_repository
Existing main.py scheduler construction: line 251 read from config.use_translation_scheduler
Existing main.py repository construction: line 254 read from config.use_sqlite_session_repository
Existing adapter construction: line 271
Existing SegmentAPI / dashboard history usage: dashboard.py line 1383 (read-only)
Existing controlled smoke config snapshot: controlled_smoke.py reads config defaults

Runtime enforcement gap: None — runtime directly reads config bools with no dependency validation

Files likely to modify:
  - src/runtime_settings_guard.py (NEW)
  - tests/test_runtime_settings_guard.py (NEW)
  - main.py (minimal: replace getattr with guard decision)

Files not to touch:
  - config, bootstrap, DMG, CI, transcriber, audio, model

Recommended runtime guard design:
  - settings_from_config(config) → dict
  - DependencyValidationResult → RuntimeSettingsDecision
  - allow_* booleans computed from ok + effective_settings
  - should_fallback_to_legacy: true if errors exist
  - mode: legacy | scheduler | scheduler_repository | invalid
