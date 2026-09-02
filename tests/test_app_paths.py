import configparser
import os
import stat

from app_paths import (
    get_app_support_dir,
    get_config_path,
    get_log_dir,
    get_permission_guide_marker,
    get_transcript_dir,
    write_config,
)


def test_app_support_override(monkeypatch, tmp_path):
    monkeypatch.setenv("REALTIME_SUBTITLE_APP_SUPPORT_DIR", str(tmp_path / "support"))
    assert get_app_support_dir() == tmp_path / "support"
    assert get_config_path() == tmp_path / "support" / "config.ini"
    assert get_permission_guide_marker() == tmp_path / "support" / ".permission_guide_seen"


def test_transcript_override(monkeypatch, tmp_path):
    destination = tmp_path / "exports"
    monkeypatch.setenv("REALTIME_SUBTITLE_TRANSCRIPT_DIR", str(destination))
    assert get_transcript_dir() == destination


def test_log_override(monkeypatch, tmp_path):
    destination = tmp_path / "logs"
    monkeypatch.setenv("REALTIME_SUBTITLE_LOG_DIR", str(destination))
    assert get_log_dir() == destination


def test_config_override_wins(monkeypatch, tmp_path):
    destination = tmp_path / "custom.ini"
    monkeypatch.setenv("REALTIME_SUBTITLE_CONFIG_PATH", str(destination))
    assert get_config_path() == destination


def test_atomic_config_write_is_private(tmp_path):
    parser = configparser.ConfigParser()
    parser["translation"] = {"mode": "off"}
    destination = write_config(parser, tmp_path / "nested" / "config.ini")

    loaded = configparser.ConfigParser()
    loaded.read(destination)
    assert loaded.get("translation", "mode") == "off"
    if os.name != "nt":
        assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert list(destination.parent.glob(".*.tmp")) == []
