# Realtime Subtitle — Acceptance Test Plan

**Version**: v2.2.7-rc
**Date**: 2026-06-12
**Commit**: 6d210b7
**DMG**: RealtimeSubtitle-2.2.7.dmg
**Status**: Release Candidate — ALL Gates must pass before Final

## Pre-flight

| Step | Action | Expected |
|------|--------|----------|
| 0.1 | Delete old app: `rm -rf /Applications/RealtimeSubtitle.app` | No app left |
| 0.2 | Delete old env: `rm -rf "$HOME/Library/Application Support/RealtimeSubtitle"` | Clean state |
| 0.3 | Delete old logs: `rm -rf "$HOME/Library/Logs/RealtimeSubtitle"` | Clean state |
| 0.4 | Download DMG from GitHub Releases | File: `RealtimeSubtitle-2.2.7.dmg` |
| 0.5 | Verify SHA-256: `shasum -a 256 RealtimeSubtitle-2.2.7.dmg` | (record in report) |

---

## Gate 1: Install + First Launch

| Step | Action | Expected | Result |
|------|--------|----------|--------|
| 1.1 | Mount DMG | DMG opens with App + Applications link + Drag prompt | |
| 1.2 | Drag to Applications | App copies successfully | |
| 1.3 | Right-click Open (not double-click) | Gatekeeper dialog → Open | |
| 1.4 | First launch setup | Terminal window shows "Realtime Subtitle — First Launch Setup" | |
| 1.5 | Dependency install | Shows "Installing dependencies... DO NOT close this window" | |
| 1.6 | Setup complete | Shows "Setup complete! Starting app..." then window closes | |
| 1.7 | App opens | Permission Setup dialog or Dashboard appears | |
| 1.8 | Log file | `~/Library/Logs/RealtimeSubtitle/launcher.log` exists, no ERRORs | |
| 1.9 | Setup marker | `~/Library/Application Support/RealtimeSubtitle/.setup_complete` exists | |

---

## Gate 2: Permission Setup

| Step | Action | Expected | Result |
|------|--------|----------|--------|
| 2.1 | Dialog visible | Permission Setup dialog with 3 cards + Skip/Continue | |
| 2.2 | Text readable (dark mode) | Title, reason, description, button text all visible | |
| 2.3 | Text readable (light mode) | Switch macOS to Light appearance, all text still readable | |
| 2.4 | Microphone card | Shows "Required for real-time speech recognition" | |
| 2.5 | Click Continue → | Dashboard opens | |
| 2.6 | Re-launch: `rm config.ini`, re-open | Permission Setup appears again | |

---

## Gate 3: Dashboard UI

| Step | Action | Expected | Result |
|------|--------|----------|--------|
| 3.1 | Window title | "Realtime Subtitle — Control Center" | |
| 3.2 | Home tab | Shows "Ready" + "▶ Launch" button | |
| 3.3 | Audio tab | Microphone and built-in System Audio are available; no virtual driver required | |
| 3.4 | Devices tab | Full name visible (not "Devic...") | |
| 3.5 | Transcript tab | ASR backend, model selection | |
| 3.6 | Translate tab | API Key, Base URL, model, Test Connection | |
| 3.7 | Models tab | List of whisper models, "Download" buttons | |
| 3.8 | Style tab | Font size, colors, opacity, display mode | |
| 3.9 | Diag tab | Run diagnostics button | |
| 3.10 | Tab tooltips | Hover each tab → shows full name | |
| 3.11 | Window width | All tabs visible without truncation (750px min) | |

---

## Gate 4: First Utterance

| Step | Action | Expected | Result |
|------|--------|----------|--------|
| 4.1 | Click Launch | Status: "Starting Pipeline..." | |
| 4.2 | Wait for Running | "Running..." + Stop button visible | |
| 4.3 | Overlay appears | Bottom-center subtitle window | |
| 4.4 | Say "Hello, can you hear me?" | Overlay shows subtitle | |
| 4.5 | Check app.log | `Utterance[1] START`, `Utterance[1] END`, `Utterance[1] FINAL` | |
| 4.6 | No crash | No "AttributeError: last_final_text" | |
| 4.7 | No empty result | FINAL has actual text (not "(empty)") | |

---

## Gate 5: 20 Fixed Sentences

**Phrase**: "Hello, can you hear me clearly?"
**Method**: Say once, pause 2-3s, repeat 20x

| Check | Expected | Result |
|-------|----------|--------|
| START count | ≈ 20 | |
| END count | ≈ 20 | |
| FINAL count | ≈ 20 | |
| Bubble count | ≈ 20 | |
| Merged utterances | 0 | |
| Duplicate finals | 0 | |
| Stale partial emits | 0 | |
| Partial busy-skip log | present | |

---

## Gate 6: Varied Speech

| Step | Action | Expected |
|------|--------|----------|
| 6.1 | Short: "Test." | Recognizes as "Test." |
| 6.2 | Long: "This is a longer sentence with many words to test continuous speech recognition over extended duration." | Full sentence recognized |
| 6.3 | Pause mid: "Hello... (3s pause) ...is anybody there?" | Single or two utterances |
| 6.4 | Mixed ZH/EN: "Let's go 吃饭吧" | Correctly transcribed |

---

## Gate 7: Translation (if API key configured)

| Step | Action | Expected |
|------|--------|----------|
| 7.1 | Configure valid translation API | Test Connection → ✅ |
| 7.2 | Speak | Original + translated both visible |
| 7.3 | Translation latency | < 3s typical |
| 7.4 | No "(translating...)" stuck | Translation completes or shows error |

---

## Gate 8: Stop + Re-Launch

| Step | Action | Expected |
|------|--------|----------|
| 8.1 | Running → click Stop | Shows "Stopping..." → "Stopped" |
| 8.2 | Overlay closed | Window disappears |
| 8.3 | Click Launch again | New session starts, no old session bleed |
| 8.4 | Stop immediately after speaking | Last utterance FINAL completed before stop |
| 8.5 | No "(translating...)" stuck in new session | |

---

## Gate 9: Error Recovery

| Step | Action | Expected |
|------|--------|----------|
| 9.1 | Disconnect mic / use invalid device | Pipeline Failed → "Error — cleaning up..." |
| 9.2 | Wait for cleanup | "Pipeline Error — ready to retry" or "Cleanup failed" |
| 9.3 | Click Retry Launch | New session starts |
| 9.4 | Check Diagnostics | Shows "Pipeline failed: YES", last error |

---

## Gate 10: Clean Exit

| Step | Action | Expected |
|------|--------|----------|
| 10.1 | Stop, then close X | Window closes immediately, no timeout |
| 10.2 | Close while Running | Stops, then exits |
| 10.3 | Check processes | `ps aux | grep realtimesubtitle` → 0 results |
| 10.4 | Re-open | Opens like fresh session |

---

## Gate 11: Logs + Diagnostics

| Step | Action | Expected |
|------|--------|----------|
| 11.1 | Run `bash tools/acceptance-test.sh` | All ✅ except expected NOT TESTED items |
| 11.2 | Run `bash tools/collect-test-logs.sh post-test` | Creates zip on Desktop |
| 11.3 | Open Diagnostics tab → Run | Shows version, pipeline state, log path |

---

## Acceptance Decision

- [ ] ALL Gates 1-11 passed → Release as Final
- [ ] Partial pass → Document failures, fix, re-test from Gate 1
- [ ] Cannot reproduce → Mark NOT TESTED with reason

**Sign-off**: __________________ **Date**: __________________
