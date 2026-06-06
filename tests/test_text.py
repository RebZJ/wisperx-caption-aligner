from wisperx_caption_aligner.text import canonical_tokens_from_lines, normalize_word


def test_normalize_word_handles_punctuation_and_apostrophes() -> None:
    assert normalize_word("I’ve") == "ive"
    assert normalize_word("stash.") == "stash"
    assert normalize_word("They be,") == "theybe"


def test_canonical_tokens_preserve_display_text() -> None:
    tokens = canonical_tokens_from_lines(["I’ve been", "", "stash."])

    assert [token.text for token in tokens] == ["I’ve", "been", "stash."]
    assert [token.line_index for token in tokens] == [0, 0, 2]
    assert [token.word_index for token in tokens] == [0, 1, 0]
