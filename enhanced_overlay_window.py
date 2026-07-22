#!/usr/bin/env python3
"""
Enhanced Overlay Window - Floating subtitle display with style customization.

Features:
  - Always on top, translucent background
  - Draggable, resizable
  - Configurable font size, colors, opacity, border radius
  - Bilingual display (original + translation)
  - Toggle show/hide, switch display modes
  - Save transcript to file
"""

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QScrollArea, QFrame, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette, QAction, QFontDatabase
import time

# macOS: show on all Spaces
try:
    from AppKit import NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowCollectionBehaviorStationary
    import objc
    from ctypes import c_void_p
    HAS_APPKIT = True
except ImportError:
    HAS_APPKIT = False


class SubtitleBubble(QFrame):
    """A single subtitle bubble showing original + translation"""
    
    def __init__(self, chunk_id, timestamp, original_text, translated_text="", 
                 parent_style=None):
        super().__init__()
        self.setObjectName("SubtitleBubble")
        self.chunk_id = chunk_id
        self.parent_style = parent_style or {}
        
        # Read font sizes FIRST — used in height calculation
        original_font_size = self.parent_style.get("original_font_size", 18)
        translation_font_size = self.parent_style.get("translation_font_size", 16)
        
        self.setStyleSheet(self._get_bubble_style())
        self.setMinimumHeight(max(70, original_font_size + translation_font_size + 30))
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        self.setLayout(layout)
        
        # Timestamp
        self.timestamp_label = QLabel(f"[{timestamp}]")
        self.timestamp_label.setStyleSheet("color: rgba(200,200,200,120); font-size: 10px;")
        self.timestamp_label.setVisible(self.parent_style.get("show_timestamp", True))
        layout.addWidget(self.timestamp_label)
        
        # Original text
        self.original_label = QLabel(original_text)
        original_font_size = self.parent_style.get("original_font_size", 18)
        original_color = self.parent_style.get("original_color", "#ffffff")
        self.original_label.setStyleSheet(
            f"color: {original_color}; font-size: {original_font_size}px; "
            f"font-weight: bold; background: transparent;"
        )
        self.original_label.setWordWrap(True)
        self.original_label.setVisible(self.parent_style.get("show_original", True))
        layout.addWidget(self.original_label)
        
        # Translated text — hidden if no translation expected (off mode)
        show_trans = self.parent_style.get("show_translation", True)
        translation_color = self.parent_style.get("translation_color", "#89b4fa")
        translation_font_size = self.parent_style.get("translation_font_size", 16)
        self.translated_label = QLabel(translated_text if translated_text else "")
        self.translated_label.setStyleSheet(
            f"color: {translation_color}; font-size: {translation_font_size}px; "
            f"background: transparent;"
        )
        self.translated_label.setWordWrap(True)
        if not show_trans or not translated_text:
            self.translated_label.setVisible(False)
        layout.addWidget(self.translated_label)
        # Copy button — hidden by default, shown on hover
        self.copy_btn = QPushButton("📋")
        self.copy_btn.setToolTip("Copy to clipboard")
        self.copy_btn.setFixedSize(20, 20)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #6c7086; font-size: 10px; } "
            "QPushButton:hover { color: #cdd6f4; }"
        )
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        self.copy_btn.hide()
        layout.addWidget(self.copy_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
    
    def _get_bubble_style(self):
        opacity = max(0.3, min(1.0, float(self.parent_style.get("window_opacity", 0.94))))
        bg = self.parent_style.get("bubble_bg", f"rgba(24, 23, 21, {round(opacity * 255)})")
        radius = self.parent_style.get("bubble_radius", 14)
        return (
            f"QFrame#SubtitleBubble {{ background-color: {bg}; "
            "border: 1px solid rgba(150, 170, 220, 42); "
            f"border-radius: {radius}px; "
            f"margin-bottom: 8px; }}"
        )
    
    def update_original(self, text):
        self.original_label.setText(text)
    
        # Show copy button on hover
        self.setMouseTracking(True)
        self.enterEvent = lambda e: self.copy_btn.show()
        self.leaveEvent = lambda e: self.copy_btn.hide()
    
    def update_translated(self, text):
        show_trans = self.parent_style.get("show_translation", True)
        if text:
            self.translated_label.setText(text)
            self.translated_label.setVisible(show_trans)
        else:
            self.translated_label.setVisible(False)
    
    def copy_to_clipboard(self):
        """Copy original + translation text to clipboard."""
        import logging
        log = logging.getLogger("RealtimeSubtitle")
        parts = []
        if self.original_label.text():
            parts.append(self.original_label.text())
        if self.translated_label.isVisible() and self.translated_label.text():
            parts.append(self.translated_label.text())
        if parts:
            text = "\n".join(parts)
            QApplication.clipboard().setText(text)
            log.info("Subtitle copied to clipboard, chars=%d", len(text))
            self.copy_btn.setText("✓")
            QTimer.singleShot(800, lambda: self.copy_btn.setText("📋"))
    
    def update_style(self, parent_style):
        """Update styling dynamically"""
        self.parent_style = parent_style
        self.setStyleSheet(self._get_bubble_style())
        
        original_font_size = parent_style.get("original_font_size", 18)
        original_color = parent_style.get("original_color", "#ffffff")
        self.original_label.setStyleSheet(
            f"color: {original_color}; font-size: {original_font_size}px; "
            f"font-weight: bold; background: transparent;"
        )
        self.original_label.setVisible(parent_style.get("show_original", True))
        
        translation_font_size = parent_style.get("translation_font_size", 16)
        translation_color = parent_style.get("translation_color", "#89b4fa")
        self.translated_label.setStyleSheet(
            f"color: {translation_color}; font-size: {translation_font_size}px; "
            f"background: transparent;"
        )
        self.translated_label.setVisible(
            parent_style.get("show_translation", True)
            and bool(self.translated_label.text())
        )
        self.timestamp_label.setVisible(parent_style.get("show_timestamp", True))
        
        self.setMinimumHeight(max(70, original_font_size + translation_font_size + 30))
        self.setStyleSheet(self._get_bubble_style())


class ResizeHandle(QLabel):
    """Drag handle for window resize"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.setText("◢")
        self.setStyleSheet("color: rgba(255, 255, 255, 80); font-size: 14px;")
        self.setFixedSize(20, 20)
        self.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.startPos = None
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.startPos = event.globalPosition().toPoint()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if self.startPos:
            delta = event.globalPosition().toPoint() - self.startPos
            screen = QApplication.screenAt(event.globalPosition().toPoint()) or QApplication.primaryScreen()
            geometry = screen.availableGeometry()
            new_w = min(
                max(self.parent_window.minimumWidth(), self.parent_window.width() + delta.x()),
                int(geometry.width() * 0.92),
            )
            new_h = min(
                max(self.parent_window.minimumHeight(), self.parent_window.height() + delta.y()),
                int(geometry.height() * 0.68),
            )
            self.parent_window.resize(new_w, new_h)
            # Update stored width
            self.parent_window.subtitle_style["window_width"] = new_w
            self.startPos = event.globalPosition().toPoint()
            event.accept()
    
    def mouseReleaseEvent(self, event):
        self.startPos = None


class EnhancedOverlayWindow(QWidget):
    """Floating subtitle overlay with rich customization"""
    
    stop_requested = pyqtSignal()
    style_changed = pyqtSignal(dict)
    
    def __init__(self, subtitle_style=None):
        super().__init__()
        
        # Default style
        self.subtitle_style = {
            "window_width": 620,
            "window_opacity": 0.94,
            "original_font_size": 20,
            "translation_font_size": 17,
            "original_color": "#ffffff",
            "translation_color": "#d99a69",
            "bubble_radius": 14,
            "show_translation": True,
            "show_original": True,
            "show_timestamp": False,
            "font_family": "Helvetica Neue",
            "display_mode": "bilingual",  # bilingual, original_only, translation_only
            "auto_scroll": True,
            "visible_subtitles": 3,
            "history_limit": 250,
            "border_width": 0,
            "border_color": "rgba(255,255,255,50)",
        }
        
        if subtitle_style:
            self.subtitle_style.update(subtitle_style)
        # Older settings used max_bubbles as a destructive history cap.  Keep
        # its display intent while retaining actual scrollback history.
        if subtitle_style and "max_bubbles" in subtitle_style and "visible_subtitles" not in subtitle_style:
            self.subtitle_style["visible_subtitles"] = subtitle_style["max_bubbles"]
        self._sync_display_mode_flags()
        
        self.items = []  # [(chunk_id, widget)]
        self.transcript_data = {}  # chunk_id -> {timestamp, original, translated}
        self.is_moving = False
        self.oldPos = None
        self.hidden = False
        
        self.init_ui()
    
    def showEvent(self, event):
        super().showEvent(event)
        if HAS_APPKIT and QApplication.platformName() != "offscreen":
            self._set_all_spaces()

    def _sync_display_mode_flags(self):
        mode = self.subtitle_style.get("display_mode", "bilingual")
        if mode == "original_only":
            self.subtitle_style["show_original"] = True
            self.subtitle_style["show_translation"] = False
        elif mode == "translation_only":
            self.subtitle_style["show_original"] = False
            self.subtitle_style["show_translation"] = True
        else:
            self.subtitle_style["display_mode"] = "bilingual"
            self.subtitle_style["show_original"] = True
            self.subtitle_style["show_translation"] = True
    
    def _set_all_spaces(self):
        try:
            win_id = int(self.winId())
            ns_view = objc.objc_object(c_void_p=c_void_p(win_id))
            ns_window = ns_view.window()
            ns_window.setCollectionBehavior_(
                NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary
            )
        except Exception as e:
            print(f"[Overlay] Could not set all-spaces: {e}")
    
    def init_ui(self):
        # Window flags
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setWindowTitle("")  # prevent macOS title bar text
        self.setObjectName("OverlaySurface")
        
        # Keep glyphs fully opaque; opacity belongs to subtitle backgrounds.
        self.setWindowOpacity(1.0)
        self.setMouseTracking(True)
        self.setMinimumSize(360, 140)
        self._apply_surface_style()
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)
        
        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 7px; margin: 3px 0; }
            QScrollBar::handle:vertical { background: rgba(220,215,204,90); border-radius: 3px; min-height: 24px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Container
        self.container = QFrame()
        self.container.setStyleSheet("background: transparent;")
        self.container_layout = QVBoxLayout()
        self.container_layout.setContentsMargins(5, 5, 5, 5)
        self.container_layout.setSpacing(0)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)  # Push latest to bottom
        self.container_layout.addStretch()  # Spacer above pushes the newest rows down.
        self.container.setLayout(self.container_layout)
        
        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)
        
        # Compact control dock. It reads as one intentional surface rather
        # than a row of unrelated circular test buttons.
        self.control_frame = QFrame()
        self.control_frame.setObjectName("ControlDock")
        self.control_frame.setStyleSheet(
            "QFrame#ControlDock { background: rgba(30,29,27,230); "
            "border: 1px solid rgba(235,225,210,42); border-radius: 18px; }"
        )
        self.control_frame.setFixedHeight(40)
        control_bar = QHBoxLayout(self.control_frame)
        control_bar.setContentsMargins(7, 4, 7, 4)
        control_bar.setSpacing(4)

        self.audio_indicator = QLabel("●  Listening")
        self.audio_indicator.setStyleSheet(
            "color: #8fe7c0; border: none; background: transparent; "
            "font-size: 10px; font-weight: 600; padding: 0 7px;"
        )
        control_bar.addWidget(self.audio_indicator)
        control_bar.addSpacing(4)
        
        # Toggle translation button
        self.toggle_btn = QPushButton("A/译")
        self.toggle_btn.setToolTip("Toggle: Bilingual / Original Only / Translation Only")
        self.toggle_btn.setFixedSize(42, 28)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet(self._control_btn_style())
        self.toggle_btn.clicked.connect(self._toggle_display_mode)
        control_bar.addWidget(self.toggle_btn)
        
        # Font size buttons
        self.font_plus_btn = QPushButton("A⁺")
        self.font_plus_btn.setToolTip("Increase font size")
        self.font_plus_btn.setFixedSize(28, 28)
        self.font_plus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.font_plus_btn.setStyleSheet(self._control_btn_style())
        self.font_plus_btn.clicked.connect(self._increase_font)
        control_bar.addWidget(self.font_plus_btn)
        
        self.font_minus_btn = QPushButton("A⁻")
        self.font_minus_btn.setToolTip("Decrease font size")
        self.font_minus_btn.setFixedSize(28, 28)
        self.font_minus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.font_minus_btn.setStyleSheet(self._control_btn_style())
        self.font_minus_btn.clicked.connect(self._decrease_font)
        control_bar.addWidget(self.font_minus_btn)
        
        # Clear button
        self.clear_btn = QPushButton("⌫")
        self.clear_btn.setToolTip("Clear all subtitles")
        self.clear_btn.setFixedSize(28, 28)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet(self._control_btn_style())
        self.clear_btn.clicked.connect(self.clear_all)
        control_bar.addWidget(self.clear_btn)
        
        control_bar.addStretch()
        
        # Save button
        self.save_btn = QPushButton("Save")
        self.save_btn.setToolTip("Save a text copy of this transcript")
        self.save_btn.setFixedSize(48, 28)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(self._control_btn_style())
        self.save_btn.clicked.connect(self._save_transcript)
        control_bar.addWidget(self.save_btn)
        
        # Stop button
        self.stop_btn = QPushButton("■")
        self.stop_btn.setToolTip("Stop translation")
        self.stop_btn.setFixedSize(28, 28)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setStyleSheet(
            "QPushButton { background: rgba(102,42,62,220); color: #ffb3c5; "
            "border-radius: 14px; border: 1px solid rgba(255,140,170,75); font-size: 10px; } "
            "QPushButton:hover { background: rgba(142,52,80,235); }"
        )
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        control_bar.addWidget(self.stop_btn)
        
        # Resize handle
        self.grip = ResizeHandle(self)
        control_bar.addWidget(self.grip)
        
        main_layout.addWidget(
            self.control_frame,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )
        
        # Initial size and position — bottom-centered like standard subtitles
        screen = QApplication.primaryScreen().availableGeometry()
        maximum_width = min(960, int(screen.width() * 0.88))
        w = min(max(460, int(self.subtitle_style.get("window_width", 620))), maximum_width)
        h = min(self._height_for_visible_rows(), int(screen.height() * 0.62))
        self.subtitle_style["window_width"] = w
        self.subtitle_style["window_height"] = h
        self.resize(w, h)
        
        x = screen.x() + (screen.width() - w) // 2
        y = screen.y() + screen.height() - h - 60
        
        # Restore saved position if available
        from PyQt6.QtCore import QSettings
        settings = QSettings("RealtimeSubtitle", "Overlay")
        saved_x = settings.value("window/x")
        saved_y = settings.value("window/y")
        placement_version = int(settings.value("window/placement_version", 0) or 0)
        if placement_version == 3 and saved_x is not None and saved_y is not None:
            try:
                x, y = int(saved_x), int(saved_y)
            except (ValueError, TypeError):
                pass
        x = max(screen.x(), min(x, screen.x() + screen.width() - w))
        y = max(screen.y(), min(y, screen.y() + screen.height() - h))
        
        self.move(x, y)

    def _apply_surface_style(self):
        # The overlay is a collection of opaque-enough subtitle cards, not a
        # large panel.  Keeping the outer surface transparent prevents it from
        # covering the video or call behind it; each bubble owns its own
        # independently configurable background opacity.
        self.setStyleSheet(
            "QWidget#OverlaySurface {"
            "background-color: transparent; border: none;"
            "}"
        )
    
    def _control_btn_style(self):
        return (
            "QPushButton { background: transparent; color: #e5dfd5; "
            "border-radius: 14px; border: none; font-size: 11px; } "
            "QPushButton:hover { background: rgba(217,130,70,70); color: white; }"
        )

    def _height_for_visible_rows(self):
        rows = max(1, min(8, int(self.subtitle_style.get("visible_subtitles", 3))))
        # SubtitleBubble has a 70 px floor; include its layout spacing plus the
        # compact 40 px control dock so the chosen count is visually honest.
        return max(140, 46 + (rows * 78))
    
    def _toggle_display_mode(self):
        modes = ["bilingual", "original_only", "translation_only"]
        current = self.subtitle_style.get("display_mode", "bilingual")
        try:
            idx = modes.index(current)
            next_mode = modes[(idx + 1) % len(modes)]
        except ValueError:
            next_mode = "bilingual"
        
        self.subtitle_style["display_mode"] = next_mode
        
        # Update visibility
        if next_mode == "bilingual":
            self.subtitle_style["show_original"] = True
            self.subtitle_style["show_translation"] = True
            self.toggle_btn.setText("A/译")
            self.toggle_btn.setToolTip("Bilingual mode")
        elif next_mode == "original_only":
            self.subtitle_style["show_original"] = True
            self.subtitle_style["show_translation"] = False
            self.toggle_btn.setText("A")
            self.toggle_btn.setToolTip("Original text only")
        elif next_mode == "translation_only":
            self.subtitle_style["show_original"] = False
            self.subtitle_style["show_translation"] = True
            self.toggle_btn.setText("文")
            self.toggle_btn.setToolTip("Translation only")
        
        self._refresh_all_bubbles()
        self.style_changed.emit(self.subtitle_style.copy())
    
    def _increase_font(self):
        self.subtitle_style["original_font_size"] = min(36, self.subtitle_style["original_font_size"] + 2)
        self.subtitle_style["translation_font_size"] = min(32, self.subtitle_style["translation_font_size"] + 2)
        self._refresh_all_bubbles()
        self.style_changed.emit(self.subtitle_style.copy())
    
    def _decrease_font(self):
        self.subtitle_style["original_font_size"] = max(10, self.subtitle_style["original_font_size"] - 2)
        self.subtitle_style["translation_font_size"] = max(8, self.subtitle_style["translation_font_size"] - 2)
        self._refresh_all_bubbles()
        self.style_changed.emit(self.subtitle_style.copy())
    
    def _refresh_all_bubbles(self):
        """Refresh all existing bubbles with new style"""
        for chunk_id, widget in self.items:
            widget.update_style(self.subtitle_style)
    
    def set_style(self, style_dict: dict):
        """Set multiple style properties at once"""
        self.subtitle_style.update(style_dict)
        self._sync_display_mode_flags()
        self.setWindowOpacity(1.0)
        self._apply_surface_style()
        if "visible_subtitles" in style_dict or "display_mode" in style_dict:
            self.subtitle_style["window_height"] = self._height_for_visible_rows()
        self.resize(
            int(self.subtitle_style.get("window_width", self.width())),
            int(self.subtitle_style.get("window_height", self.height())),
        )
        self._refresh_all_bubbles()
        self.style_changed.emit(self.subtitle_style.copy())
    
    def update_text(self, chunk_id, original_text, translated_text=""):
        """Update or add a row while preserving user-controlled scrollback."""
        if not original_text and not translated_text:
            return

        scroll_bar = self.scroll_area.verticalScrollBar()
        was_near_bottom = scroll_bar.maximum() - scroll_bar.value() <= 24
        
        # Store data
        if chunk_id not in self.transcript_data:
            self.transcript_data[chunk_id] = {
                'timestamp': time.strftime("%H:%M:%S"),
                'original': original_text,
                'translated': translated_text
            }
        else:
            if original_text:
                self.transcript_data[chunk_id]['original'] = original_text
            if translated_text:
                self.transcript_data[chunk_id]['translated'] = translated_text
        
        # Check if widget exists for this chunk
        existing = None
        for cid, w in self.items:
            if cid == chunk_id:
                existing = w
                break
        
        if existing:
            if original_text:
                existing.update_original(original_text)
            if translated_text:
                existing.update_translated(translated_text)
        else:
            # The stretch remains above the rows so short transcripts sit at
            # the bottom, while long transcripts naturally become scrollable.
            timestamp = self.transcript_data[chunk_id]['timestamp']
            bubble = SubtitleBubble(
                chunk_id, timestamp, original_text, translated_text,
                parent_style=self.subtitle_style
            )
            self.items.append((chunk_id, bubble))
            self.container_layout.addWidget(bubble)
        
        # Bound memory without conflating retention with the visible row count.
        history_limit = max(20, int(self.subtitle_style.get("history_limit", 250)))
        while len(self.items) > history_limit:
            old_id, old_widget = self.items.pop(0)
            self.container_layout.removeWidget(old_widget)
            old_widget.deleteLater()
            if old_id in self.transcript_data:
                del self.transcript_data[old_id]
        
        # Auto-scroll to latest
        if self.subtitle_style.get("auto_scroll", True) and was_near_bottom:
            QTimer.singleShot(10, self._scroll_to_bottom)
    
    def _scroll_to_bottom(self):
        sb = self.scroll_area.verticalScrollBar()
        sb.setValue(sb.maximum())
    
    def toggle_hide(self):
        """Toggle window visibility"""
        if self.isVisible():
            self.hide()
            self.hidden = True
        else:
            self.show()
            self.hidden = False
    
    def clear_all(self):
        """Clear all subtitle bubbles"""
        for chunk_id, widget in self.items:
            self.container_layout.removeWidget(widget)
            widget.deleteLater()
        self.items.clear()
        self.transcript_data.clear()

    def remove_text(self, chunk_id):
        """Remove a superseded PARTIAL row after sentence-level merging."""
        for index, (existing_id, widget) in enumerate(list(self.items)):
            if existing_id != chunk_id:
                continue
            self.items.pop(index)
            self.container_layout.removeWidget(widget)
            widget.deleteLater()
            break
        self.transcript_data.pop(chunk_id, None)
    
    def update_audio_status(self, status_text, volume_level):
        """Update audio monitoring indicator"""
        if hasattr(self, "audio_indicator"):
            listening = "Listening" in status_text
            color = "#8fe7c0" if listening else "#6f7b95"
            label = "Listening" if listening else "Waiting"
            self.audio_indicator.setText(f"●  {label}")
            self.audio_indicator.setToolTip(f"Input level: {volume_level:.2f}")
            self.audio_indicator.setStyleSheet(
                f"color: {color}; border: none; background: transparent; "
                "font-size: 10px; font-weight: 600; padding: 0 7px;"
            )
    
    def _save_transcript(self):
        """Save transcript to file"""
        if not self.transcript_data:
            return
        
        from app_paths import get_transcript_dir
        transcript_dir = get_transcript_dir()
        transcript_dir.mkdir(parents=True, exist_ok=True)
        filename = transcript_dir / f"transcript_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        
        sorted_ids = sorted(self.transcript_data.keys())
        try:
            with filename.open("w", encoding="utf-8") as f:
                f.write(f"Transcript - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                for cid in sorted_ids:
                    data = self.transcript_data[cid]
                    f.write(f"[{data['timestamp']}] #{cid}\n")
                    f.write(f"Original: {data['original']}\n")
                    f.write(f"Translation: {data['translated']}\n")
                    f.write("-" * 40 + "\n")
            
            original_text = self.save_btn.text()
            self.save_btn.setText("✓")
            self.save_btn.setToolTip(f"Saved to {filename}")
            QTimer.singleShot(2000, lambda: self.save_btn.setText(original_text))
            
        except Exception as e:
            self.save_btn.setText("✗")
            QTimer.singleShot(2000, lambda: self.save_btn.setText("Save"))
            print(f"[Overlay] Save error: {e}")
    
    # Dragging
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_moving = True
            self.oldPos = event.globalPosition().toPoint()
    
    def mouseMoveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if self.is_moving and self.oldPos:
            delta = event.globalPosition().toPoint() - self.oldPos
            new_x = self.x() + delta.x()
            new_y = self.y() + delta.y()
            
            # Constrain to current screen rectangle
            screen = QApplication.screenAt(event.globalPosition().toPoint())
            if screen is None:
                screen = QApplication.primaryScreen()
            geo = screen.availableGeometry()
            new_x = max(geo.x(), min(new_x, geo.x() + geo.width() - self.width()))
            new_y = max(geo.y(), min(new_y, geo.y() + geo.height() - self.height()))
            
            self.move(new_x, new_y)
            self.oldPos = event.globalPosition().toPoint()
    
    def mouseReleaseEvent(self, event):
        self.is_moving = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        # Persist position
        from PyQt6.QtCore import QSettings
        settings = QSettings("RealtimeSubtitle", "Overlay")
        settings.setValue("window/x", self.x())
        settings.setValue("window/y", self.y())
        settings.setValue("window/placement_version", 3)


# For backward compatibility
OverlayWindow = EnhancedOverlayWindow
