"""CrossHair result classification helpers."""

import re
from typing import Any, Optional

# Report-style line:
# /path/file.py:7: error: false when calling divide(1, -1) (which returns -1.0)
_REFUTE_REPORT_RE = re.compile(r":\s*error:\s*(.+)$")

# Rich counterexample line (often in verbose stdout/stderr):
# false when calling divide(1, -1) (which returns -1.0)
_FALSE_WHEN_CALLING_RE = re.compile(
    r"(false when calling\s+[A-Za-z_]\w*\(.*?\)\s+\(which returns\s+.*?\))",
    re.DOTALL,
)

_NO_CHECKABLES_RE = re.compile(r"contain no checkable functions", re.IGNORECASE)


def _last_nonempty_line(text: str) -> str:
    """Return the last non-empty line in a string."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def classify_crosshair_result(
    *,
    stdout: str,
    stderr: str,
    exit_code: int,
    path_tree_stats_last: Optional[dict[str, int]] = None,
    iterations_last: Optional[int] = None,
) -> dict[str, Any]:
    """Classify CrossHair output into PASSED/REFUTED/INCONCLUSIVE/TOOL_ERROR.

    Args:
        stdout: CrossHair stdout.
        stderr: CrossHair stderr.
        exit_code: CrossHair exit code.
        path_tree_stats_last: Optional path tree stats.
        iterations_last: Optional iteration count.

    Returns:
        dict[str, Any]: Classification details with status and optional metadata.
    """
    stdout = stdout or ""
    stderr = stderr or ""
    combined = stdout + "\n" + stderr

    # Import/setup failure text
    if "Could not import your code" in combined:
        return {
            "status": "TOOL_ERROR",
            "reason": "import_error",
            "details": combined.strip(),
        }

    # CrossHair found nothing checkable (common “passed but useless”)
    if exit_code == 0 and _NO_CHECKABLES_RE.search(combined):
        return {
            "status": "TOOL_ERROR",
            "reason": "no_checkable_functions",
            "details": combined.strip(),
        }

    if exit_code == 0:
        unknown = 0
        if path_tree_stats_last:
            unknown = int(path_tree_stats_last.get("UNKNOWN", 0) or 0)

        if unknown > 0:
            return {
                "status": "INCONCLUSIVE",
                "reason": "unknown_paths",
                "unknown": unknown,
                "path_tree_stats_last": path_tree_stats_last or {},
                "iterations_last": iterations_last,
            }

        return {"status": "PASSED", "reason": None}

    if exit_code == 1:
        # Prefer the rich “false when calling …” payload if present:
        m = _FALSE_WHEN_CALLING_RE.search(combined)
        if m:
            cx = m.group(1).strip()
        else:
            # Fallback: parse report-style “: error: …”
            last = _last_nonempty_line(combined)
            m2 = _REFUTE_REPORT_RE.search(last)
            cx = m2.group(1).strip() if m2 else last

        return {
            "status": "REFUTED",
            "reason": "counterexample_found",
            "counterexample": cx,
        }

    # exit_code 2 or anything else
    return {
        "status": "TOOL_ERROR",
        "reason": "nonzero_exit",
        "details": (stderr.strip() or stdout.strip()),
    }
