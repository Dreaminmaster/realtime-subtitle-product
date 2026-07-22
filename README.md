<div align="center">
  <img src="assets/icon/realtime-subtitle-icon.png" width="128" alt="Realtime Subtitle icon">
  <h1>Realtime Subtitle</h1>
  <p><strong>让每一句话，都在你眼前。</strong><br>Private, low-latency live captions and translation for macOS.</p>
</div>

![Realtime Subtitle Control Center](docs/images/control-center.png)

## 下载 / Download

当前稳定版：**v2.5.2** · macOS 13 Ventura 或更高版本

Current stable release: **v2.5.2** · macOS 13 Ventura or later

| Mac | 安装包 / Installer | 适用设备 / Hardware |
|---|---|---|
| Apple Silicon | [下载 ARM64 DMG](https://github.com/Dreaminmaster/realtime-subtitle-product/releases/latest/download/RealtimeSubtitle-2.5.2-macos-arm64.dmg) | M1 / M2 / M3 / M4 and newer |
| Intel | [下载 Intel DMG](https://github.com/Dreaminmaster/realtime-subtitle-product/releases/latest/download/RealtimeSubtitle-2.5.2-macos-x86_64.dmg) | Intel-based Macs |

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
- 应用界面支持全局中文/English 即时切换，入口位于 **System**。
- 开始字幕后控制中心会完全隐藏，只保留悬浮字幕；字幕工具条中的 **主界面** 可随时恢复控制中心。
- 运行时点击控制中心红色关闭按钮只隐藏窗口，不会中断字幕；点击字幕工具条停止按钮会结束会话，`⌘Q` 会完全退出 App。
- 在线 API、本地 LLM、OpenAI-compatible 自定义 API，以及完全关闭翻译。
- 翻译服务通过单一 Provider 选择器配置：Agnes AI、LM Studio 或任意 OpenAI-compatible 服务。
- 麦克风输入与 BlackHole 系统音频输入。
- 模型管理、按需权限提示、运行诊断和本地字幕记录。
- Apple Silicon 与 Intel 分架构原生安装包。

![Realtime Subtitle floating overlay](docs/images/subtitle-overlay.png)

### 安装与首次使用

1. 根据上表下载与你的 Mac 匹配的 DMG。
2. 打开 DMG，把 `RealtimeSubtitle.app` 拖入 `Applications`。
3. 首次启动若出现安全提示，Control-click App → **打开**。
4. App 会直接进入控制中心；首次点击开始时，按 macOS 提示授予麦克风权限。
5. 打开 **Audio** 选择输入设备；在 **Language** 设置识别语言和翻译模式。
6. 回到 **Live**，点击 **Start Live Subtitles**。

首次启动会在用户目录创建独立运行环境，所需核心依赖和默认模型已包含在 App 中。这个过程通常需要一两分钟，不会修改系统 Python。

### 系统声音

macOS 不会直接向普通应用提供其他 App 的音频。若要给视频、会议或浏览器内容加字幕，请先安装 BlackHole 2ch：

```bash
brew install blackhole-2ch
```

然后在 **Audio → System Audio** 中选择 BlackHole。你还需要在“音频 MIDI 设置”中建立多输出设备，才能在捕获声音的同时继续从扬声器或耳机收听。

### 翻译模式

| 模式 | 用途 |
|---|---|
| Off | 只显示原文；最私密、延迟最低 |
| Online API | OpenAI 或兼容服务；通常体验最好 |
| Local LLM | LM Studio、Ollama 等本地 OpenAI-compatible 服务 |
| Custom API | 自定义 Base URL、模型与 API Key |

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
- Instant app-wide English / Simplified Chinese switching under **System**.
- Online, local-LLM, custom OpenAI-compatible, or disabled translation.
- A single provider selector for Agnes AI, LM Studio, and custom OpenAI-compatible endpoints.
- The control center hides completely after a session starts; use **Controls** in the caption bar to bring it back.
- Closing the control-center window during a live session hides that window without stopping captions. Use the overlay Stop button to end the session, or `⌘Q` to quit the app completely.
- Context-aware phrase revisions join likely unfinished speech after a short pause and retranslate the same caption instead of leaving fragmented lines.
- Strict quoted-speech prompting, automatic retry, and response screening prevent local models from answering spoken questions as a chat assistant.
- Microphone and BlackHole system-audio input.
- Model management, permission prompts only when needed, diagnostics, and local transcripts.
- Separate native downloads for Apple Silicon and Intel Macs.

### Install and start

1. Download the DMG matching your Mac from the table above.
2. Open it and drag `RealtimeSubtitle.app` to `Applications`.
3. If Gatekeeper blocks the unsigned build, Control-click the app and choose **Open**.
4. The control center opens immediately; grant microphone access when you first start captions.
5. Choose an input under **Audio**, then configure recognition and translation under **Language**.
6. Return to **Live** and click **Start Live Subtitles**.

On first launch the app creates an isolated runtime under your user account. Core dependencies and the default model are bundled, and the system Python installation is not modified.

### System audio

To caption audio from meetings, browsers, or media players, install BlackHole 2ch:

```bash
brew install blackhole-2ch
```

Select it under **Audio → System Audio**. Create a Multi-Output Device in Audio MIDI Setup if you also want to hear the captured audio through speakers or headphones.

### Translation and privacy

Audio is transcribed locally. When online translation is enabled, only recognized text is sent to the provider configured by the user; this project does not upload the audio. Select **Off** for a fully local transcription path.

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
bash build_dmg.sh 2.5.2 arm64

# Intel host, or Apple Silicon with Rosetta installed
bash build_dmg.sh 2.5.2 x86_64
```

Outputs:

```text
dist/RealtimeSubtitle-2.5.2-macos-arm64.dmg
dist/RealtimeSubtitle-2.5.2-macos-x86_64.dmg
```

The GitHub Actions release workflow builds `arm64` on an Apple Silicon runner and `x86_64` on an Intel runner, verifies the embedded architecture and app icon, creates SHA-256 checksums, and publishes both DMGs to one release.

## 项目结构 / Architecture

```text
Audio input → local ASR → utterance lifecycle → subtitle overlay
                              └→ translation scheduler → translation provider

Control Center
├── Live
├── History
├── Audio: Input / System Audio
├── Language: Recognition / Translation / Models
├── Appearance
└── System
```

## 已知限制 / Known limitations

- The public community builds are unsigned and not notarized.
- System-audio capture requires a virtual device such as BlackHole.
- Intel recognition is supported but generally slower than Apple Silicon.
- The current product targets macOS only.
- MLX Whisper is optional and Apple Silicon-only; the packaged default uses `faster-whisper` for both architectures.

## License and acknowledgements

[MIT License](LICENSE). Productized from [Vanyoo/realtime-subtitle](https://github.com/Vanyoo/realtime-subtitle), with recognition powered by projects including [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [MLX Whisper](https://github.com/ml-explore/mlx-examples), and [FunASR](https://github.com/modelscope/FunASR).
