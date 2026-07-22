import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from dashboard import Dashboard
from enhanced_overlay_window import EnhancedOverlayWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _dispose(widget, app):
    widget.hide()
    widget.deleteLater()
    app.processEvents()


def test_switching_provider_invalidates_visible_connection_result(app):
    dashboard = Dashboard()
    dashboard.trans_test_result.setText("✅ stale provider result")
    dashboard._translation_test_fingerprint = dashboard._translation_settings_snapshot()
    previous_generation = dashboard._translation_test_generation
    target = "custom" if dashboard.translation_mode.currentData() != "custom" else "local"

    dashboard.translation_mode.setCurrentIndex(dashboard.translation_mode.findData(target))

    assert dashboard._translation_test_generation > previous_generation
    assert dashboard._translation_test_fingerprint is None
    assert "✅" not in dashboard.trans_test_result.text()
    _dispose(dashboard, app)


def test_stale_async_connection_result_cannot_reappear(app):
    dashboard = Dashboard()
    dashboard.translation_mode.setCurrentIndex(dashboard.translation_mode.findData("local"))
    dashboard._translation_test_generation = 20
    dashboard._translation_test_fingerprint = dashboard._translation_settings_snapshot()
    dashboard.trans_test_result.setText("new settings pending")

    dashboard._on_translation_test_finished(19, True, "Connected to old provider")
    assert dashboard.trans_test_result.text() == "new settings pending"

    dashboard._on_translation_test_finished(20, True, "Connected to current provider")
    assert "Connected to current provider" in dashboard.trans_test_result.text()
    _dispose(dashboard, app)


def test_editing_endpoint_invalidates_success_for_current_provider(app):
    dashboard = Dashboard()
    dashboard.translation_mode.setCurrentIndex(dashboard.translation_mode.findData("local"))
    dashboard._translation_test_generation = 30
    dashboard._translation_test_fingerprint = dashboard._translation_settings_snapshot()
    dashboard._on_translation_test_finished(30, True, "Connected")
    assert dashboard.trans_test_result.text().startswith("✅")

    dashboard.base_url.setText("http://127.0.0.1:1235/v1")

    assert "✅" not in dashboard.trans_test_result.text()
    assert dashboard._translation_test_fingerprint is None
    _dispose(dashboard, app)


def test_running_session_hides_control_center_instead_of_minimizing(app):
    dashboard = Dashboard()
    dashboard.show()
    app.processEvents()

    dashboard._hide_control_center_for_session()

    assert not dashboard.isVisible()
    assert not bool(dashboard.windowState() & Qt.WindowState.WindowMinimized)
    assert dashboard._control_center_hidden_for_session is True

    overlay = EnhancedOverlayWindow({"ui_language": "zh-Hans"})
    overlay.update_text(1, "A new sentence", "新的一句话")
    app.processEvents()
    assert not dashboard.isVisible()

    dashboard._show_control_center()
    app.processEvents()
    assert dashboard.isVisible()
    assert dashboard._control_center_hidden_for_session is False
    _dispose(overlay, app)
    _dispose(dashboard, app)


def test_red_close_during_session_only_hides_dashboard(app):
    class SpontaneousClose:
        def __init__(self):
            self.ignored = False

        def spontaneous(self):
            return True

        def ignore(self):
            self.ignored = True

    dashboard = Dashboard()
    pipeline = object()
    dashboard.pipeline = pipeline
    dashboard.show()
    event = SpontaneousClose()

    dashboard.closeEvent(event)

    assert event.ignored is True
    assert dashboard.pipeline is pipeline
    assert not dashboard.isVisible()
    dashboard.pipeline = None
    _dispose(dashboard, app)


def test_overlay_has_explicit_localized_control_center_return(app):
    overlay = EnhancedOverlayWindow({"ui_language": "zh-Hans"})
    requested = []
    overlay.control_center_requested.connect(lambda: requested.append(True))

    overlay.control_center_btn.click()

    assert overlay.control_center_btn.text() == "主界面"
    assert requested == [True]
    _dispose(overlay, app)
