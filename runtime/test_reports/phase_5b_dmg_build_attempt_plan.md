Phase: 5b
Platform: macOS only (GitHub Actions)

Build steps (recommended):
  1. Push v2.4.0-architecture to GitHub
  2. Go to https://github.com/Dreaminmaster/realtime-subtitle-product/actions/workflows/build-dmg.yml
  3. Click "Run workflow", enter version: 2.4.0-alpha1
  4. Wait for DMG artifact
  5. Download DMG

Post-build smoke (manual, on Mac):
  1. Open DMG, drag app to /Applications
  2. Launch: open /Applications/RealtimeSubtitle.app (right-click → Open)
  3. Verify dashboard → Diagnostics tab shows Architecture Status, Runtime Decision, Transcript History
  4. Verify no crash on Launch Translator, Stop
  5. (Optional) Enable feature flags → verify new architecture

Do NOT: publish GitHub Release until manual smoke passes
Do NOT: merge to main until manual smoke passes
