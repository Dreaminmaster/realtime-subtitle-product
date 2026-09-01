"""Bridge to Apple's on-device Translation framework (macOS 26+)."""

from __future__ import annotations

import atexit
import json
import platform
import selectors
import subprocess
import sys
import threading
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
    return True, (
        "Apple Translation helper is available; the selected language pair "
        "and downloaded assets are verified when the connection is tested"
    )


class _PersistentTranslationService:
    def __init__(self):
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._key: tuple[str, str, str] | None = None
        self._request_id = 0

    def close(self) -> None:
        process = self._process
        self._process = None
        self._key = None
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=1.0)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    def _ensure_process(self, path: Path, source: str, target: str) -> subprocess.Popen:
        key = (str(path), source, target)
        if self._process is not None and self._process.poll() is None and self._key == key:
            return self._process
        self.close()
        self._process = subprocess.Popen(
            [str(path), "--server", source, target],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._key = key
        return self._process

    def translate(
        self,
        path: Path,
        source: str,
        target: str,
        text: str,
        timeout: float,
        *,
        wait_if_busy: bool,
    ) -> str:
        if not self._lock.acquire(blocking=wait_if_busy):
            return ""
        try:
            process = self._ensure_process(path, source, target)
            if process.stdin is None or process.stdout is None:
                raise RuntimeError("Apple Translation service pipes are unavailable")
            self._request_id += 1
            request_id = self._request_id
            process.stdin.write(
                json.dumps({"id": request_id, "text": str(text)}, ensure_ascii=False) + "\n"
            )
            process.stdin.flush()

            selector = selectors.DefaultSelector()
            try:
                selector.register(process.stdout, selectors.EVENT_READ)
                events = selector.select(timeout=max(1.0, float(timeout)))
            finally:
                selector.close()
            if not events:
                self.close()
                raise TimeoutError("Apple Translation timed out")

            line = process.stdout.readline()
            if not line:
                error = ""
                if process.stderr is not None:
                    error = process.stderr.read().strip()
                self.close()
                raise RuntimeError(error or "Apple Translation service stopped")
            payload = json.loads(line)
            if int(payload.get("id", -1)) != request_id:
                raise RuntimeError("Apple Translation returned an out-of-order response")
            if payload.get("error"):
                raise RuntimeError(str(payload["error"]))
            return str(payload.get("translated") or "").strip()
        finally:
            self._lock.release()


_SERVICE = _PersistentTranslationService()
atexit.register(_SERVICE.close)


def translate(
    text: str,
    *,
    source_language: str | None = None,
    target_language: str | None = None,
    timeout: float = 20.0,
    wait_if_busy: bool = True,
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
    if source != "auto":
        return _SERVICE.translate(
            helper_path(),
            source,
            target,
            str(text),
            timeout,
            wait_if_busy=wait_if_busy,
        )
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
