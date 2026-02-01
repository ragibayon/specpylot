from __future__ import annotations

"""Helpers for running CrossHair cover and aggregating pytest stubs."""

import re
from typing import Any, Iterable

from specpylot.utils.exec import run_project_local

_DEF_RE = re.compile(r"^\s*(async\s+)?def\s+([A-Za-z_]\w*)\s*\(", re.MULTILINE)


def _iter_cover_targets(
    annotated_code: str,
    annotated_relpath: str,
    *,
    include_dunder: bool = False,
    max_indent: int = 8,
) -> list[dict[str, Any]]:
    """Return targets as dicts containing name, lineno, indent, and file:line."""
    targets: list[dict[str, Any]] = []
    lines = annotated_code.splitlines()

    for m in _DEF_RE.finditer(annotated_code):
        # Compute 1-based line number from match start offset
        lineno = annotated_code.count("\n", 0, m.start()) + 1
        name = m.group(2)

        # Compute indentation (spaces before 'def')
        line = lines[lineno - 1] if 0 <= lineno - 1 < len(lines) else ""
        indent = len(line) - len(line.lstrip(" "))

        if indent > max_indent:
            # Skip nested defs/closures by default (often not sensible cover targets)
            continue

        if not include_dunder and name.startswith("__") and name.endswith("__"):
            continue

        targets.append(
            {
                "name": name,
                "lineno": lineno,
                "indent": indent,
                "target": f"{annotated_relpath}:{lineno}",
            }
        )

    # De-dupe by (lineno) while preserving order
    seen = set()
    deduped: list[dict[str, Any]] = []
    for t in targets:
        key = t["lineno"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    return deduped


def run_crosshair_cover_pytest(
    *,
    annotated_relpath: str,
    annotated_code: str,
    cover_cmd_prefix: Iterable[str],
    timeout_seconds: int = 360,
    include_dunder: bool = False,
    max_indent: int = 8,
) -> dict[str, Any]:
    """Run `crosshair cover` per target and combine generated pytest stubs.

    Args:
        annotated_relpath: Relative path for the annotated code file.
        annotated_code: Annotated code contents.
        cover_cmd_prefix: Base CrossHair cover command.
        timeout_seconds: Overall timeout per target.
        include_dunder: Whether to include dunder methods as targets.
        max_indent: Max indentation depth to consider as a target.

    Returns:
        dict[str, Any]: Combined stdout/stderr plus per-target metadata.
    """
    targets = _iter_cover_targets(
        annotated_code,
        annotated_relpath,
        include_dunder=include_dunder,
        max_indent=max_indent,
    )

    # If we can't find any defs, fall back to covering the whole file at line 1
    if not targets:
        targets = [
            {
                "name": "(fallback)",
                "lineno": 1,
                "indent": 0,
                "target": f"{annotated_relpath}:1",
            }
        ]

    per_target: list[dict[str, Any]] = []
    combined_stdout_parts: list[str] = []
    combined_stderr_parts: list[str] = []

    any_timeout = False
    exit_code_summary = 0
    runtime_sum = 0

    for t in targets:
        cover_cmd = list(cover_cmd_prefix) + [t["target"]]

        res = run_project_local(
            files={annotated_relpath: annotated_code},
            command=cover_cmd,
            timeout_seconds=timeout_seconds,
            workdir=".",
        )

        # Attach metadata for logging / downstream usage
        res["cover_cmd"] = cover_cmd
        res["cover_target"] = t["target"]
        res["cover_lineno"] = t["lineno"]
        res["def_name"] = t["name"]

        per_target.append(res)

        stdout = (res.get("stdout") or "").rstrip()
        stderr = (res.get("stderr") or "").rstrip()

        # Keep your pipeline behavior: produce ONE pytest file via stdout.
        # We separate chunks with comments so it's debuggable.
        if stdout:
            combined_stdout_parts.append(
                "\n".join(
                    [
                        f"# --- CrossHair cover target: {t['target']} (def {t['name']}) ---",
                        stdout,
                        "",
                    ]
                )
            )
        if stderr:
            combined_stderr_parts.append(
                "\n".join(
                    [
                        f"# --- CrossHair cover stderr: {t['target']} (def {t['name']}) ---",
                        stderr,
                        "",
                    ]
                )
            )

        # Aggregate status
        any_timeout = any_timeout or bool(res.get("timeout"))
        runtime_sum += int(res.get("runtime") or 0)

        ec = res.get("exit_code")
        if isinstance(ec, int) and ec != 0 and exit_code_summary == 0:
            exit_code_summary = ec

    combined = {
        "stdout": (
            ("\n".join(combined_stdout_parts).rstrip() + "\n")
            if combined_stdout_parts
            else ""
        ),
        "stderr": (
            ("\n".join(combined_stderr_parts).rstrip() + "\n")
            if combined_stderr_parts
            else ""
        ),
        "exit_code": exit_code_summary,
        "runtime": runtime_sum,
        "timeout": any_timeout,
        "cover_targets": [t["target"] for t in targets],
        "per_target": per_target,
    }
    return combined
