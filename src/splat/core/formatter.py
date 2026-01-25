"""GitHub issue formatting for error reports."""

from __future__ import annotations

import traceback
from typing import Any


def format_issue_title(exception: BaseException) -> str:
    """
    Format the GitHub issue title.

    Format: [Splat] {ExceptionType} in {filename}:{line}

    Args:
        exception: The exception to format

    Returns:
        Formatted issue title
    """
    exc_type = type(exception).__name__

    # Extract location from traceback
    filename = "unknown"
    lineno = 0

    tb = exception.__traceback__
    if tb is not None:
        while tb.tb_next is not None:
            tb = tb.tb_next
        filename = tb.tb_frame.f_code.co_filename.split("/")[-1]
        lineno = tb.tb_lineno

    return f"[Splat] {exc_type} in {filename}:{lineno}"


def format_issue_body(
    exception: BaseException,
    signature: str,
    context: dict[str, Any] | None = None,
    logs: str | None = None,
) -> str:
    """
    Format the GitHub issue body with full error details.

    Args:
        exception: The exception to format
        signature: Error signature for deduplication
        context: Optional user-provided context dict
        logs: Optional log string

    Returns:
        Formatted Markdown issue body
    """
    exc_type = type(exception).__name__
    exc_msg = str(exception)

    # Extract location from traceback
    filename = "unknown"
    lineno = 0
    funcname = "unknown"

    tb = exception.__traceback__
    if tb is not None:
        while tb.tb_next is not None:
            tb = tb.tb_next
        frame = tb.tb_frame
        filename = frame.f_code.co_filename
        lineno = tb.tb_lineno
        funcname = frame.f_code.co_name

    # Format traceback
    tb_str = "".join(
        traceback.format_exception(
            type(exception), exception, exception.__traceback__
        )
    )

    # Build body sections
    sections = []

    # Error section
    sections.append(
        f"""## Error

**Type:** {exc_type}
**Message:** {exc_msg}
**File:** {filename}
**Line:** {lineno}
**Function:** {funcname}"""
    )

    # Traceback section
    sections.append(
        f"""## Traceback

```
{tb_str.strip()}
```"""
    )

    # Context section (if provided)
    if context:
        context_rows = "\n".join(f"| {k} | {v} |" for k, v in context.items())
        sections.append(
            f"""## Context

| Key | Value |
|-----|-------|
{context_rows}"""
        )

    # Logs section (if provided and non-empty)
    if logs:
        sections.append(
            f"""## Recent Logs

<details>
<summary>Recent log entries</summary>

```
{logs}
```

</details>"""
        )

    # Footer with signature
    sections.append(
        f"""---
Signature: `{signature}`
Reported by [Splat](https://github.com/yourorg/splat)"""
    )

    return "\n\n".join(sections)
