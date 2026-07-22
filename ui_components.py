"""Reusable product UI controls shared by dashboard pages."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QComboBox, QColorDialog, QPushButton


class ThemedComboBox(QComboBox):
    """Combo box whose popup is wide enough and always uses the app palette."""

    def showPopup(self):
        view = self.view()
        width = max(self.width(), self.sizeHint().width())
        if self.count():
            width = max(width, view.sizeHintForColumn(0) + 44)
        view.setMinimumWidth(min(max(width, 180), 620))
        super().showPopup()


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
