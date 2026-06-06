from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

APP_NAME = "wisperx-caption-aligner"


@dataclass(frozen=True)
class AppConfig:
    venv_path: str


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> AppConfig | None:
    path = config_path()
    if not path.exists():
        return None

    payload = json.loads(path.read_text())
    venv_path = payload.get("venv_path")
    if not isinstance(venv_path, str) or not venv_path:
        return None

    return AppConfig(venv_path=venv_path)


def save_config(config: AppConfig) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2) + "\n")
    return path


def config_payload() -> dict[str, Any]:
    loaded = load_config()
    return {} if loaded is None else asdict(loaded)
