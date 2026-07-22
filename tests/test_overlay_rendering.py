import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from enhanced_overlay_window import EnhancedOverlayWindow, SubtitleBubble


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_translated_label_is_in_layout_and_visible(app):
    bubble = SubtitleBubble(
        1,
        "12:00:00",
        "Hello",
        "你好",
        parent_style={"show_original": True, "show_translation": True},
    )
    bubble.show()
    app.processEvents()
    assert bubble.layout().indexOf(bubble.translated_label) >= 0
    assert bubble.translated_label.isVisible()
    bubble.close()


def test_original_only_hides_translation(app):
    window = EnhancedOverlayWindow({"display_mode": "original_only"})
    window.update_text(1, "Hello", "你好")
    window.show()
    app.processEvents()
    bubble = window.items[0][1]
    assert bubble.original_label.isVisible()
    assert not bubble.translated_label.isVisible()
    window.close()


def test_translation_only_hides_original(app):
    window = EnhancedOverlayWindow({"display_mode": "translation_only"})
    window.update_text(1, "Hello", "你好")
    window.show()
    app.processEvents()
    bubble = window.items[0][1]
    assert not bubble.original_label.isVisible()
    assert bubble.translated_label.isVisible()
    window.close()


def test_set_style_updates_mode_visibility(app):
    window = EnhancedOverlayWindow()
    window.update_text(1, "Hello", "你好")
    window.show()
    app.processEvents()
    bubble = window.items[0][1]

    window.set_style({"display_mode": "translation_only"})
    app.processEvents()
    assert not bubble.original_label.isVisible()
    assert bubble.translated_label.isVisible()
    window.close()


def test_background_opacity_never_fades_text_window(app):
    window = EnhancedOverlayWindow({"window_opacity": 0.35})
    window.update_text(1, "Readable", "清晰")
    window.show()
    app.processEvents()
    assert window.windowOpacity() == 1.0
    assert "89" in window.items[0][1].styleSheet()  # round(.35 * 255)
    window.close()


def test_overlay_keeps_history_beyond_visible_row_count(app):
    window = EnhancedOverlayWindow()
    for chunk_id in range(1, 4):
        window.update_text(chunk_id, f"Line {chunk_id}", f"第 {chunk_id} 行")

    assert [chunk_id for chunk_id, _ in window.items] == [1, 2, 3]
    assert set(window.transcript_data) == {1, 2, 3}
    window.close()


def test_visible_row_count_changes_height_without_deleting_history(app):
    window = EnhancedOverlayWindow({"visible_subtitles": 2})
    initial_height = window.height()
    for chunk_id in range(1, 8):
        window.update_text(chunk_id, f"Line {chunk_id}", f"第 {chunk_id} 行")

    window.set_style({"visible_subtitles": 5})

    assert window.height() > initial_height
    assert len(window.items) == 7
    assert len(window.transcript_data) == 7
    window.close()


def test_history_limit_is_a_safety_cap_not_visible_count(app):
    window = EnhancedOverlayWindow({"visible_subtitles": 1, "history_limit": 20})
    for chunk_id in range(25):
        window.update_text(chunk_id, str(chunk_id), str(chunk_id))

    assert len(window.items) == 20
    assert [chunk_id for chunk_id, _ in window.items][:2] == [5, 6]
    window.close()
