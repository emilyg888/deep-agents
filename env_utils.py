from __future__ import annotations

import os
from pathlib import Path


def load_project_dotenv(dotenv_path: Path) -> None:
    try:
        from dotenv import load_dotenv as external_load_dotenv
    except (ImportError, AttributeError):
        external_load_dotenv = None

    if external_load_dotenv is not None:
        external_load_dotenv(dotenv_path=dotenv_path)
        return

    if not dotenv_path.exists():
        return

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))
