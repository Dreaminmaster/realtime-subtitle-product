from src.accuracy_refinement import AccuracyRefinementCoordinator
from src.contextual_phrase_composer import ContextualPhraseComposer


def test_refinement_updates_the_same_display_position():
    composer = ContextualPhraseComposer()
    decision = composer.compose(7, "we can sea", now=1)
    coordinator = AccuracyRefinementCoordinator(composer, session_generation=4)
    coordinator.register(decision, "we can sea", start_offset=1.0, end_offset=2.0)

    update = coordinator.apply(7, "we can see", session_generation=4)

    assert update.display_chunk_id == 7
    assert update.text == "we can see"
    assert update.start_offset == 1.0
    assert update.end_offset == 2.0


def test_out_of_order_refinements_rebuild_a_merged_line():
    composer = ContextualPhraseComposer()
    first = composer.compose(1, "I was wondering if", now=1)
    second = composer.compose(2, "you can sea.", now=2)
    coordinator = AccuracyRefinementCoordinator(composer, session_generation=0)
    coordinator.register(first, "I was wondering if")
    coordinator.register(second, "you can sea.")

    later = coordinator.apply(2, "you can see.", session_generation=0)
    earlier = coordinator.apply(1, "I was wondering whether", session_generation=0)

    assert later.display_chunk_id == 1
    assert later.text == "I was wondering if you can see."
    assert earlier.text == "I was wondering whether you can see."


def test_stale_session_and_unchanged_text_are_ignored():
    composer = ContextualPhraseComposer()
    decision = composer.compose(3, "hello there", now=1)
    coordinator = AccuracyRefinementCoordinator(composer, session_generation=9)
    coordinator.register(decision, "hello there")

    assert coordinator.apply(3, "hello there", session_generation=9) is None
    assert coordinator.apply(3, "hello world", session_generation=8) is None

