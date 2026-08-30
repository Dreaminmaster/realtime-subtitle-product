"""Bridge to Apple's on-device Translation framework (macOS 26+)."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path


LANGUAGE_CODES = {
    "auto": "auto",
    "automatic": "auto",
    "chinese": "zh-Hans",
    "simplified chinese": "zh-Hans",
    "traditional chinese": "zh-Hant",
    "english": "en",
    "japanese": "ja",
    "french": "fr",
    "spanish": "es",
    "german": "de",
    "korean": "ko",
    "italian": "it",
    "portuguese": "pt",
}


def normalize_language_code(value: str | None, *, default: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return default
    return LANGUAGE_CODES.get(cleaned.lower(), cleaned.replace("_", "-"))


def helper_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidates = (
        base / "bin" / "mac-translation",
        Path(__file__).resolve().parent / "native" / "mac-translation",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def availability() -> tuple[bool, str]:
    if sys.platform != "darwin":
        return False, "Apple Translation is available only on macOS"
    try:
        major = int(platform.mac_ver()[0].split(".")[0])
    except (ValueError, IndexError):
        major = 0
    if major < 26:
        return False, "Apple Translation in Realtime Subtitle requires macOS 26 or later"
    path = helper_path()
    if not path.is_file():
        return False, "Apple Translation helper is not installed"
    return True, "Apple Translation is ready"


def translate(
    text: str,
    *,
    source_language: str | None = None,
    target_language: str | None = None,
    timeout: float = 20.0,
) -> str:
    ready, reason = availability()
    if not ready:
        raise RuntimeError(reason)
    source = normalize_language_code(source_language, default="auto")
    target = normalize_language_code(target_language, default="zh-Hans")
    # A same-language request is a valid no-op, not an unsupported pair.
    # The native helper repeats this guard after auto language detection.
    if source != "auto" and source.lower() == target.lower():
        return str(text).strip()
    completed = subprocess.run(
        [str(helper_path()), source, target, str(text)],
        capture_output=True,
        text=True,
        timeout=max(1.0, float(timeout)),
        check=False,
    )
    if completed.returncode != 0:
        error = completed.stderr.strip() or "Apple Translation failed"
        raise RuntimeError(error)
    return completed.stdout.strip()
