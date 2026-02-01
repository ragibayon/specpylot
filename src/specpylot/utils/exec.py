"""Run project commands in a temporary workspace."""

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Optional


def run_project_local(
    *,
    files: dict[str, str],
    command: list[str],
    timeout_seconds: int = 30,
    workdir: str = ".",
    extra_env: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Run a command against temporary project files and return a result dict.

    Args:
        files: Mapping of relative file paths to file contents.
        command: Command to execute.
        timeout_seconds: Timeout for the command.
        workdir: Working directory inside the temporary project.
        extra_env: Optional environment overrides.

    Returns:
        dict[str, Any]: Result with stdout/stderr/exit_code/runtime/timeout.
    """
    start_time = time.time()

    # Create an isolated temp project directory
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Write all provided files into the temp directory (safely)
        for filename, content in files.items():
            path_obj = Path(filename)

            # Block absolute paths and path traversal (../) for safety
            if path_obj.is_absolute() or ".." in path_obj.parts:
                return {
                    "stdout": "",
                    "stderr": f"Invalid file path: {filename}",
                    "exit_code": -1,
                    "runtime": 0,
                    "timeout": False,
                    "error": f"Invalid file path: {filename}",
                }

            file_path = root / path_obj
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

        # Build environment variables for the subprocess
        env = os.environ.copy()
        env.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",  # don't create .pyc files
                "PYTHONUNBUFFERED": "1",  # flush output immediately
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",  # prevent loading external pytest plugins
                "PYTHONVERBOSE": "0",  # reduce noisy import logs
                "PYTHONPATH": str(root),  # allow imports from project root
            }
        )
        if extra_env:
            env.update(extra_env)  # caller can add/override env vars

        # Choose working directory inside the temp project
        cwd = root / workdir
        cwd.mkdir(parents=True, exist_ok=True)

        try:
            # Run the command and capture output
            result = subprocess.run(
                command,
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )

            # Measure runtime in milliseconds
            runtime_ms = int((time.time() - start_time) * 1000)

            # Return a consistent result dict
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "runtime": runtime_ms,
                "timeout": False,
                "error": None,
            }

        except subprocess.TimeoutExpired as e:
            # Command exceeded timeout
            runtime_ms = int((time.time() - start_time) * 1000)
            return {
                "stdout": e.stdout or "",
                "stderr": (e.stderr or "") + "\nExecution timed out",
                "exit_code": -1,
                "runtime": runtime_ms,
                "timeout": True,
                "error": None,
            }

        except Exception as e:
            # Any other unexpected failure
            runtime_ms = int((time.time() - start_time) * 1000)
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "runtime": runtime_ms,
                "timeout": False,
                "error": str(e),
            }
