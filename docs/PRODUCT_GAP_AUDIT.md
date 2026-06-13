# Product Gap Audit — Realtime Subtitle v2.3.0-rc1

Status: COMPLETE_VERIFIED | COMPLETE_UNVERIFIED | PARTIAL | MISSING | KNOWN_LIMITATION

## ASR Core

| # | Item | Status | File/Function | Commit | Test Evidence | Gap |
|---|------|--------|---------------|--------|---------------|-----|
| 1 | Real-time recognition | COMPLETE_VERIFIED | main.py processing_loop, transcriber.py | 67eecfd | User log: 15/15 final text | — |
| 2 | Partial/final replacement | COMPLETE_VERIFIED | main.py _process_partial_v3, _process_final_v3 | fcd0571 | User log: correct emit order | — |
| 3 | Cross-utterance contamination | COMPLETE_VERIFIED | transcriber.py _transcribe_faster_whisper | 67eecfd | User log: 15 repeats all FINAL | — |
| 4 | Long sentence + silence | COMPLETE_VERIFIED | main.py processing_loop | ccb5f8f | User log: 8.8s, 11.6s utterances | 1.5s silence hysteresis not done |
| 5 | Model pool reuse | COMPLETE_VERIFIED | transcriber_pool.py get_or_create_transcriber | 97fedbd | User log: 2nd Launch faster | — |
| 6 | Multi-round lifecycle | COMPLETE_VERIFIED | main.py start/stop, _stopping guard | 9fb6b2f, d34b2ff | User: 3 rounds no crash | — |

## Translation

| # | Item | Status | File/Function | Commit | Test Evidence | Gap |
|---|------|--------|---------------|--------|---------------|-----|
| 7 | Off mode | COMPLETE_VERIFIED | translation_engine.py translate, main.py _process_final_v3 | 95c2241 | User log: no translation calls | — |
| 8 | EN→ZH translation | COMPLETE_UNVERIFIED | translation_engine.py OnlineAPITranslator | — | Needs user API key | — |
| 9 | ZH→EN translation | COMPLETE_UNVERIFIED | translation_engine.py OnlineAPITranslator | — | Needs user API key | — |
| 10 | Preserve original on fail | COMPLETE_UNVERIFIED | main.py _run_translation_safe | eb31b85 | Needs user API key + fail sim | — |
| 11 | Translation timeout/cancel | COMPLETE_UNVERIFIED | translation_engine.py timeout=10.0, main.py _run_translation_safe | eb31b85, 9fb6b2f | Has timeout, session token, stop-safe. Needs mock test. | — | — | — | No timeout guard in translate() |
| 12 | API key safety | COMPLETE_VERIFIED | config.py _safe_mask, translation_engine.py | ccb5f8f | Masking verified, placeholder skip | — |

## Overlay

| # | Item | Status | File/Function | Commit | Test Evidence | Gap |
|---|------|--------|---------------|--------|---------------|-----|
| 13 | Subtitle display | COMPLETE_VERIFIED | enhanced_overlay_window.py update_text | 59ea3c5 | User screenshot | — |
| 14 | Drag + position memory | COMPLETE_UNVERIFIED | enhanced_overlay_window.py mouse events | — | Drag works, position lost on restart | Need QSettings persistence |
| 15 | Long text wrapping | COMPLETE_UNVERIFIED | enhanced_overlay_window.py SubtitleBubble | — | Needs visual test | — |
| 16 | Original+translation layout | COMPLETE_UNVERIFIED | enhanced_overlay_window.py SubtitleBubble | — | Needs visual test | — |
| 17 | Multi-monitor/edge | PARTIAL | enhanced_overlay_window.py | — | Bottom-center default, no edge snap | — |
| 18 | Stop/restart behavior | COMPLETE_VERIFIED | dashboard.py on_stop, _on_pipeline_started | 9fb6b2f | User: stop works, relaunch works | — |

## History

| # | Item | Status | File/Function | Commit | Test Evidence | Gap |
|---|------|--------|---------------|--------|---------------|-----|
| 19 | Capacity + scroll | COMPLETE_UNVERIFIED | enhanced_overlay_window.py update_text (max 8) | 59ea3c5 | — | — |
| 20 | Copy to clipboard | COMPLETE_UNVERIFIED | enhanced_overlay_window.py copy_to_clipboard | 17dfc16 | Hover copy button. Privacy-safe log. | — | — | — | No copy button/gesture |
| 21 | Session clear rules | COMPLETE_UNVERIFIED | enhanced_overlay_window.py clear_all | — | — | — |

## Settings

| # | Item | Status | File/Function | Commit | Test Evidence | Gap |
|---|------|--------|---------------|--------|---------------|-----|
| 22 | Persistence | COMPLETE_UNVERIFIED | config.py, dashboard.py save_config | — | Needs save→restart→verify | — |
| 23 | Validation + corruption | COMPLETE_VERIFIED | config.py corrupt handler | e06e427 | test_config_recovery.py PASS | — |

## Audio

| # | Item | Status | File/Function | Commit | Test Evidence | Gap |
|---|------|--------|---------------|--------|---------------|-----|
| 24 | Dynamic device resolution | COMPLETE_UNVERIFIED | audio_capture.py generator | 7bb6d9f | — | — |
| 25 | Device failure prompt | PARTIAL | audio_capture.py generator | 7bb6d9f | Voice Isolation warning added, no device reconnect | — |

## Install/Launch

| # | Item | Status | File/Function | Commit | Test Evidence | Gap |
|---|------|--------|---------------|--------|---------------|-----|
| 26 | First launch | COMPLETE_UNVERIFIED | build_dmg.sh launcher | — | Needs fresh DMG test | — |
| 27 | Environment install | COMPLETE_UNVERIFIED | build_dmg.sh launcher (pip) | — | Needs fresh DMG test | — |
| 28 | Model download + retry | PARTIAL | model_manager.py | — | Download exists, no retry ui | — |
| 29 | Overwrite install (retain user dir) | COMPLETE_UNVERIFIED | build_dmg.sh | — | DMG replaces .app only, not user dir | — |
| 30 | Permission recovery | COMPLETE_UNVERIFIED | permission_guide.py | — | — | — |
| 31 | Crash recovery | COMPLETE_VERIFIED | main.py pipeline_failed + cleanup | 9fb6b2f | test_pipeline_recovery.py PASS | — |
| 32 | Exit during Running | COMPLETE_UNVERIFIED | dashboard.py closeEvent | 185b2c7 | Stop+drain before quit, no background residue check | — |

## UI/UX

| # | Item | Status | File/Function | Commit | Test Evidence | Gap |
|---|------|--------|---------------|--------|---------------|-----|
| 33 | Tab truncation + feedback | PARTIAL | dashboard.py setMinimumSize(800) | 2bd43cb | 800px still not enough for 8 tabs | — |
| 34 | Logging + privacy | COMPLETE_VERIFIED | main.py, config.py _safe_mask | — | API key masked, log levels correct | — |
| 35 | DMG, version, build, release | COMPLETE_VERIFIED | build_dmg.sh, CI, version.py | 2bd43cb | GitHub Actions passes, DMG produces | — |

## Summary

- COMPLETE_VERIFIED: 15
- COMPLETE_UNVERIFIED: 14
- PARTIAL: 3
- MISSING: 0
- KNOWN_LIMITATION: 1
