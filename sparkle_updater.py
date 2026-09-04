"""Safe Python wrapper for the bundled Sparkle 2 Objective-C bridge."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path


class SparkleUpdater:
    def __init__(self, library_path: str | Path | None = None):
        self._library = None
        self.error = ""
        if sys.platform != "darwin":
            self.error = "Sparkle updates are available in the macOS app."
            return
        path = Path(library_path) if library_path else self._default_library_path()
        if not path.is_file():
            self.error = "The Sparkle update component is not included in this development build."
            return
        try:
            library = ctypes.CDLL(str(path))
            library.RTSparkleStart.argtypes = [ctypes.c_char_p]
            library.RTSparkleStart.restype = ctypes.c_bool
            library.RTSparkleCheckForUpdates.restype = None
            library.RTSparkleCheckForUpdatesInBackground.restype = None
            library.RTSparkleCanCheckForUpdates.restype = ctypes.c_bool
            library.RTSparkleAutomaticallyChecksForUpdates.restype = ctypes.c_bool
            library.RTSparkleSetAutomaticallyChecksForUpdates.argtypes = [ctypes.c_bool]
            library.RTSparkleAutomaticallyDownloadsUpdates.restype = ctypes.c_bool
            library.RTSparkleSetAutomaticallyDownloadsUpdates.argtypes = [ctypes.c_bool]
            library.RTSparkleInstalledUpdateReady.restype = ctypes.c_bool
            library.RTSparklePrepareRelaunch.restype = ctypes.c_bool
            library.RTSparkleLastError.restype = ctypes.c_char_p
            self._library = library
        except OSError as exc:
            self.error = f"Unable to load the Sparkle update component: {exc}"

    @staticmethod
    def _default_library_path() -> Path:
        from platform_support import bundled_resources_dir

        return bundled_resources_dir().parent / "Frameworks" / "libRealtimeSubtitleUpdater.dylib"

    @staticmethod
    def _host_bundle_path() -> Path:
        from platform_support import bundled_resources_dir

        resources = bundled_resources_dir()
        candidate = resources.parent.parent
        return candidate if candidate.suffix == ".app" else Path()

    @property
    def available(self) -> bool:
        return self._library is not None

    def start(self) -> bool:
        if not self.available:
            return False
        bundle = self._host_bundle_path()
        if not bundle.is_dir():
            self.error = "Realtime Subtitle application bundle was not found."
            return False
        started = bool(self._library.RTSparkleStart(str(bundle).encode("utf-8")))
        if not started:
            raw_error = self._library.RTSparkleLastError()
            if raw_error:
                self.error = raw_error.decode("utf-8", errors="replace")
        return started

    def check_for_updates(self) -> bool:
        if not self.available:
            return False
        self._library.RTSparkleCheckForUpdates()
        return True

    def check_for_updates_in_background(self) -> bool:
        """Exercise the same quiet path used by scheduled automatic checks."""
        if not self.available:
            return False
        self._library.RTSparkleCheckForUpdatesInBackground()
        return True

    @property
    def automatically_updates(self) -> bool:
        if not self.available:
            return False
        return bool(self._library.RTSparkleAutomaticallyChecksForUpdates()) and bool(
            self._library.RTSparkleAutomaticallyDownloadsUpdates()
        )

    def set_automatically_updates(self, enabled: bool) -> bool:
        if not self.available:
            return False
        value = bool(enabled)
        self._library.RTSparkleSetAutomaticallyChecksForUpdates(value)
        self._library.RTSparkleSetAutomaticallyDownloadsUpdates(value)
        return True

    @property
    def installed_update_ready(self) -> bool:
        """True only after Sparkle selected and replaced a newer bundle."""
        return bool(self.available and self._library.RTSparkleInstalledUpdateReady())

    def prepare_relaunch(self) -> bool:
        """Start the wait-for-exit helper; the Qt app may then quit cleanly."""
        return bool(self.available and self._library.RTSparklePrepareRelaunch())
