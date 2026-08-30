from pathlib import Path
import wave

from session_export import copy_audio_export, write_bundle, write_text_export


def _wav(path: Path):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\0\0" * 1600)


def test_export_text_audio_and_bundle_are_scoped_to_destination(tmp_path):
    source = tmp_path / "source.wav"
    _wav(source)
    text_result = write_text_export(tmp_path / "one.txt", "hello\n你好")
    audio_result = copy_audio_export(source, tmp_path / "one.wav")
    bundle = write_bundle(tmp_path, "Selected session", "hello", source)
    assert text_result.text_path.read_text(encoding="utf-8") == "hello\n你好"
    assert audio_result.audio_path.stat().st_size > 44
    assert bundle.text_path.parent.name == "Selected session"
    assert bundle.text_path.is_file() and bundle.audio_path.is_file()
