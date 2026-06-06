from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any


def read_lyrics(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing lyrics file: {path}")
    return path.read_text().splitlines()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def convert_to_wav(source: Path, wav_path: Path) -> None:
    wav_path.parent.mkdir(parents=True, exist_ok=True)

    if shutil.which("afconvert"):
        subprocess.run(
            [
                "afconvert",
                str(source),
                str(wav_path),
                "-f",
                "WAVE",
                "-d",
                "LEI16@16000",
                "-c",
                "1",
            ],
            check=True,
        )
        return

    if shutil.which("ffmpeg"):
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-sample_fmt",
                "s16",
                str(wav_path),
            ],
            check=True,
        )
        return

    raise RuntimeError("Audio conversion requires macOS afconvert or ffmpeg on PATH.")


def wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        sample_rate = wav.getframerate()
    return round((frames / sample_rate) * 1000)


def cache_root() -> Path:
    return Path(".cache") / "wisperx-caption-aligner"
