from __future__ import annotations

from typing import Any


def validate_captions(
    captions: list[dict[str, Any]],
    *,
    expected_words: int | None,
    max_duration_ms: int,
) -> list[str]:
    errors: list[str] = []

    if expected_words is not None and len(captions) != expected_words:
        errors.append(f"Expected {expected_words} captions, got {len(captions)}.")

    for index, caption in enumerate(captions):
        start_ms = caption["startMs"]
        end_ms = caption["endMs"]

        if start_ms < 0 or end_ms < 0:
            errors.append(f"Caption {index} has negative timing.")
        if end_ms < start_ms:
            errors.append(f"Caption {index} ends before it starts.")
        if index > 0 and start_ms < captions[index - 1]["startMs"]:
            errors.append(f"Caption {index} starts before the previous caption.")
        if end_ms > max_duration_ms:
            errors.append(f"Caption {index} ends after {max_duration_ms}ms.")

    return errors
