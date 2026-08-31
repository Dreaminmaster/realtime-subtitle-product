import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from config import config
from dashboard import Dashboard
from model_download_task import SUCCEEDED
from model_manager import model_manager

_APP = None

def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _dispose(widget):
    widget.hide()
    widget.deleteLater()
    _app().processEvents()


def test_enhanced_controls_follow_config_and_show_download(monkeypatch):
    _app()
    monkeypatch.setattr(config, "enhanced_accuracy", True)
    monkeypatch.setattr(config, "accuracy_profile", "fast")
    monkeypatch.setattr(model_manager, "is_downloaded", lambda *args: False)
    dashboard = Dashboard()
    try:
        assert dashboard.enhanced_accuracy_mode.currentData() is True
        assert dashboard.accuracy_profile.currentData() == "fast"
        assert dashboard.accuracy_profile.isEnabled() is True
        assert dashboard.accuracy_download_btn.isEnabled() is True
        assert "small" in dashboard.accuracy_download_btn.text()
    finally:
        _dispose(dashboard)


def test_runtime_performance_control_preserves_all_hardware_choices(monkeypatch):
    _app()
    monkeypatch.setattr(config, "performance_profile", "efficient", raising=False)
    dashboard = Dashboard()
    try:
        assert dashboard.performance_profile.currentData() == "efficient"
        assert dashboard.performance_profile.findData("balanced") >= 0
        assert dashboard.performance_profile.findData("maximum") >= 0
    finally:
        _dispose(dashboard)


def test_accuracy_download_does_not_replace_the_live_model(monkeypatch):
    _app()
    dashboard = Dashboard()
    try:
        dashboard.whisper_model.setCurrentText("tiny")
        dashboard._accuracy_download_model_id = "turbo"
        monkeypatch.setattr(dashboard, "_refresh_model_list", lambda: None)
        monkeypatch.setattr(dashboard, "_update_accuracy_plan_ui", lambda: None)
        dashboard._on_model_done("turbo", SUCCEEDED, None, 1)
        assert dashboard.whisper_model.currentText() == "tiny"
    finally:
        _dispose(dashboard)


def test_accuracy_button_shows_immediate_download_state(monkeypatch):
    _app()
    monkeypatch.setattr(config, "enhanced_accuracy", True)
    monkeypatch.setattr(config, "accuracy_profile", "fast")
    monkeypatch.setattr(model_manager, "is_downloaded", lambda *args: False)
    dashboard = Dashboard()
    try:
        dashboard._active_downloads["small"] = SimpleNamespace(cancel=lambda: None)
        dashboard._update_accuracy_plan_ui()
        assert dashboard.accuracy_download_btn.isEnabled() is False
        assert "small" in dashboard.accuracy_download_btn.text()
        assert (
            "Downloading" in dashboard.accuracy_download_btn.text()
            or "正在下载" in dashboard.accuracy_download_btn.text()
        )
    finally:
        _dispose(dashboard)
