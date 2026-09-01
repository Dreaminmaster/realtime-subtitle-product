#!/usr/bin/env python3
"""Process a generated 30-minute session through one sustained ASR runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import sys
import time
import wave

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _rss_mb() -> float:
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return value / (1024 * 1024) if sys.platform == "darwin" else value / 1024


def _read(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        audio = np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2")
    return audio.astype(np.float32) / 32768.0, rate


def _looks_repetitive(text: str) -> bool:
    words = str(text or "").casefold().split()
    if len(words) < 8:
        return False
    trigrams = [tuple(words[index : index + 3]) for index in range(len(words) - 2)]
    return len(set(trigrams)) < len(trigrams) * 0.55


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audio",
        type=Path,
        default=ROOT / "benchmarks" / "generated" / "continuous_30min.wav",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "benchmarks" / "results" / "long-session.json",
    )
    parser.add_argument("--segment-seconds", type=float, default=9.0)
    parser.add_argument(
        "--profile", choices=("efficient", "balanced", "maximum"), default="balanced"
    )
    args = parser.parse_args()

    from config import config
    from model_manager import model_manager
    from runtime_performance import resolve_hardware_runtime_plan
    from transcriber import Transcriber

    audio, rate = _read(args.audio)
    plan = resolve_hardware_runtime_plan(args.profile)
    model_name = config.whisper_model
    model_path = model_manager.get_model_path(model_name, "whisper") or model_name
    transcriber = Transcriber(
        backend=config.asr_backend,
        model_size=model_path,
        device=config.whisper_device,
        compute_type=config.whisper_compute_type,
        language=None,
        cpu_threads=plan.cpu_threads,
        num_workers=plan.num_workers,
    )
    transcriber.warmup()

    segment_samples = max(rate, int(args.segment_seconds * rate))
    rss_start = _rss_mb()
    rss_samples = [rss_start]
    started = time.monotonic()
    cpu_started = time.process_time()
    empty = 0
    hallucinations = 0
    failures = []
    inference_seconds = 0.0
    processed_audio = 0.0
    segments = 0
    for index, offset in enumerate(range(0, len(audio), segment_samples)):
        chunk = audio[offset : offset + segment_samples]
        if len(chunk) < rate * 0.4:
            continue
        call_started = time.monotonic()
        try:
            text = transcriber.transcribe(chunk)
        except Exception as exc:
            failures.append({"segment": index, "error": str(exc)})
            continue
        inference_seconds += time.monotonic() - call_started
        processed_audio += len(chunk) / rate
        segments += 1
        empty += int(not text)
        hallucinations += int(_looks_repetitive(text))
        if index % 20 == 0:
            rss_samples.append(_rss_mb())

    wall = time.monotonic() - started
    cpu = time.process_time() - cpu_started
    rss_samples.append(_rss_mb())
    result = {
        "version": "2.10.0",
        "audio_minutes": round(processed_audio / 60, 2),
        "segments": segments,
        "segment_seconds": args.segment_seconds,
        "profile": plan.profile,
        "cpu_threads": plan.cpu_threads,
        "wall_seconds": round(wall, 3),
        "inference_seconds": round(inference_seconds, 3),
        "rtf": round(inference_seconds / max(0.001, processed_audio), 4),
        "process_cpu_percent": round(cpu / max(0.001, wall) * 100, 2),
        "rss_start_mb": round(rss_start, 2),
        "rss_end_mb": round(rss_samples[-1], 2),
        "rss_peak_mb": round(max(rss_samples), 2),
        "rss_growth_mb": round(rss_samples[-1] - rss_start, 2),
        "empty_segments": empty,
        "repetition_flags": hallucinations,
        "failures": failures,
        "completed": not failures and processed_audio >= 1799.0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
