"""Small platform capability layer shared by UI, capture, and packaging.

Keep operating-system branching here instead of scattering product copy and
filesystem assumptions throughout the application.  The feature set remains
the same on macOS and Windows, while native integrations are selected only
when the host can actually provide them.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import platform
from pathlib import Path


@dataclass(frozen=True)
class PlatformCapabilities:
    system: str
    product_name: str
    system_audio_backend: str
    supports_system_audio: bool
    supports_apple_translation: bool
    supports_windows_loopback: bool
    native_font_family: str

    @property
    def is_windows(self) -> bool:
        return self.system == "Windows"

    @property
    def is_macos(self) -> bool:
        return self.system == "Darwin"

    @property
    def device_label(self) -> str:
        return "Windows PC" if self.is_windows else "Mac"


def current_platform(system: str | None = None) -> PlatformCapabilities:
    # The override is used by deterministic UI capture/tests. Production
    # builds never set it and therefore always follow the real host OS.
    value = str(system or os.getenv("REALTIME_SUBTITLE_PLATFORM") or platform.system())
    if value == "Windows":
        return PlatformCapabilities(
            system=value,
            product_name="Windows",
            system_audio_backend="WASAPI loopback",
            supports_system_audio=True,
            supports_apple_translation=False,
            supports_windows_loopback=True,
            native_font_family="Segoe UI Variable",
        )
    if value == "Darwin":
        return PlatformCapabilities(
            system=value,
            product_name="macOS",
            system_audio_backend="ScreenCaptureKit",
            supports_system_audio=True,
            supports_apple_translation=True,
            supports_windows_loopback=False,
            native_font_family="Helvetica Neue",
        )
    return PlatformCapabilities(
        system=value,
        product_name=value or "Desktop",
        system_audio_backend="unsupported",
        supports_system_audio=False,
        supports_apple_translation=False,
        supports_windows_loopback=False,
        native_font_family="Sans Serif",
    )


def local_app_data_dir(app_name: str = "RealtimeSubtitle") -> Path:
    """Return the conventional writable app-data root for this platform."""
    override = os.getenv("REALTIME_SUBTITLE_APP_SUPPORT_DIR")
    if override:
        return Path(override).expanduser()
    caps = current_platform()
    if caps.is_windows:
        base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
        if base:
            return Path(base) / app_name
        return Path.home() / "AppData" / "Local" / app_name
    if caps.is_macos:
        return Path.home() / "Library" / "Application Support" / app_name
    return Path.home() / ".local" / "share" / app_name


def bundled_resources_dir() -> Path:
    override = os.getenv("REALTIME_SUBTITLE_RESOURCES_DIR")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent
