Phase: 5b
Platform: Linux aarch64 (iSH)
OS: Alpine Linux
Python: 3.12.13

DMG build script: build_dmg.sh
CI workflow (GitHub Actions macOS): .github/workflows/build-dmg.yml

Note: x86_64 DMG can only be built on macOS GitHub Actions.
Linux platform (iSH) cannot run build_dmg.sh.
Tests run on Linux verify code correctness; actual DMG packaging requires CI.

Build entry point: .github/workflows/build-dmg.yml (macOS runner)
Build trigger: workflow_dispatch (manual)
Build artifact: RealtimeSubtitle-*.dmg
