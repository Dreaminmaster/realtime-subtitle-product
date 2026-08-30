import importlib.util
from pathlib import Path
import wave

import numpy as np


TOOL = Path(__file__).resolve().parents[1] / "tools" / "compare_recognition_quality.py"
SPEC = importlib.util.spec_from_file_location("compare_recognition_quality", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_word_error_rate_reports_substitution():
    assert MODULE.word_error_rate("we can see it", "we can sea it") == 0.25


def test_load_pcm16_wav_converts_stereo_and_resamples(tmp_path):
    path = tmp_path / "sample.wav"
    stereo = np.array([[1000, -1000], [2000, 0], [3000, 1000], [4000, 2000]], dtype="<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(stereo.tobytes())

    audio = MODULE.load_pcm16_wav(path, target_rate=16000)

    assert audio.dtype == np.float32
    assert len(audio) == 8
