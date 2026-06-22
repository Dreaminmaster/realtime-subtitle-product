# Phase 3d — Dashboard Wire Mapping

Phase: 3d-dashboard-wire
Branch: v2.4.0-architecture
Commit before: 52c0abe

Formatter exists: yes (src/runtime_decision_formatter.py)
dashboard.py imports formatter: no ❌
dashboard.py displays Runtime Decision: no ❌
diagnostics tab contains Runtime Decision QLabel: no ❌
Architecture Status location: dashboard.py line 1373 (QLabel). Style defined.
Runtime Decision location: NOT PRESENT
Transcript History location: dashboard.py line 1383 (QLabel)
Need code change: yes ⚠️
Need dashboard.py change: yes ⚠️

Plan: insert Runtime Decision QLabel between Architecture Status and Transcript History in diagnostics tab (line ~1382).
