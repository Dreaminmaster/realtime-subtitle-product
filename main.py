#!/usr/bin/env python3
"""
Realtime Subtitle - Main Entry Point

macOS real-time speech recognition + translation with floating subtitle overlay.

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

# Fix library conflicts
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Setup app-level logging
LOG_DIR = os.path.join(os.path.expanduser("~"), "Library", "Logs", "RealtimeSubtitle")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "app.log")),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("RealtimeSubtitle")

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
        log.info(f"Realtime Subtitle v{BUILD_VERSION} (commit {BUILD_COMMIT} built {BUILD_TIME})")
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
    
    signal.signal(signal.SIGINT, lambda sig, frame: os._exit(0))
    
    # First-launch permission guide (GUI)
    if not args.no_permission_check:
        try:
            from permission_guide import create_permission_guide
            guide = create_permission_guide()
            if guide:
                guide.exec()
        except Exception as e:
            log.warning(f"Permission guide error: {e}")
    
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
    
    log.info("Creating pipeline (non-UI)...")
    
    class WorkerSignals(QObject):
        update_text = pyqtSignal(int, str, str)
        audio_status = pyqtSignal(str, float)  # (status_text, volume_level 0.0-1.0)
        pipeline_failed = pyqtSignal(str)       # error message when pipeline crashes
        pipeline_cleanup_finished = pyqtSignal(bool, str) # (success, message)
        pipeline_started = pyqtSignal()          # pipeline loop started successfully
    
    class Pipeline(QObject):
        def __init__(self, signals_obj):
            super().__init__()
            self.signals = signals_obj
            self.running = True
            # Utterance lifecycle tracking — generation-guarded, pruned, thread-safe
            import threading as _threading_mod
            self._lifecycle_lock = _threading_mod.RLock()
            self._utt_lifecycle = {}  # uid -> {"generation": int, "state": str}
            self._finalizing_uids = set()
            self._finalized_uids = set()
            self._latest_partial_seq = {}  # uid -> latest seq
            self._session_generation = 0    # incremented each Launch, stops stale tasks
            self.last_final_text = ""        # context prompt across utterances
            self._cleanup_in_progress = False
            self._failed = False
            
            from audio_capture import AudioCapture
            from transcriber import Transcriber
            
            log.info("Pipeline: initializing audio capture...")
            config.print_config()
            
            self.audio = AudioCapture(
                device_index=config.device_index,
                sample_rate=config.sample_rate,
                silence_threshold=config.silence_threshold,
                silence_duration=config.silence_duration,
                chunk_duration=config.chunk_duration,
                max_phrase_duration=config.max_phrase_duration,
                streaming_mode=config.streaming_mode,
                streaming_interval=config.streaming_interval,
                streaming_step_size=config.streaming_step_size,
                streaming_overlap=config.streaming_overlap
            )
            log.info("Pipeline: audio capture initialized")
            
            if config.asr_backend == "funasr":
                model_size = config.funasr_model
            else:
                model_size = config.whisper_model
            
            log.info(f"Pipeline: initializing transcriber ({config.asr_backend}/{model_size})...")
            self.transcriber = Transcriber(
                backend=config.asr_backend,
                model_size=model_size,
                device=config.whisper_device,
                compute_type=config.whisper_compute_type,
                language=config.source_language
            )
            log.info("Pipeline: transcriber initialized")
            
            from translation_engine import translation_engine
            self.translation_engine = translation_engine
            trans_mode = getattr(config, 'translation_mode', 'off')
            self.translation_engine.set_mode(
                trans_mode,
                base_url=config.api_base_url,
                api_key=config.api_key or "",
                model=config.model
            )
            log.info(f"Pipeline: translation engine ({trans_mode}) initialized")
            
            log.info("Pipeline: warming up transcriber...")
            self.transcriber.warmup()
            log.info("Pipeline: warmup complete")
        
        def start(self):
            self.thread = threading.Thread(target=self.processing_loop, daemon=True, name="PipelineLoop")
            self.thread.start()
        
        def stop(self):
            log.info("Stop requested")
            self.running = False
            self.audio.stop()
            log.info("Audio capture stopped")
            if hasattr(self, 'thread') and self.thread.is_alive():
                self.thread.join(timeout=15)
                if self.thread.is_alive():
                    log.error("Pipeline loop did not stop within timeout")
                    return False
            # Session invalidation ONLY after clean shutdown
            self._session_generation += 1
            log.info("Pipeline stopped — session invalidated")
            return True
        
        def processing_loop(self):
            log.info("Pipeline: processing loop started (state-machine mode)")
            
            translate_executor = ThreadPoolExecutor(max_workers=config.translation_threads)
            lifecycle_lock = self._lifecycle_lock
            session_gen = self._session_generation  # snapshot for this session
            
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
                        self._process_final_v3(audio, uid, gen, prompt, translate_executor, lifecycle_lock, session_gen)
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
            
            # Signal pipeline started — everything is ready
            try:
                self.signals.pipeline_started.emit()
            except Exception:
                log.critical("pipeline_started signal broken")
            
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
            
            SILENCE_DUR_SEC = config.silence_duration
            MIN_UTTERANCE_DUR = 1.0
            MAX_UTTERANCE_DUR = config.max_phrase_duration
            PARTIAL_INTERVAL = 1.2
            PRE_ROLL_MS = 0.4
            
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
                for audio_chunk in audio_gen:
                    if not self.running:
                        break
                    
                    chunk_rms = float(np.sqrt(np.mean(audio_chunk**2)))
                    is_speech = chunk_rms > self.audio.silence_threshold
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
                            log.info(f"Utterance[{utterance_id}] START gen={utterance_generation} state=recording rms={chunk_rms:.4f} pre_roll_ms={len(pre_roll)/self.audio.sample_rate*1000:.0f}")
                            buffer = pre_roll.copy()
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
                        
                        should_finalize = False
                        reason = ""
                        
                        if buf_dur >= MAX_UTTERANCE_DUR:
                            should_finalize = True
                            reason = "max_dur"
                        elif silence_counter >= SILENCE_DUR_SEC and buf_dur >= MIN_UTTERANCE_DUR:
                            should_finalize = True
                            reason = "silence"
                        
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
                            
                            self._seq_counter += 1
                            task = {
                                "type": "final",
                                "uid": uid,
                                "gen": gen,
                                "audio": buffer.copy(),
                                "prompt": self.last_final_text,
                                "created_at": time.time(),
                            }
                            log.info(f"Utterance[{uid}] FINAL queued priority=0")
                            asr_queue.put((0, self._seq_counter, task))  # priority 0 = FINAL
                            
                            utterance_id += 1
                            _reset_recording_state()
                        
                        # Partial: throttled, replaces pending if same uid
                        elif buf_dur >= 1.0 and (now - last_partial_time) >= PARTIAL_INTERVAL:
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
                            "created_at": time.time()}
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
                
                translate_executor.shutdown(wait=False)
                
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
                text = self.transcriber.transcribe(audio_data, prompt=prompt)
                
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
                    log.info(f"Utterance[{chunk_id}] PARTIAL text=\"{text}\" seq={seq}")
                    self.signals.update_text.emit(chunk_id, text, "")
            except Exception:
                log.exception(f"Utterance[{chunk_id}] PARTIAL error")
        
        def _process_final_v3(self, audio_data, chunk_id, gen, prompt="",
                              translate_executor=None, lifecycle_lock=None, session_gen=None):
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
                    log.info(f"Utterance[{chunk_id}] FINAL text=\"{text}\" dur={dur:.1f}s rms={rms:.4f} peak={peak:.3f}")
                
                if text:
                    if len(text.split()) > 2:
                        self.last_final_text = text
                    trans_active = self.translation_engine.current_mode != "off"
                    if trans_active:
                        self.signals.update_text.emit(chunk_id, text, "(translating...)")
                        if translate_executor:
                            translate_executor.submit(self._run_translation_safe, text, chunk_id, session_gen)
                    else:
                        self.signals.update_text.emit(chunk_id, text, "")
                
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
        
        def _run_translation_safe(self, text, chunk_id, session_gen):
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

def create_and_show_overlay(pipeline, signals, start_pipeline=True):
    """Create and show the overlay window (MUST be called from main thread).
    Set start_pipeline=False if caller needs to connect signals first."""
    global _overlay_window, _overlay_pipeline
    
    from enhanced_overlay_window import EnhancedOverlayWindow
    
    log.info("Creating overlay window on main thread...")
    window = EnhancedOverlayWindow()
    window.show()
    log.info("Overlay window shown")
    
    # Connect signals
    signals.update_text.connect(window.update_text)
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
