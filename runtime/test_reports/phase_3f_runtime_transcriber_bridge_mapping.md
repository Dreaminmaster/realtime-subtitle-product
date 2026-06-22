# Phase 3f — Runtime Transcriber Bridge Mapping

Phase: 3f, Branch: v2.4.0-architecture, Commit before: afc9960

Existing Pipeline class: main.py Pipeline(line 188)
Existing transcriber output/callback: _process_final_v3(line 619)/_process_partial_v3(line 567)
Existing PARTIAL path: _process_partial_v3 → signals.update_text.emit(chunk_id,text,"")
Existing STABLE path: none(# not produced)
Existing FINAL path: _process_final_v3 → signals.emit + adapter.on_final_text(hasattr check)
Existing TranslationAdapter construction: main.py line 252-280(inside Pipeline.__init__)
Existing RuntimeSettingsGuard decision: self._runtime_decision(main.py:250)
Existing config flags: use_translation_scheduler, use_sqlite_session_repository(config.py:102-108)
Existing transcriber bridge file: src/transcriber_output_bridge.py
Current gap: no runtime wiring of TranscriberOutputBridge into main.py
Files likely to modify: src/settings_dependency_engine.py, src/runtime_settings_guard.py, src/runtime_decision_formatter.py, config.py, tests
Files not to touch: build_dmg.sh, setup_controller, setup_runtime, launcher, transcriber.py, transcriber_pool.py, audio_capture.py, model_manager.py, .github/workflows/build-dmg.yml
Recommended runtime wiring plan: Phase 3f only expose bridge hook + test; Phase 3g switches real callback
