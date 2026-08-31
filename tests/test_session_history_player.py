import os
import wave

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from session_history_player import SessionHistoryPlayer
from src.segment_api import SegmentView, SessionView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_history_view_mode_and_lyrics_highlight(app, tmp_path):
    audio = tmp_path / "session.wav"
    with wave.open(str(audio), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\0\0" * 64000)
    session = SessionView(
        "s1", "CLOSED", 0.0, 0.0,
        metadata={"record_audio": True, "audio_path": str(audio), "audio_duration": 4.0},
    )
    segments = [
        SegmentView("s1", "a", 1, "FINAL", "first", "第一句", "DONE", start_offset=0.0, end_offset=2.0),
        SegmentView("s1", "b", 1, "FINAL", "second", "第二句", "DONE", start_offset=2.0, end_offset=4.0),
    ]
    player = SessionHistoryPlayer()
    player.set_session(session, segments)
    assert player.play_button.isEnabled()
    player.view_mode.setCurrentIndex(player.view_mode.findData("translation_only"))
    assert all(line.original.isHidden() for line in player._line_widgets)
    player._on_position_changed(2500)
    assert player._active_index == 1
    assert player._line_widgets[1].property("active") is True
    assert player._line_widgets[0].property("active") is False
    player.set_language("zh-Hans")
    assert player.header.text() == "会话时间轴"
    assert "录音已就绪" in player.recording_hint.text()


def test_transcript_lines_flow_without_bubble_selection(app):
    session = SessionView("s2", "CLOSED", 0.0, 0.0, metadata={"record_audio": False})
    segments = [
        SegmentView(
            "s2", "long", 1, "FINAL",
            "A long subtitle should wrap naturally across the available width instead of being clipped.",
            "较长的字幕应该根据可用宽度自然换行，而不是被固定气泡挤压。", "DONE",
            start_offset=0.0, end_offset=3.0,
        )
    ]
    player = SessionHistoryPlayer()
    player.resize(700, 360)
    player.show()
    player.set_session(session, segments)
    app.processEvents()
    line = player._line_widgets[0]
    assert "border-radius" not in line.styleSheet()
    assert player.transcript.selectionMode() == player.transcript.SelectionMode.NoSelection
    assert "不能" in player.recording_hint.text() or "only" in player.recording_hint.text()
    assert player.transport.isHidden()


def test_history_reflows_when_window_narrows_without_horizontal_scroll(app):
    session = SessionView("s3", "CLOSED", 0.0, 0.0, metadata={"record_audio": False})
    segments = [
        SegmentView(
            "s3", "long", 1, "FINAL",
            "A long saved sentence must remain readable after the app window becomes much narrower, without asking the user to pan left and right.",
            "保存下来的长句在应用窗口明显变窄后也应该保持可读，并在当前区域内自然换行。",
            "DONE", start_offset=0.0, end_offset=4.0,
        )
    ]
    player = SessionHistoryPlayer()
    player.resize(760, 400)
    player.show()
    player.set_session(session, segments)
    app.processEvents()
    wide_height = player._line_items[0].sizeHint().height()

    player.resize(440, 400)
    app.processEvents()
    player._sync_all_line_sizes()
    narrow_height = player._line_items[0].sizeHint().height()

    assert player.transcript.horizontalScrollBar().maximum() == 0
    assert narrow_height > wide_height
    assert player._line_widgets[0].width() <= player.transcript.viewport().width()
