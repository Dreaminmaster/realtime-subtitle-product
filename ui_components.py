"""Reusable product UI controls shared by dashboard pages."""

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QColorDialog, QFrame, QGridLayout, QLabel,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
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
        self.setMinimumWidth(164)
        self.setObjectName("ColorWell")
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
        swatch = QPixmap(24, 24)
        swatch.fill(self._color)
        self.setIcon(QIcon(swatch))
        self.setIconSize(QSize(20, 20))
        self.setText(value.upper())
        self.setStyleSheet(
            f"/* selected color: {value} */ "
            "QPushButton { text-align: left; padding: 8px 12px; "
            "background: #292824; color: #ece9e2; border: 1px solid #4a4741; "
            "border-radius: 9px; } QPushButton:hover { border-color: #d98246; }"
        )


class SubtitlePreview(QFrame):
    """A faithful, non-floating preview of the real subtitle overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SubtitlePreviewStage")
        self.setMinimumSize(220, 210)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.addStretch()

        self.overlay = QFrame()
        self.overlay.setObjectName("SubtitlePreviewOverlay")
        overlay_layout = QVBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(18, 14, 18, 14)
        overlay_layout.setSpacing(5)
        self.original = QLabel("The subtitle window updates as you adjust it.")
        self.original.setWordWrap(True)
        self.translation = QLabel("调整时，字幕效果会在这里实时显示。")
        self.translation.setWordWrap(True)
        overlay_layout.addWidget(self.original)
        overlay_layout.addWidget(self.translation)
        root.addWidget(self.overlay)
        root.addStretch()

    def set_preview_style(self, style: dict):
        original_size = int(style.get("original_font_size", 20))
        translation_size = int(style.get("translation_font_size", 17))
        original_color = str(style.get("original_color", "#ffffff"))
        translation_color = str(style.get("translation_color", "#d99a69"))
        opacity = max(0.0, min(1.0, float(style.get("window_opacity", 0.94))))
        mode = str(style.get("display_mode", "bilingual"))
        alpha = round(opacity * 255)
        width = max(300, min(720, int(style.get("window_width", 620))))
        rows = max(1, min(8, int(style.get("visible_subtitles", 3))))
        self.overlay.setMinimumWidth(190)
        self.overlay.setMaximumWidth(min(width, 620))
        self.overlay.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.overlay.setMinimumHeight(min(230, 58 + rows * 28))
        self.overlay.setStyleSheet(
            "QFrame#SubtitlePreviewOverlay {"
            f"background: rgba(18, 18, 17, {alpha});"
            "border: 1px solid rgba(255, 255, 255, 38); border-radius: 16px;"
            "}"
        )
        self.original.setStyleSheet(
            f"color: {original_color}; font-size: {original_size}px; font-weight: 650; background: transparent;"
        )
        self.translation.setStyleSheet(
            f"color: {translation_color}; font-size: {translation_size}px; background: transparent;"
        )
        self.original.setVisible(mode != "translation_only")
        self.translation.setVisible(mode != "original_only")
