# Phase 1e — Pipeline Mapping Report

## ASR event source
`main.py` → `Pipeline._process_final_v3()` (line ~619)
- AudioCapture → transcriber.transcribe() → text
- Currently emits `signals.update_text.emit(chunk_id, text, translated_text)`
- Chunk_id = utterance_id (monotonic integer per session)

## Subtitle event model
- Current: tuple (chunk_id, text, translated_text) via PyQt signals
- v2.4: TranscriptEvent with session_id, segment_id, utterance_id, revision, phase
- Phase: current pipeline only produces FINAL (PARTIAL is suppressed/not wired)
- STABLE is reserved — not produced by current pipeline

## Transcript write point
- `signals.update_text.emit(chunk_id, text, translated_text)` → `EnhancedOverlayWindow.update_text()`
- Overlay stores in `self._bubbles` list (SubtitleBubble objects)
- No persistent transcript store yet (SessionRepository is Phase 1e+)

## Current translation call point
- `_process_final_v3` line ~662: `translate_executor.submit(self._run_translation_safe, text, chunk_id, session_gen)`
- `_run_translation_safe` calls `self.translation_engine.translate(text)`
- Result emitted via `signals.update_text.emit(chunk_id, text, translated)`

## Overlay update path
- `signals.update_text.connect(window.update_text)` (line ~726)
- window.update_text: finds or creates SubtitleBubble, updates text/translation

## Session lifecycle owner
- `Pipeline._session_generation` — incremented on each stop()
- Session ID: currently `str(id(self))` — one session per Pipeline instance
- `_process_final_v3` checks `session_gen` to discard stale ASR results

## Shutdown lifecycle owner
- `Pipeline.stop()` → `self.running = False` → `audio.stop()` → `session_generation += 1`
- No explicit scheduler shutdown (translator uses `translate_executor.shutdown()`)

## Files likely to modify (Phase 1e)
- `main.py` — Pipeline.__init__, _process_final_v3, stop()
- `src/translation_adapter.py` — bridge layer (new)
- `config.py` — feature flag (optional)

## Files not to touch
- build_dmg.sh
- setup_controller.py / setup_runtime.py / launcher.py
- transcriber.py / transcriber_pool.py
- audio_capture.py
- model_manager.py
- overlay_window.py / enhanced_overlay_window.py
- .github/workflows/build-dmg.yml
