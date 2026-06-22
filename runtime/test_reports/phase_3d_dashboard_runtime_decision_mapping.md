# Phase 3d-dashboard — Mapping

Phase: 3d-dashboard
Branch: v2.4.0-architecture
Commit before: fd50913

RuntimeSettingsGuard file: src/runtime_settings_guard.py
RuntimeSettingsDecision fields: ok, mode, allow_translation_scheduler, allow_sqlite_repository, allow_segment_history, allow_segment_export, allow_segment_overlay, should_fallback_to_legacy, reason, issues, recommended_changes
main.py enforcement point: line 249: RuntimeSettingsGuard().evaluate(settings_from_config(config))
dashboard.py diagnostics tab structure: _arch_status → _history_status ← insert here
Existing Architecture Status display: QLabel with _refresh_arch_status()
Existing history status display: QLabel with _refresh_history_status()
Recommended runtime decision display point: between _arch_status and _history_status
Files likely to modify: dashboard.py
Files not to touch: main.py, config.py, bootstrap, DMG, CI, transcriber
