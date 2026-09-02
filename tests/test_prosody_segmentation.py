"""Tests for language-neutral narration boundary handling."""

from piper.voice_selection import _split_sentences, parse_script


def test_ellipsis_stays_inside_the_same_sentence() -> None:
    assert _split_sentences("Wait… I need to think. Next sentence.") == [
        "Wait… I need to think.",
        "Next sentence.",
    ]


def test_full_width_sentence_punctuation_can_split_without_spaces() -> None:
    assert _split_sentences("这是第一句。這是第二句！真的？") == [
        "这是第一句。",
        "這是第二句！",
        "真的？",
    ]


def test_paragraph_and_sentence_indexes_are_preserved() -> None:
    segments = parse_script("First. Second.\n\nThird!")

    assert [(item.paragraph_index, item.sentence_index) for item in segments] == [
        (0, 0),
        (0, 1),
        (1, 0),
    ]
    assert [item.paragraph_end for item in segments] == [False, True, True]
