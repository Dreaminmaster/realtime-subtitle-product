"""Reusable product UI controls shared by dashboard pages."""

from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QKeyEvent, QMouseEvent, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QColorDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSizePolicy,
    QStyle, QStyleOption, QVBoxLayout, QWidget,
)


class ThemedComboBox(QComboBox):
    """Combo box with a compact app-owned popup instead of macOS menu chrome.

    Qt's native combo popup can add an unstyled white host window and excess
    empty space on macOS.  Keeping the value control as a real ``QComboBox``
    preserves form APIs and keyboard behavior while this small popup owns only
    the visual list boundary.
    """

    _POPUP_STYLE = """
        QFrame#ComboPopup {
            background: #282622;
            border: 1px solid #565149;
            border-radius: 10px;
        }
        QListWidget#ComboPopupList {
            background: transparent;
            color: #f5f1e9;
            border: none;
            outline: none;
            padding: 5px;
        }
        QListWidget#ComboPopupList::item {
            min-height: 32px;
            padding: 0 10px;
            border-radius: 6px;
        }
        QListWidget#ComboPopupList::item:hover {
            background: #38342f;
        }
        QListWidget#ComboPopupList::item:selected {
            background: #b9612f;
            color: white;
        }
        QListWidget#ComboPopupList::item:disabled {
            color: #77736b;
        }
        QListWidget#ComboPopupList QScrollBar:vertical {
            background: #201f1c;
            width: 9px;
            margin: 5px 3px 5px 0;
            border-radius: 4px;
        }
        QListWidget#ComboPopupList QScrollBar::handle:vertical {
            background: #625c53;
            min-height: 28px;
            border-radius: 4px;
        }
        QListWidget#ComboPopupList QScrollBar::add-line:vertical,
        QListWidget#ComboPopupList QScrollBar::sub-line:vertical {
            height: 0;
        }
        QListWidget#ComboPopupList QScrollBar::add-page:vertical,
        QListWidget#ComboPopupList QScrollBar::sub-page:vertical {
            background: transparent;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._popup = None

    def _ensure_popup(self):
        if self._popup is not None:
            return self._popup
        popup = QFrame(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        popup.setObjectName("ComboPopup")
        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        popup.setStyleSheet(self._POPUP_STYLE)
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(1, 1, 1, 1)
        self._popup_list = QListWidget()
        self._popup_list.setObjectName("ComboPopupList")
        self._popup_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._popup_list.itemClicked.connect(self._select_popup_item)
        self._popup_list.installEventFilter(self)
        layout.addWidget(self._popup_list)
        self._popup = popup
        return popup

    def _select_popup_item(self, item):
        index = int(item.data(Qt.ItemDataRole.UserRole))
        if item.flags() & Qt.ItemFlag.ItemIsEnabled:
            self.setCurrentIndex(index)
        self.hidePopup()

    def showPopup(self):
        if not self.isEnabled() or self.count() <= 0:
            return
        popup = self._ensure_popup()
        self._popup_list.clear()
        max_text_width = self.width()
        metrics = self.fontMetrics()
        model = self.model()
        for index in range(self.count()):
            item = QListWidgetItem(self.itemIcon(index), self.itemText(index))
            item.setData(Qt.ItemDataRole.UserRole, index)
            model_index = model.index(index, self.modelColumn(), self.rootModelIndex())
            flags = model.flags(model_index)
            if not flags & Qt.ItemFlag.ItemIsEnabled:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._popup_list.addItem(item)
            max_text_width = max(max_text_width, metrics.horizontalAdvance(self.itemText(index)) + 58)

        self._popup_list.setCurrentRow(max(0, self.currentIndex()))
        visible_rows = min(self.count(), 8)
        popup_width = min(max(max_text_width, self.width()), 620)
        # Keep the inherited view sizing contract for tests and any callers
        # that inspect it, even though the visible list is app-owned.
        self.view().setMinimumWidth(popup_width)
        popup_height = visible_rows * 36 + 12
        anchor = self.mapToGlobal(QPoint(0, self.height() + 5))
        screen = QApplication.screenAt(anchor) or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else QRect(anchor.x(), anchor.y(), popup_width, popup_height)
        x = min(max(available.left() + 6, anchor.x()), available.right() - popup_width - 6)
        below_y = anchor.y()
        above_y = self.mapToGlobal(QPoint(0, -popup_height - 5)).y()
        y = below_y if below_y + popup_height <= available.bottom() else max(available.top() + 6, above_y)
        popup.setGeometry(x, y, popup_width, popup_height)
        popup.show()
        popup.raise_()
        self._popup_list.setFocus()

    def hidePopup(self):
        if self._popup is not None:
            self._popup.hide()

    def eventFilter(self, watched, event):
        if watched is getattr(self, "_popup_list", None) and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                item = self._popup_list.currentItem()
                if item is not None:
                    self._select_popup_item(item)
                return True
            if key == Qt.Key.Key_Escape:
                self.hidePopup()
                self.setFocus()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.showPopup()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        """Draw a system chevron without a separate trailing button block."""
        super().paintEvent(event)
        option = QStyleOption()
        option.initFrom(self)
        option.rect = QRect(self.width() - 24, max(0, (self.height() - 14) // 2), 14, 14)
        painter = QPainter(self)
        self.style().drawPrimitive(
            QStyle.PrimitiveElement.PE_IndicatorArrowDown,
            option,
            painter,
            self,
        )


class SegmentedControl(QWidget):
    """Small popup-free selector for two to four high-frequency choices."""

    currentIndexChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._buttons = []
        self._current_index = -1
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

    def addItem(self, text, data=None):
        index = len(self._items)
        self._items.append((str(text), data))
        button = QPushButton(str(text))
        button.setObjectName("SegmentOption")
        button.setCheckable(True)
        button.setMinimumHeight(34)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda checked=False, value=index: self.setCurrentIndex(value))
        self._buttons.append(button)
        self._group.addButton(button, index)
        self._layout.addWidget(button, 1)
        if self._current_index < 0:
            self.setCurrentIndex(0)

    def findData(self, data):
        for index, (_, item_data) in enumerate(self._items):
            if item_data == data:
                return index
        return -1

    def currentIndex(self):
        return self._current_index

    def currentData(self):
        return self._items[self._current_index][1] if self._current_index >= 0 else None

    def currentText(self):
        return self._items[self._current_index][0] if self._current_index >= 0 else ""

    def setCurrentIndex(self, index):
        if not 0 <= int(index) < len(self._items):
            return
        index = int(index)
        if not self._buttons[index].isEnabled():
            return
        changed = index != self._current_index
        self._current_index = index
        self._buttons[index].setChecked(True)
        if changed:
            self.currentIndexChanged.emit(index)

    def setItemEnabled(self, data, enabled):
        index = self.findData(data)
        if index >= 0:
            self._buttons[index].setEnabled(bool(enabled))


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


class _DraggableSubtitleFrame(QFrame):
    """Preview-only draggable frame constrained to its parent stage."""

    moved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_offset = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_offset is None or not event.buttons() & Qt.MouseButton.LeftButton:
            super().mouseMoveEvent(event)
            return
        parent = self.parentWidget()
        if parent is None:
            return
        target = self.mapToParent(event.position().toPoint() - self._drag_offset)
        x = max(10, min(target.x(), parent.width() - self.width() - 10))
        y = max(10, min(target.y(), parent.height() - self.height() - 10))
        self.move(x, y)
        self.moved.emit()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_offset = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


class SubtitlePreview(QFrame):
    """Movable subtitle preview over stacked light and dark surfaces."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SubtitlePreviewStage")
        self.setMinimumSize(250, 230)
        self._user_positioned = False
        self._target_width = 360

        self.dark_surface = QFrame(self)
        self.dark_surface.setStyleSheet("background: #11110f; border: none;")
        self.light_surface = QFrame(self)
        self.light_surface.setStyleSheet("background: #e7e2d8; border: none;")
        self.dark_label = QLabel("DARK", self.dark_surface)
        self.dark_label.setStyleSheet("color: #6f6b63; font-size: 9px; font-weight: 700;")
        self.light_label = QLabel("LIGHT", self.light_surface)
        self.light_label.setStyleSheet("color: #858078; font-size: 9px; font-weight: 700;")

        self.overlay = _DraggableSubtitleFrame(self)
        self.overlay.setObjectName("SubtitlePreviewOverlay")
        overlay_layout = QVBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(18, 14, 18, 14)
        overlay_layout.setSpacing(5)
        samples = (
            ("The subtitle window updates as you adjust it.", "调整时，字幕效果会在这里实时显示。"),
            ("Each recent sentence stays visible.", "最近的每句话都会保持可见。"),
            ("Drag this preview across both backgrounds.", "拖动预览即可检查不同背景。"),
            ("Longer phrases wrap naturally without being squeezed.", "较长的句子会自然换行，不再被挤压。"),
            ("Context helps the next sentence read more smoothly.", "上下文会让下一句读起来更自然。"),
            ("Playback can follow the transcript like lyrics.", "回放时字幕会像歌词一样跟随。"),
            ("Your colors remain independent from the background.", "文字颜色与背景透明度相互独立。"),
            ("Everything remains stored locally on this Mac.", "所有内容仍只保存在这台 Mac 上。"),
        )
        self._preview_rows = []
        for original_text, translation_text in samples:
            row = QWidget(self.overlay)
            row.setStyleSheet("background: transparent;")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)
            original = QLabel(original_text)
            original.setWordWrap(True)
            translation = QLabel(translation_text)
            translation.setWordWrap(True)
            row_layout.addWidget(original)
            row_layout.addWidget(translation)
            overlay_layout.addWidget(row)
            self._preview_rows.append((row, original, translation))
        self.original = self._preview_rows[0][1]
        self.translation = self._preview_rows[0][2]
        self.overlay.moved.connect(self._mark_user_positioned)
        self.overlay.raise_()

    def _mark_user_positioned(self):
        self._user_positioned = True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        half = self.height() // 2
        self.dark_surface.setGeometry(0, 0, self.width(), half)
        self.light_surface.setGeometry(0, half, self.width(), self.height() - half)
        self.dark_label.move(14, 12)
        self.light_label.move(14, 12)
        self._fit_overlay(preserve_position=self._user_positioned)

    def _fit_overlay(self, *, preserve_position=True):
        if self.width() <= 0 or self.height() <= 0:
            return
        old_center = self.overlay.geometry().center()
        width = max(190, min(self._target_width, self.width() - 24))
        self.overlay.setFixedWidth(width)
        self.overlay.adjustSize()
        height = min(self.overlay.sizeHint().height(), self.height() - 24)
        self.overlay.resize(width, max(86, height))
        if preserve_position and old_center != QPoint(0, 0):
            x = old_center.x() - width // 2
            y = old_center.y() - self.overlay.height() // 2
        else:
            # Start across the horizontal contrast boundary so long subtitle
            # lines are not split into narrow columns.
            x = self.width() // 2 - width // 2
            y = self.height() // 2 - self.overlay.height() // 2
        x = max(10, min(x, self.width() - width - 10))
        y = max(10, min(y, self.height() - self.overlay.height() - 10))
        self.overlay.move(x, y)
        self.overlay.raise_()

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
        estimated_row_height = max(34, original_size + translation_size + 8)
        self.setMinimumHeight(max(230, min(540, 52 + rows * estimated_row_height)))
        self._target_width = min(width, 620)
        self.overlay.setMinimumWidth(190)
        self.overlay.setMaximumWidth(620)
        self.overlay.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.overlay.setMinimumHeight(min(500, 30 + rows * estimated_row_height))
        self.overlay.setStyleSheet(
            "QFrame#SubtitlePreviewOverlay {"
            f"background: rgba(18, 18, 17, {alpha});"
            "border: 1px solid rgba(255, 255, 255, 38); border-radius: 16px;"
            "}"
        )
        for index, (row_widget, original, translation) in enumerate(self._preview_rows):
            row_widget.setVisible(index < rows)
            original.setStyleSheet(
                f"color: {original_color}; font-size: {original_size}px; font-weight: 650; background: transparent;"
            )
            translation.setStyleSheet(
                f"color: {translation_color}; font-size: {translation_size}px; background: transparent;"
            )
            original.setVisible(mode != "translation_only")
            translation.setVisible(mode != "original_only")
        self._fit_overlay(preserve_position=self._user_positioned)
