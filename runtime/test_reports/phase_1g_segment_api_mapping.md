# Phase 1g — Segment API Mapping Report

Phase: 1g
Branch: v2.4.0-architecture
Commit before: 0e1c6da
Repository file: src/session_repository.py
Existing read methods: get_session, list_sessions, get_latest_segment, list_segments
Existing write methods: create_session, close_session, upsert_original_segment, apply_translation, mark_translation_failed
Session fields: session_id, created_at, updated_at, closed_at, status, source_language, target_language, metadata_json
Segment fields: session_id, segment_id, revision, status, original_text, translated_text, translation_status, created_at, updated_at, finalized_at, translated_at
Current active session concept: none (not yet implemented in repository layer)
Current export support: none
Files likely to modify: none (new file only)
Files not to touch: main.py, config.py, adapter, scheduler, repository, all protected files
Recommended Segment API design: thin read-only wrapper over SQLiteSessionRepository with View types
