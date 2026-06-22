# Phase 3b — WAV File Audio Mapping

Phase: 3b
Branch: v2.4.0-architecture
Commit before: fdb2a4f

Existing audio file support: none (wave module not used previously)
Existing audio chunk format: np.float32, from sounddevice InputStream
Existing sample rate assumptions: 16000
Existing channel assumptions: 1
Existing dtype assumptions: float32
AudioCapture file: audio_capture.py
Transcriber file: transcriber.py
Phase 3a harness file: src/audio_smoke_harness.py

WAV fixture design: generated 16kHz mono 16-bit PCM sine wave
Loader design: stdlib wave + struct, readframes with chunk size

Files likely to modify: none (all new files)
Files not to touch: audio_capture.py, transcriber.py, main.py, config.py, bootstrap, DMG, CI
