from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from .models import CanonicalToken, RawWord, TimedToken
from .text import normalize_word

MIN_WORD_DURATION_MS = 40


def levenshtein(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))

    for row_index, a_char in enumerate(a, start=1):
        current = [row_index]

        for column_index, b_char in enumerate(b, start=1):
            substitution_cost = 0 if a_char == b_char else 1
            current.append(
                min(
                    previous[column_index] + 1,
                    current[column_index - 1] + 1,
                    previous[column_index - 1] + substitution_cost,
                )
            )

        previous = current

    return previous[-1]


def word_cost(canonical: str, raw: str) -> float:
    if canonical == raw:
        return 0
    if {canonical, raw} == {"fibre", "fiber"}:
        return 0.05
    if not canonical or not raw:
        return 2.6

    edit_cost = levenshtein(canonical, raw) / max(len(canonical), len(raw))
    close_enough = edit_cost <= 0.34 or (canonical[0] == raw[0] and edit_cost <= 0.42)

    if not close_enough:
        return 2.6

    return min(0.95, edit_cost * (0.82 if canonical[0] == raw[0] else 1))


def align_sequence(
    canonical: list[CanonicalToken],
    raw_words: list[RawWord],
) -> list[tuple[CanonicalToken, RawWord | None]]:
    canonical_gap_cost = 0.9
    raw_gap_cost = 0.48
    rows = len(canonical) + 1
    columns = len(raw_words) + 1
    costs = [[0.0 for _ in range(columns)] for _ in range(rows)]
    moves: list[list[str | None]] = [[None for _ in range(columns)] for _ in range(rows)]

    for row in range(1, rows):
        costs[row][0] = row * canonical_gap_cost
        moves[row][0] = "up"

    for column in range(1, columns):
        costs[0][column] = column * raw_gap_cost
        moves[0][column] = "left"

    for row in range(1, rows):
        for column in range(1, columns):
            diagonal = costs[row - 1][column - 1] + word_cost(
                canonical[row - 1].normalized,
                raw_words[column - 1].normalized,
            )
            up = costs[row - 1][column] + canonical_gap_cost
            left = costs[row][column - 1] + raw_gap_cost
            best = min(diagonal, up, left)
            costs[row][column] = best
            moves[row][column] = "diag" if best == diagonal else "left" if best == left else "up"

    pairs: list[tuple[CanonicalToken, RawWord | None]] = []
    row = len(canonical)
    column = len(raw_words)

    while row > 0 or column > 0:
        move = moves[row][column]

        if move == "diag":
            pairs.append((canonical[row - 1], raw_words[column - 1]))
            row -= 1
            column -= 1
            continue

        if move == "left":
            column -= 1
            continue

        pairs.append((canonical[row - 1], None))
        row -= 1

    return list(reversed(pairs))


def fill_missing(tokens: list[TimedToken], max_duration_ms: int) -> list[TimedToken]:
    anchors = [index for index, token in enumerate(tokens) if token.source in {"whisperx", "fuzzy"}]
    if not anchors:
        step = max_duration_ms / max(1, len(tokens))
        return [
            replace(
                token,
                start_ms=round(index * step),
                end_ms=round(min(max_duration_ms, (index + 1) * step)),
                source="fallback",
            )
            for index, token in enumerate(tokens)
        ]

    filled = list(tokens)

    for index, token in enumerate(filled):
        if token.source in {"whisperx", "fuzzy"}:
            continue

        previous_anchor = next((anchor for anchor in reversed(anchors) if anchor < index), None)
        next_anchor = next((anchor for anchor in anchors if anchor > index), None)

        if previous_anchor is not None and next_anchor is not None:
            gap_slots = next_anchor - previous_anchor
            local_step = max(
                MIN_WORD_DURATION_MS,
                (filled[next_anchor].start_ms - filled[previous_anchor].end_ms) / gap_slots,
            )
            start_ms = round(filled[previous_anchor].end_ms + local_step * (index - previous_anchor))
            end_ms = min(filled[next_anchor].start_ms - 1, round(start_ms + local_step))
        elif next_anchor is not None:
            local_step = 160
            start_ms = max(0, filled[next_anchor].start_ms - round(local_step * (next_anchor - index)))
            end_ms = min(filled[next_anchor].start_ms - 1, round(start_ms + local_step))
        elif previous_anchor is not None:
            local_step = 160
            start_ms = min(
                max_duration_ms - MIN_WORD_DURATION_MS,
                filled[previous_anchor].end_ms + round(local_step * (index - previous_anchor)),
            )
            end_ms = min(max_duration_ms, round(start_ms + local_step))
        else:
            start_ms = 0
            end_ms = MIN_WORD_DURATION_MS

        filled[index] = replace(
            token,
            start_ms=max(0, start_ms),
            end_ms=max(start_ms + MIN_WORD_DURATION_MS, end_ms),
            source="interpolated",
        )

    return filled


def enforce_valid_timings(tokens: list[TimedToken], max_duration_ms: int) -> list[TimedToken]:
    valid: list[TimedToken] = []
    previous_start = 0

    for token in tokens:
        start_ms = max(0, min(max_duration_ms - MIN_WORD_DURATION_MS, token.start_ms))
        start_ms = max(previous_start, start_ms)
        end_ms = max(start_ms + MIN_WORD_DURATION_MS, token.end_ms)
        end_ms = min(max_duration_ms, end_ms)
        valid.append(replace(token, start_ms=start_ms, end_ms=end_ms))
        previous_start = start_ms

    return valid


def raw_word_segments(aligned: dict[str, Any], max_duration_ms: int) -> list[RawWord]:
    words: list[RawWord] = []

    for index, segment in enumerate(aligned.get("word_segments", [])):
        text = str(segment.get("word", "")).strip()
        normalized = normalize_word(text)
        start = segment.get("start")
        end = segment.get("end")

        if not text or not normalized or start is None or end is None:
            continue

        start_ms = max(0, round(float(start) * 1000))
        end_ms = max(start_ms + MIN_WORD_DURATION_MS, round(float(end) * 1000))
        words.append(
            RawWord(
                text=text,
                normalized=normalized,
                start_ms=start_ms,
                end_ms=min(max_duration_ms, end_ms),
                confidence=segment.get("score"),
                index=index,
            )
        )

    return words


def align_canonical_words(
    canonical: list[CanonicalToken],
    raw_words: list[RawWord],
    max_duration_ms: int,
) -> list[TimedToken]:
    aligned: list[TimedToken] = []

    for token, raw_word in align_sequence(canonical, raw_words):
        if raw_word is None:
            aligned.append(
                TimedToken(
                    text=token.text,
                    normalized=token.normalized,
                    line_index=token.line_index,
                    word_index=token.word_index,
                    start_ms=-1,
                    end_ms=-1,
                    source="interpolated",
                    matched_text=None,
                    confidence=None,
                )
            )
            continue

        source = "whisperx" if token.normalized == raw_word.normalized else "fuzzy"
        aligned.append(
            TimedToken(
                text=token.text,
                normalized=token.normalized,
                line_index=token.line_index,
                word_index=token.word_index,
                start_ms=raw_word.start_ms,
                end_ms=raw_word.end_ms,
                source=source,
                matched_text=raw_word.text,
                confidence=raw_word.confidence,
            )
        )

    return enforce_valid_timings(fill_missing(aligned, max_duration_ms), max_duration_ms)


def captions_from_timed_tokens(tokens: list[TimedToken]) -> list[dict[str, Any]]:
    return [
        {
            "text": f"{'' if index == 0 else ' '}{token.text}",
            "startMs": token.start_ms,
            "endMs": token.end_ms,
            "timestampMs": token.start_ms,
            "confidence": token.confidence,
        }
        for index, token in enumerate(tokens)
    ]


def captions_from_raw_words(words: list[RawWord]) -> list[dict[str, Any]]:
    return [
        {
            "text": f"{'' if index == 0 else ' '}{word.text}",
            "startMs": word.start_ms,
            "endMs": word.end_ms,
            "timestampMs": word.start_ms,
            "confidence": word.confidence,
        }
        for index, word in enumerate(words)
    ]


def timing_sources(tokens: list[TimedToken]) -> dict[str, int]:
    counts: dict[str, int] = {}

    for token in tokens:
        counts[token.source] = counts.get(token.source, 0) + 1

    return counts


def tokens_to_debug(tokens: list[TimedToken]) -> list[dict[str, Any]]:
    return [asdict(token) for token in tokens]


def raw_words_to_debug(words: list[RawWord]) -> list[dict[str, Any]]:
    return [asdict(word) for word in words]
