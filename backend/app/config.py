from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path("backend/.env"), override=False)


def env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
