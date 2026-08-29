import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QWidget

from product_navigation import ProductNavigation, SectionTabs


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_eight_feature_pages_are_grouped_into_live_and_settings(app):
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
    assert navigation.stack.count() == 2
    assert list(navigation._section_buttons) == [
        "Live",
        "Settings",
    ]
    assert isinstance(navigation._section_widgets["Settings"], SectionTabs)
    assert navigation._section_widgets["Settings"].count() == 7
    assert [
        navigation._section_widgets["Settings"].tabText(index)
        for index in range(7)
    ] == ["Audio", "System Audio", "Recognition", "Translation", "Models", "Appearance", "System"]


def test_first_section_is_selected_and_tooltip_reaches_page(app):
    navigation = ProductNavigation()
    page = QWidget()
    index = navigation.addTab(page, "🏠 Home")
    navigation.setTabToolTip(index, "Live subtitle controls")

    assert navigation.stack.currentIndex() == 0
    assert navigation._section_buttons["Live"].isChecked()
    assert page.toolTip() == "Live subtitle controls"
