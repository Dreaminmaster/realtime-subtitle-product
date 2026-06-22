# Phase 4b — Real Transcriber Wrapper Mapping

Phase: 4b, Branch: v2.4.0-architecture, Commit before: 6b41371
Transcriber wrapper: transcriber.py Transcriber class
Constructor: Transcriber(backend, model_size, device, compute_type, language)
Backend setting: self.backend = backend.lower()
Model construction: _init_whisper / _init_mlx / _init_funasr
Fake injection point: monkeypatch Transcriber._init_whisper or self.model after construction
Real deps: faster_whisper, mlx_whisper, funasr (not called in these tests)
Audio input: numpy array float32
Output: str (text.strip())
