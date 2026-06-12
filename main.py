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
    
    class Pipeline(QObject):
        def __init__(self, signals_obj):
            super().__init__()
            self.signals = signals_obj
            self.running = True
            
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
            log.info("Pipeline: stopping...")
            self.running = False
            self.audio.stop()
            if hasattr(self, 'thread') and self.thread.is_alive():
                self.thread.join(timeout=3)
            log.info("Pipeline: stopped")
        
        def processing_loop(self):
            log.info("Pipeline: processing loop started (state-machine mode)")
            
            transcribe_executor = ThreadPoolExecutor(max_workers=1)
            translate_executor = ThreadPoolExecutor(max_workers=config.translation_threads)
            
            STATE_IDLE = 0
            STATE_RECORDING = 1
            
            state = STATE_IDLE
            buffer = np.array([], dtype=np.float32)
            pre_roll = np.array([], dtype=np.float32)
            silence_counter = 0
            utterance_id = 1
            utterance_generation = 0
            last_partial_time = 0.0
            
            # ASR task lifecycle — NEVER reset by recording state reset.
            # These track async tasks that may outlive the recording state.
            self._finalizing_uids = set()       # uids with final submitted (NOT yet completed)
            self._finalized_uids = set()        # uids with final completed
            self._partial_future = None         # current pending partial future
            self._partial_uid = 0               # uid of current pending partial
            
            SILENCE_DUR_SEC = config.silence_duration
            MIN_UTTERANCE_DUR = 1.0
            MAX_UTTERANCE_DUR = config.max_phrase_duration
            PARTIAL_INTERVAL = 1.2
            PRE_ROLL_MS = 0.4
            
            def _reset_recording_state():
                """Reset ONLY recording state. ASR lifecycle (finalizing/finalized) is separate."""
                nonlocal buffer, pre_roll, silence_counter, state, last_partial_time
                buffer = np.array([], dtype=np.float32)
                pre_roll = np.array([], dtype=np.float32)
                silence_counter = 0
                state = STATE_IDLE
                last_partial_time = 0.0
            
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
                            log.info(f"Utterance[{utterance_id}] START gen={utterance_generation} rms={chunk_rms:.4f} pre_roll_ms={len(pre_roll)/self.audio.sample_rate*1000:.0f}")
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
                            
                            # Cancel in-flight partial
                            pf = self._partial_future
                            if pf and not pf.done():
                                cancelled = pf.cancel()
                                log.info(f"Utterance[{uid}] PARTIAL cancel requested cancelled={cancelled}")
                            
                            # Mark finalizing BEFORE submitting — closes the gate for old partial
                            self._finalizing_uids.add(uid)
                            buf_copy = buffer.copy()
                            prompt = self.last_final_text
                            
                            log.info(f"Utterance[{uid}] END dur={buf_dur:.1f}s silence={silence_counter:.1f}s reason={reason}")
                            log.info(f"Utterance[{uid}] FINAL queued")
                            
                            transcribe_executor.submit(
                                self._process_final_v2, buf_copy, uid, gen, prompt, translate_executor
                            )
                            
                            utterance_id += 1
                            _reset_recording_state()
                        
                        # Partial: busy-skip + generation tracking
                        elif buf_dur >= 1.0 and (now - last_partial_time) >= PARTIAL_INTERVAL:
                            pf = self._partial_future
                            if pf and not pf.done():
                                log.debug(f"Utterance[{utterance_id}] PARTIAL skipped: worker busy")
                            else:
                                gen = utterance_generation
                                uid = utterance_id
                                log.debug(f"Utterance[{utterance_id}] PARTIAL requested dur={buf_dur:.1f}s gen={gen}")
                                self._partial_uid = uid
                                self._partial_future = transcribe_executor.submit(
                                    self._process_partial_v2, buffer.copy(), uid, gen, self.last_final_text
                                )
                            last_partial_time = now
                    
            except Exception:
                log.exception("Pipeline loop error")
            finally:
                transcribe_executor.shutdown(wait=False)
                translate_executor.shutdown(wait=False)
                log.info("Pipeline loop ended")
        
        def _partial_safe_to_emit_v2(self, uid, gen):
            """Check if partial may emit: not finalizing, not finalized."""
            if uid in self._finalizing_uids:
                log.debug(f"Utterance[{uid}] PARTIAL blocked: finalizing")
                return False
            if uid in self._finalized_uids:
                log.debug(f"Utterance[{uid}] PARTIAL blocked: finalized")
                return False
            return True
        
        def _process_partial_v2(self, audio_data, chunk_id, gen, prompt=""):
            """Partial with two-phase guard — before AND after ASR."""
            t0 = time.time()
            try:
                if not self._partial_safe_to_emit_v2(chunk_id, gen):
                    log.debug(f"Utterance[{chunk_id}] PARTIAL discarded: state changed before ASR gen={gen}")
                    return
                
                text = self.transcriber.transcribe(audio_data, prompt=prompt)
                
                # Re-check — may have been overtaken by final during ASR
                if not self._partial_safe_to_emit_v2(chunk_id, gen):
                    latency = time.time() - t0
                    log.info(f"Utterance[{chunk_id}] PARTIAL result discarded: stale gen={gen} latency={latency:.2f}s")
                    return
                
                if text:
                    latency = time.time() - t0
                    log.info(f"Utterance[{chunk_id}] PARTIAL text=\"{text}\" latency={latency:.2f}s")
                    self.signals.update_text.emit(chunk_id, text, "")
            except Exception:
                log.exception(f"Utterance[{chunk_id}] PARTIAL error")
        
        def _process_final_v2(self, audio_data, chunk_id, gen, prompt="", translate_executor=None):
            """Final with lifecycle tracking in sets (not single uid)."""
            t0 = time.time()
            try:
                log.info(f"Utterance[{chunk_id}] FINAL started")
                
                dur = len(audio_data) / self.audio.sample_rate
                rms = float(np.sqrt(np.mean(audio_data**2)))
                peak = float(np.max(np.abs(audio_data)))
                
                text = self.transcriber.transcribe(audio_data, prompt=prompt)
                t1 = time.time()
                latency = t1 - t0
                
                # Discard if already finalized (duplicate)
                if chunk_id in self._finalized_uids:
                    log.warning(f"Utterance[{chunk_id}] FINAL duplicate discarded")
                    return
                
                # Move from finalizing → finalized
                self._finalizing_uids.discard(chunk_id)
                self._finalized_uids.add(chunk_id)
                # Prune old
                while len(self._finalized_uids) > 20:
                    self._finalized_uids.remove(min(self._finalized_uids))
                while len(self._finalizing_uids) > 10:
                    self._finalizing_uids.remove(min(self._finalizing_uids))
                
                if text:
                    log.info(f"Utterance[{chunk_id}] FINAL text=\"{text}\" dur={dur:.1f}s rms={rms:.4f} peak={peak:.3f} latency={latency:.2f}s")
                else:
                    log.info(f"Utterance[{chunk_id}] FINAL (empty) dur={dur:.1f}s rms={rms:.4f} peak={peak:.3f} latency={latency:.2f}s")
                
                if text:
                    if len(text.split()) > 2:
                        self.last_final_text = text
                    
                    trans_active = self.translation_engine.current_mode != "off"
                    
                    if trans_active:
                        self.signals.update_text.emit(chunk_id, text, "(translating...)")
                        if translate_executor:
                            translate_executor.submit(self._run_translation, text, chunk_id)
                    else:
                        self.signals.update_text.emit(chunk_id, text, "")
            except Exception:
                log.exception(f"Utterance[{chunk_id}] FINAL error")
            finally:
                # Ensure cleanup even on error
                self._finalizing_uids.discard(chunk_id)
    
    signals = WorkerSignals()
    pipeline = Pipeline(signals)
    return pipeline, signals


# ---- Overlay launcher (MUST be called on main thread!) ----

_overlay_window = None
_overlay_pipeline = None

def create_and_show_overlay(pipeline, signals):
    """Create and show the overlay window (MUST be called from main thread)."""
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
    
    log.info("Starting pipeline...")
    pipeline.start()
    log.info("Translator launched successfully")
    
    return window


def _launch_overlay_session():
    """Called on main thread via QTimer for --overlay-only mode."""
    try:
        log.info("Launching overlay session...")
        pipeline, signals = create_pipeline()
        create_and_show_overlay(pipeline, signals)
    except Exception:
        log.exception("Failed to launch overlay session")
        from PyQt6.QtWidgets import QMessageBox
        import traceback
        QMessageBox.critical(None, "Launch Failed",
                           f"Failed to launch translator:\n\n{traceback.format_exc()[:500]}")


if __name__ == "__main__":
    main()
