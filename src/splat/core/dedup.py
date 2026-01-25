"""Error deduplication via signature generation and GitHub search."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any, cast

import httpx

if TYPE_CHECKING:
    from types import TracebackType


def generate_signature(
    exception: BaseException,
    tb: TracebackType | None = None,
) -> str:
    """
    Generate a unique signature for an exception.

    The signature is based on:
    - Exception type name
    - Source file path
    - Line number
    - Function name

    Args:
        exception: The exception to generate a signature for
        tb: Optional traceback (uses exception's __traceback__ if not provided)

    Returns:
        8-character hex signature
    """
    if tb is None:
        tb = exception.__traceback__

    # Extract location info from traceback
    filename = "unknown"
    lineno = 0
    funcname = "unknown"

    if tb is not None:
        # Get the innermost frame (where the exception was raised)
        while tb.tb_next is not None:
            tb = tb.tb_next

        frame = tb.tb_frame
        filename = frame.f_code.co_filename
        lineno = tb.tb_lineno
        funcname = frame.f_code.co_name

    # Build signature components
    components = [
        type(exception).__name__,
        filename,
        str(lineno),
        funcname,
    ]

    # Hash to 8 chars
    signature_str = "|".join(components)
    hash_bytes = hashlib.md5(signature_str.encode()).hexdigest()
    return hash_bytes[:8]


async def check_duplicate(
    repo: str,
    token: str,
    signature: str,
) -> int | None:
    """
    Check if an issue with this signature already exists on GitHub.

    Args:
        repo: GitHub repository (owner/repo format)
        token: GitHub API token
        signature: Error signature to search for

    Returns:
        Issue number if duplicate found, None otherwise
    """
    query = f"repo:{repo} label:splat {signature} in:body"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/search/issues",
            params={"q": query},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()

    items: list[dict[str, Any]] = data.get("items", [])
    if items:
        return cast(int, items[0]["number"])

    return None
