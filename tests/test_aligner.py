from wisperx_caption_aligner.aligner import (
    align_canonical_words,
    captions_from_timed_tokens,
    word_cost,
)
from wisperx_caption_aligner.models import RawWord, TimedToken
from wisperx_caption_aligner.text import canonical_tokens_from_lines
from wisperx_caption_aligner.validate import validate_captions


def raw(text: str, start: int, end: int, index: int = 0) -> RawWord:
    return RawWord(
        text=text,
        normalized=text.lower().replace(".", ""),
        start_ms=start,
        end_ms=end,
        confidence=0.9,
        index=index,
    )


def test_word_cost_accepts_fibre_fiber() -> None:
    assert word_cost("fibre", "fiber") == 0.05


def test_align_canonical_words_interpolates_missing_tokens() -> None:
    canonical = canonical_tokens_from_lines(["hello missing world"])
    raw_words = [raw("hello", 100, 200, 0), raw("world", 500, 650, 1)]

    aligned = align_canonical_words(canonical, raw_words, max_duration_ms=1000)

    assert [token.text for token in aligned] == ["hello", "missing", "world"]
    assert aligned[1].source == "interpolated"
    assert aligned[0].start_ms <= aligned[1].start_ms <= aligned[2].start_ms


def test_caption_validation_catches_bad_timing() -> None:
    captions = [{"text": " bad", "startMs": 200, "endMs": 100, "timestampMs": 200, "confidence": None}]

    errors = validate_captions(captions, expected_words=1, max_duration_ms=1000)

    assert any("ends before it starts" in error for error in errors)


def test_captions_from_timed_tokens_remotion_shape() -> None:
    token = TimedToken(
        text="hello",
        normalized="hello",
        line_index=0,
        word_index=0,
        start_ms=10,
        end_ms=100,
        source="whisperx",
        matched_text="hello",
        confidence=0.7,
    )

    assert captions_from_timed_tokens([token]) == [
        {"text": "hello", "startMs": 10, "endMs": 100, "timestampMs": 10, "confidence": 0.7}
    ]
