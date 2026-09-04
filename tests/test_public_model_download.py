import os

import pytest

from public_model_download import PublicModelDownloadError, public_hf_api, public_snapshot_download
from model_progress_channel import ModelProgressChannel


class Response:
    status_code = 401


class Unauthorized(RuntimeError):
    response = Response()


def test_public_download_forces_anonymous_token():
    calls = []

    def download(**kwargs):
        calls.append(kwargs)
        return "/snapshot"

    assert public_snapshot_download("org/model", downloader=download) == "/snapshot"
    assert calls == [{"repo_id": "org/model", "token": False}]


def test_401_retries_without_environment_token_and_restores_it(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "expired-secret")
    seen = []

    def download(**kwargs):
        seen.append((kwargs["token"], os.environ.get("HF_TOKEN")))
        if len(seen) == 1:
            raise Unauthorized("401 Client Error")
        return "/snapshot"

    assert public_snapshot_download("org/model", downloader=download) == "/snapshot"
    assert seen == [(False, "expired-secret"), (False, None)]
    assert os.environ["HF_TOKEN"] == "expired-secret"


def test_persistent_401_becomes_safe_actionable_error():
    def download(**_kwargs):
        raise Unauthorized("401 Client Error: token=should-not-appear")

    with pytest.raises(PublicModelDownloadError) as failure:
        public_snapshot_download("org/model", downloader=download)
    assert "401 Client Error" not in str(failure.value)
    assert failure.value.model_url == "https://huggingface.co/org/model"
    assert "匿名下载" in failure.value.message("zh-Hans")


def test_public_api_is_anonymous():
    seen = []

    def factory(**kwargs):
        seen.append(kwargs)
        return object()

    public_hf_api(api_factory=factory)
    assert seen == [{"token": False}]


def test_progress_channel_localizes_typed_access_error():
    event = ModelProgressChannel("model", language="zh-Hans").on_fail(
        PublicModelDownloadError("org/model"), 2
    )
    assert "匿名下载" in event.message
    assert "401 Client Error" not in event.message
