# Phase 2b-dashboard — History UI Wiring Report

Phase: 2b-dashboard
Branch: v2.4.0-architecture
Commit before: fc8ca7c
Commit after: (pending)

Files changed: 8
Files added:
  - src/history_dashboard_formatter.py (NEW)
  - src/dashboard_history_adapter.py (NEW)
  - tests/test_dashboard_history_formatting.py (NEW)
  - tests/test_dashboard_history_adapter.py (NEW)
  - dashboard.py (minimal: history section on diagnostics tab)
  - runtime/test_reports/phase_2b_dashboard_*.md

Dashboard touched: YES
Config touched: NO
Runtime touched: NO

Formatter: format_history_viewmodel_html()
Adapter: build_history_viewmodel_for_dashboard()
Display: QLabel in diagnostics tab, below Architecture Status
Escaping: html.escape() on all user text
Truncation: 1200 chars per transcript, 10 sessions, 20 segments

Tests added: 14
Total: 293 (+14 from Phase 2b)
