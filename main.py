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

# Fix library conflicts
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


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
        for m in downloaded:
            print(f"    - {m['name']}: {m['installed_size_mb']} MB")
        disk = model_manager.get_disk_usage()
        print(f"  Total disk: {disk['total_mb']} MB across {disk['model_count']} models")
    except Exception as e:
        print(f"  Model manager check FAILED: {e}")
    
    print("\n--- Python Environment ---")
    print(f"  Python: {sys.version}")
    print(f"  Executable: {sys.executable}")
    print(f"  Platform: {sys.platform}")
    print(f"  Prefix: {sys.prefix}")


def main():
    args = parse_args()
    
    # Handle diagnostics mode — no GUI imports needed
    if args.diagnostics:
        run_diagnostics()
        return
    
    # Lazy import PyQt6 only when GUI is needed
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer
    except ImportError:
        print("ERROR: PyQt6 is required for GUI mode.")
        print("Install it with: pip install PyQt6>=6.5")
        print("")
        print("Or run diagnostics without GUI:")
        print("  python3 main.py --diagnostics")
        sys.exit(1)
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    # Set up signal handler
    signal.signal(signal.SIGINT, lambda sig, frame: os._exit(0))
    
    # First-launch permission guide (GUI)
    if not args.no_permission_check:
        try:
            from permission_guide import PermissionGuide
            if PermissionGuide.should_show():
                guide = PermissionGuide()
                guide.exec()
        except Exception as e:
            print(f"[Main] Permission guide error: {e}")
    
    # Start diagnostics logging
    from diagnostics import logger, diagnostics
    diagnostics._check_platform()
    
    # Launch dashboard or overlay
    if args.overlay_only:
        from main import start_overlay_session
        win, pipe = start_overlay_session()
    else:
        from dashboard import Dashboard
        dash = Dashboard()
        dash.show()
    
    # Event loop with signal handling
    timer = QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)
    
    try:
        sys.exit(app.exec())
    except SystemExit:
        pass


# Backward-compatible overlay session starter
def start_overlay_session():
    """Start overlay and pipeline (imported by dashboard and main)"""
    from PyQt6.QtCore import QObject, pyqtSignal
    from enhanced_overlay_window import EnhancedOverlayWindow
    from config import config
    import threading
    import time
    import numpy as np
    from concurrent.futures import ThreadPoolExecutor
    
    class WorkerSignals(QObject):
        update_text = pyqtSignal(int, str, str)
    
    class Pipeline(QObject):
        def __init__(self):
            super().__init__()
            self.signals = WorkerSignals()
            self.running = True
            
            from audio_capture import AudioCapture
            from transcriber import Transcriber
            
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
            
            # Determine model size
            if config.asr_backend == "funasr":
                model_size = config.funasr_model
            else:
                model_size = config.whisper_model
            
            self.transcriber = Transcriber(
                backend=config.asr_backend,
                model_size=model_size,
                device=config.whisper_device,
                compute_type=config.whisper_compute_type,
                language=config.source_language
            )
            
            # Initialize translation engine
            from translation_engine import translation_engine
            self.translation_engine = translation_engine
            
            # Set translation mode from config
            trans_mode = getattr(config, 'translation_mode', 'online')
            self.translation_engine.set_mode(
                trans_mode,
                base_url=config.api_base_url,
                api_key=config.api_key,
                model=config.model
            )
            
            # Warmup
            self.transcriber.warmup()
        
        def start(self):
            self.thread = threading.Thread(target=self.processing_loop, daemon=True)
            self.thread.start()
        
        def stop(self):
            self.running = False
            self.audio.stop()
            if self.thread.is_alive():
                self.thread.join(timeout=2)
        
        def processing_loop(self):
            logger.info("Pipeline processing loop started")
            
            is_mlx = (config.asr_backend == "mlx")
            
            if config.asr_backend == "funasr":
                model_size = config.funasr_model
            else:
                model_size = config.whisper_model
            
            transcribe_executor = ThreadPoolExecutor(max_workers=1)
            translate_executor = ThreadPoolExecutor(max_workers=config.translation_threads)
            
            buffer = np.array([], dtype=np.float32)
            chunk_id = 1
            last_update_time = time.time()
            self.last_final_text = ""
            
            audio_gen = self.audio.generator()
            
            try:
                for audio_chunk in audio_gen:
                    if not self.running:
                        break
                    
                    buffer = np.concatenate([buffer, audio_chunk])
                    now = time.time()
                    buffer_duration = len(buffer) / self.audio.sample_rate
                    
                    # Silence detection
                    is_silence = False
                    min_silence_dur = config.silence_duration
                    
                    if buffer_duration > min_silence_dur:
                        tail = buffer[-int(self.audio.sample_rate * min_silence_dur):]
                        rms = np.sqrt(np.mean(tail**2))
                        if rms < self.audio.silence_threshold:
                            is_silence = True
                    
                    standard_cut = (is_silence and buffer_duration > 2.0)
                    soft_limit_cut = False
                    if buffer_duration > 6.0:
                        short_tail = int(self.audio.sample_rate * 0.4)
                        if len(buffer) > short_tail:
                            t_rms = np.sqrt(np.mean(buffer[-short_tail:]**2))
                            if t_rms < self.audio.silence_threshold:
                                soft_limit_cut = True
                    
                    hard_limit_cut = (buffer_duration > self.audio.max_phrase_duration)
                    should_finalize = standard_cut or soft_limit_cut or hard_limit_cut
                    
                    if should_finalize and buffer_duration > 0.5:
                        final_buffer = buffer.copy()
                        cid = chunk_id
                        prompt = self.last_final_text
                        
                        overall_rms = np.sqrt(np.mean(final_buffer**2))
                        if overall_rms >= self.audio.silence_threshold:
                            transcribe_executor.submit(
                                self._process_final_chunk,
                                final_buffer, cid, prompt, translate_executor
                            )
                        
                        buffer = np.array([], dtype=np.float32)
                        chunk_id += 1
                        last_update_time = now
                    
                    elif now - last_update_time > config.update_interval and buffer_duration > 0.5:
                        partial_buffer = buffer.copy()
                        prompt = self.last_final_text
                        
                        rms = np.sqrt(np.mean(partial_buffer**2))
                        if rms > self.audio.silence_threshold:
                            transcribe_executor.submit(
                                self._process_partial_chunk,
                                partial_buffer, chunk_id, prompt
                            )
                        
                        last_update_time = now
                        
            except Exception as e:
                logger.error(f"Pipeline error: {e}")
            finally:
                transcribe_executor.shutdown(wait=False)
                translate_executor.shutdown(wait=False)
        
        def _process_partial_chunk(self, audio_data, chunk_id, prompt=""):
            try:
                text = self.transcriber.transcribe(audio_data, prompt=prompt)
                if text:
                    self.signals.update_text.emit(chunk_id, text, "")
            except Exception:
                pass
        
        def _process_final_chunk(self, audio_data, chunk_id, prompt="", translate_executor=None):
            try:
                text = self.transcriber.transcribe(audio_data, prompt=prompt)
                if text:
                    if len(text.split()) > 2:
                        self.last_final_text = text
                    
                    self.signals.update_text.emit(chunk_id, text, "(translating...)")
                    
                    if translate_executor:
                        translate_executor.submit(self._run_translation, text, chunk_id)
            except Exception as e:
                logger.error(f"Final chunk error: {e}")
        
        def _run_translation(self, text, chunk_id):
            try:
                translated = self.translation_engine.translate(text)
                self.signals.update_text.emit(chunk_id, text, translated)
            except Exception as e:
                self.signals.update_text.emit(chunk_id, text, "[Translation Failed]")
    
    # Create overlay window
    window = EnhancedOverlayWindow()
    window.show()
    
    pipeline = Pipeline()
    pipeline.signals.update_text.connect(window.update_text)
    pipeline.start()
    
    return window, pipeline


if __name__ == "__main__":
    main()
