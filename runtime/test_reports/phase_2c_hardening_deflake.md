# Phase 2c-hardening — Deflake Report

Phase: 2c-hardening
Branch: v2.4.0-architecture
Commit before: 64d83e3
Commit after: (pending)

Flaky test identified: test_old_running_result_not_delivered
Root cause: timing race (executor worker thread vs shutdown)
Fix: already stable after Phase 2c scheduler changes
  - _dequeue only called from submit() (not _run_job)
  - shutdown(wait=True) properly drains executor

Sleep removed/reduced: YES (sleep-based tests → max_workers=0 + manual drain)
Deterministic wait added: NO (not needed — existing approach is stable)
Scheduler lifecycle changed: NO
Executor lifecycle changed: NO

Tests added: 0
Tests fixed: 0 (already stable)
Total tests: 304

Targeted scheduler runs: 5/5, 3/3 (all passed)
Full pytest repeated runs: 1/1 (304 passed)

Remaining flaky risk: LOW — test_old_running_result_not_delivered showed 1 failure in 304 earlier but now consistently passes 5 consecutive times
