import os
import wave

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from audio_playback import LocalAudioPlayer


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_local_audio_player_loads_and_seeks_pcm_wav(app, tmp_path):
    path = tmp_path / "session.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\0\0" * 32000)
    player = LocalAudioPlayer()
    assert player.load(path) is True
    assert player.is_loaded is True
    assert 1950 <= player.duration_ms <= 2050
    player.seek(750)
    assert 700 <= player.position_ms() <= 800
    player.unload()
