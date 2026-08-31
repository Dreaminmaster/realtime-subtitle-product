from adaptive_vad import AdaptiveNoiseGate


def test_off_mode_matches_fixed_threshold():
    gate = AdaptiveNoiseGate(0.01, "off")
    assert gate.classify(0.009) is False
    assert gate.classify(0.011) is True


def test_balanced_mode_learns_a_steady_noise_floor():
    gate = AdaptiveNoiseGate(0.005, "balanced")
    for sample in (0.009, 0.010, 0.0095, 0.0105, 0.0098, 0.0102):
        gate.classify(sample)

    assert gate.effective_threshold > 0.005
    assert gate.classify(0.010) is False
    assert gate.classify(0.020) is True


def test_recording_uses_a_gentler_release_threshold():
    gate = AdaptiveNoiseGate(0.005, "strong")
    for _ in range(8):
        gate.classify(0.01)
    idle_threshold = gate.effective_threshold
    gate.classify(0.015, recording=True)
    assert gate.effective_threshold < idle_threshold

