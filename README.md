# 🎙️ Realtime Subtitle

**macOS 实时字幕翻译工具** — macOS real-time speech recognition + translation with floating subtitle overlay.

你的 Mac 变成一个实时字幕和翻译屏幕。面对面交流、上课、会议、看视频时，实时显示原文和中文翻译。

> Based on [Vanyoo/realtime-subtitle](https://github.com/Vanyoo/realtime-subtitle), productized for better user experience.

---

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| 🎤 实时语音识别 | ASR 引擎，支持 whisper / mlx / FunASR |
| 🌐 异步翻译 | 原文立即显示，翻译延迟 1-3 秒补全 |
| 🪟 浮窗字幕 | 置顶、半透明、可拖动、可调整样式 |
| 🔄 多翻译后端 | 在线 API / 本地 LLM / 自定义 API / 关闭翻译 |
| 📦 模型管理 | 内置下载、删除、切换 ASR 模型 |
| 🎨 字幕样式 | 字体大小、颜色、透明度、双语模式 |
| 🔒 隐私友好 | 本地 ASR，不必上传语音 |
| 📋 DMG 打包 | 一键打包分发 |

---

## 🚀 快速开始

### 安装依赖

```bash
# 1. 克隆仓库
git clone https://github.com/Dreaminmaster/realtime-subtitle-product.git
cd realtime-subtitle-product

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. (可选) 安装 BlackHole 用于系统音频捕获
brew install blackhole-2ch
```

### 运行

```bash
# 启动控制面板
python3 main.py

# 直接启动字幕浮窗（跳过面板）
python3 main.py --overlay-only

# 运行系统诊断
python3 main.py --diagnostics
```

### 使用流程

1. 打开 App（控制面板）
2. 在 **📦 Models** 标签页下载推荐模型（small 或 turbo）
3. 在 **🎤 Audio** 标签页选择输入设备
4. 在 **🈵 Translation** 标签页配置翻译后端
5. 点击 **▶ Launch Translator** 开始

---

## 📲 下载 DMG

从 [GitHub Releases](https://github.com/Dreaminmaster/realtime-subtitle-product/releases) 下载最新 DMG。

无需用户额外安装 Python。App 自带 portable Python 3.12。

### 安装步骤

1. 下载 `RealtimeSubtitle-x.x.x.dmg`
2. 双击打开 DMG
3. 拖动 `RealtimeSubtitle.app` 到 `Applications` 文件夹
4. 首次打开：**右键 → Open**（App 未签名）
5. 首次启动会自动在尾部创建 Python 环境并安装依赖（约 1-2 分钟）

> ⚠️ 未签名的 App 会被 macOS Gatekeeper 拦截。
> 右键点击 App → 选择 "Open" → 确认打开。

### 卸载

```bash
# 删除 App 本体
rm -rf /Applications/RealtimeSubtitle.app

# 清理用户运行环境
rm -rf "$HOME/Library/Application Support/RealtimeSubtitle"
rm -rf "$HOME/Library/Logs/RealtimeSubtitle"
rm -rf "$HOME/Library/Caches/RealtimeSubtitle"
```

如果模型下载到了 Hugging Face 缓存目录（通过 dashboard 的模型管理下载）：

```bash
# 注意：这会删除所有 Hugging Face 缓存，不仅限本项目
# 建议先查看大小再决定
du -sh "$HOME/.cache/huggingface"
rm -rf "$HOME/.cache/huggingface"
```

---

## 🔧 翻译模式

### 模式 A：在线 API（推荐）

```text
本地 ASR + 在线翻译 API
```
- 最低延迟，最好体验
- 配置 OpenAI API 或兼容 API

### 模式 B：本地 LLM

```text
本地 ASR + 本地翻译模型
```
- 不依赖网络、不产生 API 费用
- 支持 LM Studio / Ollama
- 设置 `base_url` 为 `http://localhost:1234/v1`（LM Studio）或 `http://localhost:11434/v1`（Ollama）

### 模式 C：自定义 API

```text
任何 OpenAI-compatible API
```
- 支持任何兼容 `/v1/chat/completions` 的 API

### 模式 D：关闭翻译

```text
只显示原文字幕，不翻译
```

---

## 🎨 字幕浮窗

浮窗特性：
- **永远置顶** — 不会沉到其他窗口下面
- **半透明背景** — 可以看到后面的内容
- **可拖动** — 拖到屏幕任何位置
- **可调整大小** — 右下角拖动
- **字体可调** — A+/A- 按钮调整大小
- **显示模式** — 双语 / 仅原文 / 仅翻译

控制按钮：
- 🌐 — 切换显示模式
- A+/A- — 调整字体大小
- 💾 — 保存字幕记录
- ⏹ — 停止识别

---

## 📦 模型管理

支持的 ASR 模型：

| 模型 | 大小 | 速度 | 准确度 | 推荐场景 |
|------|------|------|--------|----------|
| tiny | 75 MB | 极快 | 较低 | 测试、低配设备 |
| base | 145 MB | 快 | 一般 | 简单交流 |
| small ⭐ | 488 MB | 较快 | 好 | **日常使用推荐** |
| medium | 1.5 GB | 中等 | 更好 | 课堂、会议 |
| large-v3 | 3.1 GB | 慢 | 最好 | 文件转写 |
| turbo ⭐ | 1.6 GB | 快-中等 | 很好 | **速度与准确度平衡** |

在控制面板的 **📦 Models** 标签页中下载和管理模型。

---

## ⌨️ 快捷键

| 快捷键 | 功能 |
|--------|------|
| 启动 / 停止 | 控制面板中 |

> 全局快捷键需要辅助功能权限。未来版本将支持。

---

## 🔒 权限说明

首次启动会引导授权：

1. **麦克风权限** — 必需，用于实时语音识别
2. **辅助功能权限** — 可选，用于全局快捷键
3. **屏幕录制权限** — 可选，用于捕获系统音频（未来）

如果拒绝了权限：  
`System Settings → Privacy & Security → Microphone` 重新开启。

---

## 📊 诊断

```bash
# 命令行诊断
python3 main.py --diagnostics

# 或在控制面板的 Diagnostics 标签页
```

诊断检查项：
- 平台兼容性（macOS / Apple Silicon）
- Python 版本
- 音频设备
- 麦克风权限
- 模型下载状态

---

## 🏗️ 打包 DMG

```bash
bash build_dmg.sh [版本号]
```

生成的文件在 `dist/RealtimeSubtitle-x.x.x.dmg`。

---

## 🧪 测试清单

### 启动测试
- [x] App 能正常启动
- [x] 首次启动显示权限提示
- [x] 无模型时提示下载
- [x] 无麦克风权限时显示引导

### 实时字幕测试
- [x] 原文字幕实时显示
- [x] 不需要等整段说完
- [x] 字幕不频繁闪烁
- [x] 停顿后文本稳定

### 翻译测试
- [x] 中文翻译异步出现
- [x] 翻译慢时不影响原文字幕
- [x] 翻译失败时原文保留
- [x] 切换翻译后端后能正常测试连接

### 字幕浮窗测试
- [x] 窗口置顶
- [x] 可以拖动
- [x] 可以调字体
- [x] 可以调透明度
- [x] 可以隐藏 / 显示
- [x] 双语显示不重叠

### 模型管理测试
- [x] 显示模型列表
- [x] 可以下载模型
- [x] 可以删除模型
- [x] 可以切换模型
- [x] 下载失败时有错误提示

### 打包测试
- [x] 可以生成 `.app`
- [x] 可以生成 `.dmg`
- [x] DMG 打开后能看到 App
- [x] README 写清楚未签名 App 的打开方式

---

## 🧰 技术架构

```
App Shell (main.py)
├── Audio Input (audio_capture.py)
├── ASR Engine (transcriber.py)
│   ├── faster-whisper (CPU/CUDA)
│   ├── mlx-whisper (Apple Silicon)
│   └── FunASR (Alibaba)
├── Translation Engine (translation_engine.py)
│   ├── Online API (OpenAI-compatible)
│   ├── Local LLM (LM Studio / Ollama)
│   └── Custom API
├── Floating Subtitle (enhanced_overlay_window.py)
├── Model Manager (model_manager.py)
├── Control Dashboard (dashboard.py)
├── Permission Guide (permission_guide.py)
├── Diagnostics & Logging (diagnostics.py)
└── Packaging (build_dmg.sh)
```

---

## 🚧 已知限制

1. **未签名 App** — 首次打开需右键 → Open
2. **系统音频捕获** — 需要 BlackHole 虚拟设备
3. **Apple Silicon 优先** — Intel Mac 性能较低
4. **macOS only** — 不支持 Windows/Linux
5. **无全球快捷键** — 需要辅助功能权限（未来版本）

---

## 🎯 降级方案

| 失败情况 | 降级方式 |
|----------|----------|
| 翻译失败 | 继续显示原文字幕 |
| 本地模型未下载 | 提示下载推荐模型 |
| 自定义 API 不可用 | 提示用户检查地址和 Key |
| 麦克风无权限 | 显示权限引导 |
| 字幕浮窗异常 | 允许在主窗口显示字幕 |

---

## 📝 License

MIT License — 基于 [Vanyoo/realtime-subtitle](https://github.com/Vanyoo/realtime-subtitle)

---

## 🙏 致谢

- [Vanyoo/realtime-subtitle](https://github.com/Vanyoo/realtime-subtitle) — 原始项目
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Whisper CTranslate2
- [mlx-whisper](https://github.com/ml-explore/mlx-examples) — Apple Silicon Whisper
- [FunASR](https://github.com/alibaba-damo-academy/FunASR) — Alibaba ASR
- [sounddevice](https://python-sounddevice.readthedocs.io/) — Python 音频库
