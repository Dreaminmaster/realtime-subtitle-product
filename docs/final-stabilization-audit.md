# Realtime Subtitle — Final Stabilization Audit

**Date**: 2026-06-12
**Base commit**: 5315f0e (v2.2.6)
**Scope**: Full system review, stabilization, verification

---

## 1. Architecture Overview

### Objects

```
Dashboard (Qt main thread)
├── Pipeline
│   ├── AudioCapture (separate callback thread)
│   ├── Transcriber (faster-whisper, loaded in main/ASR thread)
│   ├── Translation Engine (online/local/off)
│   ├── PriorityQueue ASR Scheduler (1 worker thread)
│   │   ├── FINAL tasks (priority 0)
│   │   └── PARTIAL tasks (priority 1, seq-superseded)
│   ├── Utterance lifecycle: _utt_lifecycle dict
│   ├── Session token: _session_generation
│   ├── Thread: PipelineLoop
│   └── Thread: ASR Worker
├── Overlay Window (EnhancedOverlayWindow, main thread)
├── Model Manager
├── Diagnostics
└── Permission Guide
```

### Signal Map

| Signal | Emitter | Receiver | Purpose |
|--------|---------|----------|---------|
| `update_text(int, str, str)` | Pipeline ASR/Translate | Overlay | Show subtitle bubble |
| `audio_status(str, float)` | Pipeline processing_loop | Overlay | Listening/Silent indicator |
| `pipeline_failed(str)` | Pipeline except handler | Dashboard | Crash notification |
| `pipeline_cleanup_finished(bool, str)` | Pipeline finally block | Dashboard | Cleanup result |
| `stop_requested` | Overlay stop button | Pipeline.stop() | User stop |
| `style_changed` | Overlay | Dashboard | Style sync |
| `ready(object)` | StartupWorker | Dashboard | Pipeline ready |
| `failed(str)` | StartupWorker | Dashboard | Setup failure |

### Thread Map

| Thread | Created by | Lifecycle | UI access |
|--------|-----------|-----------|-----------|
| Qt Main | QApplication | App lifetime | ✅ |
| PipelineLoop | Pipeline.start() | Until stop/exception | ❌ (signals only) |
| ASR Worker | PipelineLoop | Until sentinel | ❌ (signals only) |
| Audio callback | AudioCapture | While recording | ❌ |
| Translation executor | PipelineLoop | ThreadPoolExecutor | ❌ (signals only) |
| StartupWorker | Dashboard.on_start() | One-shot | ❌ (signals only) |

### Critical Lifecycle Flow

```
Dashboard.on_start()
  → StartupWorker.run()
    → create_pipeline() [NO UI!]
      → Pipeline.__init__()
        → Transcriber init + warmup
        → Translation engine set_mode
      → signals = WorkerSignals()
      → return pipeline, signals
  → ready signal emitted
  → _on_startup_ready() ON MAIN THREAD:
    → self.pipeline = pipeline
    → connect signals (pipeline_failed, cleanup_finished)
    → create_and_show_overlay(start_pipeline=False)
    → pipeline.start()  ← LAST STEP
```

---

## 2. State Machine Design

```
IDLE ──[Launch]──> STARTING ──[pipeline_started]──> RUNNING
RUNNING ──[stop/crash]──> STOPPING/DRAINING
STOPPING ──[cleanup OK]──> IDLE
STOPPING ──[cleanup timeout]──> CLEANUP_FAILED
CLEANUP_FAILED ──[retry/quit]──> IDLE/EXIT
RUNNING ──[exception]──> FAILED ──[cleanup OK]──> IDLE
```

### State Transitions

| From | Trigger | To | UI State |
|------|---------|-----|----------|
| IDLE | Click Launch | STARTING | "Initializing..." / Launch disabled |
| STARTING | pipeline_started signal | RUNNING | "Running..." / Stop visible |
| RUNNING | Stop clicked | STOPPING | "Stopping..." / Stop disabled |
| STOPPING | Cleanup complete | IDLE | "Ready" / Launch enabled |
| RUNNING | Exception | FAILED | "Pipeline Error..." / Launch disabled |
| FAILED | cleanup_finished(true) | IDLE | "Pipeline Error — retry" / Launch enabled |
| FAILED | cleanup_finished(false) | CLEANUP_FAILED | "Cleanup failed" / Launch disabled |

---

## 3. Confirmed Issues (Pre-fix)

### P0-1: Pipeline never actually started in v2.2.6
- `create_and_show_overlay` accepts `start_pipeline=False`
- Dashboard calls it with this flag
- But pipeline.start() must be explicitly called after signal connection
- **Status**: Will verify in final code review

### P0-2: No pipeline_started signal
- Dashboard shows "Running..." immediately without actual start confirmation
- If audio device fails, UI still shows Running
- **Fix**: Add pipeline_started signal, only show Running after confirmation

### P0-3: Missing cleanup_in_progress transition
- `_cleanup_in_progress` field exists but never set to True
- Only cleared to False at end of finally
- **Fix**: Set to True at finally entry

### P0-4: Permission card visibility in light mode
- QDialog background forcing #1e1e2e already in v2.2.4
- Need to verify with actual macOS light mode test

### P0-5: Diagnostic completeness
- Missing: ASR worker alive (separate from PipelineLoop)
- Missing: translation executor state
- Missing: model path verification
- **Fix**: Extend diagnostics output

---

## 4. Modification Plan

### Phase 1: State machine + pipeline_started signal
- Add `pipeline_started = pyqtSignal()`
- Emit after audio generator succeeds first chunk
- Dashboard: only show "Running" on pipeline_started
- If pipeline_started never arrives, show timeout error

### Phase 2: Cleanup lifecycle
- Set `_cleanup_in_progress = True` at finally entry
- Expose via diagnostics
- Ensure cleanup_finished(bool) emission reflects reality

### Phase 3: Full Gate testing
- Gate A: py_compile + import
- Gate B: Unit tests (lifecycle, guards, state transitions)
- Gate C: DMG real install test
- Gate D: Consistency check

---

## 5. Acceptance Criteria

All 13 gates from the specification must pass before release.

## 6. Known Gaps (BLOCKED / NOT TESTED)

- Real DMG install test cannot be done in iSH environment
- macOS permissions testing requires physical Mac
- Audio device testing requires physical Mac
- Light/dark mode visual testing requires physical Mac
- These items are marked **NOT TESTED** pending user Mac testing
