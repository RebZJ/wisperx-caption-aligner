import json
from pathlib import Path

from wisperx_caption_aligner.editor_server import read_captions
from wisperx_caption_aligner.validate import validate_captions


def test_read_captions_requires_list(tmp_path: Path) -> None:
    captions = tmp_path / "captions.json"
    captions.write_text(json.dumps({"text": "nope"}))

    try:
        read_captions(captions)
    except ValueError as error:
        assert "must be a list" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_editor_save_validation_can_skip_max_duration() -> None:
    errors = validate_captions(
        [{"text": "hello", "startMs": 100, "endMs": 200, "timestampMs": 100}],
        expected_words=None,
        max_duration_ms=None,
    )
    assert errors == []
