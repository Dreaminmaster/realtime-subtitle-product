# Phase 3a — Audio Smoke Design

Phase: 3a
Branch: v2.4.0-architecture

Design:
  - FakeAudioChunkBuilder produces np.float32 arrays
  - FakeTranscriber returns fixed text per chunk
  - FakeTranslator returns prefixed text
  - Pipeline boundary: adapter.on_final_text(text, chunk_id)
  - Repository: tmp sqlite path
  - SegmentAPI reads back

Not in Phase 3a:
  - No real microphone
  - No real Whisper
  - No real API

Implementation: src/audio_smoke_harness.py
Tests: tests/test_audio_smoke_harness.py
