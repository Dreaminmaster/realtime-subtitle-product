"""Capture deterministic dashboard states for visual review.

This helper keeps screenshots away from the user's real configuration and
session library.  It is intentionally small so release UI changes can be
checked at the same viewport before packaging.
"""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _prepare_environment() -> Path:
    state_dir = Path(tempfile.mkdtemp(prefix="realtime-subtitle-ui-"))
    os.environ.setdefault("REALTIME_SUBTITLE_APP_SUPPORT_DIR", str(state_dir))
    os.environ.setdefault("REALTIME_SUBTITLE_CONFIG_PATH", str(state_dir / "config.ini"))
    if os.getenv("REALTIME_SUBTITLE_PLATFORM") == "Windows":
        resources = state_dir / "resources"
        for model_id in ("opus-en-zh", "opus-zh-en"):
            model = resources / "models" / "translation" / model_id
            model.mkdir(parents=True, exist_ok=True)
            for name in ("model.bin", "source.spm", "target.spm"):
                (model / name).write_bytes(b"ui-review")
        os.environ.setdefault("REALTIME_SUBTITLE_RESOURCES_DIR", str(resources))
    return state_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/tmp/realtime-ui-review"))
    parser.add_argument("--width", type=int, default=1200)
    parser.add_argument("--height", type=int, default=780)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()

    state_dir = _prepare_environment()

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QListWidgetItem
    from dashboard import Dashboard

    app = QApplication.instance() or QApplication([])
    args.output.mkdir(parents=True, exist_ok=True)

    dashboard = Dashboard()
    dashboard.resize(args.width, args.height)
    dashboard.show()
    app.processEvents()

    dashboard.grab().save(str(args.output / "01-live.png"))

    dashboard.tabs.stack.setCurrentIndex(2)
    settings = dashboard.tabs._section_widgets["Settings"]
    settings.setCurrentIndex(4)
    app.processEvents()
    dashboard.grab().save(str(args.output / "02-appearance.png"))

    settings.setCurrentIndex(5)
    dashboard.ui_language_combo.setCurrentIndex(
        dashboard.ui_language_combo.findData("zh-Hans")
    )
    app.processEvents()
    dashboard.grab().save(str(args.output / "03-system.png"))
    dashboard.language_card.grab().save(str(args.output / "03a-language-card.png"))

    dashboard.tabs.showRoute("Settings", "Recognition")
    dashboard.enhanced_accuracy_mode.setCurrentIndex(1)
    app.processEvents()
    dashboard.grab().save(str(args.output / "04-enhanced-recognition.png"))

    dashboard.tabs.showRoute("Settings", "Translation")
    native_mode = "offline" if os.getenv("REALTIME_SUBTITLE_PLATFORM") == "Windows" else "fast"
    dashboard.translation_mode.setCurrentIndex(
        dashboard.translation_mode.findData(native_mode)
    )
    dashboard.target_lang.setCurrentIndex(
        dashboard.target_lang.findData("Chinese" if native_mode == "offline" else "English")
    )
    app.processEvents()
    dashboard.grab().save(str(args.output / (
        "04a-windows-translation.png" if native_mode == "offline"
        else "04a-apple-translation.png"
    )))
    dashboard.target_lang.showPopup()
    app.processEvents()
    dashboard.target_lang._popup.grab().save(str(args.output / "04b-target-language-popup.png"))
    dashboard.target_lang.hidePopup()

    dashboard.translation_mode.setCurrentIndex(
        dashboard.translation_mode.findData("offline")
    )
    dashboard.target_lang.setCurrentIndex(dashboard.target_lang.findData("Chinese"))
    app.processEvents()
    dashboard.grab().save(str(args.output / "04c-offline-translation.png"))

    from src.segment_api import SegmentView, SessionView
    from session_recording import SessionAudioRecorder
    import numpy as np

    recording = state_dir / "review.wav"
    recorder = SessionAudioRecorder(recording, 16000)
    recorder.start()
    seconds = 7
    timeline = np.arange(16000 * seconds, dtype=np.float32) / 16000.0
    recorder.write((0.08 * np.sin(2 * math.pi * 220 * timeline)).astype(np.float32))
    recorder.stop()
    session = SessionView(
        session_id="review",
        status="CLOSED",
        created_at=0.0,
        updated_at=0.0,
        metadata={
            "record_audio": True,
            "audio_path": str(recording),
            "audio_duration": float(seconds),
        },
    )
    segments = [
        SegmentView("review", "1", 1, "FINAL", "Welcome to your saved session.", "欢迎查看保存的会话。", "DONE", start_offset=0.0, end_offset=2.1),
        SegmentView("review", "2", 1, "FINAL", "The active line follows the recording like lyrics.", "当前字幕会像歌词一样跟随录音。", "DONE", start_offset=2.1, end_offset=4.8),
        SegmentView("review", "3", 1, "FINAL", "Click any line to jump to that moment.", "点击任意字幕即可跳转到对应时间。", "DONE", start_offset=4.8, end_offset=7.0),
    ]
    dashboard.tabs.stack.setCurrentIndex(1)
    dashboard.history_list.clear()
    history_item = QListWidgetItem("Today  10:24\nEnglish → Chinese")
    history_item.setData(Qt.ItemDataRole.UserRole, "review")
    dashboard.history_list.addItem(history_item)
    dashboard.history_list.setCurrentItem(history_item)
    dashboard.history_player.set_session(session, segments)
    dashboard.history_player._on_position_changed(2600)
    app.processEvents()
    dashboard.grab().save(str(args.output / "04-session-playback.png"))
    dashboard.resize(900, args.height)
    app.processEvents()
    dashboard.grab().save(str(args.output / "04d-session-narrow.png"))

    from enhanced_overlay_window import EnhancedOverlayWindow
    overlay = EnhancedOverlayWindow({
        "ui_language": "zh-Hans",
        "window_width": 760,
        "visible_subtitles": 2,
        "original_font_size": 22,
        "translation_font_size": 19,
    })
    overlay.resize(760, 360)
    overlay.update_caption_state(
        1,
        "You also mentioned a long section about making money, investing it properly, and the emotional and logical parts of the decision.",
        "你还提到了一段很长的内容，讲如何赚钱、合理投资，以及决策中情感与逻辑的不同部分。",
        "FINAL",
        3,
    )
    overlay.update_caption_state(
        2,
        "This changing draft remains one subtitle and wraps naturally inside the current window while the speaker continues",
        "这条正在变化的草稿仍然属于同一条字幕，并会在当前窗口内自然换行",
        "PARTIAL",
        2,
    )
    overlay.show()
    app.processEvents()
    overlay.grab().save(str(args.output / "04e-overlay-long-wrap.png"))
    overlay.close()

    dashboard.tabs.stack.setCurrentIndex(2)
    settings.setCurrentIndex(1)
    dashboard.source_language.showPopup()
    app.processEvents()
    dashboard.source_language._popup.grab().save(str(args.output / "05-combo-popup.png"))
    dashboard.source_language.hidePopup()

    from session_export import SessionExportDialog

    export_dialog = SessionExportDialog(
        display_mode="bilingual", has_audio=True, parent=dashboard
    )
    export_dialog.show()
    app.processEvents()
    export_dialog.grab().save(str(args.output / "06-export-dialog.png"))
    export_dialog.close()

    if args.reference and args.reference.is_file():
        from PyQt6.QtCore import QRect
        from PyQt6.QtGui import QColor, QImage, QPainter

        reference = QImage(str(args.reference))
        implementation = QImage(str(args.output / "04-session-playback.png"))
        slot_width, slot_height = 1200, 780
        comparison = QImage(slot_width * 2, slot_height, QImage.Format.Format_ARGB32)
        comparison.fill(QColor("#171716"))
        painter = QPainter(comparison)
        for index, source in enumerate((reference, implementation)):
            scaled = source.scaled(
                slot_width - 24,
                slot_height - 24,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = index * slot_width + (slot_width - scaled.width()) // 2
            y = (slot_height - scaled.height()) // 2
            painter.drawImage(QRect(x, y, scaled.width(), scaled.height()), scaled)
        painter.end()
        comparison.save(str(args.output / "07-history-comparison.png"))

    dashboard.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
