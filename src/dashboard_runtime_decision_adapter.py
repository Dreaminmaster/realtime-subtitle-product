"""Dashboard adapter: builds runtime decision HTML for dashboard diagnostics tab.

Encapsulates config read, guard evaluation, and formatting in a single
function.  Never creates repositories or schedulers.  Never touches
filesystem or network.
"""

from __future__ import annotations


def build_runtime_decision_html(config=None) -> str:
    """Build runtime decision HTML for dashboard display.

    Returns HTML string suitable for QLabel.setText().
    Never mutates config.  Never creates repository/scheduler.
    """
    if config is None:
        from config import config as _cfg
        config = _cfg

    try:
        from src.runtime_settings_guard import RuntimeSettingsGuard, settings_from_config
        from src.runtime_decision_formatter import format_runtime_settings_decision_html
        settings = settings_from_config(config)
        decision = RuntimeSettingsGuard().evaluate(settings)
        return format_runtime_settings_decision_html(decision)
    except Exception as e:
        return f"<h3>Runtime Decision</h3><p><i>Runtime decision unavailable: {e}</i></p>"
