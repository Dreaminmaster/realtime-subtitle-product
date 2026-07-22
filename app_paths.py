"""User-writable storage paths for the installed macOS application."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


APP_NAME = "RealtimeSubtitle"


def get_app_support_dir() -> Path:
    override = os.getenv("REALTIME_SUBTITLE_APP_SUPPORT_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Library" / "Application Support" / APP_NAME


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
    return Path.home() / "Library" / "Logs" / APP_NAME


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
