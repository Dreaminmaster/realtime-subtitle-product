from recognition_quality import AccuracyPlan, HardwareProfile, resolve_accuracy_plan


def hardware(machine="arm64", memory=16, apple=True):
    return HardwareProfile(machine=machine, memory_gb=memory, apple_silicon=apple)


def test_auto_uses_turbo_on_high_memory_apple_silicon_to_avoid_thermal_load():
    plan = resolve_accuracy_plan("auto", hardware(memory=32))
    assert plan.model_id == "turbo"
    assert plan.resolved_profile == "balanced"


def test_auto_uses_turbo_on_mainstream_apple_silicon():
    plan = resolve_accuracy_plan("auto", hardware(memory=16))
    assert plan.model_id == "turbo"
    assert plan.resolved_profile == "balanced"


def test_auto_uses_small_on_intel():
    plan = resolve_accuracy_plan("auto", hardware("x86_64", 32, False))
    assert plan.model_id == "small"
    assert plan.compute_type == "int8"


def test_explicit_profile_overrides_hardware():
    plan = resolve_accuracy_plan("accurate", hardware("x86_64", 8, False))
    assert plan == AccuracyPlan("accurate", "accurate", "large-v3", 3100)


def test_unknown_profile_falls_back_to_auto():
    plan = resolve_accuracy_plan("mystery", hardware(memory=16))
    assert plan.requested_profile == "auto"
    assert plan.model_id == "turbo"
