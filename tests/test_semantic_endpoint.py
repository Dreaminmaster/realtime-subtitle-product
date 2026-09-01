from src.semantic_endpoint import EndpointSignals, SemanticEndpointPolicy, looks_incomplete


def test_punctuation_allows_a_quicker_endpoint():
    policy = SemanticEndpointPolicy(base_silence=1.0)
    decision = policy.decide(
        EndpointSignals(duration=2.0, silence=0.55, text="That is all.", language="en")
    )
    assert decision.should_finalize is True
    assert decision.reason == "punctuated_pause"


def test_unfinished_phrase_survives_a_normal_short_pause():
    policy = SemanticEndpointPolicy(base_silence=0.9)
    decision = policy.decide(
        EndpointSignals(duration=3.0, silence=1.0, text="we need to", language="en")
    )
    assert decision.should_finalize is False
    assert decision.incomplete is True
    assert decision.required_silence > 1.0


def test_cjk_continuation_particle_is_incomplete():
    assert looks_incomplete("我们这一次因为", "zh") is True
    assert looks_incomplete("我们完成了。", "zh") is False


def test_hard_duration_bounds_long_monologue_without_silence():
    policy = SemanticEndpointPolicy(max_duration=8.0)
    decision = policy.decide(
        EndpointSignals(duration=8.1, silence=0.0, text="a continuing long thought")
    )
    assert decision.should_finalize is True
    assert decision.reason == "hard_duration"


def test_content_limit_waits_for_a_small_pause():
    policy = SemanticEndpointPolicy(max_words=8, max_duration=30)
    text = "one two three four five six seven eight nine"
    assert not policy.decide(EndpointSignals(4, 0.1, text)).should_finalize
    assert policy.decide(EndpointSignals(4, 0.31, text)).should_finalize


def test_recently_changing_hypothesis_requires_more_evidence():
    policy = SemanticEndpointPolicy(base_silence=0.8)
    decision = policy.decide(
        EndpointSignals(
            duration=2.0,
            silence=0.85,
            text="this may continue",
            seconds_since_text_change=0.1,
        )
    )
    assert decision.should_finalize is False
    assert decision.reason.endswith("still_changing")


def test_too_short_audio_is_not_finalized():
    policy = SemanticEndpointPolicy(min_duration=0.5)
    decision = policy.decide(EndpointSignals(0.2, 2.0, "hi"))
    assert decision.should_finalize is False
    assert decision.reason == "too_short"
