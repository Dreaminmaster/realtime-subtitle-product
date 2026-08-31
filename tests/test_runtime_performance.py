from runtime_performance import RuntimePerformancePolicy


def test_balanced_keeps_live_asr_responsive():
    policy = RuntimePerformancePolicy("balanced")
    assert policy.partial_interval(0.5) == 0.78
    assert policy.partial_interval(1.0) == 1.0


def test_provider_aware_draft_translation_budget():
    policy = RuntimePerformancePolicy("balanced")
    apple = policy.draft_translation_interval("fast", "balanced")
    local = policy.draft_translation_interval("local", "balanced")
    assert apple is not None and local is not None
    assert apple < local
    assert policy.draft_translation_interval("fast", "final_only") is None


def test_maximum_preserves_continuous_enhancement():
    maximum = RuntimePerformancePolicy("maximum")
    balanced = RuntimePerformancePolicy("balanced")
    efficient = RuntimePerformancePolicy("efficient")
    assert maximum.accuracy_cooldown(14.0, "large-v3") == 0.0
    assert 3.5 <= balanced.accuracy_cooldown(14.0, "large-v3") <= 10.0
    assert efficient.accuracy_cooldown(14.0, "large-v3") > balanced.accuracy_cooldown(
        14.0, "large-v3"
    )


def test_unknown_profile_safely_uses_balanced():
    assert RuntimePerformancePolicy("mystery").profile == "balanced"


def test_caption_segments_remain_scannable_by_profile():
    assert RuntimePerformancePolicy("efficient").caption_segment_limit(30) == 7.5
    assert RuntimePerformancePolicy("balanced").caption_segment_limit(30) == 9.0
    assert RuntimePerformancePolicy("maximum").caption_segment_limit(30) == 12.0
    assert RuntimePerformancePolicy("balanced").caption_segment_limit(6) == 6.0
