"""Small, dependency-light UI localization layer.

English remains the source language in widget construction.  The translator
stores that source text on each widget so switching languages is reversible
without rebuilding the dashboard or losing form state.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QGroupBox,
    QLabel,
    QTabWidget,
    QWidget,
)


SUPPORTED_LANGUAGES = ("en", "zh-Hans")


ZH_HANS = {
    # Navigation and primary session controls.
    "Live": "实时字幕",
    "Sessions": "会话",
    "Settings": "设置",
    "Audio": "音频",
    "Language": "语言与翻译",
    "Appearance": "外观",
    "System": "系统",
    "Input": "输入",
    "System Audio": "系统音频",
    "Recognition": "识别",
    "Translation": "翻译",
    "Models": "模型",
    "Recognition Models": "识别模型",
    "Live subtitles": "实时字幕",
    "Start once, then keep only the floating subtitles above your other apps.": "启动后，可以只保留悬浮字幕窗口显示在其他应用上方。",
    "CAPTION SESSION": "字幕会话",
    "Ready when you are": "准备就绪",
    "Audio remains on this Mac. Saved sessions can keep a transcript and an optional recording.": "音频保留在这台 Mac 上；保存会话可保留字幕记录与可选录音。",
    "Session type": "会话类型",
    "Temporary": "临时字幕",
    "Save subtitles": "保存字幕",
    "Subtitles + recording": "字幕＋录音",
    "Choose exactly what remains on this Mac after the session.": "明确选择本次会话结束后要在本机保留的内容。",
    "Temporary captions leave no transcript or recording.": "临时字幕不会留下字幕记录或录音。",
    "Saves subtitles only. This session will not have audio playback.": "仅保存字幕；本次会话之后不能播放录音。",
    "Saves subtitles and a playable recording locally on this Mac.": "在这台 Mac 上保存字幕与可播放的录音。",
    "Record full audio for playback": "录制完整音频用于回放",
    "Optional · recording stays only on this Mac.": "可选 · 录音仅保存在这台 Mac 上。",
    "Temporary sessions leave no transcript or recording.": "临时会话不会留下字幕记录或录音。",
    "This session will save subtitles and a playable local recording.": "本次会话将保存字幕与可播放的本地录音。",
    "This session will save subtitles only. Choose recording if you want playback later.": "本次会话仅保存字幕；如果之后需要回放，请开启录音。",
    "Choose an input, then start. The subtitle window stays above your other apps.": "选择输入源，然后开始。字幕窗口会保持在其他应用上方。",
    "Start Live Subtitles": "开始实时字幕",
    "Stop Session": "停止字幕",
    "Ready": "就绪",
    "Running…": "运行中…",
    "Stopping…": "正在停止…",
    "Initializing…": "正在初始化…",
    "Loading…": "正在加载…",
    "Starting…": "正在启动…",
    "Initialization Failed": "初始化失败",
    "Pipeline Error — cleaning up…": "字幕管线出错 — 正在清理…",
    "Cleaning up…": "正在清理…",
    "Cleanup failed — retry or force quit": "清理失败 — 请重试或强制退出",
    "Retry Stop": "重试停止",
    "Pipeline Error — ready to retry": "字幕管线出错 — 可以重试",
    "Retry Start": "重新开始",
    "Audio Device Error": "音频设备错误",
    "Wait…": "请稍候…",
    "Start failed — timeout": "启动失败 — 请求超时",
    "Stop timed out — Retry or Force Quit": "停止超时 — 请重试或强制退出",
    "Stopped": "已停止",
    "Appearance applied": "外观已应用",
    "Settings saved": "设置已保存",
    "Saved": "已保存",
    "Running Quick Check…": "正在快速检查…",
    "Input Device:": "输入设备：",
    "Input Source:": "输入来源：",
    "Microphone": "麦克风",
    "System audio (built in)": "系统声音（内置）",
    "Uses macOS ScreenCaptureKit. No BlackHole or virtual audio device is required.": "使用 macOS ScreenCaptureKit，无需 BlackHole 或虚拟声卡。",
    "Sample Rate:": "采样率：",
    "Silence Threshold:": "静音阈值：",
    "Silence Duration:": "静音时长：",
    "Chunk Duration:": "分段时长：",
    "Silence Duration (s):": "静音时长（秒）：",
    "Noise filtering:": "环境降噪：",
    "Strong": "强力",
    "Spoken language": "说话语言",
    "Choose a fixed language for better accuracy and lower processing load; keep Automatic for mixed-language conversations.": "只有一种说话语言时请直接选定，可提升准确率并减少处理负担；多语言对话再使用自动检测。",
    "INPUT": "输入",
    "RECOGNITION": "识别",
    "TRANSLATION": "翻译",
    "Default microphone": "默认麦克风",
    "System audio": "系统声音",
    "Off": "关闭",
    "History": "历史记录",
    "Session History": "会话记录",
    "Session timeline": "会话时间轴",
    "Select a session": "选择一个会话",
    "Play": "播放",
    "Pause": "暂停",
    "This session has no recording": "此会话没有录音",
    "Transcript only · audio recording was not enabled": "仅字幕记录 · 本次会话未开启录音",
    "Local recording available · click any subtitle to jump to it": "本地录音可用 · 点击任意字幕可跳转播放",
    "Recording ready · the current subtitle will follow playback": "录音已就绪 · 当前字幕会随播放进度高亮",
    "Recording was enabled, but the audio file is missing or empty": "本次会话开启了录音，但音频文件缺失或为空",
    "This session saved subtitles only · enable ‘Subtitle + recording’ before the next session": "本次会话仅保存了字幕 · 下次开始前请选择“字幕＋录音”",
    "This session does not contain a recording": "本次会话不包含录音",
    "Unable to play this recording": "无法播放这段录音",
    "No subtitle lines were saved in this session.": "本次会话没有保存字幕内容。",
    "No saved sessions yet. Start Live with ‘Saved session’ selected.": "还没有保存的会话。请在实时字幕页选择“保存会话”后开始。",
    "Session:": "会话：",
    "Saved session": "保存会话",
    "Temporary session": "临时会话",
    "Saved locally · switch to Temporary for private one-off captions": "仅保存在本机 · 私密的一次性字幕可切换为临时会话",
    "Saved sessions stay only on this Mac. Choose Temporary on Live for a session that leaves no history.": "会话仅保存在这台 Mac 上。在实时字幕页选择“临时会话”即可不留下记录。",
    "Export": "导出",
    "Export selected session": "导出当前会话",
    "Choose what to export. Transcript text follows the view currently selected in the session:": "选择导出内容。字幕文本会按照当前会话的查看方式导出：",
    "Text": "字幕文本",
    "Recording": "录音",
    "Original + translation": "原文＋译文",
    "Original only": "仅原文",
    "Translation only": "仅译文",
    "Recording is ready to export.": "录音已可导出。",
    "This session contains subtitles only, so recording export is unavailable.": "本次会话只有字幕，因此无法导出录音。",
    "Choose destination": "选择保存位置",
    "Both": "双语",
    "Original": "原文",
    "Translation": "译文",
    "Delete": "删除",
    "Audio Device Manager": "音频设备管理",
    "Create multi-output devices to capture system audio + hear it through speakers": "创建多输出设备，在捕获系统音频的同时保留扬声器播放。",
    "Available Output Devices:": "可用输出设备：",
    "Virtual/BlackHole Devices:": "虚拟 / BlackHole 设备：",
    "Refresh Devices": "刷新设备",
    "Create Multi-Output Device": "创建多输出设备",
    "Set Selected as Default Output": "将所选设备设为默认输出",
    "ASR Backend:": "识别引擎：",
    "Whisper Model:": "Whisper 模型：",
    "Open Recognition Models": "打开识别模型",
    "Tiny/Base prioritizes speed and often splits or mishears natural speech. Use Small for everyday accuracy or Turbo on a capable Mac.": "Tiny / Base 更偏重速度，容易把自然语句切碎或听错。日常使用建议 Small，性能较好的 Mac 建议 Turbo。",
    "A fixed source language usually improves recognition accuracy and stability.": "明确选择说话语言通常能提升识别准确率与稳定性。",
    "Accuracy enhancement:": "准确率增强：",
    "Standard": "标准",
    "Enhanced": "增强",
    "Hardware profile:": "硬件方案：",
    "Runtime performance:": "运行性能：",
    "Efficient": "节能",
    "High accuracy": "高精度",
    "Balanced is recommended. Efficient lowers heat; High accuracy is intended for faster or externally cooled Macs and still requires an optional refinement model.": "推荐使用均衡。节能模式可降低发热；高精度适合更快或具有额外散热条件的 Mac，并且仍需按需下载可选修正模型。",
    "Balanced adapts update cadence and pauses a slow enhancement model between corrections. High accuracy keeps every enabled correction running continuously.": "均衡模式会调整更新频率，并在耗时的增强修正之间冷却；高精度会持续运行所有已启用的修正。",
    "Auto (recommended)": "自动匹配（推荐）",
    "Fast": "快速",
    "Balanced": "均衡",
    "Accurate": "高准确率",
    "Enhanced mode shows a fast draft first, then corrects the same subtitle line with a larger local model.": "增强模式会先显示快速识别结果，再用更大的本地模型修正同一条字幕。",
    "Download accuracy model": "下载增强模型",
    "Accuracy model ready": "增强模型已就绪",
    "Download Required": "需要下载模型",
    "Download enhanced model?": "下载增强识别模型？",
    "Enhanced accuracy needs the recommended local model before this session can start.": "增强准确率需要先下载本机推荐模型，完成后才能开始本次字幕会话。",
    "FunASR Model:": "FunASR 模型：",
    "Compute Device:": "计算设备：",
    "Quantization:": "量化方式：",
    "Source Language:": "源语言：",
    "Spoken Language:": "说话语言：",
    "Automatic": "自动检测",
    "Refresh": "刷新",
    "Download": "下载",
    "Downloaded": "已下载",
    "Delete All Models": "删除全部模型",
    "Apply": "应用",
    "Save Settings": "保存设置",
    "Save Changes": "保存更改",
    # Translation.
    "Translation Provider": "翻译服务",
    "Choose a provider, then test it here. The same settings are used when Live starts.": "选择翻译服务并在此测试；开始实时字幕时会使用同一套设置。",
    "Provider:": "服务：",
    "No translation": "不翻译",
    "Apple Translation": "Apple 本地翻译",
    "Downloaded offline model": "已下载的离线模型",
    "Agnes AI": "Agnes AI",
    "LM Studio / local server": "LM Studio / 本地服务",
    "Online API": "在线 API",
    "API service:": "API 服务：",
    "Other OpenAI-compatible provider": "其他 OpenAI 兼容服务",
    "Custom API": "自定义 API",
    "Mode:": "模式：",
    "API Key:": "API 密钥：",
    "Base URL:": "接口地址：",
    "Model:": "模型：",
    "Translation Model:": "翻译模型：",
    "Offline model:": "离线模型：",
    "Translate into:": "翻译成：",
    "Live translation:": "实时翻译：",
    "Final only": "仅最终译文",
    "Realtime": "更实时",
    "Balanced shows a throttled draft while you speak, then replaces it with the final translation. Realtime updates more often and uses more power or API calls.": "均衡模式会在说话时显示节流的草稿译文，定稿后自动替换；更实时模式更新更频繁，也会消耗更多电量或 API 请求。",
    "Target Language:": "目标语言：",
    "Fetch": "获取",
    "Load Models": "加载模型",
    "Translation models come from the selected service. LM Studio models are downloaded and loaded in LM Studio, then selected here.": "翻译模型由当前服务提供。LM Studio 模型需先在 LM Studio 中下载并加载，再回到这里选择。",
    "?  Install Apple languages": "?  安装 Apple 翻译语言",
    "Test Connection": "测试连接",
    "Use Agnes AI": "使用 Agnes AI",
    "Use LM Studio": "使用 LM Studio",
    "Off — original subtitles only": "关闭 — 仅显示原文",
    "Online API — hosted OpenAI-compatible": "在线 API — OpenAI 兼容服务",
    "Local LLM — LM Studio / Ollama": "本地模型 — LM Studio / Ollama",
    "Custom OpenAI-compatible API": "自定义 OpenAI 兼容 API",
    "macOS System Translation (experimental)": "macOS 系统翻译（实验性）",
    "Chinese": "中文",
    "English": "英语",
    "Japanese": "日语",
    "French": "法语",
    "Spanish": "西班牙语",
    "German": "德语",
    "Korean": "韩语",
    # Appearance.
    "Subtitle Appearance": "字幕外观",
    "Subtitle appearance": "字幕外观",
    "Adjust the floating subtitle window and see every change before applying it.": "调整悬浮字幕窗口，并在应用前实时查看每项更改。",
    "LIVE PREVIEW": "实时预览",
    "Drag the subtitle between the dark and light areas to check contrast without squeezing long lines.": "在上下深浅背景间拖动字幕检查对比度，长句也不会被窄列挤压。",
    "Original Font Size:": "原文字号：",
    "Translation Font Size:": "译文字号：",
    "Original Text Color:": "原文颜色：",
    "Translation Color:": "译文颜色：",
    "Window Opacity:": "窗口透明度：",
    "Background Opacity:": "背景透明度：",
    "Window Width:": "窗口宽度：",
    "Visible Subtitle Rows:": "可见字幕条数：",
    "Display Mode:": "显示模式：",
    "Display Mode": "显示模式",
    "Bilingual": "双语",
    "Original only": "仅原文",
    "Translation only": "仅译文",
    "Apply Style": "应用外观",
    "Applied": "已应用",
    "Applied — the subtitle window is updated": "已应用 — 字幕窗口已经更新",
    # System/product-facing diagnostics.
    "App Language": "应用语言",
    "Interface Language:": "界面语言：",
    "Changes apply immediately across the app.": "更改会立即应用到整个应用。",
    "About": "关于",
    "Version": "版本",
    "Audio and settings stay on this Mac.": "音频与设置保留在这台 Mac 上。",
    "Support": "支持",
    "Run Quick Check": "运行快速检查",
    "View Logs": "查看日志",
    "Technical Details": "技术详情",
    "Hide Technical Details": "收起技术详情",
    "Run Diagnostics": "运行诊断",
    "Recent Logs:": "最近日志：",
    "No logs available yet.": "暂无日志。",
    "Model Management": "模型管理",
    "Speech Recognition Models": "语音识别模型",
    "These downloads are only for speech recognition. Translation models are selected on the Translation page and are managed by that service.": "这里下载的仅是语音识别模型。翻译模型请在“翻译”页面选择；离线翻译模型也可在该页面按需下载。",
    "Find a community model": "查找社区模型",
    "Search Hugging Face or paste an organization/model URL. Only faster-whisper compatible models can be installed.": "搜索 Hugging Face 或粘贴 organization/model 链接；仅可安装兼容 faster-whisper 的模型。",
    "Search": "搜索",
    "Download selected": "下载所选模型",
    "Download speech-recognition models for offline use. Smaller models are faster; larger models are more accurate.": "下载用于离线识别的语音模型。小模型速度更快，大模型识别更准确。",
    "Installed": "已安装",
    "Extremely Fast": "极速",
    "Fast": "快速",
    "Moderate": "中等",
    "Slower": "较慢",
    "Slow": "慢",
    "Fast-Moderate": "较快",
    "Low": "较低",
    "Low (English only)": "较低（仅英语）",
    "Moderate (English only)": "中等（仅英语）",
    "Good": "良好",
    "Good (English only)": "良好（仅英语）",
    "Better": "优秀",
    "Best": "最佳",
    "Very Good": "非常好",
    "Testing, low-end devices": "测试与低配置设备",
    "Testing, English only": "测试，仅英语",
    "Simple conversations": "简单对话",
    "Simple English conversations": "简单英语对话",
    "Daily use (Recommended)": "日常使用（推荐）",
    "Daily English use": "日常英语使用",
    "Classrooms, meetings": "课堂与会议",
    "English meetings": "英语会议",
    "Transcription, high-performance devices": "高性能设备与高质量转写",
    "Best balance of speed & accuracy": "速度与准确率的最佳平衡",
    "Backend:": "后端：",
    "Recommended": "推荐",
    "Cancel": "取消",
    "Download Progress": "下载进度",
    "Retry": "重试",
    "Close": "关闭",
}


def normalize_language(value: str | None) -> str:
    return "zh-Hans" if str(value).lower() in {"zh", "zh-cn", "zh_hans", "zh-hans"} else "en"


def translate(source: str, language: str) -> str:
    if normalize_language(language) == "zh-Hans":
        return ZH_HANS.get(source, source)
    return source


def _translate_widget_text(widget: QWidget, language: str) -> None:
    if isinstance(widget, (QLabel, QAbstractButton, QGroupBox)):
        source = widget.property("i18n_source_text")
        if source is None:
            source = widget.text() if hasattr(widget, "text") else widget.title()
            widget.setProperty("i18n_source_text", source)
        translated = translate(str(source), language)
        if isinstance(widget, QGroupBox):
            widget.setTitle(translated)
        else:
            widget.setText(translated)

    if isinstance(widget, QComboBox):
        sources = widget.property("i18n_combo_sources")
        if sources is None:
            sources = [widget.itemText(index) for index in range(widget.count())]
            widget.setProperty("i18n_combo_sources", sources)
        if len(sources) == widget.count():
            current_data = widget.currentData()
            current_text = widget.currentText()
            widget.blockSignals(True)
            for index, source in enumerate(sources):
                widget.setItemText(index, translate(str(source), language))
            data_index = widget.findData(current_data)
            if data_index >= 0:
                widget.setCurrentIndex(data_index)
            elif widget.isEditable():
                widget.setCurrentText(current_text)
            widget.blockSignals(False)

    if isinstance(widget, QTabWidget):
        sources = widget.property("i18n_tab_sources")
        if sources is None:
            sources = [widget.tabText(index) for index in range(widget.count())]
            widget.setProperty("i18n_tab_sources", sources)
        if len(sources) == widget.count():
            for index, source in enumerate(sources):
                widget.setTabText(index, translate(str(source), language))


def apply_language(root: QWidget, language: str) -> None:
    """Translate the existing widget tree in place, preserving form state."""
    language = normalize_language(language)
    _translate_widget_text(root, language)
    for widget in root.findChildren(QWidget):
        _translate_widget_text(widget, language)
