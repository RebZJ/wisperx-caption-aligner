from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from .setup_env import python_bin


def ensure_runner_available(venv_path: Path) -> None:
    py = python_bin(venv_path)
    if not py.exists():
        raise RuntimeError(f"Configured WhisperX virtualenv is missing Python: {py}")

    check = subprocess.run(
        [str(py), "-c", "import whisperx, numpy"],
        text=True,
        capture_output=True,
    )
    if check.returncode != 0:
        raise RuntimeError(
            "Configured virtualenv does not have WhisperX installed. "
            "Run `wisperx-caption-aligner setup` again."
        )


def run_whisperx_worker(
    *,
    venv_path: Path,
    audio_wav: Path,
    result_path: Path,
    prompt: str,
    model: str,
    language: str,
    device: str,
    compute_type: str,
    batch_size: int,
) -> None:
    ensure_runner_available(venv_path)
    worker_path = Path(__file__).with_name("_whisperx_worker.py")
    payload = {
        "audio_wav": str(audio_wav),
        "result_path": str(result_path),
        "prompt": prompt,
        "model": model,
        "language": language,
        "device": device,
        "compute_type": compute_type,
        "batch_size": batch_size,
    }
    subprocess.run([str(python_bin(venv_path)), str(worker_path), json.dumps(payload)], check=True)


def local_worker_importable() -> bool:
    return importlib.util.find_spec("whisperx") is not None and importlib.util.find_spec("numpy") is not None
