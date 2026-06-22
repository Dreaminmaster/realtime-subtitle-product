# Phase 3e — Transcriber Output Mapping

Phase: 3e
Branch: v2.4.0-architecture
Commit before: 82cbdee
Existing transcriber files: transcriber.py, transcriber_pool.py, main.py (Pipeline._process_*_v3)
Existing transcriber classes: Transcriber class with _init_whisper, _init_mlx, _init_funasr
Existing raw transcriber output: WhisperModel.transcribe returns (segments, info), text extracted in _process_final_v3
Existing partial output path: Pipeline._process_partial_v3 → signals.update_text.emit(chunk_id, text, "")
Existing stable output path: none (TranscriptPhase.STABLE reserved, not produced)
Existing final output path: Pipeline._process_final_v3 → signals.update_text.emit + adapter.on_final_text
Existing main.py FINAL bridge: hasattr(self,'translation_adapter') → adapter.on_final_text(text, chunk_id)
Existing ASRResultAdapter: src/asr_result_adapter.py
Existing forward bridge: forward_normalized_asr_to_translation_adapter in asr_result_adapter.py
Existing audio smoke files: src/audio_smoke_harness.py, src/audio_file_smoke.py
Existing runtime guard: src/runtime_settings_guard.py, integrated in main.py line 249
Files likely to modify: none (new files only)
Files not to touch: main.py, transcriber.py, transcriber_pool.py, audio_capture, config, DMG, CI
Recommended bridge design: TranscriberOutputBridge → ASRResultAdapter → forward → TranslationAdapter
