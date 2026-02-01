from __future__ import annotations

"""Minimal terminal logging helpers."""

import logging
import os
import sys
import time
from contextlib import contextmanager
from typing import Any, Iterator


def _is_tty() -> bool:
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def _colors_enabled() -> bool:
    # Respect NO_COLOR convention + avoid ANSI when not a TTY
    if os.environ.get("NO_COLOR"):
        return False
    return _is_tty()


class _Ansi:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def wrap(self, s: str, code: str) -> str:
        if not self.enabled:
            return s
        return f"\033[{code}m{s}\033[0m"

    def bold(self, s: str) -> str:
        return self.wrap(s, "1")

    def dim(self, s: str) -> str:
        return self.wrap(s, "2")

    def red(self, s: str) -> str:
        return self.wrap(s, "31")

    def green(self, s: str) -> str:
        return self.wrap(s, "32")

    def yellow(self, s: str) -> str:
        return self.wrap(s, "33")

    def blue(self, s: str) -> str:
        return self.wrap(s, "34")

    def magenta(self, s: str) -> str:
        return self.wrap(s, "35")

    def cyan(self, s: str) -> str:
        return self.wrap(s, "36")


class TermLog:
    """
    Minimal, dependency-free terminal UI.

    - Uses Python logging (so you can redirect to files later if you want)
    - ANSI colors/bold only when stdout is a TTY and NO_COLOR is not set
    """

    def __init__(self, name: str = "specpylot") -> None:
        """Create a terminal logger with optional ANSI color output.

        Args:
            name: Logger name.
        """
        self.ansi = _Ansi(_colors_enabled())
        self.log = logging.getLogger(name)
        self.log.setLevel(logging.INFO)

        if not self.log.handlers:
            h = logging.StreamHandler(sys.stdout)
            h.setLevel(logging.INFO)
            h.setFormatter(logging.Formatter("%(message)s"))
            self.log.addHandler(h)

    def header(self, title: str) -> None:
        """Log a section header.

        Args:
            title: Header text.
        """
        line = "=" * 72
        self.log.info(self.ansi.bold(line))
        self.log.info(self.ansi.bold(title))
        self.log.info(self.ansi.bold(line))

    def info(self, msg: str) -> None:
        """Log an informational message.

        Args:
            msg: Message to log.
        """
        self.log.info(f"{self.ansi.cyan('INFO')}  {msg}")

    def ok(self, msg: str) -> None:
        """Log a success message.

        Args:
            msg: Message to log.
        """
        self.log.info(f"{self.ansi.green('OK')}    {msg}")

    def warn(self, msg: str) -> None:
        """Log a warning message.

        Args:
            msg: Message to log.
        """
        self.log.info(f"{self.ansi.yellow('WARN')}  {msg}")

    def err(self, msg: str) -> None:
        """Log an error message.

        Args:
            msg: Message to log.
        """
        self.log.info(f"{self.ansi.red('ERROR')} {msg}")

    def kv(self, title: str, data: dict[str, Any]) -> None:
        """Log a key-value mapping with a title.

        Args:
            title: Section title.
            data: Mapping of key-value pairs to log.
        """
        self.log.info(self.ansi.bold(title))
        for k, v in data.items():
            self.log.info(f"  - {self.ansi.bold(str(k))}: {v}")

    @contextmanager
    def step(self, title: str) -> Iterator[None]:
        """Context manager for timing a step and logging its duration.

        Args:
            title: Step title.

        Yields:
            None
        """
        start = time.perf_counter()
        self.log.info(f"{self.ansi.blue('>>')} {self.ansi.bold(title)}")
        try:
            yield
        except Exception as e:
            elapsed = time.perf_counter() - start
            self.log.info(
                f"{self.ansi.red('!!')} {self.ansi.bold(title)} {self.ansi.dim(f'({elapsed:.2f}s)')}"
            )
            raise
        else:
            elapsed = time.perf_counter() - start
            self.log.info(
                f"{self.ansi.green('<<')} {self.ansi.bold(title)} {self.ansi.dim(f'({elapsed:.2f}s)')}"
            )
