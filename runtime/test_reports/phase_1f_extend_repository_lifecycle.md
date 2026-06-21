# Phase 1f-extend — Repository Lifecycle Report

## Repository creation point
- Created in main.py Pipeline.__init__ only if both feature flags are on
- Otherwise: not constructed

## Repository initialization failure behavior
- If initialize() fails, adapter gracefully skips repository writes
- RepositoryError raised for after-close operations

## Repository close point
- Not currently closed by pipeline (feature flag off)
- When wired: closed in Pipeline.stop() or adapter.stop_session()

## Adapter stop behavior
- stop_session(): scheduler.stop_session() — rejects new jobs, cancels pending
- Does NOT close repository (owned by pipeline)

## Pipeline stop behavior
- Dedup guard (_stopping)
- Audio stop → thread join → session gen increment
- adapter.stop_session()

## Double stop behavior
- All stop/close operations are idempotent

## SQLite lock risk
- Mutex protected (threading.Lock)
- check_same_thread=False on connection
- WAL mode for concurrent read/write safety
- Low contention in practice (separate connection per repository)

## Remaining lifecycle risks
- Repository not wired in main.py (feature flag off)
- No WAL checkpoint on close (auto-recovery on next open)
