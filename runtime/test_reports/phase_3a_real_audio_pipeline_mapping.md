# Phase 3a — Real Audio Pipeline Mapping Report

Phase: 3a
Branch: v2.4.0-architecture
Commit before: b34e4e2
Commit after: (pending)

Audio input files:
  - audio_capture.py → AudioCapture class
  - Uses sounddevice library (sd.InputStream, sd.query_devices)

Audio device discovery files:
  - audio_capture.py: sd.query_devices(kind='input')
  - config.py: _find_blackhole_device() — auto-detect

Microphone capture path:
  AudioCapture(start) → _record_loop thread → sd.InputStream → generator()
  → main.py Pipeline.processing_loop: for audio_chunk in audio_gen

System audio / BlackHole path:
  - Config auto-detects BlackHole via sounddevice.query_devices
  - AudioCapture uses the resolved device_index for the stream
  - No separate system audio source class (Phase 1c InputSource not wired)

File audio path: none (not implemented)

Audio chunk type / shape:
  - np.float32 array, flat, variable length (~1600 samples at 16kHz/0.1s chunk)
  - From generator(): blocksize = samplerate * streaming_step_size

Audio chunk producer:
  - AudioCapture.generator() → sd.InputStream.read() → yield data.flatten()

Audio chunk consumer:
  - main.py Pipeline.processing_loop: for audio_chunk in audio_gen

ASR / transcriber file:
  - transcriber.py → Transcriber class
  - transcriber_pool.py → get_or_create_transcriber singleton

ASR input method:
  - Transcriber.transcribe(audio_data, prompt) → WhisperModel.transcribe()

ASR output type:
  - text: str (transcribed text from Whisper)

Partial result path:
  - Pipeline._process_partial_v3 → signals.update_text.emit(chunk_id, text, "")
  - PARTIAL does NOT go through TranslationAdapter

Stable result path:
  - Not yet produced in current pipeline
  - No dedicated stable handler exists

Final result path:
  - Pipeline._process_final_v3 → text from transcriber.transcribe()
  - → signals.update_text.emit(chunk_id, text, translated)
  - If trans_active and translation_adapter exists:
      translation_adapter.on_final_text(text, chunk_id)
  - Else:
      translate_executor.submit(_run_translation_safe, ...) (legacy)

TranslationAdapter entry point:
  - Pipeline._process_final_v3 line ~667:
    hasattr(self, 'translation_adapter') → adapter.on_final_text(text, chunk_id)
  - Adapter creates TranscriptEvent, submits to TranslationScheduler
  - _on_result → repo.apply_translation → overlay update

Feature flag interaction:
  - use_translation_scheduler: controls adapter creation + scheduler wiring
  - use_sqlite_session_repository: controls repository creation
  - Both false → legacy translate_executor path

Current tests covering audio: none (all use fake data)
Current tests missing audio:
  - No fake audio chunk → transcriber path test
  - No PARTIAL/STABLE emission test
  - No real FINAL → adapter integration test (only fake data smoke)

Files likely to modify in Phase 3b:
  - tests/test_audio_smoke_harness.py (NEW — fake audio → adapter → repo smoke)
  - src/audio_smoke_harness.py (NEW — optional harness)

Files not to touch in Phase 3a:
  - audio_capture.py, transcriber.py, transcriber_pool.py (no internal changes)
  - build_dmg.sh, setup_controller, setup_runtime, launcher, config
  - .github/workflows/build-dmg.yml

Recommended smoke design:
  - FakeAudioChunkBuilder → np.zeros(1600, float32) or fixture wav
  - FakeTranscriber → returns fixed text on transcribe()
  - extends controlled_smoke.py: step 3a = fake_audio_boundary
