from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .config import AppConfig, save_config

HEAVY_REQUIREMENTS = [
    "numpy",
    "whisperx",
]


def default_venv_path() -> Path:
    return Path.home() / ".local" / "share" / "wisperx-caption-aligner" / ".venv-whisperx"


def python_bin(venv_path: Path) -> Path:
    if sys.platform == "win32":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def ensure_venv(venv_path: Path) -> None:
    if python_bin(venv_path).exists():
        return
    venv_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)


def install_heavy_dependencies(venv_path: Path) -> None:
    py = python_bin(venv_path)
    subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(py), "-m", "pip", "install", *HEAVY_REQUIREMENTS], check=True)


def configure_venv(venv_path: Path) -> Path:
    return save_config(AppConfig(venv_path=str(venv_path.expanduser().resolve())))
