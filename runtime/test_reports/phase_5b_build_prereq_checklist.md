Phase: 5b
Ready for DMG build attempt: YES

Prerequisites:
- [x] Full pytest 489/489 PASSED
- [x] 0 skipped / 0 failed / 0 flaky
- [x] HEAD == origin/v2.4.0-architecture
- [x] Protected files unchanged (build_dmg.sh, setup_*, transcriber, etc)
- [x] config.py changes: feature flags only (ALL default false)
- [x] main.py changes: guarded, flag-gated
- [x] No real dependency on Whisper/faster-whisper in test suite
- [x] No real microphone access in test suite
- [x] No real API calls in test suite

Build entry: .github/workflows/build-dmg.yml (macOS runner)
Trigger: workflow_dispatch with version input
