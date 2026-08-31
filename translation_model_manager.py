"""Manage optional pair-specific offline translation models.

Translation downloads intentionally live outside the application bundle.  This
keeps the installer small and lets people opt into only the language pairs they
actually use.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from app_paths import get_translation_model_dir


@dataclass(frozen=True)
class TranslationModel:
    model_id: str
    repo_id: str
    source: str
    target: str
    title: str
    size_mb: int
    license: str = "Apache-2.0"


# These CTranslate2 conversions are small enough for an interactive download,
# CPU-friendly, and permissively licensed. Add pairs only after verifying both
# the repository license and its SentencePiece assets.
TRANSLATION_MODELS = (
    TranslationModel(
        "opus-en-zh", "gaudi/opus-mt-en-zh-ctranslate2", "en", "zh",
        "English → 简体中文", 153,
    ),
    TranslationModel(
        "opus-zh-en", "gaudi/opus-mt-zh-en-ctranslate2", "zh", "en",
        "简体中文 → English", 153,
    ),
)


LANGUAGE_CODES = {
    "english": "en", "en": "en",
    "chinese": "zh", "simplified chinese": "zh", "zh": "zh",
    "zh-hans": "zh", "简体中文": "zh", "中文": "zh",
    "japanese": "ja", "ja": "ja", "日语": "ja",
    "french": "fr", "fr": "fr", "法语": "fr",
    "spanish": "es", "es": "es", "西班牙语": "es",
    "german": "de", "de": "de", "德语": "de",
    "korean": "ko", "ko": "ko", "韩语": "ko",
    "vietnamese": "vi", "vi": "vi", "越南语": "vi",
}


def normalize_pair_language(value: str | None) -> str:
    return LANGUAGE_CODES.get(str(value or "").strip().lower(), str(value or "").strip().lower())


class TranslationModelManager:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root is not None else get_translation_model_dir()

    def catalog(self) -> tuple[TranslationModel, ...]:
        return TRANSLATION_MODELS

    def model(self, model_id: str) -> TranslationModel | None:
        return next((item for item in TRANSLATION_MODELS if item.model_id == model_id), None)

    def for_pair(self, source: str | None, target: str | None) -> list[TranslationModel]:
        source_code = normalize_pair_language(source)
        target_code = normalize_pair_language(target)
        return [
            item for item in TRANSLATION_MODELS
            if item.source == source_code and item.target == target_code
        ]

    def recommended(self, source: str | None, target: str | None) -> TranslationModel | None:
        matches = self.for_pair(source, target)
        return matches[0] if matches else None

    def path_for(self, model_id: str) -> Path:
        if self.model(model_id) is None:
            raise ValueError(f"Unknown translation model: {model_id}")
        return self.root / model_id

    @staticmethod
    def _sentencepiece_files(path: Path) -> tuple[Path | None, Path | None]:
        source = next((p for p in (path / "source.spm", path / "source.model") if p.exists()), None)
        target = next((p for p in (path / "target.spm", path / "target.model") if p.exists()), None)
        if source is None or target is None:
            candidates = sorted((*path.glob("*.spm"), *path.glob("*.model")))
            if len(candidates) == 1:
                source = target = candidates[0]
            elif len(candidates) >= 2:
                source, target = candidates[:2]
        return source, target

    def assets(self, model_id: str) -> tuple[Path, Path, Path]:
        path = self.path_for(model_id)
        source, target = self._sentencepiece_files(path)
        if not (path / "model.bin").is_file() or source is None or target is None:
            raise FileNotFoundError(f"Offline translation model is incomplete: {model_id}")
        return path, source, target

    def is_downloaded(self, model_id: str) -> bool:
        try:
            self.assets(model_id)
            return True
        except (FileNotFoundError, ValueError):
            return False

    def download_model_sync(self, model_id: str) -> Path:
        item = self.model(model_id)
        if item is None:
            raise ValueError(f"Unknown translation model: {model_id}")
        destination = self.path_for(model_id)
        destination.mkdir(parents=True, exist_ok=True)
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=item.repo_id,
            local_dir=str(destination),
            allow_patterns=(
                "config.json", "model.bin", "shared_vocabulary.json",
                "source_vocabulary.json", "target_vocabulary.json",
                "source.spm", "target.spm", "*.model", "tokenizer_config.json",
            ),
        )
        self.assets(model_id)
        metadata = {
            "model_id": item.model_id,
            "repo_id": item.repo_id,
            "source": item.source,
            "target": item.target,
            "license": item.license,
        }
        (destination / "realtime-subtitle.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return destination

    def delete_model(self, model_id: str) -> None:
        path = self.path_for(model_id)
        if path.exists():
            shutil.rmtree(path)


translation_model_manager = TranslationModelManager()
