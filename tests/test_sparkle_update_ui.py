import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from dashboard import Dashboard
from sparkle_updater import SparkleUpdater


class FakeUpdater:
    available = True
    error = ""

    def __init__(self):
        self.automatically_updates = True
        self.checks = 0

    def check_for_updates(self):
        self.checks += 1
        return True

    def set_automatically_updates(self, enabled):
        self.automatically_updates = bool(enabled)
        return True


def test_settings_update_controls_share_one_updater():
    app = QApplication.instance() or QApplication([])
    dashboard = Dashboard()
    updater = FakeUpdater()
    dashboard.configure_updater(updater)

    assert dashboard.check_updates_btn.isEnabled()
    assert dashboard.automatic_updates_check.isChecked()
    dashboard._check_for_updates()
    assert updater.checks == 1
    dashboard.automatic_updates_check.setChecked(False)
    assert updater.automatically_updates is False
    dashboard.hide()
    dashboard.deleteLater()
    app.processEvents()


class FakeBridge:
    def __init__(self, ready=True, prepared=True):
        self.ready = ready
        self.prepared = prepared
        self.prepare_calls = 0

    def RTSparkleInstalledUpdateReady(self):
        return self.ready

    def RTSparklePrepareRelaunch(self):
        self.prepare_calls += 1
        return self.prepared


def test_verified_installed_update_can_prepare_single_flow_relaunch():
    updater = SparkleUpdater.__new__(SparkleUpdater)
    updater._library = FakeBridge()
    updater.error = ""

    assert updater.installed_update_ready is True
    assert updater.prepare_relaunch() is True
    assert updater._library.prepare_calls == 1


def test_relaunch_is_not_prepared_before_sparkle_replaces_expected_version():
    updater = SparkleUpdater.__new__(SparkleUpdater)
    updater._library = FakeBridge(ready=False)
    updater.error = ""

    assert updater.installed_update_ready is False
