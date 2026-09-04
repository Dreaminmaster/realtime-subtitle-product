"""Anonymous downloads and product-facing errors for public model assets.

Built-in model catalog entries are public.  They must never inherit a user's
Hugging Face login, because an expired token can turn a valid public download
into a misleading HTTP 401 response.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import quote


_AUTH_ENV_NAMES = (
    "HF_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
    "HUGGINGFACE_HUB_TOKEN",
)
_AUTH_ENV_LOCK = threading.RLock()


def _looks_like_auth_failure(error: BaseException) -> bool:
    status = getattr(getattr(error, "response", None), "status_code", None)
    if status in {401, 403}:
        return True
    text = f"{type(error).__name__}: {error}".lower()
    return any(
        marker in text
        for marker in (
            "401 client error",
            "403 client error",
            "unauthorized",
            "forbidden",
            "invalid token",
            "token is invalid",
        )
    )


@contextmanager
def _without_huggingface_credentials():
    """Temporarily hide legacy environment tokens during one retry.

    Current huggingface_hub releases honor ``token=False`` directly.  The
    guarded environment fallback protects installations using an older hub
    release without permanently changing the user's shell configuration.
    """

    with _AUTH_ENV_LOCK:
        previous = {name: os.environ.get(name) for name in _AUTH_ENV_NAMES}
        try:
            for name in _AUTH_ENV_NAMES:
                os.environ.pop(name, None)
            yield
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


@dataclass(frozen=True)
class PublicModelDownloadError(RuntimeError):
    """A safe, localizable download failure without credentials or raw URLs."""

    repo_id: str
    reason: str = "access"

    @property
    def model_url(self) -> str:
        safe = "/".join(quote(part, safe="") for part in self.repo_id.split("/"))
        return f"https://huggingface.co/{safe}"

    def message(self, language: str = "en") -> str:
        if language == "zh-Hans":
            return (
                "无法匿名下载这个公开模型。已自动忽略失效的 Hugging Face 登录信息并重试；"
                "该模型可能已改为私有、需要先接受许可，或下载服务暂时拒绝访问。"
            )
        return (
            "This public model could not be downloaded anonymously. Realtime Subtitle "
            "ignored stale Hugging Face credentials and retried; the model may now be "
            "private, require license acceptance, or be temporarily unavailable."
        )

    def __str__(self) -> str:
        # Never leak the original HTTP exception or a token-bearing request.
        return self.message("en")


def public_snapshot_download(repo_id: str, *, downloader=None, **kwargs):
    """Download a public repository without implicit authentication.

    A 401/403 receives one credential-free retry.  Persistent access errors
    become ``PublicModelDownloadError`` so the UI can offer a useful action.
    """

    if downloader is None:
        from huggingface_hub import snapshot_download as downloader

    call_kwargs = dict(kwargs)
    call_kwargs["repo_id"] = repo_id
    call_kwargs["token"] = False
    try:
        return downloader(**call_kwargs)
    except Exception as error:
        if not _looks_like_auth_failure(error):
            raise

    try:
        with _without_huggingface_credentials():
            return downloader(**call_kwargs)
    except Exception as retry_error:
        if _looks_like_auth_failure(retry_error):
            raise PublicModelDownloadError(repo_id) from None
        raise


def public_hf_api(*, api_factory=None):
    """Return an anonymous Hub API client for public catalog discovery."""

    if api_factory is None:
        from huggingface_hub import HfApi as api_factory
    return api_factory(token=False)
