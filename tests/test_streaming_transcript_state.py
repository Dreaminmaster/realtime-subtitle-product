from src.streaming_transcript_state import StreamingTranscriptState
from src.transcript_event import TranscriptPhase


def test_first_hypothesis_is_partial_and_second_confirms_safe_prefix():
    state = StreamingTranscriptState(unsafe_tail_tokens=2)

    first = state.observe(7, "we are building a caption")
    second = state.observe(7, "we are building a caption now")

    assert first.phase is TranscriptPhase.PARTIAL
    assert first.stable_text == ""
    assert second.phase is TranscriptPhase.STABLE
    assert second.stable_text == "we are building"
    assert second.volatile_text == "a caption now"
    assert second.display_text == "we are building a caption now"


def test_stable_prefix_never_regresses_during_partial_rewrite():
    state = StreamingTranscriptState(unsafe_tail_tokens=1)
    state.observe("a", "the quick brown fox")
    agreed = state.observe("a", "the quick brown fox jumps")
    rewritten = state.observe("a", "the quick blue car")

    assert agreed.stable_text == "the quick brown"
    assert rewritten.stable_text == "the quick brown"
    assert rewritten.phase is TranscriptPhase.STABLE
    assert rewritten.display_text.startswith("the quick brown")


def test_strong_punctuation_can_confirm_the_whole_agreed_hypothesis():
    state = StreamingTranscriptState(unsafe_tail_tokens=3)
    state.observe(1, "How are you?")
    update = state.observe(1, "How are you?")

    assert update.stable_text == "How are you?"
    assert update.volatile_text == ""


def test_cjk_is_tokenized_without_whitespace():
    state = StreamingTranscriptState(unsafe_tail_tokens=2)
    state.observe(2, "我们正在制作实时字幕")
    update = state.observe(2, "我们正在制作实时字幕应用")

    assert update.stable_text == "我们正在制作实时"
    assert update.display_text == "我们正在制作实时字幕应用"


def test_finalize_freezes_segment_and_reports_stable_conflict():
    state = StreamingTranscriptState(unsafe_tail_tokens=1)
    state.observe(3, "I saw a blue bird")
    state.observe(3, "I saw a blue bird today")

    final = state.finalize(3, "I saw two blue birds today.")

    assert final.phase is TranscriptPhase.FINAL
    assert final.display_text == "I saw two blue birds today."
    assert final.stable_text == final.display_text
    assert final.volatile_text == ""
    assert final.final_conflicted_with_stable is True
    assert state.observe(3, "late stale output") is None
    assert state.finalize(3, "duplicate final") is None


def test_reset_and_discard_remove_segment_state():
    state = StreamingTranscriptState()
    state.observe("one", "hello there friend")
    state.discard("one")
    assert state.snapshot("one") is None

    state.observe("two", "another useful phrase")
    state.reset()
    assert state.snapshot("two") is None


def test_empty_updates_are_ignored():
    state = StreamingTranscriptState()
    assert state.observe(1, "  ") is None
    assert state.finalize(1, "") is None
