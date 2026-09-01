from runtime_performance import RuntimePerformancePolicy, resolve_hardware_runtime_plan


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


def test_hardware_plan_limits_sustained_cpu_threads_by_profile():
    efficient = resolve_hardware_runtime_plan(
        "efficient", machine="x86_64", memory_gb=8, cpu_count=8
    )
    balanced = resolve_hardware_runtime_plan(
        "balanced", machine="arm64", memory_gb=16, cpu_count=10
    )
    maximum = resolve_hardware_runtime_plan(
        "maximum", machine="arm64", memory_gb=32, cpu_count=12
    )

    assert efficient.cpu_threads == 4
    assert efficient.num_workers == 1
    assert balanced.cpu_threads == 5
    assert balanced.num_workers == 1
    assert maximum.cpu_threads == 10
    assert maximum.num_workers == 2
    assert efficient.partial_window_seconds < maximum.partial_window_seconds


def test_low_memory_maximum_does_not_create_parallel_model_workers():
    plan = resolve_hardware_runtime_plan(
        "maximum", machine="x86_64", memory_gb=8, cpu_count=12
    )
    assert plan.num_workers == 1
    assert plan.compute_type == "int8"


def test_translation_worker_budget_prevents_provider_contention():
    assert RuntimePerformancePolicy("efficient").translation_workers(8) == 1
    assert RuntimePerformancePolicy("balanced").translation_workers(8) == 2
    assert RuntimePerformancePolicy("maximum").translation_workers(8) == 4
    assert RuntimePerformancePolicy("balanced").translation_workers(1) == 1
