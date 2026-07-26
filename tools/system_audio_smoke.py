#!/usr/bin/env python3
"""Real macOS smoke test for the bundled ScreenCaptureKit PCM helper."""

from __future__ import annotations

import argparse
import os
import select
import subprocess
import sys
import time

import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("helper")
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args()

    process = subprocess.Popen(
        [args.helper, "--sample-rate", "16000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    try:
        ready, _, _ = select.select([process.stderr], [], [], args.timeout)
        if not ready:
            raise RuntimeError("Timed out waiting for ScreenCaptureKit permission/capture")
        status = process.stderr.readline().decode("utf-8", errors="replace").strip()
        print(status)
        if status != "READY":
            raise RuntimeError(status or "System audio helper exited before READY")

        subprocess.run(
            ["/usr/bin/afplay", "/System/Library/Sounds/Glass.aiff"],
            check=True,
            timeout=5,
        )

        deadline = time.monotonic() + 4.0
        payload = bytearray()
        while time.monotonic() < deadline and len(payload) < 16_000:
            readable, _, _ = select.select([process.stdout], [], [], 0.5)
            if readable:
                payload.extend(os.read(process.stdout.fileno(), 16_000 - len(payload)))

        samples = np.frombuffer(payload[: len(payload) - len(payload) % 4], dtype="<f4")
        rms = float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0
        print(f"SYSTEM_AUDIO_SMOKE bytes={len(payload)} samples={samples.size} rms={rms:.6f}")
        if samples.size < 400 or rms <= 0.00001:
            raise RuntimeError("No usable system-audio samples were captured")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1.0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SYSTEM_AUDIO_SMOKE_FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
