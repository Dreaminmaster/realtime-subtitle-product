"""Translation scheduler for v2.4.0 architecture.

Phase 1d: full queue / revision / session-guard / stale-discard semantics.
Phase 1d does NOT call a real translation API — it uses an injectable
translator callable (default: no-op that returns a fixed string).

Core guarantees:
  1. Only FINAL events enter the queue (PARTIAL/STABLE return None).
  2. Queue has max_size; overflow drops oldest pending non-RUNNING jobs.
  3. job_key = session_id:segment_id:revision.
  4. New revision cancels old pending job for same (session_id, segment_id).
  5. Running old job result is discarded when revision is stale.
  6. Old-session results are discarded (session_id mismatch).
  7. stop() rejects new jobs; pending → CANCELLED.
  8. Translator failure does NOT affect future jobs.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future


class TranslationStatus(Enum):
    NOT_REQUESTED = auto()
    QUEUED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    STALE = auto()
    CANCELLED = auto()
    DISCARDED = auto()


class TranslationSchedulerError(RuntimeError):
    """Raised by the scheduler itself (not the translator)."""
    def __init__(self, message, *, job_key=None, session_id=None):
        super().__init__(message)
        self.job_key = job_key
        self.session_id = session_id


# ── job / result data types ───────────────────────────────────────
@dataclass
class TranslationJob:
    job_key: str
    session_id: str
    segment_id: str
    revision: int
    text: str
    target_lang: str | None = None
    status: TranslationStatus = TranslationStatus.NOT_REQUESTED
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    _future: Future | None = field(default=None, repr=False)


@dataclass
class TranslationResult:
    job_key: str
    session_id: str
    segment_id: str
    revision: int
    original_text: str
    translated_text: str | None
    status: TranslationStatus
    error: str | None = None
    created_at: float = field(default_factory=time.time)


# ── scheduler ─────────────────────────────────────────────────────
def _noop_translate(text: str, target_lang: str | None) -> str:
    """Phase 1d default: returns a mock translation."""
    return f"[{target_lang or 'unknown'}]: {text}"


class TranslationScheduler:
    """Manages the translation job queue with session/revision guards.

    Thread-safe.  All callbacks are invoked under the scheduler's lock
    to prevent re-entrant deadlocks with session transitions.
    """

    def __init__(
        self,
        translator: callable = _noop_translate,
        max_queue: int = 20,
        max_workers: int = 2,
        on_result: callable | None = None,
        on_error: callable | None = None,
    ):
        self._translator = translator
        self._max_queue = max(1, max_queue)
        if max_workers > 0:
            self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="transl")
        else:
            self._executor = None  # no auto-dequeue — test mode
        self._lock = threading.Lock()
        self._on_result = on_result
        self._on_error = on_error

        # Active session
        self._session_id: str | None = None

        # All jobs (key → TranslationJob)
        self._jobs: dict[str, TranslationJob] = {}
        # Queue ordering (keys in insertion order)
        self._queue: list[str] = []
        # Currently RUNNING keys
        self._running: set[str] = set()

        # Stopped flag
        self._stopped = False

    # ── session lifecycle ───────────────────────────────────────
    def start_session(self, session_id: str) -> None:
        with self._lock:
            self._session_id = session_id
            self._stopped = False

    def stop_session(self) -> None:
        """Stop accepting new jobs and cancel pending work atomically."""
        with self._lock:
            self._stop_session_locked()

    def _stop_session_locked(self) -> None:
        """Internal stop implementation. ``self._lock`` must be held."""
        self._stopped = True
        self._session_id = None
        for idx in list(reversed(self._queue)):
            self._fail_job(idx, TranslationStatus.CANCELLED, "session stopped")

    def shutdown(self, wait: bool = True) -> None:
        """Idempotent shutdown: stop + join executor."""
        with self._lock:
            self._stop_session_locked()
        if self._executor is not None:
            self._executor.shutdown(wait=wait, cancel_futures=True)

    # ── submit ─────────────────────────────────────────────────
    def submit(self, event) -> TranslationStatus | None:
        """Submit a TranscriptEvent for translation.

        Returns:
          - None if the event was NOT queued (not FINAL, already stopped)
          - TranslationStatus.QUEUED if queued
        """
        from src.transcript_event import TranscriptEvent, TranscriptPhase
        if not isinstance(event, TranscriptEvent):
            raise TypeError("submit() expects a TranscriptEvent")

        # Only FINAL events are translated
        if event.phase != TranscriptPhase.FINAL:
            return None

        text = event.effective_text
        if not (text and text.strip()):
            return None

        with self._lock:
            if self._stopped or self._session_id is None:
                return None

            job_key = self._make_key(event.session_id, event.segment_id, event.revision)

            # Already have a job for this key?
            existing = self._jobs.get(job_key)
            if existing and existing.status == TranslationStatus.COMPLETED:
                return existing.status  # already done

            # If a different-revision job for same (session_id, segment_id) is pending,
            # cancel it.
            self._cancel_old_revisions(event.session_id, event.segment_id, event.revision)

            # Ensure capacity
            self._ensure_capacity()

            job = TranslationJob(
                job_key=job_key,
                session_id=event.session_id,
                segment_id=event.segment_id,
                revision=event.revision,
                text=text,
                target_lang=event.target_lang,
                status=TranslationStatus.QUEUED,
            )
            self._jobs[job_key] = job
            self._queue.append(job_key)
            self._dequeue()
            return TranslationStatus.QUEUED

    # ── internal ────────────────────────────────────────────────
    @staticmethod
    def _make_key(session_id: str, segment_id: str, revision: int) -> str:
        return f"{session_id}:{segment_id}:{revision}"

    def _cancel_old_revisions(self, session_id: str, segment_id: str, new_revision: int) -> None:
        """Mark all jobs for (session_id, segment_id) with revision < new_revision
        as CANCELLED if QUEUED, or STALE if RUNNING (will be discarded on completion)."""
        for key, job in self._jobs.items():
            if job.session_id != session_id or job.segment_id != segment_id:
                continue
            if job.revision >= new_revision:
                continue
            if job.status == TranslationStatus.QUEUED:
                self._fail_job(key, TranslationStatus.CANCELLED, "superseded by revision")
            elif job.status == TranslationStatus.RUNNING:
                job.status = TranslationStatus.STALE  # will be discarded on completion

    def _ensure_capacity(self) -> None:
        """Drop oldest QUEUED job if queue is full."""
        while len(self._queue) >= self._max_queue:
            # Find oldest QUEUED entry
            for idx in self._queue:
                job = self._jobs.get(idx)
                if job and job.status == TranslationStatus.QUEUED:
                    self._fail_job(idx, TranslationStatus.DISCARDED, "queue full")
                    break
            else:
                break  # no QUEUED jobs left

    def _dequeue(self) -> None:
        """Submit the next QUEUED job to the executor. Caller must hold lock."""
        if not self._executor or self._stopped:
            return
        # Find first QUEUED
        idx = None
        for q in self._queue:
            j = self._jobs.get(q)
            if j and j.status == TranslationStatus.QUEUED:
                idx = q
                break
        if idx is None:
            return
        job = self._jobs[idx]
        if job._future is not None:
            return
        job.status = TranslationStatus.RUNNING
        job.started_at = time.time()
        self._running.add(idx)
        job._future = self._executor.submit(self._run_job, idx)

    def _run_job(self, job_key: str):
        """Execute in executor thread."""
        with self._lock:
            job = self._jobs.get(job_key)
            if job is None:
                return
            if job.status == TranslationStatus.STALE:
                # Already marked stale while queued running — discard
                self._finish(job_key, TranslationStatus.DISCARDED, None, "stale")
                return

        # Run translator (outside lock to avoid blocking)
        error = None
        result_text = None
        try:
            result_text = self._translator(job.text, job.target_lang)
        except Exception as e:
            error = str(e)

        with self._lock:
            job = self._jobs.get(job_key)
            if job is None:
                return
            if job.status == TranslationStatus.STALE:
                self._finish(job_key, TranslationStatus.DISCARDED, None, "stale")
            elif error is not None:
                self._finish(job_key, TranslationStatus.FAILED, None, error)
            else:
                self._finish(job_key, TranslationStatus.COMPLETED, result_text, None)

    def _finish(self, job_key: str, status: TranslationStatus, text: str | None, error: str | None):
        job = self._jobs.get(job_key)
        if job is None:
            return
        job.status = status
        job.finished_at = time.time()
        job.error = error
        self._running.discard(job_key)
        if job_key in self._queue:
            self._queue.remove(job_key)

        # Build result
        result = TranslationResult(
            job_key=job_key,
            session_id=job.session_id,
            segment_id=job.segment_id,
            revision=job.revision,
            original_text=job.text,
            translated_text=text,
            status=status,
            error=error,
        )

        # Session guard: discard if session changed
        if job.session_id != self._session_id:
            result.status = TranslationStatus.DISCARDED
            return

        # Revision guard: discard STALE/DISCARDED
        if result.status in (TranslationStatus.STALE, TranslationStatus.DISCARDED):
            return

        # Invoke callbacks (protected — caller errors don't kill scheduler)
        if status == TranslationStatus.COMPLETED and self._on_result is not None:
            try:
                self._on_result(result)
            except Exception:
                pass
        elif status == TranslationStatus.FAILED and self._on_error is not None:
            try:
                self._on_error(job, result)
            except Exception:
                pass

        # Do NOT call _dequeue() from here — when an executor worker
        # thread submits to its own executor, CPython's ThreadPoolExecutor
        # can deadlock on shutdown(wait=True).  The next submit() call
        # will call _dequeue() on its own.

    def _fail_job(self, key: str, status: TranslationStatus, reason: str) -> None:
        """Transition a job to a terminal failure status and remove from queue."""
        job = self._jobs.get(key)
        if job is None:
            return
        if job.status in (TranslationStatus.QUEUED,):
            job.status = status
            job.error = reason
            job.finished_at = time.time()
            if key in self._queue:
                self._queue.remove(key)

    # ── query ──────────────────────────────────────────────────
    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status == TranslationStatus.QUEUED)

    def running_count(self) -> int:
        with self._lock:
            return len(self._running)

    def is_stopped(self) -> bool:
        with self._lock:
            return self._stopped

    def job_status(self, session_id: str, segment_id: str, revision: int) -> TranslationStatus | None:
        key = self._make_key(session_id, segment_id, revision)
        with self._lock:
            j = self._jobs.get(key)
            return j.status if j else None
