"""Reusable product UI controls shared by dashboard pages."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QColorDialog, QGridLayout, QPushButton, QWidget,
)


class ThemedComboBox(QComboBox):
    """Combo box whose popup is wide enough and always uses the app palette."""

    def showPopup(self):
        view = self.view()
        width = max(self.width(), self.sizeHint().width())
        if self.count():
            width = max(width, view.sizeHintForColumn(0) + 44)
        view.setMinimumWidth(min(max(width, 180), 620))
        super().showPopup()


class ProviderSelector(QWidget):
    """Popup-free provider grid with a QComboBox-compatible value API."""

    currentIndexChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._buttons = []
        self._current_index = -1
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(8)
        self._layout.setVerticalSpacing(8)

    def addItem(self, text, data=None):
        index = len(self._items)
        self._items.append((str(text), data))
        button = QPushButton(str(text))
        button.setObjectName("ProviderOption")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(42)
        button.clicked.connect(lambda checked=False, value=index: self.setCurrentIndex(value))
        self._buttons.append(button)
        self._group.addButton(button, index)
        self._layout.addWidget(button, index // 2, index % 2)
        if self._current_index < 0:
            self.setCurrentIndex(0)

    def findData(self, data):
        for index, (_, item_data) in enumerate(self._items):
            if item_data == data:
                return index
        return -1

    def setCurrentIndex(self, index):
        if not 0 <= int(index) < len(self._items):
            return
        index = int(index)
        changed = index != self._current_index
        self._current_index = index
        self._buttons[index].setChecked(True)
        if changed:
            self.currentIndexChanged.emit(index)

    def currentData(self):
        return self._items[self._current_index][1] if self._current_index >= 0 else None

    def currentText(self):
        return self._buttons[self._current_index].text() if self._current_index >= 0 else ""


class ColorButton(QPushButton):
    """Compact color swatch that opens the native modern color panel."""

    colorChanged = pyqtSignal(str)

    def __init__(self, color="#ffffff", parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        if not self._color.isValid():
            self._color = QColor("#ffffff")
        self.setMinimumWidth(150)
        self.clicked.connect(self._choose)
        self._refresh()

    def color(self):
        return self._color.name()

    def setColor(self, value):
        color = QColor(value)
        if color.isValid():
            self._color = color
            self._refresh()

    def currentText(self):
        return self.color()

    def _choose(self):
        chosen = QColorDialog.getColor(
            self._color, self, "Choose subtitle color", QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if chosen.isValid():
            chosen.setAlpha(255)  # Text opacity is independent from background opacity.
            self._color = chosen
            self._refresh()
            self.colorChanged.emit(self.color())

    def _refresh(self):
        value = self.color()
        self.setText(value.upper())
        self.setStyleSheet(
            "QPushButton { text-align: left; padding-left: 42px; "
            f"background: {value}; color: {'#161513' if self._color.lightness() > 145 else '#ffffff'}; "
            "border: 1px solid #5a564e; border-radius: 8px; }"
        )
