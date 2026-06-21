# Phase 1e — Translation Scheduler Pipeline Integration Report

## Metadata
- Phase: 1e
- Branch: v2.4.0-architecture
- Commit before: f2cee46 (Phase 1d)
- Commit after: (pending)
- Files changed: 5
- Files added: 4
- Feature flag: REALTIME_SUBTITLE_USE_TRANSLATION_SCHEDULER / config.use_translation_scheduler
- Default: false (legacy translate_executor path unchanged)

## Pipeline entry point
`main.py` → `Pipeline._process_final_v3()` → `translation_adapter.on_final_text(text, chunk_id)`
PARTIAL events go through `_process_partial_v3()` which does NOT touch the scheduler.

## Scheduler creation point
`main.py` → `Pipeline.__init__()` — guarded by `config.use_translation_scheduler`

## Scheduler shutdown point
`main.py` → `Pipeline.stop()` → `translation_adapter.stop_session()`

## Translation result write-back point
`TranslationAdapter._on_result()` → `self._on_update_text(chunk_id, original_text, translated_text)`
→ `signals.update_text.emit()` → `EnhancedOverlayWindow.update_text()`

## Tests added
- `tests/test_scheduler_pipeline_integration.py` (12 tests)
- `tests/test_translation_adapter.py` (8 tests, Phase 1e earlier)

## Tests passed
174/174 (all existing + new)

## Coverage
1. FINAL enters scheduler: ✅
2. PARTIAL ignored: ✅
3. STABLE ignored: ✅
4. Translation non-blocking: ✅
5. Stale revision discarded: ✅
6. Stale session discarded: ✅
7. Translator failure safe: ✅
8. Callback crash safe: ✅
9. Shutdown safe: ✅
10. Feature flag off preserves old behavior: ✅

## Files changed
- `main.py` — feature flag guard in __init__, adapter wiring in _process_final_v3, stop_session in stop()
- `config.py` — use_translation_scheduler feature flag
- `src/translation_adapter.py` — bridge layer (new)
- `tests/test_translation_adapter.py` — 8 tests (new)
- `tests/test_scheduler_pipeline_integration.py` — 12 tests (new)

## Files not touched
- build_dmg.sh, setup_controller.py, setup_runtime.py, launcher.py
- transcriber.py, transcriber_pool.py, audio_capture.py, model_manager.py
- .github/workflows/build-dmg.yml

## Known risks
- Feature flag is OFF by default (env var or config.ini) — no production impact
- Pipeline stop() does not call scheduler.shutdown(wait=True) — executor threads
  may linger briefly after stop.  Process exit cleans them up.
- TranslationAdapter assumes chunk_id maps 1:1 to segment_id — fine for
  current pipeline where each chunk is a unique utterance.

## Not done in this phase
- SessionRepository integration (Phase 1e next)
- Segment API integration
- STABLE phase production
- UI changes

## Next recommended phase
Phase 1f: SessionRepository (SQLite) + persistence of transcript events
