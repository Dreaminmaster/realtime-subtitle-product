# Phase 2b — History ViewModel Contract

Types:
  HistorySessionItem: session_id, status, created_at, updated_at, closed_at, label
  HistorySegmentItem: session_id, segment_id, revision, status, original_text, translated_text, translation_status
  HistoryDashboardViewModel: available, title, summary, sessions, selected_session_id, segments, original_text, translated_text, bilingual_text, export_preview_txt, export_preview_json, messages

Behaviors:
  segment_api is None → unavailable, "enable SQLite repository"
  list_sessions error → unavailable, error message
  no sessions → available, "No transcript sessions"
  recover_last_session → priority over first session
  get_session_snapshot error → message added, no crash
  export error → message added, preview empty
  all read-only — never writes to repository

Side effects: none
Serializable: yes
Dashboard ready: yes (needs Phase 2b-dashboard for UI wiring)
