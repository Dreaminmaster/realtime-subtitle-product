#!/usr/bin/env python3
"""Generate privacy-safe benchmark WAV files with macOS system voices."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import wave

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "phrases.json"


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        if width != 2:
            raise ValueError(f"Expected 16-bit WAV, got {width * 8}-bit")
        samples = np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2")
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples.astype(np.float32) / 32768.0, rate


def _write_wav(path: Path, samples: np.ndarray, rate: int = 16000) -> None:
    samples = np.clip(samples, -1.0, 1.0)
    pcm = (samples * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())


def generate(output: Path, *, include_soak: bool) -> list[dict]:
    if not shutil.which("say") or not shutil.which("afconvert"):
        raise RuntimeError("This generator requires macOS 'say' and 'afconvert'.")
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    generated = []
    for case in manifest["cases"]:
        aiff = output / f"{case['id']}.aiff"
        wav_path = output / f"{case['id']}.wav"
        command = ["say", "-v", case["voice"], "-o", str(aiff)]
        if case.get("rate"):
            command.extend(["-r", str(case["rate"])])
        command.append(case["text"])
        _run(command)
        _run(
            [
                "afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1",
                str(aiff), str(wav_path),
            ]
        )
        aiff.unlink(missing_ok=True)
        samples, rate = _read_wav(wav_path)
        gain = float(case.get("gain", 1.0))
        samples *= gain
        rng = np.random.default_rng(abs(hash(case["id"])) % (2**32))
        noise = float(case.get("noise", 0.0))
        if noise:
            samples += rng.normal(0.0, noise, len(samples)).astype(np.float32)
        tone_hz = float(case.get("tone_hz", 0.0))
        if tone_hz:
            time_axis = np.arange(len(samples), dtype=np.float32) / rate
            samples += 0.018 * np.sin(2 * np.pi * tone_hz * time_axis)
        _write_wav(wav_path, samples, rate)
        generated.append(
            {
                **case,
                "path": str(wav_path),
                "duration": round(len(samples) / rate, 3),
            }
        )

    if include_soak:
        pieces = []
        silence = np.zeros(16000, dtype=np.float32)
        source = [_read_wav(Path(item["path"]))[0] for item in generated]
        length = 0
        target = 30 * 60 * 16000
        index = 0
        while length < target:
            piece = source[index % len(source)]
            pieces.extend((piece, silence))
            length += len(piece) + len(silence)
            index += 1
        soak = np.concatenate(pieces)[:target]
        soak_path = output / "continuous_30min.wav"
        _write_wav(soak_path, soak)
        generated.append(
            {
                "id": "continuous_30min",
                "language": "auto",
                "text": "Repeated project-authored phrases separated by one second.",
                "tags": ["30-minute", "soak"],
                "path": str(soak_path),
                "duration": 1800.0,
            }
        )

    result_path = output / "manifest.generated.json"
    result_path.write_text(
        json.dumps({"cases": generated}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return generated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "benchmarks" / "generated",
    )
    parser.add_argument("--include-soak", action="store_true")
    args = parser.parse_args()
    cases = generate(args.output, include_soak=args.include_soak)
    print(f"Generated {len(cases)} cases in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
