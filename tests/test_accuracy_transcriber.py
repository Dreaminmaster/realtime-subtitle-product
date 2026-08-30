import accuracy_transcriber
from config import config
from model_manager import model_manager
import transcriber as transcriber_module


def test_factory_is_off_by_default(monkeypatch):
    monkeypatch.setattr(config, "enhanced_accuracy", False)
    assert accuracy_transcriber.create_accuracy_transcriber() is None


def test_factory_does_not_trigger_an_implicit_download(monkeypatch):
    monkeypatch.setattr(config, "enhanced_accuracy", True)
    monkeypatch.setattr(config, "accuracy_profile", "fast")
    monkeypatch.setattr(config, "asr_backend", "funasr")
    monkeypatch.setattr(model_manager, "get_model_path", lambda *args: None)
    assert accuracy_transcriber.create_accuracy_transcriber() is None


def test_factory_uses_the_resolved_local_model(monkeypatch):
    created = {}

    class FakeTranscriber:
        def __init__(self, **kwargs):
            created.update(kwargs)
            self.warmed = False

        def warmup(self):
            self.warmed = True

    monkeypatch.setattr(config, "enhanced_accuracy", True)
    monkeypatch.setattr(config, "accuracy_profile", "fast")
    monkeypatch.setattr(config, "asr_backend", "funasr")
    monkeypatch.setattr(config, "source_language", "en")
    monkeypatch.setattr(model_manager, "get_model_path", lambda *args: "/local/small")
    monkeypatch.setattr(transcriber_module, "Transcriber", FakeTranscriber)

    plan, runtime = accuracy_transcriber.create_accuracy_transcriber()

    assert plan.model_id == "small"
    assert created["model_size"] == "/local/small"
    assert created["device"] == "cpu"
    assert created["compute_type"] == "int8"
    assert created["language"] == "en"
    assert runtime.warmed is True
