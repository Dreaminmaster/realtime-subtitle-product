"""Dashboard history HTML formatter for v2.4.0.

Pure function: HistoryDashboardViewModel → HTML string.
No Qt, no filesystem, no repository access.
"""

from __future__ import annotations
from html import escape
from src.history_viewmodel import HistoryDashboardViewModel

MAX_TRANSCRIPT_CHARS = 1200
MAX_SESSIONS = 10
MAX_SEGMENTS = 20


def _truncate(text: str, max_chars: int = MAX_TRANSCRIPT_CHARS) -> str:
    if not text:
        return "(empty)"
    if len(text) <= max_chars:
        return escape(text)
    return escape(text[:max_chars]) + "<br><i>(truncated, total {} chars)</i>".format(len(text))


def format_history_viewmodel_html(viewmodel: HistoryDashboardViewModel) -> str:
    lines = ["<h3>Transcript History</h3>"]

    # Status
    status_color = "#a6e3a1" if viewmodel.available else "#f38ba8"
    lines.append(f'<p><b>Status:</b> <span style="color:{status_color};">'
                 f'{"Available" if viewmodel.available else "Unavailable"}</span></p>')
    lines.append(f"<p>{escape(viewmodel.title)} — {escape(viewmodel.summary)}</p>")

    # Sessions
    if viewmodel.sessions:
        shown = viewmodel.sessions[:MAX_SESSIONS]
        lines.append("<p><b>Sessions:</b></p><ul>")
        for s in shown:
            selected = " ▶" if s.session_id == viewmodel.selected_session_id else ""
            lines.append(
                f"<li>{escape(s.label or s.session_id[:12])}"
                f" · {escape(s.status)} · created={s.created_at:.0f}"
                f"{selected}</li>"
            )
        if len(viewmodel.sessions) > MAX_SESSIONS:
            lines.append(f"<li><i>... and {len(viewmodel.sessions) - MAX_SESSIONS} more</i></li>")
        lines.append("</ul>")
    else:
        lines.append("<p><i>No transcript sessions.</i></p>")

    # Selected session
    if viewmodel.selected_session_id:
        lines.append(f"<p><b>Selected:</b> {escape(viewmodel.selected_session_id[:20])}</p>")

    # Transcripts
    if viewmodel.original_text or viewmodel.translated_text:
        lines.append("<hr>")
        if viewmodel.original_text:
            lines.append("<p><b>Original:</b></p>")
            lines.append(f"<pre>{_truncate(viewmodel.original_text)}</pre>")
        if viewmodel.translated_text:
            lines.append("<p><b>Translated:</b></p>")
            lines.append(f"<pre>{_truncate(viewmodel.translated_text)}</pre>")
        if viewmodel.bilingual_text:
            lines.append("<p><b>Bilingual:</b></p>")
            lines.append(f"<pre>{_truncate(viewmodel.bilingual_text)}</pre>")

    # Segments
    if viewmodel.segments:
        lines.append(f"<p><b>Segments:</b> ({len(viewmodel.segments)} total)</p>")
        shown = viewmodel.segments[:MAX_SEGMENTS]
        lines.append("<ul>")
        for seg in shown:
            tstat = f" [{seg.translation_status}]" if seg.translation_status else ""
            lines.append(
                f"<li>{escape(seg.original_text[:80] or '(empty)')}"
                f"{escape(tstat)}</li>"
            )
        lines.append("</ul>")

    # Export preview
    if viewmodel.export_preview_txt or viewmodel.export_preview_json:
        lines.append("<p><b>Export preview:</b></p>")
        if viewmodel.export_preview_txt:
            lines.append(f"<p>TXT length: {len(viewmodel.export_preview_txt)} chars</p>")
        if viewmodel.export_preview_json:
            lines.append(f"<p>JSON length: {len(viewmodel.export_preview_json)} chars</p>")

    # Messages
    if viewmodel.messages:
        lines.append("<p><b>Messages:</b></p><ul>")
        for msg in viewmodel.messages[:10]:
            lines.append(f"<li>{escape(msg[:200])}</li>")
        lines.append("</ul>")

    return "\n".join(lines)
