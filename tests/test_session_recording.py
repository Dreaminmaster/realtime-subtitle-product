import wave

import numpy as np

from session_recording import SessionAudioRecorder, get_session_recording_path


def test_session_audio_recorder_writes_pcm_and_tracks_offsets(tmp_path):
    path = tmp_path / "session.wav"
    recorder = SessionAudioRecorder(path, 16000)
    recorder.start()
    first = recorder.write(np.ones(1600, dtype=np.float32) * 0.25)
    second = recorder.write(np.zeros(800, dtype=np.float32))
    duration = recorder.stop()

    assert first == (0.0, 0.1)
    assert second == (0.1, 0.15)
    assert duration == 0.15
    with wave.open(str(path), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getframerate() == 16000
        assert audio.getnframes() == 2400


def test_recording_path_rejects_empty_session_id(monkeypatch, tmp_path):
    monkeypatch.setattr("session_recording.get_recordings_dir", lambda: tmp_path)
    assert get_session_recording_path("safe-id").name == "safe-id.wav"
    try:
        get_session_recording_path("///")
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe empty id must be rejected")
