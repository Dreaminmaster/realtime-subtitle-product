# Phase 1g — Segment API Contract

SessionView fields: session_id, status, created_at, updated_at, closed_at, source_language, target_language, metadata
SegmentView fields: session_id, segment_id, revision, status, original_text, translated_text, translation_status, created_at, updated_at, finalized_at, translated_at
TranscriptSnapshot fields: session, segments, original_text, translated_text, bilingual_text

list_sessions: returns list[SessionView], latest first
get_session: returns SessionView or None
list_segments: returns list[SegmentView], ordered by updated_at DESC, revision DESC
get_latest_segment: returns SegmentView with highest revision or None
get_latest_transcript: assembled from latest revision per segment_id, original_text only
get_translated_transcript: assembled from latest revision per segment_id, DONE→translated, FAILED→original, missing→original
get_session_snapshot: returns TranscriptSnapshot with all three transcript forms
recover_last_session: active→latest updated→None
export_transcript: txt (header+bilingual) or json (session+segments+transcripts), raises ValueError if missing
Error behavior: missing session→None (get), raises ValueError (export), RepositoryError after close
