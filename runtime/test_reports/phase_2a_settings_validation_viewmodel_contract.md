# Phase 2a — Settings Validation ViewModel Contract

Fields:
  SettingsValidationMessage: code, severity, message, setting, recommended_changes
  SettingsValidationViewModel: ok, title, summary, mode_label, messages, effective_settings, recommended_changes, can_use_new_architecture, can_use_history, can_use_export

Behaviors:
  Legacy: false/false → ok, Lean legacy mode, no capabilities
  Scheduler only: true/false → ok, new arch true, history false
  Both on: true/true → ok, all capabilities true
  Repository only: false/true → error, no capabilities, recommended scheduler=true

Dependencies:
  History → repo + scheduler
  Export → repo + scheduler
  Overlay → warning if repo off

Recommended changes: display-only, never auto-applied
Side effects: none
Serializable: yes
Dashboard display: QLabel with HTML, mode/errors/warnings/recommended
