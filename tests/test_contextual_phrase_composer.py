from src.contextual_phrase_composer import ContextualPhraseComposer


def test_unfinished_phrase_reuses_chunk_and_revises_text():
    composer = ContextualPhraseComposer(join_window=4.0)
    first = composer.compose(1, "I was wondering if", now=10.0)
    second = composer.compose(2, "you could help me.", now=12.0)
    assert first.complete is False
    assert second.chunk_id == 1
    assert second.source_chunk_id == 2
    assert second.merged is True
    assert second.revision == 2
    assert second.text == "I was wondering if you could help me."


def test_question_starts_a_new_caption():
    composer = ContextualPhraseComposer()
    first = composer.compose(1, "What are you doing now?", now=1.0)
    second = composer.compose(2, "I missed you", now=2.0)
    assert first.complete is True
    assert second.chunk_id == 2
    assert second.merged is False


def test_artificial_period_after_continuation_word_is_joined():
    composer = ContextualPhraseComposer()
    first = composer.compose(7, "I think that.", now=1.0)
    second = composer.compose(8, "we should leave.", now=2.0)
    assert first.complete is False
    assert second.text == "I think that we should leave."


def test_old_fragment_does_not_merge():
    composer = ContextualPhraseComposer(join_window=2.0)
    composer.compose(1, "This is", now=1.0)
    decision = composer.compose(2, "another thought", now=5.0)
    assert decision.chunk_id == 2
    assert decision.merged is False


def test_cjk_phrases_join_without_extra_space():
    composer = ContextualPhraseComposer()
    composer.compose(1, "我觉得", now=1.0)
    decision = composer.compose(2, "这样更自然。", now=2.0)
    assert decision.text == "我觉得这样更自然。"


def test_complete_unpunctuated_sentence_does_not_swallow_next_caption():
    composer = ContextualPhraseComposer()
    first = composer.compose(1, "I missed you", now=1.0)
    second = composer.compose(2, "How are you", now=2.0)
    assert first.complete is True
    assert second.chunk_id == 2
    assert second.merged is False


def test_lowercase_clause_after_short_pause_revises_previous_caption():
    composer = ContextualPhraseComposer(join_window=4.0)
    first = composer.compose(1, "We will keep this brief.", now=1.0)
    second = composer.compose(2, "and focus on the details.", now=2.0)
    assert first.complete is True
    assert second.chunk_id == 1
    assert second.merged is True
    assert second.text == "We will keep this brief and focus on the details."


def test_capitalized_sentence_after_period_stays_separate():
    composer = ContextualPhraseComposer(join_window=4.0)
    composer.compose(1, "We will keep this brief.", now=1.0)
    second = composer.compose(2, "Next topic starts here.", now=2.0)
    assert second.chunk_id == 2
    assert second.merged is False


def test_complete_cjk_phrase_does_not_swallow_next_caption():
    composer = ContextualPhraseComposer()
    first = composer.compose(1, "我很想你", now=1.0)
    second = composer.compose(2, "最近好吗", now=2.0)
    assert first.complete is True
    assert second.chunk_id == 2
    assert second.merged is False


def test_korean_continuation_keeps_word_spacing():
    composer = ContextualPhraseComposer()
    composer.compose(1, "하지만", now=1.0)
    decision = composer.compose(2, "다시 해볼게요.", now=2.0)
    assert decision.text == "하지만 다시 해볼게요."


def test_join_parts_uses_the_same_language_aware_rules():
    assert ContextualPhraseComposer.join_parts(["我觉得", "这样更好。"] ) == "我觉得这样更好。"
    assert ContextualPhraseComposer.join_parts(["we should.", "continue"]) == "we should continue"


def test_revise_current_changes_the_base_for_a_later_join():
    composer = ContextualPhraseComposer()
    first = composer.compose(1, "I think that", now=1)
    assert composer.revise_current(first.chunk_id, "I believe that") is True
    second = composer.compose(2, "we should go.", now=2)
    assert second.text == "I believe that we should go."
