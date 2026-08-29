from types import SimpleNamespace

import pytest

from model_catalog import is_compatible_faster_whisper, normalize_huggingface_repo


def _siblings(*names):
    return [SimpleNamespace(rfilename=name) for name in names]


def test_normalize_repo_id_and_url():
    assert normalize_huggingface_repo("Systran/faster-whisper-small") == "Systran/faster-whisper-small"
    assert normalize_huggingface_repo(
        "https://huggingface.co/Systran/faster-whisper-small/tree/main"
    ) == "Systran/faster-whisper-small"


def test_rejects_non_huggingface_url():
    with pytest.raises(ValueError, match="huggingface.co"):
        normalize_huggingface_repo("https://example.com/org/model")


def test_compatibility_requires_ct2_files():
    assert is_compatible_faster_whisper(
        _siblings("config.json", "model.bin", "tokenizer.json")
    )
    assert not is_compatible_faster_whisper(
        _siblings("config.json", "pytorch_model.bin")
    )
