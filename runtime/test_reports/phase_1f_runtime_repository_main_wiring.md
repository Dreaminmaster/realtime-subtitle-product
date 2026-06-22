# Phase 1f-runtime — Main Wiring Report

Phase: 1f-runtime
Branch: v2.4.0-architecture
Commit before: cbf9151
Commit after: (pending)

Files changed: 4
  - main.py (repository construction + close)
  - src/session_repository.py (WAL checkpoint on close)
  - tests/test_runtime_repository_wiring.py (NEW)
  - runtime/test_reports/*.md

main.py touched: YES (Pipeline.__init__ repository block, Pipeline.stop close)
config touched: NO
repository touched: YES (WAL checkpoint)
adapter touched: NO
Runtime default changed: NO
Feature flags: use_translation_scheduler + use_sqlite_session_repository (both false)

Repository construction rule:
  Both flags ON → repository created + initialized
  Either flag OFF → no repository

Repository init failure: caught, logged, adapter runs without repository
Adapter repository injection: repository= + repository_enabled= params
Pipeline stop: adapter.stop_session() → repository.close() → idempotent
Repository close: WAL checkpoint(TRUNCATE) → conn.close() → idempotent

Tests added: 12
Total: 219 (was 207)

Coverage:
  1. both flags off no repository: ✅
  2. repo on + scheduler off no repo: ✅
  3. scheduler on + repo off no repo: ✅
  4. both on constructs repository: ✅
  5. init failure safe: ✅
  6. close idempotent: ✅
  7. operation after close error: ✅
  8. WAL checkpoint on close: ✅
  9. checkpoint failure safe: ✅
  10. no real user path: ✅
  11. adapter stop + repo close safe: ✅
  12. old tests pass: ✅

Known risks:
  - _repo_owned flag reset to False after close (correct)
  - No WAL file cleanup (auto-recovery on next open)
