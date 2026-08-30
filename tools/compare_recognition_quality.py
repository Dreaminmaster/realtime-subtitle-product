#!/usr/bin/env python3
"""Compare the live and refinement models on exactly the same local WAV."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import wave

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def word_error_rate(reference: str, hypothesis: str) -> float:
    expected = reference.lower().split()
    actual = hypothesis.lower().split()
    if not expected:
        return 0.0 if not actual else 1.0
    previous = list(range(len(actual) + 1))
    for row, expected_word in enumerate(expected, start=1):
        current = [row]
        for column, actual_word in enumerate(actual, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (expected_word != actual_word),
            ))
        previous = current
    return previous[-1] / len(expected)


def load_pcm16_wav(path: Path, target_rate: int = 16000) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if width != 2:
        raise ValueError("This verifier accepts 16-bit PCM WAV recordings")
    audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != target_rate and audio.size:
        duration = audio.size / float(rate)
        old_axis = np.linspace(0.0, duration, num=audio.size, endpoint=False)
        new_size = max(1, int(round(duration * target_rate)))
        new_axis = np.linspace(0.0, duration, num=new_size, endpoint=False)
        audio = np.interp(new_axis, old_axis, audio).astype(np.float32)
    return audio


def _local_transcriber(model_id: str, language: str | None):
    from model_manager import model_manager
    from transcriber import Transcriber

    local_path = model_manager.get_model_path(model_id, "whisper")
    if not local_path:
        raise RuntimeError(
            f"Model '{model_id}' is not installed. Download it in Settings → Recognition Models."
        )
    runtime = Transcriber(
        backend="whisper",
        model_size=local_path,
        device="cpu",
        compute_type="int8",
        language=language,
    )
    runtime.warmup()
    return runtime


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run two locally installed recognition models on one WAV."
    )
    parser.add_argument("wav", type=Path)
    parser.add_argument("--draft", default="tiny")
    parser.add_argument("--refiner", default="turbo")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--reference", help="Optional ground-truth transcript for WER")
    args = parser.parse_args()

    audio = load_pcm16_wav(args.wav.expanduser())
    language = None if args.language == "auto" else args.language
    draft_text = _local_transcriber(args.draft, language).transcribe(audio)
    refined_text = _local_transcriber(args.refiner, language).transcribe(audio)

    print(f"Draft ({args.draft}): {draft_text}")
    print(f"Refined ({args.refiner}): {refined_text}")
    if args.reference is not None:
        print(f"Draft WER: {word_error_rate(args.reference, draft_text):.1%}")
        print(f"Refined WER: {word_error_rate(args.reference, refined_text):.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

