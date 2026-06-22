# Phase 3g — main.py Bridge Hook Mapping

Phase: 3g, Branch: v2.4.0-architecture, Commit before: 7fba5c4
Pipeline class location: main.py line 188
RuntimeSettingsGuard usage: main.py line 249
TranslationAdapter construction point: main.py line 273
Repository construction point: main.py line 256
Existing FINAL path: _process_final_v3 → signals.update_text.emit + adapter.on_final_text via translate_executor
Existing transcriber output path: _process_final_v3 / _process_partial_v3
Existing bridge factory: src/runtime_transcriber_bridge_adapter.py
Current main.py gap: no TranscriberOutputBridge instantiation in Pipeline.__init__
Files likely to modify: main.py
Files not to touch: build_dmg.sh, setup_*, launcher, transcriber*, audio_capture, model_manager, config.py, CI
Recommended minimal hook design: Pipeline.__init__ creates self.transcriber_output_bridge via factory + adds _handle_transcriber_output_via_bridge method
