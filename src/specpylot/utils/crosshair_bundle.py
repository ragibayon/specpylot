from __future__ import annotations

"""Build compact evidence bundles for CrossHair refutations."""

import re
from typing import Any, Optional

_FALSE_WHEN_RE = re.compile(r"false when calling\s+(.+)$")


def build_crosshair_refutation_bundle(
    *,
    stdout: str,
    stderr: str,
    cls: dict[str, Any],
    meta: dict[str, Any],
    max_tail_lines: int = 60,
) -> dict[str, Any]:
    """Build a compact, LLM-friendly bundle of CrossHair evidence.

    Args:
        stdout: CrossHair stdout.
        stderr: CrossHair stderr.
        cls: Classification dict.
        meta: Metadata dict.
        max_tail_lines: Max lines to keep from stdout/stderr.

    Returns:
        dict[str, Any]: Evidence bundle for refinement prompts.
    """
    stdout = stdout or ""
    stderr = stderr or ""

    stdout_lines = [ln.rstrip() for ln in stdout.splitlines() if ln.strip()]
    stderr_lines = [ln.rstrip() for ln in stderr.splitlines() if ln.strip()]

    stdout_tail = "\n".join(stdout_lines[-max_tail_lines:])
    stderr_tail = "\n".join(stderr_lines[-max_tail_lines:])

    last_error_line: Optional[str] = None
    for ln in reversed(stdout_lines):
        if ": error:" in ln:
            last_error_line = ln
            break

    counterexample = cls.get("counterexample") or ""
    call_expr: Optional[str] = None
    if counterexample:
        m = _FALSE_WHEN_RE.search(counterexample)
        if m:
            call_expr = m.group(1).strip()

    bundle = {
        "status": cls.get("status"),
        "reason": cls.get("reason"),
        "counterexample": counterexample,
        "call_expr": call_expr,
        "last_error_line": last_error_line or "",
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "path_tree_stats_last": meta.get("path_tree_stats_last") or {},
        "iterations_last": meta.get("iterations_last"),
    }
    return bundle
