"""Small generic helpers."""

from pathlib import Path


def find_project_root(start: Path) -> Path:
    """Walk upward to find the project root containing pyproject.toml.

    Args:
        start: Starting path for the search.

    Returns:
        Path: Project root path.

    Raises:
        FileNotFoundError: If no pyproject.toml is found.
    """
    cur = start.resolve()
    for p in [cur, *cur.parents]:
        if (p / "pyproject.toml").exists():
            return p
    raise FileNotFoundError("Could not find project root (pyproject.toml not found).")
