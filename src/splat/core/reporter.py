"""Main Splat error reporter class."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from splat.core.config import SplatConfig, load_config
from splat.core.dedup import generate_signature, check_duplicate
from splat.core.formatter import format_issue_title, format_issue_body
from splat.core.log_buffer import LogBuffer

logger = logging.getLogger(__name__)


class Splat:
    """
    Automatic GitHub issue creation on application crashes.

    Usage:
        splat = Splat(repo="owner/repo", token="ghp_...")

        try:
            do_something()
        except Exception as e:
            await splat.report(e)
    """

    def __init__(
        self,
        *,
        repo: str | None = None,
        token: str | None = None,
        enabled: bool | None = None,
        log_buffer_size: int | None = None,
        labels: list[str] | None = None,
    ) -> None:
        self.config = load_config(
            repo=repo,
            token=token,
            enabled=enabled,
            log_buffer_size=log_buffer_size,
            labels=labels,
        )

        # Set up log buffer
        self._log_buffer = LogBuffer(capacity=self.config.log_buffer_size)
        logging.getLogger().addHandler(self._log_buffer)

        if not self.is_enabled():
            logger.warning(
                "Splat is disabled. Set SPLAT_GITHUB_REPO and SPLAT_GITHUB_TOKEN "
                "environment variables or pass repo/token to enable."
            )

    def is_enabled(self) -> bool:
        """Check if Splat is enabled and properly configured."""
        return bool(
            self.config.enabled
            and self.config.repo
            and self.config.token
        )

    async def report(
        self,
        exception: BaseException,
        context: dict[str, Any] | None = None,
        logs: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Report an exception to GitHub Issues.

        Args:
            exception: The exception to report
            context: Optional user-provided context dict
            logs: Optional log string (uses buffered logs if not provided)

        Returns:
            Created issue data dict, or None if disabled/duplicate
        """
        if not self.is_enabled():
            return None

        assert self.config.repo is not None
        assert self.config.token is not None

        signature = generate_signature(exception)

        existing = await check_duplicate(
            repo=self.config.repo,
            token=self.config.token,
            signature=signature,
        )

        if existing is not None:
            logger.info(f"Duplicate error, issue #{existing} already exists")
            return None

        if logs is None:
            logs = self._log_buffer.get_logs_as_string()

        title = format_issue_title(exception)
        body = format_issue_body(
            exception,
            signature=signature,
            context=context,
            logs=logs,
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/repos/{self.config.repo}/issues",
                headers={
                    "Authorization": f"Bearer {self.config.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={
                    "title": title,
                    "body": body,
                    "labels": self.config.labels,
                },
            )
            response.raise_for_status()
            issue_data: dict[str, Any] = response.json()

        logger.info(f"Created issue #{issue_data['number']}: {issue_data['html_url']}")
        return issue_data
