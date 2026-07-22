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
    "Audio": "音频",
    "Language": "语言与翻译",
    "Appearance": "外观",
    "System": "系统",
    "Input": "输入",
    "System Audio": "系统音频",
    "Recognition": "识别",
    "Translation": "翻译",
    "Models": "模型",
    "Live subtitles": "实时字幕",
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
    "Sample Rate:": "采样率：",
    "Silence Threshold:": "静音阈值：",
    "Silence Duration:": "静音时长：",
    "Chunk Duration:": "分段时长：",
    "Silence Duration (s):": "静音时长（秒）：",
    "INPUT": "输入",
    "RECOGNITION": "识别",
    "TRANSLATION": "翻译",
    "Default microphone": "默认麦克风",
    "Off": "关闭",
    "History": "历史记录",
    "Session History": "会话记录",
    "Session:": "会话：",
    "Saved session": "保存会话",
    "Temporary session": "临时会话",
    "Saved locally · switch to Temporary for private one-off captions": "仅保存在本机 · 私密的一次性字幕可切换为临时会话",
    "Saved sessions stay only on this Mac. Choose Temporary on Live for a session that leaves no history.": "会话仅保存在这台 Mac 上。在实时字幕页选择“临时会话”即可不留下记录。",
    "Export": "导出",
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
    "FunASR Model:": "FunASR 模型：",
    "Compute Device:": "计算设备：",
    "Quantization:": "量化方式：",
    "Source Language:": "源语言：",
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
    "Agnes AI": "Agnes AI",
    "LM Studio / local server": "LM Studio / 本地服务",
    "Other OpenAI-compatible provider": "其他 OpenAI 兼容服务",
    "Mode:": "模式：",
    "API Key:": "API 密钥：",
    "Base URL:": "接口地址：",
    "Model:": "模型：",
    "Target Language:": "目标语言：",
    "Fetch": "获取",
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
    "Original Font Size:": "原文字号：",
    "Translation Font Size:": "译文字号：",
    "Original Text Color:": "原文颜色：",
    "Translation Color:": "译文颜色：",
    "Window Opacity:": "窗口透明度：",
    "Background Opacity:": "背景透明度：",
    "Window Width:": "窗口宽度：",
    "Visible Subtitle Rows:": "可见字幕条数：",
    "Display Mode:": "显示模式：",
    "Bilingual": "双语",
    "Original only": "仅原文",
    "Translation only": "仅译文",
    "Apply Style": "应用外观",
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
    "Backend:": "后端：",
    "Recommended": "推荐",
    "Cancel": "取消",
    "Download Progress": "下载进度",
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
