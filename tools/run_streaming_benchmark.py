#!/usr/bin/env python3
"""Reproducible streaming ASR benchmark for generated, non-private audio."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time
import wave

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime_metrics import _process_peak_rss_mb


def _normal(text: str) -> list[str]:
    return re.findall(
        r"[a-z0-9]+(?:['’-][a-z0-9]+)*|[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]",
        str(text or "").casefold(),
    )


def _distance(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for i, left_item in enumerate(left, 1):
        current = [i]
        for j, right_item in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (left_item != right_item),
                )
            )
        previous = current
    return previous[-1]


def error_rate(reference: str, hypothesis: str) -> float:
    reference_tokens = _normal(reference)
    return _distance(reference_tokens, _normal(hypothesis)) / max(1, len(reference_tokens))


def _read(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        samples = np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2")
    return samples.astype(np.float32) / 32768.0, rate


def benchmark_case(transcriber, case: dict, *, partial_step: float) -> dict:
    from src.streaming_transcript_state import StreamingTranscriptState

    audio, rate = _read(Path(case["path"]))
    # Single-language cases deliberately lock the language, matching the
    # product recommendation; the mixed case exercises automatic detection.
    transcriber.language = None if case["language"] == "auto" else case["language"]
    tracker = StreamingTranscriptState()
    first_partial = None
    first_stable = None
    partial_calls = 0
    partial_cpu = 0.0
    step = max(1, int(partial_step * rate))
    for end in range(step, len(audio) + step, step):
        window = audio[: min(end, len(audio))]
        started = time.monotonic()
        text = transcriber.transcribe_partial(window)
        partial_cpu += time.monotonic() - started
        partial_calls += 1
        update = tracker.observe(case["id"], text)
        if update is not None and first_partial is None:
            first_partial = min(end, len(audio)) / rate + partial_cpu
        if update is not None and update.stable_text and first_stable is None:
            first_stable = min(end, len(audio)) / rate + partial_cpu
        if end >= len(audio):
            break

    final_started = time.monotonic()
    final_text = transcriber.transcribe(audio)
    final_compute = time.monotonic() - final_started
    final_update = tracker.finalize(case["id"], final_text) if final_text else None
    reference_tokens = _normal(case["text"])
    cjk = bool(re.search(r"[\u3400-\u9fff]", case["text"]))
    return {
        "id": case["id"],
        "language": case["language"],
        "duration_seconds": round(len(audio) / rate, 3),
        "partial_calls": partial_calls,
        "first_partial_seconds": round(first_partial, 3) if first_partial else None,
        "first_stable_seconds": round(first_stable, 3) if first_stable else None,
        "final_compute_seconds": round(final_compute, 3),
        "final_after_eos_seconds": round(final_compute, 3),
        "rtf": round(final_compute / max(0.001, len(audio) / rate), 3),
        "wer_or_cer": round(error_rate(case["text"], final_text), 4),
        "metric": "CER-like token rate" if cjk else "WER",
        "reference": case["text"],
        "hypothesis": final_text,
        "stable_conflict": bool(
            final_update and final_update.final_conflicted_with_stable
        ),
        "reference_tokens": len(reference_tokens),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "benchmarks" / "generated" / "manifest.generated.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "benchmarks" / "results" / "latest.json",
    )
    parser.add_argument("--partial-step", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--profile", choices=("efficient", "balanced", "maximum"), default="balanced"
    )
    args = parser.parse_args()

    from config import config
    from model_manager import model_manager
    from runtime_performance import resolve_hardware_runtime_plan
    from transcriber import Transcriber

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    cases = [case for case in manifest["cases"] if "30-minute" not in case.get("tags", [])]
    if args.limit:
        cases = cases[: args.limit]
    model_name = config.whisper_model
    resolved = model_manager.get_model_path(model_name, "whisper") or model_name
    plan = resolve_hardware_runtime_plan(args.profile)
    transcriber = Transcriber(
        backend=config.asr_backend,
        model_size=resolved,
        device=config.whisper_device,
        compute_type=config.whisper_compute_type,
        language=config.source_language,
        cpu_threads=plan.cpu_threads,
        num_workers=plan.num_workers,
    )
    transcriber.warmup()

    wall_started = time.monotonic()
    cpu_started = time.process_time()
    results = [benchmark_case(transcriber, case, partial_step=args.partial_step) for case in cases]
    wall = time.monotonic() - wall_started
    cpu = time.process_time() - cpu_started
    from version import BUILD_VERSION

    summary = {
        "version": str(BUILD_VERSION).removeprefix("v"),
        "backend": config.asr_backend,
        "model": model_name,
        "source_language": "fixed per case; mixed-language case uses auto",
        "profile": plan.profile,
        "cpu_threads": plan.cpu_threads,
        "wall_seconds": round(wall, 3),
        "process_cpu_percent": round(cpu / max(0.001, wall) * 100, 2),
        "max_rss_mb": round(_process_peak_rss_mb(), 2),
        "mean_error_rate": round(sum(item["wer_or_cer"] for item in results) / max(1, len(results)), 4),
        "mean_rtf": round(sum(item["rtf"] for item in results) / max(1, len(results)), 3),
        "cases": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
