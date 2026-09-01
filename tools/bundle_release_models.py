#!/usr/bin/env python3
"""Download permissively licensed models into a release resources tree."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from huggingface_hub import snapshot_download


MODELS = (
    ("Systran/faster-whisper-tiny", "models/whisper/tiny"),
    ("gaudi/opus-mt-en-zh-ctranslate2", "models/translation/opus-en-zh"),
    ("gaudi/opus-mt-zh-en-ctranslate2", "models/translation/opus-zh-en"),
)


def copy_snapshot(repo_id: str, destination: Path) -> None:
    source = Path(snapshot_download(repo_id))
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.is_file():
            shutil.copy2(item, destination / item.name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("resources", type=Path)
    args = parser.parse_args()
    for repo_id, relative in MODELS:
        destination = args.resources / relative
        if destination.exists():
            shutil.rmtree(destination)
        print(f"Bundling {repo_id} -> {destination}", flush=True)
        copy_snapshot(repo_id, destination)

    required = {
        "models/whisper/tiny": ("config.json", "model.bin", "tokenizer.json"),
        "models/translation/opus-en-zh": ("model.bin",),
        "models/translation/opus-zh-en": ("model.bin",),
    }
    for relative, names in required.items():
        directory = args.resources / relative
        missing = [name for name in names if not (directory / name).is_file()]
        spm = list(directory.glob("*.spm")) + list(directory.glob("*.model"))
        if "translation" in relative and not spm:
            missing.append("SentencePiece model")
        if missing:
            raise SystemExit(f"Incomplete bundled model {relative}: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
