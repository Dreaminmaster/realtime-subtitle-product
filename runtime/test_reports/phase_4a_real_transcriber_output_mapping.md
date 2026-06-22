# Phase 4a — Real Transcriber Output Mapping

Phase: 4a, Branch: v2.4.0-architecture, Commit before: 9f37141

Existing transcriber files: transcriber.py, transcriber_pool.py
Transcriber class: Transcriber(backend, model_size, device, compute_type, language).transcribe(audio_data, prompt)
Existing output: plain text (str), stripped, hallucination-filtered
Internal WhisperModel output: (segments, info) → segments[].text joined
Existing partial/interim: not produced (pipeline calls transcribe once per FINAL)
Existing final: text passed to _process_final_v3
Existing Pipeline bridge hook: _handle_transcriber_output_via_bridge(raw)
Real output candidates: plain str, dict{"text":"...","status":"FINAL"}, dict{"transcript":"...","is_final":True}, segments list, object

Recommended fixture strategy: create fixtures that match what real pipeline could produce at the bridge entry point
