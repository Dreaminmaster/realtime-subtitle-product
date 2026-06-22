# Phase 1h — Settings Dependency Engine Contract

DependencyIssue: code, severity, message, setting, depends_on, recommended_changes
DependencyValidationResult: ok, issues, effective_settings, recommended_changes, has_errors, has_warnings

Rules:
  legacy: both flags off → ok
  scheduler without repo → ok
  repo requires scheduler → error (code: repository_requires_scheduler)
  both on → ok
  history requires repo → error (code: history_requires_repository)
  export requires repo → error (code: export_requires_repository)
  overlay segment api without repo → warning (code: overlay_segment_api_requires_repository)
  unknown settings → info
  non-bool normalization: effective_settings are bool, input never mutated
  recommended_changes: suggestions only, never auto-applied

Error:   blocks ok, recommends changes
Warning: does not block ok, informational
Info:    silent, no action required

Side-effect policy: NO filesystem, NO network, NO repository creation, NO scheduler start
