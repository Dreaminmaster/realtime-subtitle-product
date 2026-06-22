"""Runtime decision formatter for dashboard display.

Pure function: RuntimeSettingsDecision → HTML string.
No side effects.  No config access.  No repository/scheduler.
"""

from __future__ import annotations
from html import escape
from src.runtime_settings_guard import RuntimeSettingsDecision


def format_runtime_settings_decision_html(decision: RuntimeSettingsDecision) -> str:
    lines = ["<h3>Runtime Decision</h3>"]

    # Mode
    mode_color = "#a6e3a1" if decision.ok else "#f38ba8"
    lines.append(
        f'<p><b>Mode:</b> <span style="color:{mode_color};">'
        f'{escape(decision.mode)}</span></p>'
    )
    lines.append(f"<p><b>OK:</b> {_bool_span(decision.ok)}</p>")

    # Fallback
    lines.append(f"<p><b>Fallback to legacy:</b> {_bool_span(decision.should_fallback_to_legacy)}</p>")
    if decision.reason:
        lines.append(f"<p><b>Reason:</b> {escape(decision.reason[:200])}</p>")

    # Capabilities
    lines.append("<ul>")
    lines.append(f"<li>Translation scheduler: {_allowed(decision.allow_translation_scheduler)}</li>")
    lines.append(f"<li>SQLite repository: {_allowed(decision.allow_sqlite_repository)}</li>")
    lines.append(f"<li>Segment history: {_allowed(decision.allow_segment_history)}</li>")
    lines.append(f"<li>Segment export: {_allowed(decision.allow_segment_export)}</li>")
    lines.append(f"<li>Segment overlay: {_allowed(decision.allow_segment_overlay)}</li>")
    lines.append(f"<li>Transcriber bridge: {_allowed(decision.allow_transcriber_output_bridge)}</li>")
    lines.append("</ul>")

    # Issues
    if decision.issues:
        lines.append("<p><b>Issues:</b></p><ul>")
        for iss in decision.issues:
            tag = iss.severity.upper()
            color = "#f38ba8" if tag == "ERROR" else "#f9e2af" if tag == "WARNING" else "#89b4fa"
            lines.append(
                f'<li><span style="color:{color};">[{escape(tag)}]</span> '
                f'{escape(iss.code)}: {escape(iss.message)}</li>'
            )
        lines.append("</ul>")
    else:
        lines.append("<p><b>Issues:</b> <i>No runtime issues.</i></p>")

    # Recommended changes
    if decision.recommended_changes:
        lines.append("<p><b>Recommended changes:</b></p><ul>")
        for k, v in decision.recommended_changes.items():
            lines.append(f"<li>{escape(k)} = {_val_escape(v)}</li>")
        lines.append("</ul>")
    else:
        lines.append("<p><b>Recommended changes:</b> <i>None.</i></p>")

    return "\n".join(lines)


def _bool_span(value: bool) -> str:
    return f'<span style="color:{"#a6e3a1" if value else "#f38ba8"};">{escape(str(value))}</span>'


def _allowed(value: bool) -> str:
    color = "#a6e3a1" if value else "#f38ba8"
    text = escape("enabled" if value else "disabled")
    return f'<span style="color:{color};">{text}</span>'


def _val_escape(value: object) -> str:
    return escape(str(value))
