# Phase 1f — Lifecycle Hardening Report

## TranslationScheduler stop behavior
- stop_session(): sets _stopped=True, _session_id=None, cancels all QUEUED jobs
- submit() checks _stopped before accepting: returns None if stopped
- shutdown(): calls stop_session() then executor.shutdown(wait=wait)
- stop_session() and shutdown() are idempotent

## TranslationAdapter stop behavior
- stop_session(): calls scheduler.stop_session()
- shutdown(wait): calls scheduler.shutdown(wait)
- Both idempotent

## Pipeline.stop behavior
- Sets _stopping, _running=False
- Stops audio capture
- Joins processing loop thread
- Increments _session_generation
- Calls adapter.stop_session() (if adapter exists)
- Repeat calls return True immediately (dedup guard)

## Executor shutdown behavior
- ThreadPoolExecutor(max_workers=2, thread_name_prefix="transl")
- Workers are non-daemon (Python 3.12 default)
- shutdown(wait=True) sends sentinel, waits for workers to consume and exit
- shutdown(wait=False) sends sentinel, returns immediately (workers exit asynchronously)
- shutdown() called from scheduler.shutdown()

## Pending job cancellation behavior
- On stop_session(): all QUEUED jobs → CANCELLED
- On new revision: QUEUED old → CANCELLED, RUNNING old → STALE
- STALE jobs complete but results are discarded in _finish()
- DISCARDED jobs from queue overflow are marked DISCARDED

## Idempotent stop coverage
- Pipeline.stop(): dedup via self._stopping flag ✅
- TranslationAdapter.shutdown(): idempotent ✅
- TranslationScheduler.shutdown(): idempotent (checks _stopped) ✅
- SQLiteSessionRepository.close(): idempotent ✅
- Test: test_shutdown_idempotent (adapter) ✅
- Test: test_shutdown_idempotent (integration) ✅
- Test: test_close_idempotent (repository) ✅
- Test: test_stop_idempotent (pipeline integration) ✅

## Remaining lifecycle risks
1. **Non-daemon executor workers**: After shutdown(wait=False), executor workers
   may keep the process alive for a few seconds until they consume the sentinel.
   In production, this is a non-issue (app quits, process exits). For testing,
   shutdown(wait=True) is used where possible.
2. **Python < 3.9**: ThreadPoolExecutor.shutdown does not support cancel_futures.
   Not an issue here (Python 3.12).
3. **WAL checkpoint**: SQLite WAL mode may leave .wal/.shm files after close.
   Next open auto-recovers. Not a data loss risk.
