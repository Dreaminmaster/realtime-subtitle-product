from pathlib import Path

import pytest

from translation_model_manager import TranslationModelManager, normalize_pair_language


def test_catalog_has_separate_bidirectional_language_pairs(tmp_path):
    manager = TranslationModelManager(tmp_path)
    assert manager.recommended("English", "Chinese").model_id == "opus-en-zh"
    assert manager.recommended("zh", "English").model_id == "opus-zh-en"


def test_downloaded_requires_engine_and_sentencepiece_assets(tmp_path):
    manager = TranslationModelManager(tmp_path)
    path = manager.path_for("opus-en-zh")
    path.mkdir(parents=True)
    (path / "model.bin").write_bytes(b"model")
    assert manager.is_downloaded("opus-en-zh") is False
    (path / "source.spm").write_bytes(b"source")
    (path / "target.spm").write_bytes(b"target")
    assert manager.is_downloaded("opus-en-zh") is True


def test_pair_language_normalization_matches_product_labels():
    assert normalize_pair_language("Chinese") == "zh"
    assert normalize_pair_language("zh-Hans") == "zh"
    assert normalize_pair_language("English") == "en"


def test_unknown_model_cannot_escape_storage_root(tmp_path):
    manager = TranslationModelManager(tmp_path)
    with pytest.raises(ValueError):
        manager.path_for("../../outside")
