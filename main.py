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
    
    log.info(f"App started with args: {args}")
    
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
            log.info("Pipeline: processing loop started")
            
            transcribe_executor = ThreadPoolExecutor(max_workers=1)
            translate_executor = ThreadPoolExecutor(max_workers=config.translation_threads)
            
            buffer = np.array([], dtype=np.float32)
            chunk_id = 1
            last_update_time = time.time()
            self.last_final_text = ""
            
            try:
                audio_gen = self.audio.generator()
                for audio_chunk in audio_gen:
                    if not self.running:
                        break
                    
                    # Emit audio status — current volume level
                    rms_now = np.sqrt(np.mean(audio_chunk**2))
                    status = "🎤 Listening" if rms_now > self.audio.silence_threshold else "🔇 Silent"
                    self.signals.audio_status.emit(status, min(float(rms_now) * 50, 1.0))
                    
                    buffer = np.concatenate([buffer, audio_chunk])
                    now = time.time()
                    buffer_duration = len(buffer) / self.audio.sample_rate
                    
                    is_silence = False
                    min_silence_dur = config.silence_duration
                    if buffer_duration > min_silence_dur:
                        tail = buffer[-int(self.audio.sample_rate * min_silence_dur):]
                        rms = np.sqrt(np.mean(tail**2))
                        if rms < self.audio.silence_threshold:
                            is_silence = True
                    
                    standard_cut = (is_silence and buffer_duration > 2.0)
                    soft_cut = (buffer_duration > 6.0 and is_silence)
                    hard_cut = (buffer_duration > self.audio.max_phrase_duration)
                    
                    if (standard_cut or soft_cut or hard_cut) and buffer_duration > 0.5:
                        fb = buffer.copy()
                        cid = chunk_id
                        prompt = self.last_final_text
                        overall_rms = np.sqrt(np.mean(fb**2))
                        if overall_rms >= self.audio.silence_threshold:
                            transcribe_executor.submit(self._process_final, fb, cid, prompt, translate_executor)
                        buffer = np.array([], dtype=np.float32)
                        chunk_id += 1
                        last_update_time = now
                    elif now - last_update_time > config.update_interval and buffer_duration > 0.5:
                        pb = buffer.copy()
                        prompt = self.last_final_text
                        rms = np.sqrt(np.mean(pb**2))
                        if rms > self.audio.silence_threshold:
                            transcribe_executor.submit(self._process_partial, pb, chunk_id, prompt)
                        last_update_time = now
            except Exception as e:
                log.exception("Pipeline loop error")
            finally:
                transcribe_executor.shutdown(wait=False)
                translate_executor.shutdown(wait=False)
                log.info("Pipeline loop ended")
        
        def _process_partial(self, audio_data, chunk_id, prompt=""):
            try:
                text = self.transcriber.transcribe(audio_data, prompt=prompt)
                if text:
                    self.signals.update_text.emit(chunk_id, text, "")
            except Exception:
                pass
        
        def _process_final(self, audio_data, chunk_id, prompt="", translate_executor=None):
            try:
                text = self.transcriber.transcribe(audio_data, prompt=prompt)
                if text:
                    if len(text.split()) > 2:
                        self.last_final_text = text
                    self.signals.update_text.emit(chunk_id, text, "(translating...)")
                    if translate_executor:
                        translate_executor.submit(self._run_translation, text, chunk_id)
            except Exception:
                log.exception("Final chunk error")
        
        def _run_translation(self, text, chunk_id):
            try:
                translated = self.translation_engine.translate(text)
                # Don't emit empty translation (off mode / original_only) — leave original alone
                if translated:
                    self.signals.update_text.emit(chunk_id, text, translated)
            except Exception:
                log.exception(f"Translation error for chunk {chunk_id}")
                # Still emit so user sees original text
                self.signals.update_text.emit(chunk_id, text, "[Translation Failed]")
    
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
