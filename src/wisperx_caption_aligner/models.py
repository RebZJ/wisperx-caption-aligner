from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalToken:
    text: str
    normalized: str
    line_index: int
    word_index: int


@dataclass(frozen=True)
class RawWord:
    text: str
    normalized: str
    start_ms: int
    end_ms: int
    confidence: float | None
    index: int


@dataclass(frozen=True)
class TimedToken:
    text: str
    normalized: str
    line_index: int
    word_index: int
    start_ms: int
    end_ms: int
    source: str
    matched_text: str | None
    confidence: float | None
