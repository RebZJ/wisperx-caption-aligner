from __future__ import annotations

from .models import CanonicalToken


def normalize_word(word: str) -> str:
    lowered = word.lower().replace("’", "").replace("'", "")
    return "".join(character for character in lowered if character.isalnum())


def canonical_tokens_from_lines(lines: list[str]) -> list[CanonicalToken]:
    tokens: list[CanonicalToken] = []

    for line_index, line in enumerate(lines):
        for word_index, text in enumerate(line.split()):
            normalized = normalize_word(text)
            if not normalized:
                continue
            tokens.append(
                CanonicalToken(
                    text=text,
                    normalized=normalized,
                    line_index=line_index,
                    word_index=word_index,
                )
            )

    return tokens


def flatten_lyrics(lines: list[str]) -> str:
    return " ".join(line.strip() for line in lines if line.strip())
