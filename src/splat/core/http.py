"""Shared HTTP client for GitHub API requests."""

from __future__ import annotations

from typing import Any

import httpx

from splat.core.config import SplatConfig


async def github_request(
    method: str,
    endpoint: str,
    config: SplatConfig,
    **kwargs: Any,
) -> httpx.Response:
    """
    Make an authenticated GitHub API request.

    Args:
        method: HTTP method (get, post, etc.)
        endpoint: API endpoint (e.g., "/repos/owner/repo/issues")
        config: SplatConfig with token, timeout, and github_api_url
        **kwargs: Additional arguments passed to httpx (json, params, etc.)

    Returns:
        httpx.Response object
    """
    url = f"{config.github_api_url}{endpoint}"

    async with httpx.AsyncClient(timeout=config.timeout) as client:
        request_method = getattr(client, method)
        response: httpx.Response = await request_method(
            url,
            headers={
                "Authorization": f"Bearer {config.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            **kwargs,
        )

    return response
