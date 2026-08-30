<div align="center">
  <img src="assets/icon/realtime-subtitle-icon.png" width="128" alt="Realtime Subtitle icon">
  <h1>Realtime Subtitle</h1>
  <p><strong>让每一句话，都在你眼前。</strong><br>Private, low-latency live captions and translation for macOS.</p>
</div>

![Realtime Subtitle Control Center](docs/images/control-center.png)

## 下载 / Download

当前稳定版：**v2.8.0** · macOS 13 Ventura 或更高版本

Current stable release: **v2.8.0** · macOS 13 Ventura or later

| Mac | 安装包 / Installer | 适用设备 / Hardware |
|---|---|---|
| Apple Silicon | [下载 ARM64 DMG](https://github.com/Dreaminmaster/realtime-subtitle-product/releases/latest/download/RealtimeSubtitle-2.8.0-macos-arm64.dmg) | M1 / M2 / M3 / M4 and newer |
| Intel | [下载 Intel DMG](https://github.com/Dreaminmaster/realtime-subtitle-product/releases/latest/download/RealtimeSubtitle-2.8.0-macos-x86_64.dmg) | Intel-based Macs |

[查看全部版本 / View all releases](https://github.com/Dreaminmaster/realtime-subtitle-product/releases)

> 当前社区安装包未使用 Apple Developer ID 签名，也未公证。首次启动若被 macOS 拦截，请按住 Control 点击 App，选择“打开”，再确认一次。
>
> The community builds are currently unsigned and not notarized. If macOS blocks the first launch, Control-click the app, choose **Open**, then confirm.

## 中文说明

Realtime Subtitle 是一款 macOS 实时字幕应用。语音识别默认在本机完成；原文会先显示，翻译结果随后异步补全，因此翻译服务变慢时也不会阻塞字幕。

### 主要功能

- 本地实时语音识别，内置 `faster-whisper tiny` 模型，安装后即可开始。
- 悬浮字幕窗始终置顶，支持拖动、缩放、双语/仅原文/仅翻译显示。
- 上下文断句会识别短暂停顿后的未完句，在同一条字幕中续接并重新翻译，避免把半句话永久切开。
- 翻译提示把所有输入严格视为“待翻译语音”，问句不会被本地模型误当成聊天请求；异常回答会自动重试并拦截。
- 可自定义屏幕上同时显示的字幕条数；向上滚动可查看本次会话的过往字幕。
- 默认把每次字幕保存为本机会话，像聊天记录一样回看、导出或删除；也可在开始前切换为不留记录的临时会话。
- 保存会话可选“录制完整音频”；结束后使用 macOS 原生音频播放路径回放。字幕会像歌词一样跟随进度，高亮并放大当前句；点击任意字幕即可跳转到对应声音。临时会话不会录音。
- 会话页可随时切换双语、仅原文或仅译文；导出严格针对当前选中的会话，可选择字幕、录音或两者，并按当前查看模式生成字幕文本。
- 外观页提供与悬浮字幕一致的实时预览；可把预览字幕拖到深色或浅色背景上检查对比度。文字颜色使用 macOS 原生颜色面板，并与背景透明度互不影响。
- 常用的二到四项选择改为直接可见的分段控件；其余下拉菜单使用应用内紧凑浮层，不再出现白色空框或多余留白。
- 应用界面支持全局中文/English 即时切换，入口位于 **设置 → 系统**。
- 开始字幕后控制中心会完全隐藏，只保留悬浮字幕；字幕工具条中的 **主界面 / 隐藏** 可双向切换控制中心。
- 运行时点击控制中心红色关闭按钮只隐藏窗口，不会中断字幕；点击字幕工具条停止按钮会结束会话，`⌘Q` 会完全退出 App。
- 在线 API、本地 LLM、OpenAI-compatible 自定义 API，以及完全关闭翻译。
- macOS 26 及以上可使用 Apple Translation 本地翻译；语言包由系统管理，识别文字无需发送给第三方。
- 翻译服务通过单一 Provider 选择器配置：Agnes AI、LM Studio 或任意 OpenAI-compatible 服务。
- 麦克风输入与内置 macOS 系统声音采集，无需 BlackHole 或虚拟声卡。
- 模型中心分为内置推荐与 Hugging Face 搜索；可粘贴 `organization/model` 或模型链接，兼容性检查通过后直接下载并选用 faster-whisper 社区模型。
- Apple Silicon 与 Intel 分架构原生安装包。

![会话录音与歌词式字幕回放](docs/images/session-playback.png)

![Realtime Subtitle floating overlay](docs/images/subtitle-overlay.png)

### 安装与首次使用

1. 根据上表下载与你的 Mac 匹配的 DMG。
2. 打开 DMG，把 `RealtimeSubtitle.app` 拖入 `Applications`。
3. 首次启动若出现安全提示，Control-click App → **打开**。
4. App 会直接进入控制中心；首次使用麦克风或系统声音时，按 macOS 提示授予对应权限。
5. 打开 **设置**，在 **音频 / 识别 / 翻译** 中完成配置。
6. 回到 **Live**，点击 **Start Live Subtitles**。

首次启动会在用户目录创建独立运行环境，所需核心依赖和默认模型已包含在 App 中。这个过程通常需要一两分钟，不会修改系统 Python。

### 系统声音

在 **音频 → 输入来源** 选择 **系统声音（内置）**，即可给视频、会议或浏览器内容加字幕。App 使用 macOS ScreenCaptureKit 只读取音频，不保存屏幕画面，也不需要 BlackHole。

首次使用时，macOS 会要求“屏幕与系统音频录制”权限。授权后请完全退出并重新打开 Realtime Subtitle，然后再开始字幕。

### 翻译模式

| 模式 | 用途 |
|---|---|
| Off | 只显示原文；最私密、延迟最低 |
| Online API | OpenAI 或兼容服务；通常体验最好 |
| Local LLM | LM Studio、Ollama 等本地 OpenAI-compatible 服务 |
| Custom API | 自定义 Base URL、模型与 API Key |
| Apple Translation | macOS 26+ 系统本地翻译；需要已安装对应语言包 |

在 Provider 中选择 **Agnes AI** 会使用官方接口 `https://apihub.agnes-ai.com/v1` 与
`agnes-2.0-flash`；选择 **LM Studio / 本地服务** 会使用
`http://127.0.0.1:1234/v1`。缺失的协议和本地 `/v1` 路径会自动补全。API Key 不会写入仓库，只在你保存设置后进入本机用户配置。

连接测试结果只对当前服务、API Key、地址、模型和目标语言有效。切换服务或修改任一字段后，旧的成功状态会立即变为“尚未测试当前设置”；旧请求稍后返回也不会覆盖新状态。

语音只在本机识别。只有启用在线翻译时，识别出的文本才会发送到你配置的服务；音频不会由本项目上传。

### 数据与隐私

| 数据 | 默认位置 |
|---|---|
| 设置 | `~/Library/Application Support/RealtimeSubtitle/config.ini` |
| 运行环境 | `~/Library/Application Support/RealtimeSubtitle/venv` |
| 日志 | `~/Library/Logs/RealtimeSubtitle` |
| 保存的会话 | `~/Library/Application Support/RealtimeSubtitle/realtime_subtitle.sqlite3` |
| 会话录音 | `~/Library/Application Support/RealtimeSubtitle/recordings` |
| 手动保存的字幕 | `~/Documents/Realtime Subtitle/Transcripts` |

API Key 保存在本机配置文件中。共享诊断信息前，请先检查其中是否包含设备名称、路径或服务地址。

### 权限排查

如果麦克风没有声音：

1. 打开 **系统设置 → 隐私与安全性 → 麦克风**。
2. 允许 Realtime Subtitle。
3. 完全退出 App 后重新打开。
4. 在 **System** 页面运行诊断并复制结果。

## English

Realtime Subtitle is a native-feeling macOS control center with an always-on-top caption overlay. Speech recognition runs locally by default. Original text appears immediately, while optional translation is scheduled asynchronously so a slow provider does not stall captions.

### Highlights

- Local live transcription with a bundled `faster-whisper tiny` model.
- Draggable, resizable bilingual overlay with original-only and translation-only modes.
- Adjustable visible-row count with in-session scrollback for older captions.
- Chat-style local session history with view, export and delete actions, plus a no-history Temporary mode.
- Optional full-session audio for Saved sessions, with native macOS playback, click-to-seek transcript lines, and a brighter, larger active line that follows playback like lyrics.
- Per-session Original, Translation, and Both views. Export the selected session as transcript, recording, or a bundle; transcript output follows the active view.
- A draggable live appearance preview with dark and light surfaces plus the native macOS color panel; text colors remain independent from background opacity.
- Compact segmented choices and app-owned popup menus remove blank native popup panels and make common options visible at a glance.
- Instant app-wide English / Simplified Chinese switching under **System**.
- Online, local-LLM, custom OpenAI-compatible, or disabled translation.
- Apple on-device Translation on macOS 26+ when the required language assets are installed.
- A single provider selector for Agnes AI, LM Studio, and custom OpenAI-compatible endpoints.
- The control center hides completely after a session starts; **Controls / Hide** in the caption bar toggles it in either direction.
- Closing the control-center window during a live session hides that window without stopping captions. Use the overlay Stop button to end the session, or `⌘Q` to quit the app completely.
- Context-aware phrase revisions join likely unfinished speech after a short pause and retranslate the same caption instead of leaving fragmented lines.
- Strict quoted-speech prompting, automatic retry, and response screening prevent local models from answering spoken questions as a chat assistant.
- Microphone and built-in ScreenCaptureKit system-audio input; no virtual audio driver is required.
- Recommended offline recognition models plus Hugging Face search/custom repository installation with faster-whisper compatibility validation.
- Separate native downloads for Apple Silicon and Intel Macs.

![Synchronized session playback](docs/images/session-playback.png)

### Install and start

1. Download the DMG matching your Mac from the table above.
2. Open it and drag `RealtimeSubtitle.app` to `Applications`.
3. If Gatekeeper blocks the unsigned build, Control-click the app and choose **Open**.
4. The control center opens immediately; grant microphone or Screen & System Audio Recording access when first requested.
5. Open **Settings** and configure **Audio**, **Recognition**, and **Translation**.
6. Return to **Live** and click **Start Live Subtitles**.

On first launch the app creates an isolated runtime under your user account. Core dependencies and the default model are bundled, and the system Python installation is not modified.

### System audio

Choose **System audio (built in)** under **Audio → Input Source** to caption meetings, browsers, or media players. Realtime Subtitle uses macOS ScreenCaptureKit and does not require BlackHole or a Multi-Output Device. The app consumes audio samples only; it does not save screen video.

macOS asks for **Screen & System Audio Recording** permission the first time. After allowing Realtime Subtitle, quit it completely and reopen it before starting captions again.

### Translation and privacy

Audio is transcribed locally. When online translation is enabled, only recognized text is sent to the provider configured by the user; this project does not upload the audio. Select **Off** for a fully local transcription path.

On macOS 26 or later, **Apple Translation** uses Apple's on-device Translation framework and system-managed language assets. Realtime Subtitle does not download those assets itself. If the selected language pair is supported but not installed, macOS reports that the language assets are missing; use the system Translation features once to install them, then test again in the app.

The Agnes AI provider uses `https://apihub.agnes-ai.com/v1` with
`agnes-2.0-flash`. The LM Studio provider uses `http://127.0.0.1:1234/v1`.
Missing schemes and the local `/v1` path are normalized automatically.
Credentials are never committed to this repository; saving them writes only to
the current user's local configuration.

Connection results are scoped to the exact provider, credential, endpoint,
model, and target language. Editing any of them immediately invalidates the old
result, and a late response from an earlier test cannot reappear as success.

## 从源码运行 / Run from source

Python 3.10–3.12 is recommended.

```bash
git clone https://github.com/Dreaminmaster/realtime-subtitle-product.git
cd realtime-subtitle-product
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-core.txt
python launcher.py
```

Useful commands:

```bash
# Control Center
python main.py

# Start directly in overlay mode
python main.py --overlay-only

# Diagnostics
python main.py --diagnostics

# Test suite
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

## 构建 / Build

Build a native DMG on a matching Mac:

```bash
# Apple Silicon host
bash build_dmg.sh 2.8.0 arm64

# Intel host, or Apple Silicon with Rosetta installed
bash build_dmg.sh 2.8.0 x86_64
```

Outputs:

```text
dist/RealtimeSubtitle-2.8.0-macos-arm64.dmg
dist/RealtimeSubtitle-2.8.0-macos-x86_64.dmg
```

The GitHub Actions release workflow builds `arm64` on an Apple Silicon runner and `x86_64` on an Intel runner, verifies the embedded architecture and app icon, creates SHA-256 checksums, and publishes both DMGs to one release.

## 项目结构 / Architecture

```text
Audio input → local ASR → utterance lifecycle → subtitle overlay
                              └→ translation scheduler → translation provider

Control Center
├── Live
├── Sessions: transcript / synchronized recording playback
└── Settings
    ├── Audio / Recognition / Translation / Models
    ├── Appearance
    └── System
```

## 已知限制 / Known limitations

- The public community builds are unsigned and not notarized.
- System-audio capture requires macOS 13 or later and the user's Screen & System Audio Recording permission.
- Intel recognition is supported but generally slower than Apple Silicon.
- The current product targets macOS only.
- MLX Whisper is optional and Apple Silicon-only; the packaged default uses `faster-whisper` for both architectures.
- Apple Translation inside Realtime Subtitle requires macOS 26 or later; older supported macOS versions can use local LM Studio or an online/custom provider.

## License and acknowledgements

[MIT License](LICENSE). Productized from [Vanyoo/realtime-subtitle](https://github.com/Vanyoo/realtime-subtitle), with recognition powered by projects including [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [MLX Whisper](https://github.com/ml-explore/mlx-examples), and [FunASR](https://github.com/modelscope/FunASR).
