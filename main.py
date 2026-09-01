#!/usr/bin/env python3
"""
Realtime Subtitle - Main Entry Point

Desktop real-time speech recognition and translation with a floating overlay.

Usage:
    python3 main.py                    # Launch with dashboard
    python3 main.py --overlay-only     # Launch overlay directly
    python3 main.py --diagnostics      # Run system diagnostics (no GUI needed)
"""

import os
import sys
import signal
import argparse
import logging

from app_paths import get_log_dir

# Fix library conflicts
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Setup app-level logging
LOG_DIR = get_log_dir()
_log_handlers = [logging.StreamHandler(sys.stdout)]
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _log_handlers.insert(0, logging.FileHandler(LOG_DIR / "app.log"))
except OSError:
    # Read-only test environments and locked-down Macs should still be able
    # to launch; diagnostics remain available on stdout.
    pass
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=_log_handlers,
)
log = logging.getLogger("RealtimeSubtitle")


def should_open_permission_guide(no_permission_check=False):
    """The dashboard now provides non-modal onboarding; never block launch."""
    return False

def parse_args():
    parser = argparse.ArgumentParser(description="Realtime Subtitle")
    parser.add_argument("--overlay-only", action="store_true",
                       help="Launch overlay window directly")
    parser.add_argument("--diagnostics", action="store_true",
                       help="Run system diagnostics and exit")
    parser.add_argument("--no-permission-check", action="store_true",
                       help="Skip first-launch permission guide")
    return parser.parse_args()


def run_diagnostics():
    """Run and display system diagnostics (no GUI required)"""
    from diagnostics import diagnostics, logger
    
    print(diagnostics.get_status_text())
    
    logs = logger.get_logs(20)
    if logs:
        print("\n--- Recent Logs ---")
        for line in logs:
            print(line.rstrip())
    
    print("\n--- Translation Engine Check ---")
    try:
        from translation_engine import TranslationEngine
        engine = TranslationEngine()
        for mode in ['off', 'online', 'local', 'custom']:
            try:
                engine.set_mode(mode)
                print(f"  {mode}: {engine.current_name} — OK")
            except Exception as e:
                print(f"  {mode}: FAILED — {e}")
    except Exception as e:
        print(f"  Translation engine load FAILED: {e}")
    
    print("\n--- Model Manager Check ---")
    try:
        from model_manager import model_manager
        whisper_models = model_manager.get_models('whisper')
        downloaded = [m for m in whisper_models if m.get('downloaded')]
        print(f"  Whisper models: {len(whisper_models)} available, {len(downloaded)} downloaded")
        disk = model_manager.get_disk_usage()
        print(f"  Total disk: {disk['total_mb']} MB across {disk['model_count']} models")
    except Exception as e:
        print(f"  Model manager check FAILED: {e}")
    
    print("\n--- Python Environment ---")
    print(f"  Python: {sys.version}")
    print(f"  Executable: {sys.executable}")
    print(f"  Platform: {sys.platform}")


def main():
    args = parse_args()
    
    try:
        from version import BUILD_VERSION, BUILD_COMMIT, BUILD_TIME
        version_label = BUILD_VERSION if str(BUILD_VERSION).startswith("v") else f"v{BUILD_VERSION}"
        log.info(f"Realtime Subtitle {version_label} (commit {BUILD_COMMIT} built {BUILD_TIME})")
    except ImportError:
        log.info("Realtime Subtitle (dev build)")
    log.info(f"Args: {args}")
    
    # Handle diagnostics mode — no GUI imports needed
    if args.diagnostics:
        run_diagnostics()
        return
    
    # Lazy import PyQt6 only when GUI is needed
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer
    except ImportError:
        log.error("PyQt6 is required for GUI mode. Install with: pip install PyQt6>=6.5")
        print("ERROR: PyQt6 is required for GUI mode.")
        print("Install it with: pip install PyQt6>=6.5")
        print("Or run diagnostics without GUI:")
        print("  python3 main.py --diagnostics")
        sys.exit(1)
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    # The control center may be hidden while the subtitle overlay remains
    # active.  Window closure is handled explicitly by Dashboard.closeEvent.
    app.setQuitOnLastWindowClosed(False)
    from single_instance import SingleInstance
    instance = SingleInstance(parent=app)
    if not instance.is_primary:
        log.info("Existing Realtime Subtitle instance notified; exiting duplicate launch")
        return
    try:
        from PyQt6.QtGui import QIcon
        icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets", "icon", "realtime-subtitle-icon.png",
        )
        if os.path.isfile(icon_path):
            app.setWindowIcon(QIcon(icon_path))
    except Exception:
        log.debug("Application icon could not be loaded", exc_info=True)
    
    # Global exception hook
    def exception_hook(exctype, value, traceback_obj):
        import traceback
        tb = ''.join(traceback.format_exception(exctype, value, traceback_obj))
        log.critical(f"Unhandled exception: {tb}")
        from PyQt6.QtWidgets import QMessageBox
        if QApplication.instance():
            QMessageBox.critical(None, "Realtime Subtitle — Crash",
                               f"Unexpected error:\n\n{str(value)[:500]}")
        sys.exit(1)
    sys.excepthook = exception_hook
    
    signal.signal(signal.SIGINT, lambda sig, frame: app.quit())
    app.aboutToQuit.connect(_shutdown_active_pipeline)
    
    from diagnostics import diagnostics
    diagnostics._check_platform()
    
    # Launch dashboard or overlay
    if args.overlay_only:
        # Overlay-only: everything on main thread
        from PyQt6.QtCore import QTimer as Timer
        Timer.singleShot(100, _launch_overlay_session)
    else:
        from dashboard import Dashboard
        dash = Dashboard()
        instance.message_received.connect(
            lambda message: dash._show_control_center()
            if message == "show-controls" else None
        )
        dash.show()
    
    timer = QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)
    
    try:
        sys.exit(app.exec())
    except SystemExit:
        pass


# ---- Non-UI pipeline helpers (safe to call from any thread) ----

def create_pipeline():
    """Create pipeline components WITHOUT creating any UI widgets.
    Returns (pipeline, config_dict) or raises on error."""
    from config import config
    import time
    import numpy as np
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from PyQt6.QtCore import QObject, pyqtSignal
    from audio_capture import AudioCapture, AudioCaptureError
    
    log.info("Creating pipeline (non-UI)...")
    
    class WorkerSignals(QObject):
        update_text = pyqtSignal(int, str, str)
        update_caption_state = pyqtSignal(int, str, str, str, int)
        remove_text = pyqtSignal(int)
        audio_status = pyqtSignal(str, float)  # (status_text, volume_level 0.0-1.0)
        pipeline_failed = pyqtSignal(str)       # error message when pipeline crashes
        pipeline_cleanup_finished = pyqtSignal(bool, str) # (success, message)
        pipeline_started = pyqtSignal()          # pipeline loop started successfully
        audio_failed = pyqtSignal(str)           # audio device failure message
    
    class Pipeline(QObject):
        def __init__(self, signals_obj):
            super().__init__()
            self.signals = signals_obj
            self.running = True
            # Utterance lifecycle tracking — generation-guarded, pruned, thread-safe
            import threading as _threading_mod
            self._lifecycle_lock = _threading_mod.RLock()
            self._phrase_lock = _threading_mod.RLock()
            self._utt_lifecycle = {}  # uid -> {"generation": int, "state": str}
            self._finalizing_uids = set()
            self._finalized_uids = set()
            self._latest_partial_seq = {}  # uid -> latest seq
            self._session_generation = 0    # incremented each Launch, stops stale tasks
            self.last_final_text = ""        # context prompt across utterances
            from src.contextual_phrase_composer import ContextualPhraseComposer
            self.phrase_composer = ContextualPhraseComposer(join_window=5.5)
            from src.accuracy_refinement import AccuracyRefinementCoordinator
            self.accuracy_coordinator = AccuracyRefinementCoordinator(
                self.phrase_composer,
                self._session_generation,
            )
            self.accuracy_transcriber = None
            self.accuracy_plan = None
            self._accuracy_model_path = None
            self._accuracy_accepting = False
            self._accuracy_condition = _threading_mod.Condition()
            self._accuracy_pending = None
            self._accuracy_thread = None
            self._latest_translation_revision = {}
            from runtime_performance import RuntimePerformancePolicy
            self.performance_policy = RuntimePerformancePolicy(
                getattr(config, "performance_profile", "balanced")
            )
            from src.runtime_metrics import RuntimeMetrics
            self.runtime_metrics = RuntimeMetrics(
                profile=self.performance_policy.profile,
                backend=getattr(config, "asr_backend", "unknown"),
                model=(
                    getattr(config, "whisper_model", "unknown")
                    if getattr(config, "asr_backend", "whisper") in {"whisper", "mlx"}
                    else getattr(config, "funasr_model", "unknown")
                ),
            )
            from src.streaming_transcript_state import StreamingTranscriptState
            self.streaming_transcript_state = StreamingTranscriptState(
                unsafe_tail_tokens=2,
                min_stable_tokens=1,
            )
            self._latest_hypothesis_text = {}
            self._latest_hypothesis_changed_at = {}
            self.live_translation_drafts = None
            self._cleanup_in_progress = False
            self._failed = False
            self._stopping = False             # dedup stop guard
            
            from transcriber_pool import get_or_create_transcriber
            
            log.info("Pipeline: initializing audio capture...")
            config.print_config()
            
            capture_class = AudioCapture
            capture_options = {"device_index": config.device_index}
            if getattr(config, "input_source", "microphone") == "system_audio":
                from system_audio_capture import SystemAudioCapture
                capture_class = SystemAudioCapture
                capture_options = {
                    "output_device_id": getattr(config, "system_output_device", "")
                }

            self.audio = capture_class(
                sample_rate=config.sample_rate,
                silence_threshold=config.silence_threshold,
                silence_duration=config.silence_duration,
                chunk_duration=config.chunk_duration,
                max_phrase_duration=config.max_phrase_duration,
                streaming_mode=config.streaming_mode,
                streaming_interval=config.streaming_interval,
                streaming_step_size=config.streaming_step_size,
                streaming_overlap=config.streaming_overlap,
                **capture_options,
            )
            log.info("Pipeline: audio capture initialized")
            if self.audio and not self.running:
                return  # stop was requested during initialization
            
            # Use global singleton — no reload on relaunch
            self.transcriber = get_or_create_transcriber()
            log.info("Pipeline: transcriber ready (pooled)")

            try:
                from accuracy_transcriber import resolve_accuracy_runtime
                accuracy_runtime = resolve_accuracy_runtime()
                if accuracy_runtime is not None:
                    self.accuracy_plan, self._accuracy_model_path = accuracy_runtime
                    log.info(
                        "Pipeline: enhanced ASR queued for background loading (%s)",
                        self.accuracy_plan.model_id,
                    )
            except Exception:
                # Accuracy enhancement is optional.  A memory or model error
                # must never prevent the normal live-caption path from starting.
                log.exception("Pipeline: enhanced ASR unavailable; using standard recognition")
            
            from translation_engine import translation_engine
            self.translation_engine = translation_engine
            trans_mode = getattr(config, 'translation_mode', 'off')
            self.translation_engine.target_lang = config.target_lang
            translation_model = (
                config.offline_translation_model
                if trans_mode == "offline" else config.model
            )
            translation_source = config.source_language or "auto"
            if trans_mode == "offline" and translation_source == "auto":
                from translation_model_manager import translation_model_manager
                offline_item = translation_model_manager.model(translation_model)
                if offline_item is not None:
                    translation_source = offline_item.source
            self.translation_engine.set_mode(
                trans_mode,
                base_url=config.api_base_url,
                api_key=config.api_key or "",
                model=translation_model,
                timeout=getattr(config, 'translation_timeout', 12.0),
                source_language=translation_source,
            )
            log.info(f"Pipeline: translation engine ({trans_mode}) initialized")

            draft_interval = self.performance_policy.draft_translation_interval(
                trans_mode,
                getattr(config, "live_translation_mode", "balanced"),
            )
            if draft_interval is not None:
                from src.live_translation_drafts import LiveTranslationDrafts

                self.live_translation_drafts = LiveTranslationDrafts(
                    translator=self.translation_engine.translate_draft,
                    on_result=self._on_live_translation_draft,
                    interval=draft_interval,
                    min_growth=self.performance_policy.draft_min_growth(
                        getattr(config, "live_translation_mode", "balanced")
                    ),
                )
                log.info(
                    "Pipeline: live draft translation enabled interval=%.2fs profile=%s",
                    draft_interval,
                    self.performance_policy.profile,
                )

            # v2.4: Runtime settings guard evaluates feature flags
            # Feature flags: REALTIME_SUBTITLE_USE_TRANSLATION_SCHEDULER
            #                REALTIME_SUBTITLE_USE_SQLITE_SESSION_REPOSITORY
            self._repository = None
            self._repo_owned = False
            self._translation_session_id = None
            self.session_recorder = None
            self._recording_duration = 0.0
            from src.runtime_settings_guard import RuntimeSettingsGuard, settings_from_config
            self._runtime_decision = RuntimeSettingsGuard().evaluate(settings_from_config(config))

            if self._runtime_decision.allow_translation_scheduler:
                from src.translation_adapter import TranslationAdapter
                from src.translation_scheduler import TranslationScheduler

                if self._runtime_decision.allow_sqlite_repository:
                    try:
                        from src.session_repository import SQLiteSessionRepository, get_default_database_path
                        self._repository = SQLiteSessionRepository(get_default_database_path())
                        self._repository.initialize()
                        self._repo_owned = True
                        log.info("Pipeline: SQLite repository initialized")
                    except Exception as exc:
                        log.error(f"Pipeline: repository init failed — running without persistence: {exc}")
                        self._repository = None
                        self._repo_owned = False

                self._translation_scheduler = TranslationScheduler(
                    translator=self.translation_engine.translate,
                    max_queue=30,
                    max_workers=self.performance_policy.translation_workers(
                        getattr(config, "translation_threads", 2)
                    ),
                )
                self.translation_adapter = TranslationAdapter(
                    scheduler=self._translation_scheduler,
                    on_update_text=self._on_final_translation_update,
                    repository=self._repository,
                    repository_enabled=self._repository is not None,
                )
                import uuid
                self._translation_session_id = uuid.uuid4().hex
                session_metadata = {
                    "record_audio": bool(getattr(config, "record_session_audio", False)),
                    "input_source": getattr(config, "input_source", "microphone"),
                }
                if session_metadata["record_audio"]:
                    from session_recording import (
                        SessionAudioRecorder,
                        get_session_recording_path,
                    )
                    recording_path = get_session_recording_path(
                        self._translation_session_id
                    )
                    self.session_recorder = SessionAudioRecorder(
                        recording_path, config.sample_rate
                    )
                    session_metadata["audio_path"] = str(recording_path)
                    session_metadata["audio_format"] = "wav"
                self.translation_adapter.start_session(
                    self._translation_session_id,
                    source_language=config.source_language or "Auto",
                    target_language=config.target_lang if trans_mode != "off" else None,
                    metadata=session_metadata,
                )
                log.info("Pipeline: v2.4 TranslationScheduler wired (use_translation_scheduler=true)")

                # v2.4 Transcriber output bridge (opt-in, off by default)
                try:
                    from src.runtime_transcriber_bridge_adapter import build_transcriber_output_bridge_for_runtime
                    self.transcriber_output_bridge = build_transcriber_output_bridge_for_runtime(
                        self._runtime_decision,
                        session_id=self._translation_session_id,
                        translation_adapter=self.translation_adapter,
                    )
                    if self.transcriber_output_bridge is not None:
                        log.info("Pipeline: transcriber output bridge wired")
                    else:
                        log.info("Pipeline: transcriber output bridge not enabled")
                except Exception as exc:
                    log.warning(f"Pipeline: transcriber bridge creation failed: {exc}")
                    self.transcriber_output_bridge = None
            else:
                self.transcriber_output_bridge = None
                log.info("Pipeline: using legacy translate_executor (use_translation_scheduler=false)")
        
        def _on_live_translation_draft(self, chunk_id, original, translated):
            self.runtime_metrics.record_translation(chunk_id)
            self.signals.update_text.emit(chunk_id, original, translated)

        def _on_final_translation_update(self, chunk_id, original, translated):
            if translated:
                self.runtime_metrics.record_translation(chunk_id)
            self.signals.update_text.emit(chunk_id, original, translated)

        def start(self):
            self._stopping = False  # reset for new session
            self.running = True     # reset from previous stop
            self.audio.prepare_start()
            if self.session_recorder is not None:
                self.session_recorder.start()
            self.thread = threading.Thread(target=self.processing_loop, daemon=True, name="PipelineLoop")
            self.thread.start()
        
        def stop(self):
            if self._stopping:
                return True  # already stopping
            self._stopping = True
            log.info("Stop requested")
            self.running = False
            self._stop_accuracy_worker()
            if self.live_translation_drafts is not None:
                self.live_translation_drafts.stop()
            self.audio.stop()
            log.info("Audio capture stopped")
            if hasattr(self, 'thread') and self.thread.is_alive():
                self.thread.join(timeout=15)
                if self.thread.is_alive():
                    log.error("Pipeline loop did not stop within timeout")
                    return False
            if self.session_recorder is not None:
                self._recording_duration = self.session_recorder.stop()
            # Session invalidation ONLY after clean shutdown
            self._session_generation += 1
            if hasattr(self, 'translation_adapter'):
                # Invalidate the scheduler before closing its repository.
                # Running HTTP calls may finish later, but their results are
                # session-guarded and cannot write to the closed connection.
                self.translation_adapter.shutdown(wait=False)
            if self._repo_owned and self._repository is not None:
                try:
                    if self._translation_session_id is not None:
                        if self.session_recorder is not None:
                            from session_recording import inspect_session_recording

                            recording_info = inspect_session_recording(
                                self.session_recorder.path
                            )
                            self._repository.update_session_metadata(
                                self._translation_session_id,
                                {
                                    "audio_duration": recording_info.duration,
                                    "audio_bytes": recording_info.bytes,
                                    "audio_ready": recording_info.playable,
                                },
                            )
                        self._repository.close_session(self._translation_session_id)
                except Exception as exc:
                    log.warning(f"Pipeline: session close error: {exc}")
                finally:
                    try:
                        self._repository.close()
                    except Exception as exc:
                        log.warning(f"Pipeline: repository close error: {exc}")
                self._repo_owned = False
                self._repository = None
            log.info("Pipeline stopped — session invalidated")
            return True
        
        def _handle_transcriber_output_via_bridge(self, raw_output) -> bool:
            """v2.4 bridge hook — consumes raw transcriber output.

            Returns:
              True  = bridge path handled the output (caller should NOT use legacy)
              False = bridge unavailable (caller should use legacy path)

            Does NOT crash on any exception.
            """
            bridge = getattr(self, 'transcriber_output_bridge', None)
            if bridge is None:
                return False
            try:
                result = bridge.handle_raw_output(raw_output)
                if result.ok:
                    return True
                log.debug(f"Bridge result: {result.message}")
                return True  # handled even if invalid — legacy should not double-process
            except Exception:
                return False  # fallback to legacy on bridge exception
        
        def processing_loop(self):
            log.info("Pipeline: processing loop started (state-machine mode)")
            
            translate_executor = ThreadPoolExecutor(
                max_workers=self.performance_policy.translation_workers(
                    getattr(config, "translation_threads", 2)
                ),
                thread_name_prefix="live-translation",
            )
            accuracy_executor = None
            lifecycle_lock = self._lifecycle_lock
            session_gen = self._session_generation  # snapshot for this session
            self.runtime_metrics.start_session()
            self.streaming_transcript_state.reset()
            self._latest_hypothesis_text.clear()
            self._latest_hypothesis_changed_at.clear()
            self.accuracy_coordinator.reset(session_gen)
            self._start_accuracy_worker(session_gen, translate_executor)
            if self.live_translation_drafts is not None:
                self.live_translation_drafts.start_session(session_gen)
            
            # ---- Priority ASR queue: FINAL(0) > PARTIAL(1) ----
            import queue as pyqueue
            _SENTINEL = object()
            asr_queue = pyqueue.PriorityQueue()
            asr_running = threading.Event()
            
            def asr_worker_loop():
                while True:
                    try:
                        prio, seq, task = asr_queue.get(timeout=0.5)
                    except pyqueue.Empty:
                        continue
                    
                    if task is _SENTINEL:
                        log.info("ASR worker shutdown sentinel received")
                        asr_queue.task_done()
                        break
                    
                    asr_running.set()
                    t0 = time.time()
                    task_type = task["type"]
                    uid = task["uid"]
                    gen = task["gen"]
                    audio = task["audio"]
                    prompt = task.get("prompt", "")
                    
                    if task_type == "final":
                        qwait = (t0 - task["created_at"]) * 1000
                        log.info(f"Utterance[{uid}] FINAL started queue_wait_ms={qwait:.0f}")
                        self._process_final_v3(
                            audio, uid, gen, prompt, translate_executor,
                            lifecycle_lock, session_gen,
                            task.get("start_offset"), task.get("end_offset"),
                            accuracy_executor=accuracy_executor,
                        )
                        inference_ms = (time.time() - t0) * 1000
                        total_ms = (time.time() - task["created_at"]) * 1000
                        log.info(f"Utterance[{uid}] FINAL completed inference_ms={inference_ms:.0f} total_ms={total_ms:.0f}")
                    else:
                        task_seq = task.get("seq", 0)
                        log.debug(f"Utterance[{uid}] PARTIAL started seq={task_seq}")
                        self._process_partial_v3(audio, uid, gen, task_seq, prompt, lifecycle_lock, session_gen)
                    
                    asr_queue.task_done()
                    asr_running.clear()
                log.info("ASR worker stopped")
            
            asr_thread = threading.Thread(target=asr_worker_loop, daemon=True, name="ASRWorker")
            asr_thread.start()
            
            # Task counter for ordering within same priority
            self._asr_seq = 0
            
            # ASR lifecycle state (never reset by recording state)
            self._finalizing_uids = set()
            self._finalized_uids = set()
            # Per-utterance pending partial: only one per uid
            self._latest_partial_seq = {}       # uid -> latest seq (for superseding)
            self._seq_counter = 0
            
            STATE_IDLE = 0
            STATE_RECORDING = 1
            state = STATE_IDLE
            buffer = np.array([], dtype=np.float32)
            pre_roll = np.array([], dtype=np.float32)
            silence_counter = 0
            utterance_id = 1
            utterance_generation = 0
            last_partial_time = 0.0
            audio_cursor = 0.0
            utterance_start_offset = 0.0
            
            # Balanced endpointing: short phrases are no longer discarded,
            # while a bounded pause closes the line quickly enough for live use.
            # Respect the user's endpoint setting.  The old 0.85 s ceiling
            # silently ignored values such as 1.0 s and split natural pauses.
            SILENCE_DUR_SEC = max(0.45, min(float(config.silence_duration), 2.0))
            MIN_UTTERANCE_DUR = 0.45
            # Keep one timed caption readable even when an older config still
            # carries the former 15–30 second paragraph-sized ceiling.
            MAX_UTTERANCE_DUR = self.performance_policy.caption_segment_limit(
                config.max_phrase_duration
            )
            # A draft every ~0.8 s still feels live while avoiding the repeated
            # whole-buffer inference seen at 0.5–0.6 s on CPU-only Macs.
            PARTIAL_INTERVAL = self.performance_policy.partial_interval(
                getattr(config, "update_interval", 0.8)
            )
            PRE_ROLL_MS = 0.4
            from adaptive_vad import AdaptiveNoiseGate
            from src.semantic_endpoint import EndpointSignals, SemanticEndpointPolicy
            noise_gate = AdaptiveNoiseGate(
                self.audio.silence_threshold,
                getattr(config, "noise_gate_mode", "balanced"),
            )
            endpoint_policy = SemanticEndpointPolicy(
                base_silence=SILENCE_DUR_SEC,
                min_duration=MIN_UTTERANCE_DUR,
                max_duration=MAX_UTTERANCE_DUR,
                max_words=42 if self.performance_policy.profile != "efficient" else 34,
            )
            
            def _reset_recording_state():
                nonlocal buffer, pre_roll, silence_counter, state, last_partial_time
                buffer = np.array([], dtype=np.float32)
                pre_roll = np.array([], dtype=np.float32)
                silence_counter = 0
                state = STATE_IDLE
                last_partial_time = 0.0
            
            def _invalidate_partials_for_uid(uid):
                """Invalidate all pending partials for uid by clearing latest seq.
                Tasks remain in the queue but will be discarded at dispatch time."""
                if uid in self._latest_partial_seq:
                    old_seq = self._latest_partial_seq.pop(uid)
                    log.info(f"Utterance[{uid}] pending PARTIAL invalidated (was seq={old_seq})")
            
            try:
                audio_gen = self.audio.generator()
                startup_confirmed = False
                for audio_chunk in audio_gen:
                    if not self.running:
                        break
                    if not startup_confirmed:
                        try:
                            self.signals.pipeline_started.emit()
                            startup_confirmed = True
                        except Exception:
                            log.critical("pipeline_started signal broken")
                    
                    chunk_start = audio_cursor
                    chunk_end = chunk_start + len(audio_chunk) / self.audio.sample_rate
                    if self.session_recorder is not None:
                        chunk_start, chunk_end = self.session_recorder.write(audio_chunk)
                    audio_cursor = chunk_end

                    # Remove DC bias for level analysis only.  The original
                    # samples still go to recording and ASR unchanged.
                    analysis_chunk = audio_chunk - float(np.mean(audio_chunk))
                    chunk_rms = float(np.sqrt(np.mean(analysis_chunk**2)))
                    is_speech = noise_gate.classify(
                        chunk_rms,
                        recording=state == STATE_RECORDING,
                    )
                    now = time.time()
                    chunk_dur = len(audio_chunk) / self.audio.sample_rate
                    
                    self.signals.audio_status.emit(
                        "🎤 Listening" if is_speech else "🔇 Silent",
                        min(chunk_rms * 50, 1.0)
                    )
                    
                    # --- STATE: IDLE ---
                    if state == STATE_IDLE:
                        pre_roll = np.concatenate([pre_roll, audio_chunk])
                        pr_samples = int(self.audio.sample_rate * PRE_ROLL_MS)
                        if len(pre_roll) > pr_samples:
                            pre_roll = pre_roll[-pr_samples:]
                        
                        if is_speech:
                            utterance_generation += 1
                            self._utt_lifecycle[utterance_id] = {"generation": utterance_generation, "state": "recording"}
                            self.runtime_metrics.begin_segment(utterance_id)
                            log.info(f"Utterance[{utterance_id}] START gen={utterance_generation} state=recording rms={chunk_rms:.4f} pre_roll_ms={len(pre_roll)/self.audio.sample_rate*1000:.0f}")
                            buffer = pre_roll.copy()
                            utterance_start_offset = max(
                                0.0,
                                chunk_end - len(buffer) / self.audio.sample_rate,
                            )
                            pre_roll = np.array([], dtype=np.float32)
                            state = STATE_RECORDING
                            silence_counter = 0
                            last_partial_time = now
                    
                    # --- STATE: RECORDING ---
                    elif state == STATE_RECORDING:
                        buffer = np.concatenate([buffer, audio_chunk])
                        buf_dur = len(buffer) / self.audio.sample_rate
                        
                        if is_speech:
                            silence_counter = 0
                        else:
                            silence_counter += chunk_dur
                        
                        with lifecycle_lock:
                            latest_hypothesis = self._latest_hypothesis_text.get(
                                utterance_id, ""
                            )
                            changed_at = self._latest_hypothesis_changed_at.get(
                                utterance_id
                            )
                        endpoint = endpoint_policy.decide(
                            EndpointSignals(
                                duration=buf_dur,
                                silence=silence_counter,
                                text=latest_hypothesis,
                                language=getattr(config, "source_language", None),
                                seconds_since_text_change=(
                                    time.monotonic() - changed_at
                                    if changed_at is not None
                                    else None
                                ),
                            )
                        )
                        should_finalize = endpoint.should_finalize
                        reason = endpoint.reason
                        
                        if should_finalize:
                            uid = utterance_id
                            gen = utterance_generation
                            
                            # Remove pending partial for this uid
                            _invalidate_partials_for_uid(uid)
                            
                            # Mark finalizing
                            self._finalizing_uids.add(uid)
                            if uid in self._utt_lifecycle:
                                old_state = self._utt_lifecycle[uid]["state"]
                                self._utt_lifecycle[uid]["state"] = "finalizing"
                                log.info(f"Utterance[{uid}] state {old_state} -> finalizing")
                            
                            log.info(f"Utterance[{uid}] END dur={buf_dur:.1f}s silence={silence_counter:.1f}s reason={reason}")
                            self.runtime_metrics.record_endpoint(reason)
                            
                            self._seq_counter += 1
                            task = {
                                "type": "final",
                                "uid": uid,
                                "gen": gen,
                                "audio": buffer.copy(),
                                "prompt": self.last_final_text,
                                "created_at": time.time(),
                                "start_offset": utterance_start_offset,
                                "end_offset": audio_cursor,
                            }
                            log.info(f"Utterance[{uid}] FINAL queued priority=0")
                            asr_queue.put((0, self._seq_counter, task))  # priority 0 = FINAL
                            
                            utterance_id += 1
                            _reset_recording_state()
                        
                        # Partial: throttled, replaces pending if same uid
                        elif (
                            buf_dur >= 0.75
                            and (now - last_partial_time) >= PARTIAL_INTERVAL
                            and not asr_running.is_set()
                            and asr_queue.qsize() == 0
                        ):
                            gen = utterance_generation
                            uid = utterance_id
                            
                            # Replace any pending partial for this uid
                            _invalidate_partials_for_uid(uid)
                            
                            self._seq_counter += 1
                            seq = self._seq_counter
                            self._latest_partial_seq[uid] = seq
                            task = {
                                "type": "partial",
                                "uid": uid,
                                "gen": gen,
                                "seq": seq,
                                "audio": buffer.copy(),
                                "prompt": self.last_final_text,
                                "created_at": time.time(),
                            }
                            log.info(f"Utterance[{uid}] PARTIAL queued seq={seq} priority=1 gen={gen} dur={buf_dur:.1f}s")
                            asr_queue.put((1, seq, task))  # priority 1 = PARTIAL
                            
                            last_partial_time = now
                    
            except AudioCaptureError as ace:
                log.error(f"Audio device error: {ace}")
                self._failed = True
                try:
                    self.signals.audio_failed.emit(str(ace))
                except Exception:
                    log.critical("audio signal broken")
            except Exception as exc:
                log.exception("Pipeline loop error")
                self._failed = True
                try:
                    self.signals.pipeline_failed.emit(str(exc))
                except Exception:
                    log.critical("pipeline_failed signal broken")
            finally:
                self._cleanup_in_progress = True
                log.info("Pipeline loop ending — draining ASR queue...")
                
                # Force-finalize any recording in progress (carries CURRENT session_gen, still valid)
                if state == STATE_RECORDING and len(buffer) > 0 and len(buffer) >= int(self.audio.sample_rate * MIN_UTTERANCE_DUR):
                    uid = utterance_id
                    gen = utterance_generation
                    log.info(f"Utterance[{uid}] FORCE-finalize on stop dur={len(buffer)/self.audio.sample_rate:.1f}s session={session_gen}")
                    with lifecycle_lock:
                        self._latest_partial_seq.pop(uid, None)
                        self._finalizing_uids.add(uid)
                        entry = self._utt_lifecycle.get(uid)
                        if entry:
                            entry["state"] = "finalizing"
                    self._seq_counter += 1
                    task = {"type": "final", "uid": uid, "gen": gen,
                            "audio": buffer.copy(), "prompt": self.last_final_text,
                            "created_at": time.time(),
                            "start_offset": utterance_start_offset,
                            "end_offset": audio_cursor}
                    asr_queue.put((0, self._seq_counter, task))
                
                # Invalidate all pending partials
                with lifecycle_lock:
                    self._latest_partial_seq.clear()
                
                # Wait for all queued FINAL tasks to complete
                log.info("Waiting for ASR queue to drain...")
                remaining = asr_queue.qsize()
                if remaining > 0:
                    log.info(f"ASR queue has {remaining} pending tasks — waiting")
                
                # Submit sentinel at lowest priority (after all FINAL=0 tasks)
                asr_queue.put((99, self._seq_counter + 1, _SENTINEL))
                
                asr_thread.join(timeout=15)
                if asr_thread.is_alive():
                    log.error("ASR worker did not stop within timeout")
                else:
                    log.info("ASR worker stopped")
                
                self._accuracy_accepting = False
                self._stop_accuracy_worker()
                if self.live_translation_drafts is not None:
                    self.live_translation_drafts.shutdown(wait=False)
                translate_executor.shutdown(wait=False, cancel_futures=True)
                log.info("Translation executor shut down (cancelled pending tasks)")
                if self.session_recorder is not None:
                    self._recording_duration = self.session_recorder.stop()
                
                self._cleanup_in_progress = True
                cleanup_ok = not asr_thread.is_alive()
                
                if self._failed:
                    if cleanup_ok:
                        try:
                            self.signals.pipeline_cleanup_finished.emit(True, "cleanup completed")
                        except Exception:
                            log.critical("Failed to emit cleanup_finished")
                    else:
                        try:
                            self.signals.pipeline_cleanup_finished.emit(False, "ASR worker did not stop")
                        except Exception:
                            log.critical("Failed to emit cleanup_finished")
                
                self._cleanup_in_progress = False
                self.runtime_metrics.log_summary(log)
                log.info("Pipeline loop ended (ASR queue drained)")
        
        def _partial_safe_to_emit_v2(self, uid, gen):
            """Check if partial may emit: gen match, not finalizing, not finalized."""
            entry = self._utt_lifecycle.get(uid)
            if entry is None:
                log.debug(f"Utterance[{uid}] PARTIAL blocked: no lifecycle entry")
                return False
            if entry.get("generation") != gen:
                log.info(f"Utterance[{uid}] PARTIAL blocked: stale generation (have={gen}, lifecycle={entry.get('generation')})")
                return False
            state = entry.get("state", "unknown")
            if state in ("finalizing", "finalized"):
                log.debug(f"Utterance[{uid}] PARTIAL blocked: state={state}")
                return False
            return True
        
        def _process_partial_v3(self, audio_data, chunk_id, gen, seq, prompt="",
                                lifecycle_lock=None, session_gen=None):
            """Partial called from ASR worker. Thread-safe lifecycle check + generation guard."""
            with lifecycle_lock or self._lifecycle_lock:
                latest_seq = self._latest_partial_seq.get(chunk_id)
                entry = self._utt_lifecycle.get(chunk_id)
                allowed = (
                    latest_seq == seq
                    and entry is not None
                    and entry.get("generation") == gen
                    and entry.get("state") not in ("finalizing", "finalized")
                )
            
            if not allowed:
                if latest_seq != seq:
                    log.info(f"Utterance[{chunk_id}] PARTIAL discarded before ASR: superseded seq={seq} latest={latest_seq}")
                else:
                    log.info(f"Utterance[{chunk_id}] PARTIAL discarded before ASR: state={entry.get('state') if entry else 'no_entry'}")
                return
            
            try:
                inference_started = time.monotonic()
                partial_transcribe = getattr(self.transcriber, "transcribe_partial", None)
                text = (
                    partial_transcribe(audio_data, prompt=prompt)
                    if callable(partial_transcribe)
                    else self.transcriber.transcribe(audio_data, prompt=prompt)
                )
                
                with lifecycle_lock or self._lifecycle_lock:
                    latest_seq = self._latest_partial_seq.get(chunk_id)
                    entry = self._utt_lifecycle.get(chunk_id)
                    allowed2 = (
                        latest_seq == seq
                        and entry is not None
                        and entry.get("generation") == gen
                        and entry.get("state") not in ("finalizing", "finalized")
                    )
                
                if not allowed2:
                    log.info(f"Utterance[{chunk_id}] PARTIAL discarded after ASR: superseded seq={seq} latest={latest_seq} state={entry.get('state') if entry else '?'}")
                    return
                
                # Session check — stop may have been called
                if session_gen is not None and self._session_generation != session_gen:
                    log.info(f"Utterance[{chunk_id}] PARTIAL discarded: session changed")
                    return
                
                with lifecycle_lock or self._lifecycle_lock:
                    if self._latest_partial_seq.get(chunk_id) == seq:
                        self._latest_partial_seq.pop(chunk_id, None)
                
                if text:
                    update = self.streaming_transcript_state.observe(chunk_id, text)
                    if update is None:
                        return
                    with lifecycle_lock or self._lifecycle_lock:
                        previous_text = self._latest_hypothesis_text.get(chunk_id)
                        self._latest_hypothesis_text[chunk_id] = update.display_text
                        if previous_text != update.display_text:
                            self._latest_hypothesis_changed_at[chunk_id] = time.monotonic()
                    log.info(
                        "Utterance[%s] %s chars=%s stable=%s revision=%s seq=%s",
                        chunk_id,
                        update.phase.name,
                        len(update.display_text),
                        len(update.stable_text),
                        update.revision,
                        seq,
                    )
                    self.signals.update_caption_state.emit(
                        chunk_id,
                        update.display_text,
                        "",
                        update.phase.name,
                        update.revision,
                    )
                    self.runtime_metrics.record_asr(
                        chunk_id,
                        update.phase.name,
                        inference_seconds=time.monotonic() - inference_started,
                        audio_seconds=len(audio_data) / self.audio.sample_rate,
                    )
                    if self.live_translation_drafts is not None and update.stable_text:
                        self.live_translation_drafts.submit(
                            session_gen,
                            chunk_id,
                            update.display_text,
                            stable_text=update.stable_text,
                            source_revision=update.revision,
                        )
            except Exception:
                log.exception(f"Utterance[{chunk_id}] PARTIAL error")
        
        def _process_final_v3(
            self, audio_data, chunk_id, gen, prompt="",
            translate_executor=None, lifecycle_lock=None, session_gen=None,
            start_offset=None, end_offset=None,
            accuracy_executor=None,
        ):
            """Final with lifecycle tracking, thread-safe, session-aware."""
            with lifecycle_lock or self._lifecycle_lock:
                self._latest_partial_seq.pop(chunk_id, None)
                self._finalizing_uids.add(chunk_id)
                entry = self._utt_lifecycle.get(chunk_id)
                if entry:
                    entry["state"] = "finalizing"
            
            if session_gen is not None and self._session_generation != session_gen:
                log.warning(f"Utterance[{chunk_id}] FINAL discarded: session changed")
                return
            
            try:
                inference_started = time.monotonic()
                dur = len(audio_data) / self.audio.sample_rate
                rms = float(np.sqrt(np.mean(audio_data**2)))
                peak = float(np.max(np.abs(audio_data)))
                
                text = self.transcriber.transcribe(audio_data, prompt=prompt)
                
                if session_gen is not None and self._session_generation != session_gen:
                    log.warning(f"Utterance[{chunk_id}] FINAL discarded after ASR: session changed")
                    return
                
                with lifecycle_lock or self._lifecycle_lock:
                    if chunk_id in self._finalized_uids:
                        log.warning(f"Utterance[{chunk_id}] FINAL duplicate discarded")
                        return
                    self._finalizing_uids.discard(chunk_id)
                    self._finalized_uids.add(chunk_id)
                    entry = self._utt_lifecycle.get(chunk_id)
                    if entry:
                        entry["state"] = "finalized"
                
                if text:
                    log.info(
                        f"Utterance[{chunk_id}] FINAL chars={len(text)} "
                        f"dur={dur:.1f}s rms={rms:.4f} peak={peak:.3f}"
                    )
                else:
                    log.warning(f"Utterance[{chunk_id}] FINAL empty: dur={dur:.1f}s rms={rms:.4f} peak={peak:.3f} samples={len(audio_data)} reason=whisper_no_text")
                    self.streaming_transcript_state.discard(chunk_id)
                    self.signals.remove_text.emit(chunk_id)
                
                if text:
                    streaming_final = self.streaming_transcript_state.finalize(
                        chunk_id, text
                    )
                    if (
                        streaming_final is not None
                        and streaming_final.final_conflicted_with_stable
                    ):
                        log.info(
                            "Utterance[%s] final corrected the volatile agreement boundary",
                            chunk_id,
                        )
                    self.runtime_metrics.record_asr(
                        chunk_id,
                        "FINAL",
                        inference_seconds=time.monotonic() - inference_started,
                        audio_seconds=dur,
                        stable_conflict=bool(
                            streaming_final
                            and streaming_final.final_conflicted_with_stable
                        ),
                    )
                    with self._phrase_lock:
                        decision = self.phrase_composer.compose(chunk_id, text)
                        display_chunk_id = decision.chunk_id
                        display_text = decision.text
                        self.accuracy_coordinator.register(
                            decision,
                            text,
                            start_offset=start_offset,
                            end_offset=end_offset,
                        )
                    if self.live_translation_drafts is not None:
                        self.live_translation_drafts.finalize(decision.source_chunk_id)
                    self._latest_translation_revision[display_chunk_id] = decision.revision
                    if decision.merged and decision.source_chunk_id != display_chunk_id:
                        # A PARTIAL bubble may already exist for the new audio
                        # chunk.  Remove it because this final revises the
                        # previous sentence instead of starting a new one.
                        self.signals.remove_text.emit(decision.source_chunk_id)
                    # Keep a short rolling language context for names and
                    # continuity.  Character length also covers CJK scripts,
                    # where whitespace word counts are not meaningful.
                    if len(display_text) >= 4:
                        self.last_final_text = display_text[-240:]
                    trans_active = self.translation_engine.current_mode != "off"
                    if trans_active:
                        self.signals.update_caption_state.emit(
                            display_chunk_id,
                            display_text,
                            "…",
                            "FINAL",
                            decision.revision,
                        )
                        if hasattr(self, 'translation_adapter'):
                            self.translation_adapter.on_final_text(
                                display_text,
                                display_chunk_id,
                                start_offset=start_offset,
                                end_offset=end_offset,
                            )
                        elif translate_executor:
                            translate_executor.submit(
                                self._run_translation_safe,
                                display_text,
                                display_chunk_id,
                                session_gen,
                                decision.revision,
                            )
                    else:
                        self.signals.update_caption_state.emit(
                            display_chunk_id,
                            display_text,
                            "",
                            "FINAL",
                            decision.revision,
                        )
                        if hasattr(self, 'translation_adapter'):
                            # Translation-off mode still records the original
                            # transcript in the v2.4 session repository.
                            self.translation_adapter.on_final_text(
                                display_text,
                                display_chunk_id,
                                translate=False,
                                start_offset=start_offset,
                                end_offset=end_offset,
                            )
                    if self._accuracy_accepting:
                        self._queue_accuracy_refinement(
                            audio_data.copy(),
                            decision.source_chunk_id,
                            prompt,
                            session_gen,
                            translate_executor,
                        )
                
                with lifecycle_lock or self._lifecycle_lock:
                    while len(self._utt_lifecycle) > 50:
                        del self._utt_lifecycle[min(self._utt_lifecycle.keys())]
                    while len(self._finalized_uids) > 50:
                        self._finalized_uids.remove(min(self._finalized_uids))
                    while len(self._finalizing_uids) > 20:
                        self._finalizing_uids.remove(min(self._finalizing_uids))
            except Exception:
                log.exception(f"Utterance[{chunk_id}] FINAL error")
            finally:
                with lifecycle_lock or self._lifecycle_lock:
                    self._finalizing_uids.discard(chunk_id)
                    self._latest_hypothesis_text.pop(chunk_id, None)
                    self._latest_hypothesis_changed_at.pop(chunk_id, None)

        def _start_accuracy_worker(self, session_gen, translate_executor):
            """Arm optional refinement without loading anything yet.

            A single latest-only slot prevents slow second-pass recognition
            from building an unbounded queue and heating the Mac long after the
            spoken phrase has become irrelevant.
            """
            if self.accuracy_plan is None or not self._accuracy_model_path:
                self._accuracy_accepting = False
                return
            self._accuracy_accepting = True
            self._accuracy_pending = None
            self._accuracy_thread = None
            log.info("Pipeline: enhanced ASR armed; model loads after the first final phrase")

        def _stop_accuracy_worker(self):
            self._accuracy_accepting = False
            with self._accuracy_condition:
                self._accuracy_pending = None
                self._accuracy_condition.notify_all()

        def _queue_accuracy_refinement(
            self, audio_data, source_chunk_id, prompt, session_gen, translate_executor
        ):
            if not self._accuracy_accepting or self._session_generation != session_gen:
                return
            thread_to_start = None
            with self._accuracy_condition:
                replaced = self._accuracy_pending is not None
                self._accuracy_pending = (
                    audio_data,
                    source_chunk_id,
                    prompt,
                    session_gen,
                    translate_executor,
                )
                if self._accuracy_thread is None:
                    self._accuracy_thread = threading.Thread(
                        target=self._accuracy_worker_loop,
                        args=(session_gen, translate_executor),
                        daemon=True,
                        name="AccuracyLatestWorker",
                    )
                    thread_to_start = self._accuracy_thread
                self._accuracy_condition.notify()
            if thread_to_start is not None:
                thread_to_start.start()
            if replaced:
                log.info("Accuracy latest-only queue replaced an older pending phrase")

        def _accuracy_worker_loop(self, session_gen, translate_executor):
            try:
                from accuracy_transcriber import load_accuracy_transcriber

                self.accuracy_transcriber = load_accuracy_transcriber(
                    self.accuracy_plan,
                    self._accuracy_model_path,
                )
                if not self._accuracy_accepting or self._session_generation != session_gen:
                    return
                log.info(
                    "Pipeline: enhanced ASR ready in background (%s)",
                    self.accuracy_plan.model_id,
                )
                while self._accuracy_accepting and self._session_generation == session_gen:
                    with self._accuracy_condition:
                        while self._accuracy_pending is None and self._accuracy_accepting:
                            self._accuracy_condition.wait(timeout=0.75)
                        if not self._accuracy_accepting:
                            return
                        task = self._accuracy_pending
                        self._accuracy_pending = None
                    if task is not None:
                        elapsed = self._refine_final_text(*task) or 0.0
                        cooldown = self.performance_policy.accuracy_cooldown(
                            elapsed,
                            getattr(self.accuracy_plan, "model_id", ""),
                        )
                        if cooldown > 0:
                            log.info(
                                "Accuracy cooling for %.1fs profile=%s",
                                cooldown,
                                self.performance_policy.profile,
                            )
                            deadline = time.monotonic() + cooldown
                            with self._accuracy_condition:
                                while self._accuracy_accepting:
                                    remaining = deadline - time.monotonic()
                                    if remaining <= 0:
                                        break
                                    self._accuracy_condition.wait(
                                        timeout=min(remaining, 0.75)
                                    )
            except Exception:
                self._accuracy_accepting = False
                log.exception("Pipeline: background enhanced ASR unavailable")
            finally:
                with self._accuracy_condition:
                    self._accuracy_pending = None

        def _refine_final_text(
            self,
            audio_data,
            source_chunk_id,
            prompt,
            session_gen,
            translate_executor,
        ):
            """Run the larger local model and revise the existing subtitle row."""
            if not self._accuracy_accepting or self._session_generation != session_gen:
                return
            try:
                started = time.time()
                corrected = self.accuracy_transcriber.transcribe(audio_data, prompt=prompt)
                if not self._accuracy_accepting or self._session_generation != session_gen:
                    return
                with self._phrase_lock:
                    update = self.accuracy_coordinator.apply(
                        source_chunk_id,
                        corrected,
                        session_generation=session_gen,
                    )
                if update is None:
                    return time.time() - started
                elapsed = time.time() - started
                log.info(
                    "Accuracy[%s→%s] corrected in %.0fms revision=%s",
                    source_chunk_id,
                    update.display_chunk_id,
                    elapsed * 1000,
                    update.revision,
                )
                self._latest_translation_revision[update.display_chunk_id] = update.revision
                if len(update.text) >= 4:
                    self.last_final_text = update.text[-240:]
                trans_active = self.translation_engine.current_mode != "off"
                if trans_active:
                    self.signals.update_text.emit(update.display_chunk_id, update.text, "…")
                    if hasattr(self, "translation_adapter"):
                        self.translation_adapter.on_final_text(
                            update.text,
                            update.display_chunk_id,
                            start_offset=update.start_offset,
                            end_offset=update.end_offset,
                        )
                    elif translate_executor is not None and self._accuracy_accepting:
                        translate_executor.submit(
                            self._run_translation_safe,
                            update.text,
                            update.display_chunk_id,
                            session_gen,
                            update.revision,
                        )
                else:
                    self.signals.update_text.emit(update.display_chunk_id, update.text, "")
                    if hasattr(self, "translation_adapter"):
                        self.translation_adapter.on_final_text(
                            update.text,
                            update.display_chunk_id,
                            translate=False,
                            start_offset=update.start_offset,
                            end_offset=update.end_offset,
                        )
                return elapsed
            except Exception:
                # The standard result is already visible.  Refinement failure
                # is intentionally non-fatal and only disables this correction.
                log.exception("Accuracy[%s] refinement failed", source_chunk_id)
                return 0.0
        
        def _run_translation_safe(self, text, chunk_id, session_gen, revision=None):
            """Session-safe translation. Discards result if session changed."""
            log.info(f"Translation[{chunk_id}] requested session={session_gen}")
            try:
                if self._session_generation != session_gen:
                    log.info(f"Translation[{chunk_id}] discarded before translate: stale session current={self._session_generation}")
                    return
                
                translated = self.translation_engine.translate(text)
                
                if self._session_generation != session_gen:
                    log.info(f"Translation[{chunk_id}] discarded after translate: stale session current={self._session_generation}")
                    return
                if revision is not None and self._latest_translation_revision.get(chunk_id) != revision:
                    log.info(f"Translation[{chunk_id}] discarded: superseded revision={revision}")
                    return
                
                if translated:
                    log.info(f"Translation[{chunk_id}] completed session={session_gen}")
                    self.signals.update_text.emit(chunk_id, text, translated)
            except Exception:
                log.exception(f"Translation[{chunk_id}] error")
    
    signals = WorkerSignals()
    pipeline = Pipeline(signals)
    return pipeline, signals


# ---- Overlay launcher (MUST be called on main thread!) ----

_overlay_window = None
_overlay_pipeline = None


def _shutdown_active_pipeline():
    """Best-effort graceful cleanup for SIGINT and QApplication shutdown."""
    pipeline = _overlay_pipeline
    if pipeline is not None:
        try:
            pipeline.stop()
        except Exception:
            log.exception("Pipeline cleanup during application quit failed")

def create_and_show_overlay(pipeline, signals, start_pipeline=True, subtitle_style=None):
    """Create and show the overlay window (MUST be called from main thread).
    Set start_pipeline=False if caller needs to connect signals first."""
    global _overlay_window, _overlay_pipeline
    
    from enhanced_overlay_window import EnhancedOverlayWindow
    
    log.info("Creating overlay window on main thread...")
    if subtitle_style is None:
        from config import config
        subtitle_style = {
            "window_width": getattr(config, "window_width", 620),
            "window_height": getattr(config, "window_height", 220),
            "visible_subtitles": getattr(config, "visible_subtitles", 3),
            "history_limit": getattr(config, "subtitle_history_limit", 250),
            "original_font_size": getattr(config, "original_font_size", 20),
            "translation_font_size": getattr(config, "translation_font_size", 17),
            "original_color": getattr(config, "original_color", "#ffffff"),
            "translation_color": getattr(config, "translation_color", "#d99a69"),
            "window_opacity": getattr(config, "window_opacity", 0.94),
            "display_mode": getattr(config, "display_mode", "bilingual"),
            "ui_language": getattr(config, "ui_language", "en"),
        }
    window = EnhancedOverlayWindow(subtitle_style)
    window.show()
    log.info("Overlay window shown")
    
    # Connect signals
    signals.update_text.connect(window.update_text)
    signals.update_caption_state.connect(window.update_caption_state)
    signals.remove_text.connect(window.remove_text)
    signals.audio_status.connect(window.update_audio_status)
    window.stop_requested.connect(pipeline.stop)
    
    _overlay_window = window
    _overlay_pipeline = pipeline
    
    if start_pipeline:
        log.info("Starting pipeline...")
        pipeline.start()
        log.info("Translator launched successfully")
    
    return window


def _launch_overlay_session():
    """Called on main thread via QTimer for --overlay-only mode."""
    try:
        log.info("Launching overlay session...")
        pipeline, signals = create_pipeline()
        create_and_show_overlay(pipeline, signals, start_pipeline=True)
    except Exception:
        log.exception("Failed to launch overlay session")
        from PyQt6.QtWidgets import QMessageBox
        import traceback
        QMessageBox.critical(None, "Launch Failed",
                           f"Failed to launch translator:\n\n{traceback.format_exc()[:500]}")


if __name__ == "__main__":
    main()
