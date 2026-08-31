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


def test_remove_text_drops_superseded_partial_row(app):
    window = EnhancedOverlayWindow()
    window.update_text(7, "unfinished partial", "")
    window.update_text(8, "another caption", "另一条字幕")

    window.remove_text(7)

    assert [chunk_id for chunk_id, _ in window.items] == [8]
    assert 7 not in window.transcript_data
    window.close()


def test_outer_surface_stays_transparent_while_bubbles_own_opacity(app):
    window = EnhancedOverlayWindow({"window_opacity": 0.8})
    window.update_text(1, "Readable", "清晰")

    assert "background-color: transparent" in window.styleSheet()
    assert "rgba(24, 23, 21, 204)" in window.items[0][1].styleSheet()
    window.close()


def test_long_live_caption_reflows_inside_viewport_after_updates(app):
    window = EnhancedOverlayWindow({"window_width": 720, "visible_subtitles": 2})
    window.show()
    long_original = (
        "This is a long sentence that keeps changing while the speaker continues, "
        "and it must wrap inside one subtitle row instead of disappearing past the edge."
    )
    long_translation = "这是一句会随着说话继续变化的长译文，它应该在同一条字幕中按照窗口宽度换行，而不是跑到窗口外面。"
    window.update_text(1, "This is a long sentence", "这是一句长译文")
    window.update_text(1, long_original, long_translation)
    app.processEvents()

    bubble = window.items[0][1]
    assert bubble.width() <= window.scroll_area.viewport().width()
    assert bubble.original_label.height() > bubble.original_label.fontMetrics().height()
    assert window.scroll_area.horizontalScrollBar().maximum() == 0
    window.close()
