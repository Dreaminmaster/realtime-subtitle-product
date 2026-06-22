# Phase 3e-hardening Mapping

Phase: 3e-hardening
Branch: v2.4.0-architecture
Commit before: db4bab2

TranscriberOutputBridge file: src/transcriber_output_bridge.py
ASRResultAdapter file: src/asr_result_adapter.py

Current exception behavior:
  - ASRResultAdapter.normalize: catches nothing → can raise on bad input
  - forward_normalized_asr_to_translation_adapter: catches nothing → adapter exceptions propagate

Current bridge error boundary:
  - TranscriberOutputBridge.handle_raw_output wraps normalize in try/except
  - BUT: if forward raises, bridge catches it too
  - Currently handle_raw_output catches fwd exception and wraps in ok=False result ✅

Current bridge stats errors counter: yes (errors field)
WAV file smoke file: src/audio_file_smoke.py
Existing WAV smoke functions: run_wav_file_smoke, iter_wav_chunks, WavFixtureFakeTranscriber
Missing WAV bridge smoke: YES (no test specifically tests the bridge path with wav)

Files likely to modify:
  - src/transcriber_output_bridge.py (hardening)
  - tests/test_transcriber_output_bridge.py (new tests)
  - tests/test_audio_file_smoke.py (new WAV bridge smoke)

Files not to touch: main.py, transcriber.py, config.py, DMG, CI
