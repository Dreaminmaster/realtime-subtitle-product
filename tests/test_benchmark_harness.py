from tools.run_streaming_benchmark import _distance, error_rate


def test_edit_distance_and_english_wer():
    assert _distance(["a", "b"], ["a", "c"]) == 1
    assert error_rate("one two three", "one two") == 1 / 3


def test_cjk_is_compared_as_characters_not_one_giant_word():
    assert error_rate("实时字幕", "实时字母") == 1 / 4


def test_case_and_punctuation_do_not_count_as_errors():
    assert error_rate("Hello, world!", "hello world") == 0.0
