"""GitHub issue formatting for error reports."""

from __future__ import annotations

import traceback
from typing import Any


def _truncate(text: str, max_length: int, suffix: str = "\n... [truncated]") -> str:
    """Truncate text with indicator if over limit."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def _truncate_logs(logs: str, max_entries: int) -> str:
    """Truncate logs to max entries, keeping most recent."""
    lines = logs.split("\n")
    if len(lines) <= max_entries:
        return logs
    truncated_count = len(lines) - max_entries
    kept_lines = lines[-max_entries:]
    prefix = f"... [{truncated_count} earlier entries truncated]\n"
    return prefix + "\n".join(kept_lines)


def _extract_traceback_info(exception: BaseException) -> tuple[str, int, str]:
    """Extract filename, line number, and function name from exception traceback."""
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

    return filename, lineno, funcname


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
    filename, lineno, _ = _extract_traceback_info(exception)
    # Use only the filename (not full path) for the title
    short_filename = filename.split("/")[-1]

    return f"[Splat] {exc_type} in {short_filename}:{lineno}"


def format_issue_body(
    exception: BaseException,
    signature: str,
    context: dict[str, Any] | None = None,
    logs: str | None = None,
    *,
    max_traceback_length: int = 50000,
    max_log_entries: int = 500,
    max_context_value_length: int = 5000,
) -> str:
    """
    Format the GitHub issue body with full error details.

    Args:
        exception: The exception to format
        signature: Error signature for deduplication
        context: Optional user-provided context dict
        logs: Optional log string
        max_traceback_length: Maximum length for traceback (default 50000)
        max_log_entries: Maximum number of log entries to keep (default 500)
        max_context_value_length: Maximum length for context values (default 5000)

    Returns:
        Formatted Markdown issue body
    """
    exc_type = type(exception).__name__
    exc_msg = str(exception)
    filename, lineno, funcname = _extract_traceback_info(exception)

    # Format traceback
    tb_str = "".join(
        traceback.format_exception(type(exception), exception, exception.__traceback__)
    )
    tb_str = _truncate(tb_str, max_traceback_length)

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
        truncated_context = {
            k: _truncate(str(v), max_context_value_length) for k, v in context.items()
        }
        context_rows = "\n".join(f"| {k} | {v} |" for k, v in truncated_context.items())
        sections.append(
            f"""## Context

| Key | Value |
|-----|-------|
{context_rows}"""
        )

    # Logs section (if provided and non-empty)
    if logs:
        truncated_logs = _truncate_logs(logs, max_log_entries)
        sections.append(
            f"""## Recent Logs

<details>
<summary>Recent log entries</summary>

```
{truncated_logs}
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
