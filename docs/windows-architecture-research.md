# Windows architecture research (v2.11.0)

This note records the Windows-specific choices made for Realtime Subtitle. It
is intentionally separate from the cross-platform streaming study in
[`streaming-architecture-research.md`](streaming-architecture-research.md).
The implementation reuses the same Partial → Stable → Final state model,
incremental translation scheduler, session store, player, and responsive UI;
only operating-system capabilities are substituted.

## Decisions

### System audio: WASAPI shared-mode loopback

Microsoft documents that WASAPI loopback can capture the mix played by a
render endpoint even when the hardware has no physical loopback device. It is
available in shared mode and does not require changing the default playback
device. This maps directly to the product expectation that a meeting or video
keeps playing normally while captions listen in the background.

- Adopted: endpoint-level WASAPI loopback through SoundCard, with a playback
  device selector, stereo capture, explicit stereo-to-mono downmix, and 48 kHz
  to 16 kHz resampling.
- Rejected: requiring VB-CABLE or “Stereo Mix”. They add installation and
  routing work and are unnecessary for normal Windows 10/11 devices.
- Deferred: per-process loopback. Microsoft's sample requires Windows 10 build
  20348 or later and adds process-tree selection complexity. Endpoint loopback
  has broader compatibility and matches the current “system audio” control.
- Failure behavior: exclusive-mode output, a removed endpoint, or a driver
  error is reported with a device-oriented recovery message; recognition does
  not silently fall back to the microphone.

Sources:

- [Microsoft: Loopback Recording](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording)
- [Microsoft: Application loopback audio capture sample](https://github.com/microsoft/Windows-classic-samples/tree/main/Samples/ApplicationLoopback)
- [SoundCard project](https://github.com/bastibe/SoundCard) and
  [documentation](https://soundcard.readthedocs.io/) (BSD-3-Clause)

Known SoundCard issue reports mention problematic single-channel capture and
backend block-size behavior. The app therefore requests two channels, performs
its own downmix, uses a conservative block size, and does not assume each read
contains an exact duration.

### Overlay and focus behavior

Qt documents `WindowStaysOnTopHint` and `WindowDoesNotAcceptFocus`, including
that the latter prevents a Windows window from appearing in the taskbar. The
overlay combines these portable flags with native `WS_EX_NOACTIVATE` and
`WS_EX_TOOLWINDOW` extended styles after the HWND is created. `SetWindowPos`
uses `SWP_NOACTIVATE`, so a caption refresh cannot activate Realtime Subtitle
or the previously frontmost application.

- Adopted: one non-activating tool overlay with a user-invoked Controls toggle.
- Rejected: calling `activateWindow`, `raise_`, or reopening the control center
  on ASR/translation updates.
- Kept: explicit activation only after the user clicks **Controls**.

Sources:

- [Qt 6 window flags](https://doc.qt.io/qt-6/qt.html#WindowType-enum)
- [Microsoft: Extended Window Styles](https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles)
- [Microsoft: SetWindowPos](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos)

### Translation choices

Windows does not expose a general desktop equivalent of Apple's Translation
framework that provides the same local language-pair API to an unpackaged Qt
application. Pretending otherwise would lead to a nonfunctional provider.

- Adopted: bundle `gaudi/opus-mt-en-zh-ctranslate2` and
  `gaudi/opus-mt-zh-en-ctranslate2` in the Windows installer. Both model cards
  declare Apache-2.0 and provide CPU `int8` guidance. They are compact,
  deterministic, offline, and cover this project's primary English/Chinese
  use case.
- Kept: LM Studio/local OpenAI-compatible servers and online APIs for more
  languages and higher-quality models.
- Rejected: bundling a multi-gigabyte multilingual LLM. It would increase
  download size, memory pressure, startup time, and heat for every user.
- UI rule: Apple Translation is never shown on Windows. The offline choice is
  labeled **Built-in offline translation**, and bundled models cannot be
  deleted accidentally.

Sources and licenses:

- [English → Chinese CTranslate2 model](https://huggingface.co/gaudi/opus-mt-en-zh-ctranslate2) — Apache-2.0
- [Chinese → English CTranslate2 model](https://huggingface.co/gaudi/opus-mt-zh-en-ctranslate2) — Apache-2.0
- [CTranslate2](https://github.com/OpenNMT/CTranslate2) — MIT

The model card benchmark is not treated as a product benchmark: it used a
specific cloud CPU and language pair. Realtime Subtitle's own latency and
quality measurements remain in `performance-benchmark.md` and must be rerun on
actual Windows hardware before making Windows performance claims.

### Runtime and installation

The installer contains a redistributable CPython runtime, an offline wheelhouse,
the default recognition model, and the two translation models. First launch
creates an isolated virtual environment under Local AppData; it does not modify
the system Python installation.

- Portable Python: `python-build-standalone` (MPL-2.0 project with component
  licenses included upstream).
- Installer: Inno Setup, per-user (`PrivilegesRequired=lowest`) under
  `%LOCALAPPDATA%\Programs`, so installation does not require elevation.
- Target: Windows 10/11 x64. ARM64 Windows is not advertised until all Python,
  CTranslate2, Qt, and audio wheels pass a native ARM64 build and smoke test.
- CI: a Windows runner creates and verifies the installer; the release job
  publishes it beside both macOS DMGs and one `SHA256SUMS.txt`.

Sources:

- [python-build-standalone](https://github.com/astral-sh/python-build-standalone)
- [Inno Setup](https://jrsoftware.org/isinfo.php)
- [Inno Setup per-user privileges](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm)

### Windows accessibility and layout

Microsoft's Windows app guidance calls for keyboard access, testing at display
scale/text-size changes, support for contrast themes, and at least 4.5:1
contrast for normal visible text. The Windows UI keeps real Qt controls (rather
than painted hit targets), visible focus behavior, word-wrapped labels, and no
horizontal scrolling in the caption/history experiences. Segoe UI Variable is
the preferred Windows family with Segoe UI and generic fallbacks.

Validation checklist:

- 100%, 150%, and 200% display scaling; 1280×720 through 4K.
- Keyboard traversal for navigation, provider selection, device selection,
  Start/Stop, downloads, connection tests, and dialogs.
- Windows Contrast themes and default dark theme text contrast.
- Long English, Chinese, and bilingual strings without clipping.
- Overlay update while another application owns keyboard focus.

Sources:

- [Microsoft: Accessibility overview](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/accessibility-overview)
- [Microsoft: Accessible text requirements](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/accessible-text-requirements)
- [Microsoft: Keyboard accessibility](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/keyboard-accessibility)

## License matrix

| Component | Purpose | License | Distribution decision |
|---|---|---|---|
| SoundCard | WASAPI loopback wrapper | BSD-3-Clause | Windows wheelhouse |
| Qt / PyQt6 | Desktop UI | GPL/commercial package terms | Existing project dependency; preserve notices |
| CTranslate2 | ASR/translation inference | MIT | Shared runtime |
| faster-whisper Tiny | Default local ASR | MIT model repository metadata | Bundled on both platforms |
| OPUS-MT EN↔ZH conversions | Basic Windows offline translation | Apache-2.0 | Bundled only in Windows installer |
| python-build-standalone | Redistributable CPython | MPL-2.0 plus component licenses | Bundled runtime |
| Inno Setup | Windows installer compiler | Inno Setup License | Build-time tool only |

No source from the references was copied. The implementation uses documented
API behavior and independently written adapters. Release artifacts must retain
the repository license and upstream notices required by their packages.

## Remaining limitations

- The Windows release is x64 only in v2.11.0.
- WASAPI loopback cannot capture an endpoint held exclusively by another app.
- Bluetooth profile changes or hot-unplugging a selected endpoint require the
  user to stop, refresh devices, and restart the session.
- Built-in offline translation is English↔Simplified Chinese only. Other
  language pairs require LM Studio/local service or an online provider.
- Community binaries are unsigned; SmartScreen reputation therefore cannot be
  guaranteed. SHA-256 checksums are published for verification.
