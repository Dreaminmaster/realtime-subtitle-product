from src.runtime_metrics import RuntimeMetrics


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


def test_metrics_capture_first_state_latencies_rtf_and_endpoint_reason():
    clock = Clock()
    metrics = RuntimeMetrics("balanced", "whisper", "tiny", clock=clock)
    metrics.start_session()
    metrics.begin_segment(1)

    clock.value = 0.4
    metrics.record_asr(1, "PARTIAL", inference_seconds=0.1, audio_seconds=1.0)
    clock.value = 0.8
    metrics.record_asr(1, "STABLE", inference_seconds=0.2, audio_seconds=2.0)
    clock.value = 1.0
    metrics.record_translation(1)
    clock.value = 1.4
    metrics.record_asr(
        1,
        "FINAL",
        inference_seconds=0.3,
        audio_seconds=3.0,
        stable_conflict=True,
    )
    metrics.record_endpoint("punctuated_pause")

    result = metrics.snapshot()
    assert result["first_partial_ms_p50"] == 400.0
    assert result["first_stable_ms_p50"] == 800.0
    assert result["translation_ms_p50"] == 1000.0
    assert result["final_ms_p50"] == 1400.0
    assert result["asr_rtf_p50"] == 0.1
    assert result["stable_conflicts"] == 1
    assert result["endpoint_reasons"] == {"punctuated_pause": 1}


def test_only_first_translation_and_first_phase_are_recorded():
    clock = Clock()
    metrics = RuntimeMetrics("efficient", "mlx", "small", clock=clock)
    metrics.start_session()
    metrics.begin_segment(2)
    clock.value = 0.5
    metrics.record_asr(2, "PARTIAL", inference_seconds=0.1, audio_seconds=1)
    clock.value = 0.8
    metrics.record_asr(2, "PARTIAL", inference_seconds=0.1, audio_seconds=1)
    metrics.record_translation(2)
    clock.value = 1.2
    metrics.record_translation(2)

    result = metrics.snapshot()
    assert result["first_partial_ms_p50"] == 500.0
    assert result["translation_ms_p50"] == 800.0
