# Realtime Subtitle — Final Validation Report

**Build**: v2.2.7 (candidate)
**Date**: 2026-06-12
**Commit**: TBD

## Gate A: Static & Import

| Check | Result |
|-------|--------|
| `python3 -m py_compile main.py` | ✅ |
| `python3 -m py_compile dashboard.py` | ✅ |
| `python3 -m py_compile enhanced_overlay_window.py` | ✅ |
| `python3 -m py_compile translation_engine.py` | ✅ |
| `python3 -m py_compile transcriber.py` | ✅ |
| `python3 -m py_compile permission_guide.py` | ✅ |
| `python3 -m py_compile diagnostics.py` | ✅ |
| `python3 -m py_compile config.py` | ✅ |
| `python3 -m py_compile model_manager.py` | ✅ |
| `python3 -m py_compile audio_capture.py` | ✅ |
| `sh -n build_dmg.sh` | ✅ |
| `requirements-core.txt` multiline format | ✅ (13 lines) |
| `requirements.txt` multiline format | ✅ (13 lines) |
| CI format checks | ✅ |

## Gate B: Automated Testing (CI)

| Test | Result |
|------|--------|
| Core dependency install (simulated first-launch) | ✅ |
| Core imports (PyQt6, numpy, sounddevice, faster_whisper) | ✅ |
| Bundle fingerprint match (utterance_id present) | ✅ |
| No pre-built venv | ✅ |
| No builder paths (/Users/runner) | ✅ |
| Portable Python present | ✅ |

## Gate C: Architecture Changes (v2.2.7)

### State machine
- Added `pipeline_started` signal — Dashboard only shows "Running" after receipt
- Added 10s startup timeout — shows "Start failed" if pipeline_started never fires
- `_cleanup_in_progress` properly set to True at finally entry
- Diagnostics shows separate states: PipelineLoop, failed flag, cleanup state

### Pipeline start order
1. Create pipeline + signals
2. Connect all lifecycle signals (pipeline_failed, cleanup_finished, pipeline_started)
3. Create overlay (start_pipeline=False)
4. `pipeline.start()` — AFTER all connections
5. Wait for pipeline_started signal
6. Show "Running..."

### Cleanup lifecycle
- `_cleanup_in_progress = True` at finally entry
- ASR worker alive check before cleanup_finished emission
- `cleanup_finished(True/False, message)`
- Dashboard handles both success and failure

## Gate D: Known Limitations

| Item | Status |
|------|--------|
| Real DMG install test | NOT TESTED (requires macOS) |
| Permission UI light/dark mode | Code fix applied, not visually verified |
| Microphone permission flow | Code present, not tested on clean Mac |
| Tab truncation at 750px | Code fix applied, not visually verified |
| Real audio recognition test | NOT TESTED (requires macOS) |
| Translation end-to-end | NOT TESTED (requires API key) |
| App quit no residual process | NOT TESTED (requires macOS) |

## Gate E: Build Consistency

To be verified by CI:
- tag == commit SHA
- DMG main.py fingerprint matches source
- version.py injected at build time
- app.log shows correct version on startup
