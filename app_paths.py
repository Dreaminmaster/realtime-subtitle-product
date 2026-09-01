"""Cross-platform user-writable storage paths for the installed app."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


APP_NAME = "RealtimeSubtitle"


def get_app_support_dir() -> Path:
    from platform_support import local_app_data_dir

    return local_app_data_dir(APP_NAME)


def get_config_path() -> Path:
    override = os.getenv("REALTIME_SUBTITLE_CONFIG_PATH")
    if override:
        return Path(override).expanduser()
    return get_app_support_dir() / "config.ini"


def get_permission_guide_marker() -> Path:
    return get_app_support_dir() / ".permission_guide_seen"


def get_transcript_dir() -> Path:
    override = os.getenv("REALTIME_SUBTITLE_TRANSCRIPT_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Documents" / "Realtime Subtitle" / "Transcripts"


def get_log_dir() -> Path:
    override = os.getenv("REALTIME_SUBTITLE_LOG_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        return get_app_support_dir() / "logs"
    return Path.home() / "Library" / "Logs" / APP_NAME


def get_setup_state_path() -> Path:
    return get_app_support_dir() / ".setup_state.json"


def get_venv_dir() -> Path:
    return get_app_support_dir() / "venv"


def get_venv_python() -> Path:
    directory = get_venv_dir()
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python3")


def get_translation_model_dir() -> Path:
    """Directory for optional, user-downloaded offline translation models."""
    override = os.getenv("REALTIME_SUBTITLE_TRANSLATION_MODEL_DIR")
    if override:
        return Path(override).expanduser()
    return get_app_support_dir() / "translation_models"


def write_config(parser, path: str | Path | None = None) -> Path:
    """Atomically save ConfigParser data with user-only file permissions."""
    destination = Path(path) if path is not None else get_config_path()
    destination = destination.expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            parser.write(handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, destination)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return destination
