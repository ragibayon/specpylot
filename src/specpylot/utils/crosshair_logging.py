"""Utilities for persisting CrossHair outputs and summaries."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_STATS_RE = re.compile(r"Path tree stats\s*\{([^}]*)\}")
_ITER_RE = re.compile(r"Number of iterations:\s*(\d+)")


def _parse_last_path_tree_stats(stderr_text: str) -> dict[str, int]:
    """Parse the last "Path tree stats" block from stderr."""
    matches = list(_STATS_RE.finditer(stderr_text or ""))
    if not matches:
        return {}

    inner = matches[-1].group(1).strip()
    if not inner:
        return {}

    out: dict[str, int] = {}
    for part in inner.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        k, v = part.split(":", 1)
        k = k.strip()
        v = v.strip()
        try:
            out[k] = int(v)
        except ValueError:
            continue
    return out


def _parse_last_iterations(stderr_text: str) -> Optional[int]:
    """Parse the last iteration count from stderr, if present."""
    matches = list(_ITER_RE.finditer(stderr_text or ""))
    if not matches:
        return None
    return int(matches[-1].group(1))


def _now_tag() -> str:
    """Return a timestamp tag for log folders."""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def log_crosshair_result(
    *,
    log_dir: Path,
    target_label: str,  # e.g., "binary_search" or question_id
    command: list[str],
    ch_result: dict[str, Any],
    annotated_code_text: Optional[str] = None,
    annotated_code_filename: str = "annotated_code.py",
) -> dict[str, Any]:
    """Persist CrossHair artifacts and return a metadata summary dict.

    Args:
        log_dir: Root directory where run logs are stored.
        target_label: Label used for the run directory name.
        command: CrossHair command used.
        ch_result: Result dict from the CrossHair execution.
        annotated_code_text: Optional annotated code to save.
        annotated_code_filename: Filename for the annotated code artifact.

    Returns:
        dict[str, Any]: Summary metadata including paths and stats.
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    run_id = f"{target_label}_{_now_tag()}"
    run_dir = log_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    stdout = ch_result.get("stdout") or ""
    stderr = ch_result.get("stderr") or ""

    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)

    annotated_path: Optional[Path] = None
    if annotated_code_text is not None:
        annotated_path = run_dir / annotated_code_filename
        annotated_path.write_text(annotated_code_text)

    stats = _parse_last_path_tree_stats(stderr)
    iterations = _parse_last_iterations(stderr)

    exit_code = ch_result.get("exit_code")
    if exit_code == 0:
        verdict = "PASSED"
    elif exit_code == 1:
        verdict = "FAILED"
    else:
        verdict = "ERROR"

    summary_path = run_dir / "summary.json"
    meta = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "command": command,
        "verdict": verdict,
        "exit_code": exit_code,
        "runtime_ms": ch_result.get("runtime"),
        "timeout": ch_result.get("timeout"),
        "path_tree_stats_last": stats,
        "iterations_last": iterations,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "summary_path": str(summary_path),
        "annotated_code_path": (str(annotated_path) if annotated_path else None),
    }
    summary_path.write_text(json.dumps(meta, indent=2, sort_keys=True))
    return meta
