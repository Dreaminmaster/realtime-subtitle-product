from pathlib import Path

from model_manager import ModelManager


def test_incomplete_huggingface_cache_is_not_reported_as_installed(tmp_path, monkeypatch):
    manager = ModelManager(data_dir=tmp_path / "models")
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / ".lock").write_text("pending")
    manager._cache["small"] = {"backend": "whisper", "snapshot_path": str(incomplete)}
    monkeypatch.setattr(manager, "get_model_path", lambda *args, **kwargs: None)
    assert manager.is_downloaded("small", "whisper") is False


def test_complete_model_uses_the_same_loadable_path_check(tmp_path, monkeypatch):
    manager = ModelManager(data_dir=tmp_path / "models")
    complete = Path(tmp_path / "complete")
    complete.mkdir()
    monkeypatch.setattr(manager, "get_model_path", lambda *args, **kwargs: str(complete))
    assert manager.is_downloaded("small", "whisper") is True
