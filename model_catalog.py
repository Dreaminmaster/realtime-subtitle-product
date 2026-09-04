"""Safe Hugging Face discovery for compatible faster-whisper models."""

from __future__ import annotations

from urllib.parse import urlparse


REQUIRED_WEIGHT_NAMES = {"model.bin", "pytorch_model.bin"}


def normalize_huggingface_repo(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    if not raw:
        raise ValueError("Enter a model name or Hugging Face URL")
    if raw.startswith(("http://", "https://")):
        parsed = urlparse(raw)
        if parsed.hostname not in {"huggingface.co", "www.huggingface.co"}:
            raise ValueError("Only huggingface.co model URLs are supported")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            raise ValueError("The URL must point to a Hugging Face model repository")
        raw = "/".join(parts[:2])
    parts = [part for part in raw.split("/") if part]
    if len(parts) != 2 or any(part in {".", ".."} for part in parts):
        raise ValueError("Use the form organization/model-name")
    return "/".join(parts)


def is_compatible_faster_whisper(siblings) -> bool:
    names = {getattr(item, "rfilename", "") for item in (siblings or [])}
    has_weights = bool(REQUIRED_WEIGHT_NAMES & names) or any(
        name.endswith(".safetensors") for name in names
    )
    has_vocab = bool({"tokenizer.json", "vocabulary.json", "vocabulary.txt"} & names)
    return "config.json" in names and has_weights and has_vocab


def validate_faster_whisper_repo(repo_id: str) -> str:
    from public_model_download import public_hf_api

    normalized = normalize_huggingface_repo(repo_id)
    info = public_hf_api().model_info(normalized, files_metadata=False)
    if not is_compatible_faster_whisper(info.siblings):
        raise ValueError(
            "This repository is not a converted faster-whisper/CTranslate2 model"
        )
    return normalized


def search_faster_whisper(query: str, *, limit: int = 10) -> list[str]:
    from public_model_download import public_hf_api

    value = str(query or "").strip()
    if not value:
        return []
    if "/" in value or value.startswith(("http://", "https://")):
        return [validate_faster_whisper_repo(value)]
    results = public_hf_api().list_models(
        search=f"faster-whisper {value}",
        pipeline_tag="automatic-speech-recognition",
        sort="downloads",
        limit=max(1, int(limit) * 3),
    )
    found = []
    for model in results:
        model_id = str(getattr(model, "id", ""))
        if "faster-whisper" not in model_id.lower():
            continue
        found.append(model_id)
        if len(found) >= limit:
            break
    return found
