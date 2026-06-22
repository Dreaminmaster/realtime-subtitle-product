# Phase 3c — ASR Adapter Mapping

Phase: 3c
Branch: v2.4.0-architecture
Commit before: ea3078b

Existing transcriber files: transcriber.py, transcriber_pool.py
Existing ASR output shapes: str (text only)
Existing partial path: main.py Pipeline._process_partial_v3
Existing stable path: none (TranscriptPhase.STABLE reserved, not produced)
Existing final path: main.py Pipeline._process_final_v3
Existing FINAL bridge: hasattr(self,'translation_adapter') → adapter.on_final_text
Existing TranscriptEvent model: src/transcript_event.py
Existing revision model: adapter maintains _revision_by_segment per chunk_id
Existing segment_id model: adapter assigns uuid per chunk_id
Existing session_id model: adapter reads from scheduler._session_id
Phase 3b WAV smoke file: src/audio_file_smoke.py

Recommended ASR adapter design:
  - NormalizedASRResult: session_id, segment_id, revision, status(PARTIAL/STABLE/FINAL), text
  - ASRResultAdapter: normalize(raw_result), normalize_many(raw_results)
  - Forward bridge: forward_normalized_asr_to_translation_adapter(result, adapter)

Files likely to modify: none (new file)
Files not to touch: audio_capture, transcriber, main.py, config, bootstrap, DMG
