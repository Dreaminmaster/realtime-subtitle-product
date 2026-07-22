"""Product-oriented navigation for the Realtime Subtitle control center."""

from __future__ import annotations

import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class ProductNavigation(QFrame):
    """Group the former eight top-level tabs into five product sections.

    ``addTab`` and ``setTabToolTip`` mirror the subset of QTabWidget used by
    Dashboard. Feature pages keep their existing logic while users see a
    calmer, grouped navigation model.
    """

    _ROUTES = {
        "Home": ("Live", "Live", None),
        "Audio": ("Audio", "Audio", "Input"),
        "Devices": ("Audio", "Audio", "System Audio"),
        "Transcript": ("Language", "Language", "Recognition"),
        "Translate": ("Language", "Language", "Translation"),
        "Models": ("Language", "Language", "Models"),
        "Style": ("Appearance", "Appearance", None),
        "Diag": ("System", "System", None),
    }
    _MULTI_SECTIONS = {"Audio", "Language"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ProductNavigation")
        self._page_count = 0
        self._section_widgets = {}
        self._section_buttons = {}
        self._last_page_widget = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(184)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(14, 18, 14, 18)
        sidebar_layout.setSpacing(6)

        label = QLabel("CONTROL CENTER")
        label.setObjectName("SidebarEyebrow")
        sidebar_layout.addWidget(label)
        sidebar_layout.addSpacing(8)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._button_layout = sidebar_layout
        sidebar_layout.addStretch()

        privacy = QLabel("LOCAL-FIRST\nAudio stays on this Mac")
        privacy.setObjectName("PrivacyNote")
        privacy.setWordWrap(True)
        sidebar_layout.addWidget(privacy)

        self.stack = QStackedWidget()
        self.stack.setObjectName("ProductStack")

        root.addWidget(self.sidebar)
        root.addWidget(self.stack, 1)

    @staticmethod
    def _plain_label(label: str) -> str:
        plain = re.sub(r"^[^A-Za-z]+", "", label).strip()
        return plain or label.strip()

    def _create_section(self, section_key: str, nav_label: str):
        if section_key in self._MULTI_SECTIONS:
            section_widget = QTabWidget()
            section_widget.setObjectName("SectionTabs")
            section_widget.setDocumentMode(True)
            section_widget.setUsesScrollButtons(False)
        else:
            section_widget = None

        stack_index = self.stack.count()
        button = QPushButton(nav_label)
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(42)
        button.clicked.connect(
            lambda checked=False, index=stack_index: self.stack.setCurrentIndex(index)
        )
        self.button_group.addButton(button)

        # Insert before the stretch and privacy note.
        self._button_layout.insertWidget(self._button_layout.count() - 2, button)
        self._section_buttons[section_key] = button
        self._section_widgets[section_key] = section_widget
        return section_widget, button

    def addTab(self, widget: QWidget, label: str):
        plain = self._plain_label(label)
        section_key, nav_label, sub_label = self._ROUTES.get(
            plain, (plain, plain, None)
        )
        section_widget = self._section_widgets.get(section_key)
        button = self._section_buttons.get(section_key)
        if button is None:
            section_widget, button = self._create_section(section_key, nav_label)
            if section_widget is None:
                self.stack.addWidget(widget)
                self._section_widgets[section_key] = widget
            else:
                self.stack.addWidget(section_widget)

            if self.stack.count() == 1:
                button.setChecked(True)
                self.stack.setCurrentIndex(0)

        section_widget = self._section_widgets[section_key]
        if isinstance(section_widget, QTabWidget):
            section_widget.addTab(widget, sub_label or plain)

        self._page_count += 1
        self._last_page_widget = widget
        return self._page_count - 1

    def count(self):
        return self._page_count

    def setTabToolTip(self, index, tooltip):
        del index
        if self._last_page_widget is not None:
            self._last_page_widget.setToolTip(tooltip)

    def setUsesScrollButtons(self, enabled):
        del enabled

    def setElideMode(self, mode):
        del mode
