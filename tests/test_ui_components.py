import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from ui_components import (
    ColorButton,
    ProviderSelector,
    SegmentedControl,
    SubtitlePreview,
    ThemedComboBox,
)
from progress_panel import ProgressPanel
from progress_events import ProgressEvent
from model_progress_channel import ModelProgressChannel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_combo_popup_expands_for_long_items(app):
    combo = ThemedComboBox()
    combo.resize(90, 30)
    combo.addItem("Other OpenAI-compatible translation provider")
    combo.showPopup()
    app.processEvents()
    assert combo.view().minimumWidth() > combo.width()
    combo.hidePopup()


def test_color_button_exposes_opaque_hex_value(app):
    button = ColorButton("#d99a69")
    assert button.currentText() == "#d99a69"
    assert "#d99a69" in button.styleSheet()


def test_provider_selector_has_popup_free_value_api(app):
    selector = ProviderSelector()
    selector.addItem("No translation", "off")
    selector.addItem("LM Studio", "local")
    selector.setCurrentIndex(selector.findData("local"))
    assert selector.currentData() == "local"
    assert selector.currentText() == "LM Studio"


def test_segmented_control_switches_without_popup(app):
    selector = SegmentedControl()
    selector.addItem("Both", "bilingual")
    selector.addItem("Original", "original_only")
    selector.setCurrentIndex(selector.findData("original_only"))
    assert selector.currentData() == "original_only"
    assert selector.currentText() == "Original"


def test_subtitle_preview_overlay_can_move_across_contrast_stage(app):
    preview = SubtitlePreview()
    preview.resize(520, 260)
    preview.show()
    app.processEvents()
    initial = preview.overlay.pos()
    preview.overlay.move(12, 14)
    preview._mark_user_positioned()
    preview.resize(540, 280)
    app.processEvents()
    assert preview.overlay.pos() != initial
    assert preview.dark_surface.width() + preview.light_surface.width() == preview.width()


def test_download_progress_uses_current_product_palette(app):
    panel = ProgressPanel()
    panel.set_progress(ProgressEvent("tiny", "downloading", "Downloading", percent=42))
    assert panel.bar.value() == 42
    assert "#313244" not in panel.styleSheet()
    assert "#d98246" in panel.styleSheet()


def test_model_progress_messages_follow_chinese_ui_language():
    channel = ModelProgressChannel("tiny", language="zh-Hans")
    assert channel.on_start().message == "正在连接模型仓库…"
    assert channel.on_success(1).message == "下载完成"


def test_terminal_download_progress_can_be_dismissed(app):
    panel = ProgressPanel()
    panel.set_progress(ProgressEvent(
        "tiny", "succeeded", "Download complete", percent=100, can_cancel=False
    ))
    assert panel.dismiss_btn.isVisible() is False  # parent is not shown yet
    assert panel.dismiss_btn.isHidden() is False
