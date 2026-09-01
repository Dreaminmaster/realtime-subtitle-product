import sys
from types import SimpleNamespace

import numpy as np

from platform_support import current_platform, local_app_data_dir
from translation_model_manager import TranslationModelManager
from windows_system_audio import WindowsSystemAudioCapture


def test_windows_capabilities_and_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    capabilities = current_platform("Windows")
    assert capabilities.supports_windows_loopback is True
    assert capabilities.supports_apple_translation is False
    assert capabilities.native_font_family == "Segoe UI Variable"
    monkeypatch.setenv("REALTIME_SUBTITLE_PLATFORM", "Windows")
    assert local_app_data_dir() == tmp_path / "RealtimeSubtitle"


def test_wasapi_capture_downmixes_and_resamples(monkeypatch):
    capture = WindowsSystemAudioCapture(
        sample_rate=16000,
        capture_sample_rate=48000,
        streaming_step_size=0.2,
    )

    class Recorder:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def record(self, numframes):
            capture.running = False
            left = np.linspace(-1.0, 1.0, numframes, dtype=np.float32)
            return np.column_stack((left, left))

    speaker = SimpleNamespace(id="speaker-1", name="Speakers")
    microphone = SimpleNamespace(recorder=lambda **_kwargs: Recorder())
    fake_soundcard = SimpleNamespace(
        default_speaker=lambda: speaker,
        all_speakers=lambda: [speaker],
        get_microphone=lambda **_kwargs: microphone,
    )
    monkeypatch.setitem(sys.modules, "soundcard", fake_soundcard)
    monkeypatch.setattr("windows_system_audio.platform.system", lambda: "Windows")

    chunks = list(capture.generator())
    assert len(chunks) == 1
    assert chunks[0].dtype == np.float32
    assert 1500 <= chunks[0].size <= 1700


def test_bundled_translation_model_precedes_download(tmp_path):
    user = tmp_path / "user"
    bundled = tmp_path / "resources" / "translation"
    path = bundled / "opus-en-zh"
    path.mkdir(parents=True)
    (path / "model.bin").write_bytes(b"model")
    (path / "source.spm").write_bytes(b"source")
    (path / "target.spm").write_bytes(b"target")

    manager = TranslationModelManager(user, bundled_root=bundled)
    assert manager.is_bundled("opus-en-zh") is True
    assert manager.is_downloaded("opus-en-zh") is True
    assert manager.assets("opus-en-zh")[0] == path


def test_windows_release_contract_contains_native_audio_and_models():
    from pathlib import Path

    build = Path("build_windows.ps1").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/build-dmg.yml").read_text(encoding="utf-8")
    requirements = Path("requirements-core.txt").read_text(encoding="utf-8")
    assert "bundle_release_models.py" in build
    assert "windows-x64-setup.exe" in build
    assert "Inno Setup 6" in build
    assert "soundcard" in requirements
    assert "build-windows" in workflow


def test_windows_metrics_falls_back_without_posix_resource(monkeypatch):
    import src.runtime_metrics as runtime_metrics

    monkeypatch.setattr(runtime_metrics, "resource", None)
    monkeypatch.setattr(runtime_metrics.sys, "platform", "win32")
    value = runtime_metrics._process_peak_rss_mb()
    assert isinstance(value, float)
    assert value >= 0.0
