# Phase 1f — Session Repository Mapping Report

Phase: 1f
Branch: v2.4.0-architecture
Commit before: 59212b5

## Existing session-related files
- src/session_state.py (SessionState + SessionStateEnum)
- main.py (Pipeline._session_generation, session_gen checks)
- src/translation_adapter.py (start_session, stop_session)
- src/translation_scheduler.py (_session_id, stop_session)

## Existing transcript-related files
- src/transcript_event.py (TranscriptEvent, TranscriptPhase, revision, session_id, segment_id)

## Existing storage mechanism
- None. Current state is entirely in-memory (overlay_window bubbles, pipeline dicts).
- No persistence across app restarts.

## Current session lifecycle owner
- Pipeline (main.py): _session_generation incremented on stop()
- TranslationAdapter: start_session/stop_session forwarded to TranslationScheduler

## Current transcript write path
- Pipeline._process_final_v3 → signals.update_text.emit(chunk_id, text, translated)
- EnhancedOverlayWindow.update_text → SubtitleBubble objects

## Current translation write-back path
- TranslationAdapter._on_result → self._on_update_text(chunk_id, orig, trans)
- Mapped back via chunk_id → segment_id lookup

## Existing shutdown/stop path
- Pipeline.stop(): audio.stop() → session_generation increment → adapter.stop_session()
- TranslationScheduler: stop_session() sets _stopped, cancels QUEUED jobs
- ThreadPoolExecutor: shutdown(wait=wait) in scheduler.shutdown()

## Files likely to modify
- src/session_repository.py (NEW)
- tests/test_session_repository_sqlite.py (NEW)
- config.py (feature flag)
- src/translation_adapter.py (optional: wire repository for write-back)

## Files not to touch
- build_dmg.sh, setup_controller.py, setup_runtime.py, launcher.py
- transcriber.py, transcriber_pool.py, audio_capture.py, model_manager.py
- .github/workflows/build-dmg.yml
- overlay_window.py, enhanced_overlay_window.py

## Recommended repository design
- SQLiteSessionRepository backed by sqlite3 stdlib
- Self-contained: initialize(), close(), create_session(), upsert_original_segment(),
  apply_translation(), get_latest_segment(), list_segments()
- Test path: :memory: or tmp_path
- Runtime path: ~/Library/Application Support/RealtimeSubtitle/realtime_subtitle.sqlite3
