# Phase 2b-dashboard — History Display Contract

Section: diagnostics tab, below Architecture Status
Displayed: status, title, summary, sessions, selected session, original/translated/bilingual transcript, segments, export preview lengths, messages
Unavailable: "Unavailable" with summary + messages
Error: caught, fallback text displayed
Read-only: YES
Config: reads use_sqlite_session_repository (flag off → unavailable)
Repository: opened + closed within adapter call, never leaked
Escaping: html.escape() on all user text
Truncation: 1200 chars per transcript, 10 sessions, 20 segments
Export preview: shows TXT/JSON byte lengths only, not full content
Dashboard integration: QLabel + _refresh_history_status()
Side effect policy: repository opened+closed per call, no long-lived connection
