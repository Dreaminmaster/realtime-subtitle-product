# Phase 3a — Manual Real Audio Test Plan

Phase: 3a
Branch: v2.4.0-architecture
Commit: fdb2a4f

This plan describes manual tests to be run on a real Mac by the user.
Automated tests are provided separately — these are NOT executable in CI.

## Microphone input manual test
1. Open the app with default microphone input
2. Speak 2-3 short phrases
3. Observe: overlay shows original text quickly, no crash
4. Observe: overlay shows translated text (if API configured) or "(translating...)" placeholder
5. Stop recording via Dashboard → observe clean shutdown

Expected: original text appears immediately, no HuggingFace download, no crash

## System audio / BlackHole manual test
1. Install BlackHole if not present
2. Set audio input device to BlackHole in config.ini
3. Play some audio from another app
4. Observe: overlay captures system audio
5. Stop recording

Expected: audio captured from system, transcribed

## Stop / restart capture manual test
1. Start recording → Stop → Start again
2. Observe: no duplicate signals, clean state
3. Repeat 3 times

Expected: no crash, no stale session leakage

## Feature flags ON manual test
1. Set REALTIME_SUBTITLE_USE_TRANSLATION_SCHEDULER=true
2. Set REALTIME_SUBTITLE_USE_SQLITE_SESSION_REPOSITORY=true
3. Start app, speak, stop
4. Open Diagnostics tab → Architecture Status section
5. Observe: "Scheduler + persistent transcript" or similar

Expected: ARCHITECTURE STATUS shows new mode label

## Feature flags OFF manual test
1. Set both flags to false
2. Start app, speak, stop
3. Open Diagnostics tab → Architecture Status section
4. Observe: "Legacy runtime" or similar

Expected: legacy behavior unchanged, app still works

## Logs to collect
- ~/Library/Logs/RealtimeSubtitle/app.log
- ~/Library/Logs/RealtimeSubtitle/launcher.log

## Expected results
- No HuggingFace download (bundled model used)
- ASR_MODEL_READY in log
- dependency_source=wheelhouse
- network_required=false
- No crash on stop

## Failure signs
- HuggingFace download shown in log → Bootstrap regression
- "exit code 1" without error message → diagnostic regression
- Crash on second launch → session state bug
- Stale translation overwriting new segment → revision bug
