from __future__ import annotations

"""Parser for the <annotated code> wrapper format."""

import re

ANNOTATED_RE = re.compile(
    r"\A"
    r"<\s*annotated\s+code\s*>\s*\r?\n"
    r"(?P<body>.*)"
    r"\r?\n\s*</\s*annotated\s+code\s*>\s*"
    r"\Z",
    re.DOTALL | re.IGNORECASE,
)


def extract_annotated_code(text: str) -> str:
    """Extract the annotated code body from a strict wrapper.

    Args:
        text: Model output text to parse.

    Returns:
        str: Annotated code body without wrapper tags.

    Raises:
        ValueError: If the wrapper format or header is invalid.
    """
    m = ANNOTATED_RE.match(text)
    if not m:
        head = text[:100]
        tail = text[-100:] if len(text) > 100 else text
        raise ValueError(
            "Output did not match required wrapper.\n"
            "Expected:\n<annotated code> ... </annotated code> (case-insensitive; spaces allowed)\n"
            f"Got (start 100 chars): {head!r}\n"
            "...\n"
            f"Got (end 100 chars): {tail!r}"
        )

    body = m.group("body")
    if not body.lstrip().startswith("# icontract annotated code"):
        raise ValueError("Missing required header line: '# icontract annotated code'")
    return body
