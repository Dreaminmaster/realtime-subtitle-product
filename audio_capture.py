import sounddevice as sd
import numpy as np
import queue
import threading
import time


class AudioCaptureError(RuntimeError):
    """Structured audio device error with stage and device info."""
    def __init__(self, message, *, stage="open", requested_device=None,
                 fallback_device=None, fallback_attempted=False):
        super().__init__(message)
        self.stage = stage                 # "permission", "open" or "read"
        self.requested_device = requested_device
        self.fallback_device = fallback_device
        self.fallback_attempted = fallback_attempted


class AudioCapture:
    def __init__(self, device_index=None, sample_rate=16000, chunk_duration=0.1, 
                 silence_threshold=0.01, silence_duration=1.0, max_phrase_duration=5.0,
                 streaming_mode=False, streaming_interval=1.5, streaming_step_size=0.2, streaming_overlap=0.3):
        """
        Captures audio and yields segments containing speech.
        
        Args:
            device_index: Index of input device (None for default).
            sample_rate: Audio sample rate (default 16000 for Whisper).
            chunk_duration: Duration of each small read in seconds.
            silence_threshold: RMS amplitude threshold for "silence".
            silence_duration: How many seconds of silence triggers a segment cut.
            max_phrase_duration: Force processing after this many seconds even without silence.
            streaming_mode: If True, emit audio at fixed intervals (no VAD).
            streaming_interval: Seconds between audio emissions in streaming mode.
            streaming_overlap: Seconds of overlap between chunks in streaming mode.
        """
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.block_size = int(sample_rate * chunk_duration)
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.max_phrase_duration = max_phrase_duration
        
        # Streaming mode settings
        self.streaming_mode = streaming_mode
        self.streaming_interval = streaming_interval
        self.streaming_mode = streaming_mode
        self.streaming_interval = streaming_interval
        self.streaming_step_size = streaming_step_size
        self.streaming_overlap = streaming_overlap
        
        self.audio_queue = queue.Queue()
        self.running = False
        self.thread = None
        self._stream_lock = threading.RLock()
        self._active_stream = None
        self._stop_event = threading.Event()

    def prepare_start(self):
        """Arm a new capture session before its worker thread is started."""
        self._stop_event.clear()
        self.running = True

    def _set_active_stream(self, stream):
        with self._stream_lock:
            self._active_stream = stream

    def _clear_active_stream(self, stream):
        with self._stream_lock:
            if self._active_stream is stream:
                self._active_stream = None

    def _interrupt_active_stream(self):
        """Release the active PortAudio stream during Stop/quit."""
        with self._stream_lock:
            stream = self._active_stream
            self._active_stream = None
        if stream is None:
            return
        try:
            stream.abort(ignore_errors=True)
        except Exception:
            pass
        try:
            stream.close(ignore_errors=True)
        except TypeError:
            try:
                stream.close()
            except Exception:
                pass
        except Exception:
            pass

    def _iter_stream_chunks(self, *, device, block_size, overflow_label="Audio overflow"):
        """Yield callback-delivered audio without blocking in PortAudio ReadStream.

        PortAudio's blocking ``read()`` cannot reliably be interrupted from a
        second thread on macOS.  A callback-backed bounded queue keeps the
        Python worker cancellable even when no audio is arriving.
        """
        chunk_queue = queue.Queue(maxsize=20)

        def callback(indata, frames, time_info, status):
            del frames, time_info
            if self._stop_event.is_set() or not self.running:
                raise sd.CallbackStop
            if status:
                print(f"{overflow_label}: {status}")

            chunk = indata.copy().reshape(-1)
            try:
                chunk_queue.put_nowait(chunk)
            except queue.Full:
                # Keep latency bounded: discard the oldest chunk and retain
                # the newest audio rather than blocking PortAudio's callback.
                try:
                    chunk_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    chunk_queue.put_nowait(chunk)
                except queue.Full:
                    pass

        stream = sd.InputStream(
            device=device,
            channels=1,
            samplerate=self.sample_rate,
            blocksize=block_size,
            dtype='float32',
            callback=callback,
        )
        self._set_active_stream(stream)
        try:
            with stream:
                while self.running and not self._stop_event.is_set():
                    try:
                        yield chunk_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
        finally:
            self._clear_active_stream(stream)

    def _ensure_microphone_permission(self):
        """Fail fast on denied macOS permission and keep first prompt cancellable."""
        from permission_guide import (
            microphone_permission_state,
            request_microphone_access,
            screen_session_is_locked,
        )

        if screen_session_is_locked():
            raise AudioCaptureError(
                "The Mac is locked, so the microphone is unavailable. Unlock "
                "the Mac and launch the translator again.",
                stage="open",
                requested_device=str(self.device_index),
            )

        state = microphone_permission_state()
        if state in {"denied", "restricted"}:
            raise AudioCaptureError(
                "Microphone access is denied. Enable Realtime Subtitle in "
                "System Settings > Privacy & Security > Microphone.",
                stage="permission",
                requested_device=str(self.device_index),
            )
        if state != "not_determined":
            return True

        was_running = self.running
        granted = request_microphone_access(
            timeout=30.0,
            cancelled=(lambda: not self.running) if was_running else None,
        )
        if granted is True:
            return True
        if granted is None and was_running and not self.running:
            return False
        if granted is False:
            detail = "Microphone access was not granted."
        else:
            detail = "Timed out waiting for microphone permission."
        raise AudioCaptureError(
            f"{detail} Enable Realtime Subtitle in System Settings > "
            "Privacy & Security > Microphone.",
            stage="permission",
            requested_device=str(self.device_index),
        )

    def start(self):
        self.prepare_start()
        self.thread = threading.Thread(target=self._record_loop, daemon=True)
        self.thread.start()
        
        # Log audio device info
        print("[AudioCapture] Starting...")
        print(f"  Sample Rate: {self.sample_rate} Hz")
        print(f"  Silence Threshold: {self.silence_threshold}")
        print(f"  Silence Duration: {self.silence_duration}s")
        
        # Get device info
        if self.device_index is None:
            default_device = sd.query_devices(kind='input')
            print(f"  Using DEFAULT input device:")
            print(f"    Name: {default_device['name']}")
            print(f"    Index: {default_device['index']}")
            print(f"    Channels: {default_device['max_input_channels']}")
        else:
            device_info = sd.query_devices(self.device_index)
            print(f"  Using device index {self.device_index}:")
            print(f"    Name: {device_info['name']}")
            print(f"    Channels: {device_info['max_input_channels']}")
        
        print("\n[AudioCapture] Available input devices:")
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                marker = " <-- SELECTED" if (self.device_index == i or (self.device_index is None and d == sd.query_devices(kind='input'))) else ""
                print(f"    [{i}] {d['name']} ({d['max_input_channels']} ch){marker}")

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=0.5)
            if self.thread.is_alive():
                # Emergency fallback only. Callback streams normally leave
                # cooperatively within the 100 ms queue polling interval.
                self._interrupt_active_stream()
                self.thread.join(timeout=1.5)
        print("Audio capture stopped.")

    def generator(self):
        """Yields small raw audio chunks for external accumulation logic."""
        if self._stop_event.is_set():
            return
        if not self.running:
            # Preserve the convenient standalone ``for chunk in generator()``
            # API while Pipeline.start() arms production sessions explicitly.
            self.prepare_start()
        if not self._ensure_microphone_permission():
            return

        # Resolve device index at stream open time
        device = self.device_index
        
        # Use configured step size
        block_size = int(self.sample_rate * self.streaming_step_size)
        
        # Resolve default device if using auto
        if device is None or isinstance(device, str) and device == "auto":
            try:
                default_dev = sd.query_devices(kind='input')
                device = default_dev['index']
                print(f"[Audio] Resolved default input: [{device}] {default_dev['name']}")
            except Exception:
                device = None
        
        # Detect Voice Isolation / aggregate mode
        try:
            dev_info = sd.query_devices(device) if device is not None else sd.query_devices(kind='input')
            dev_name = dev_info.get('name', '')
            if 'aggregate' in dev_name.lower() or 'isolation' in dev_name.lower():
                import logging
                log = logging.getLogger("RealtimeSubtitle")
                log.warning(f"Audio device '{dev_name}' may be affected by macOS Voice Isolation.")
                log.warning("If no audio is captured, switch Mic Mode to Standard in the macOS menu bar.")
        except Exception:
            pass
        
        print(f"[Audio] Starting raw processing stream (step={self.streaming_step_size}s, device={device})")
        
        try:
            yield from self._iter_stream_chunks(
                device=device,
                block_size=block_size,
                overflow_label="Audio overflow",
            )
        except AudioCaptureError:
            raise  # re-raise structured errors
        except Exception as e:
            if self._stop_event.is_set() or not self.running:
                return
            print(f"\n[ERROR] Audio Device Initialization Failed: {e}")
            print("Possible causes:")
            print("1. Terminal/App does not have Microphone Permissions (System Settings > Privacy > Microphone)")
            print(f"2. Sample rate {self.sample_rate}Hz not supported by device (Try 44100 or 48000)")
            print("3. Invalid device index in config.ini (Try 'auto' or check 'python audio_capture.py')")
            # Try reconnection with default device
            print("[Audio] Attempting fallback to default input device...")
            try:
                default_dev = sd.query_devices(kind='input')
                print(f"[Audio] Fallback: [{default_dev['index']}] {default_dev['name']}")
                yield from self._iter_stream_chunks(
                    device=None,
                    block_size=block_size,
                    overflow_label="Audio overflow (fallback)",
                )
            except Exception as e2:
                if self._stop_event.is_set() or not self.running:
                    return
                print(f"[Audio] FALLBACK ALSO FAILED: {e2}")
                import logging
                log = logging.getLogger("RealtimeSubtitle")
                log.error(f"Audio capture failed on all devices: {e} | fallback: {e2}")
                self.running = False
                raise AudioCaptureError(
                    f"Audio device failed: requested device={device}, fallback also failed: {e2}",
                    stage="open",
                    requested_device=str(device),
                    fallback_attempted=True
                ) from e2
            
        print("[Audio] Generator stopped.")

    def get_audio_stream(self):
        """Generator that yields numpy arrays of float32 audio containing speech."""
        while self.running:
            try:
                # Get a segment from the queue
                audio_segment = self.audio_queue.get(timeout=1)
                yield audio_segment
            except queue.Empty:
                continue

    def _record_loop(self):
        try:
            if self.streaming_mode:
                self._streaming_record_loop()
            else:
                self._vad_record_loop()
        except Exception:
            if not self._stop_event.is_set():
                raise
    
    def _streaming_record_loop(self):
        """Continuous streaming: emit audio every streaming_interval seconds with overlap"""
        print(f"[Audio] Streaming mode: interval={self.streaming_interval}s, overlap={self.streaming_overlap}s")
        
        interval_samples = int(self.sample_rate * self.streaming_interval)
        overlap_samples = int(self.sample_rate * self.streaming_overlap)
        
        # Ring buffer to hold audio with overlap
        buffer = np.array([], dtype=np.float32)
        
        last_emit_time = time.time()

        for audio_chunk in self._iter_stream_chunks(
            device=self.device_index,
            block_size=self.block_size,
        ):
            buffer = np.concatenate([buffer, audio_chunk])

            # Check if it's time to emit
            if time.time() - last_emit_time >= self.streaming_interval:
                if len(buffer) > 0:
                    # Check if there's any audio (not pure silence)
                    rms = np.sqrt(np.mean(buffer**2))
                    if rms > self.silence_threshold * 0.5:  # Lower threshold for streaming
                        duration = len(buffer) / self.sample_rate
                        print(f"[Audio] Streaming emit: {duration:.2f}s, RMS={rms:.4f}")
                        self.audio_queue.put(buffer.copy())

                    # Keep overlap for context, discard the rest
                    if len(buffer) > overlap_samples:
                        buffer = buffer[-overlap_samples:]

                last_emit_time = time.time()
    
    def _vad_record_loop(self):
        """VAD-based recording: wait for speech and silence"""
        # Buffer to hold current speech phrase
        current_phrase = []
        silence_start_time = None
        has_speech = False
        
        debug_counter = 0
        max_rms_seen = 0
        phrase_start_time = None  # Track when current phrase started

        for audio_chunk in self._iter_stream_chunks(
            device=self.device_index,
            block_size=self.block_size,
        ):

            rms = np.sqrt(np.mean(audio_chunk**2))
            max_rms_seen = max(max_rms_seen, rms)
                
                # Debug logging every 2 seconds
            debug_counter += 1
            if debug_counter % 20 == 0:
                status = "SPEECH" if has_speech else "silent"
                phrase_dur = time.time() - phrase_start_time if phrase_start_time else 0
                print(f"[Audio] RMS: {rms:.4f} | Max: {max_rms_seen:.4f} | Threshold: {self.silence_threshold} | {status} | Phrase: {phrase_dur:.1f}s")
                
                # Always collect audio if above threshold
            if rms > self.silence_threshold:
                if not has_speech:
                    has_speech = True
                    phrase_start_time = time.time()
                    print(f"[Audio] Speech detected! RMS={rms:.4f}")
                current_phrase.append(audio_chunk)
                silence_start_time = None
            else:
                if has_speech:
                    current_phrase.append(audio_chunk)

                    if silence_start_time is None:
                        silence_start_time = time.time()
                    elif time.time() - silence_start_time > self.silence_duration:
                        # Silence long enough, cut phrase
                        self._emit_phrase(current_phrase, "silence")
                        current_phrase = []
                        has_speech = False
                        silence_start_time = None
                        phrase_start_time = None

                # Force cut if phrase is too long (real-time requirement)
            if has_speech and phrase_start_time:
                phrase_duration = time.time() - phrase_start_time
                if phrase_duration >= self.max_phrase_duration:
                    self._emit_phrase(current_phrase, "max_time")
                    current_phrase = []
                    has_speech = False
                    silence_start_time = None
                    phrase_start_time = None
    
    def _emit_phrase(self, phrase_chunks, reason):
        """Helper to emit a complete phrase"""
        if not phrase_chunks:
            return
        full_phrase = np.concatenate(phrase_chunks)
        duration = len(full_phrase) / self.sample_rate
        print(f"[Audio] Phrase complete ({reason}): {duration:.2f}s")
        self.audio_queue.put(full_phrase)

if __name__ == "__main__":
    # Test
    print("Available devices:")
    print(sd.query_devices())
    
    cap = AudioCapture()
    cap.start()
    try:
        for i, segment in enumerate(cap.get_audio_stream()):
            print(f"Got audio segment {i}: length {len(segment)/16000:.2f}s")
    except KeyboardInterrupt:
        cap.stop()
