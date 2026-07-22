import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget

from localization import apply_language, normalize_language


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_language_normalization():
    assert normalize_language("zh-CN") == "zh-Hans"
    assert normalize_language("zh-Hans") == "zh-Hans"
    assert normalize_language("anything-else") == "en"


def test_widget_tree_switches_both_directions_without_losing_combo_data(app):
    root = QWidget()
    layout = QVBoxLayout(root)
    label = QLabel("App Language")
    button = QPushButton("Save Changes")
    combo = QComboBox()
    combo.addItem("Chinese", "Chinese")
    combo.addItem("English", "English")
    combo.setCurrentIndex(1)
    layout.addWidget(label)
    layout.addWidget(button)
    layout.addWidget(combo)

    apply_language(root, "zh-Hans")
    assert label.text() == "应用语言"
    assert button.text() == "保存更改"
    assert combo.itemText(0) == "中文"
    assert combo.currentData() == "English"

    apply_language(root, "en")
    assert label.text() == "App Language"
    assert button.text() == "Save Changes"
    assert combo.itemText(0) == "Chinese"
    assert combo.currentData() == "English"
