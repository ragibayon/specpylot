from __future__ import annotations

"""Filesystem helpers for pipeline artifacts."""

import re
from pathlib import Path


def fs_safe_name(value: str) -> str:
    """Sanitize a string for use in filenames.

    Args:
        value: Input string to sanitize.

    Returns:
        str: Filesystem-safe name.
    """
    safe = (value or "").strip()
    safe = re.sub(r"\s+", "-", safe)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", safe)
    return safe or "unknown"


def write_text(path: Path, text: str) -> None:
    """Write text to a path, creating parent directories as needed.

    Args:
        path: Target file path.
        text: Text content to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
