"""Lightweight adaptive voice activity detection for live captions.

The gate only decides when a phrase starts/ends; it never modifies recorded or
transcribed audio.  A rolling low percentile tracks steady room noise without
adding a neural denoiser's CPU and latency cost.
"""

from __future__ import annotations

from collections import deque

import numpy as np


class AdaptiveNoiseGate:
    MODES = {"off", "balanced", "strong"}

    def __init__(self, base_threshold: float, mode: str = "balanced", history: int = 40):
        self.base_threshold = max(0.0001, float(base_threshold))
        self.mode = str(mode or "balanced").lower()
        if self.mode not in self.MODES:
            self.mode = "balanced"
        self._samples = deque(maxlen=max(8, int(history)))
        self.noise_floor = self.base_threshold * 0.45
        self.effective_threshold = self.base_threshold

    def classify(self, rms: float, *, recording: bool = False) -> bool:
        rms = max(0.0, float(rms))
        if self.mode == "off":
            self.effective_threshold = self.base_threshold
            return rms > self.effective_threshold

        # While idle, include the ambient stream.  Once recording has begun,
        # only quiet frames may update the floor so speech cannot teach the
        # gate that the speaker is "noise".
        if not recording or rms <= self.effective_threshold * 1.15:
            self._samples.append(rms)
        if len(self._samples) >= 4:
            self.noise_floor = float(np.percentile(tuple(self._samples), 20))

        ratio = 1.55 if self.mode == "balanced" else 2.05
        if recording:
            # A gentler release preserves word endings and short pauses.
            ratio = min(ratio, 1.40)
        adaptive = self.noise_floor * ratio
        self.effective_threshold = min(
            self.base_threshold * 4.0,
            max(self.base_threshold, adaptive),
        )
        return rms > self.effective_threshold

