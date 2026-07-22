import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget

from product_navigation import ProductNavigation


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_eight_feature_pages_are_grouped_into_five_sections(app):
    navigation = ProductNavigation()
    labels = [
        "🏠 Home",
        "🎙 Audio",
        "🔧 Devices",
        "📝 Transcript",
        "🎯 Translate",
        "📦 Models",
        "🎨 Style",
        "🔍 Diag",
    ]

    for label in labels:
        navigation.addTab(QWidget(), label)

    assert navigation.count() == 8
    assert navigation.stack.count() == 5
    assert list(navigation._section_buttons) == [
        "Live",
        "Audio",
        "Language",
        "Appearance",
        "System",
    ]
    assert isinstance(navigation._section_widgets["Audio"], QTabWidget)
    assert navigation._section_widgets["Audio"].count() == 2
    assert navigation._section_widgets["Language"].count() == 3
    assert [
        navigation._section_widgets["Language"].tabText(index)
        for index in range(3)
    ] == ["Recognition", "Translation", "Models"]


def test_first_section_is_selected_and_tooltip_reaches_page(app):
    navigation = ProductNavigation()
    page = QWidget()
    index = navigation.addTab(page, "🏠 Home")
    navigation.setTabToolTip(index, "Live subtitle controls")

    assert navigation.stack.currentIndex() == 0
    assert navigation._section_buttons["Live"].isChecked()
    assert page.toolTip() == "Live subtitle controls"
