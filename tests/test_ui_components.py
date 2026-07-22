import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from ui_components import ColorButton, ThemedComboBox


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
