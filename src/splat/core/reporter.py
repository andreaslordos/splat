"""Main Splat error reporter class."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from splat.core.config import load_config
from splat.core.dedup import check_duplicate, generate_signature
from splat.core.formatter import format_issue_body, format_issue_title
from splat.core.log_buffer import LogBuffer
from splat.core.vercel_logs import VercelLogStore

logger = logging.getLogger(__name__)


def _mask_token(token: str | None) -> str:
    """Mask a token for safe logging."""
    if not token:
        return "None"
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


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
        vercel_secret: str | None = None,
        vercel_webhook_path: str | None = None,
        vercel_log_ttl: int | None = None,
        debug: bool | None = None,
    ) -> None:
        self.config = load_config(
            repo=repo,
            token=token,
            enabled=enabled,
            log_buffer_size=log_buffer_size,
            labels=labels,
            vercel_secret=vercel_secret,
            vercel_webhook_path=vercel_webhook_path,
            vercel_log_ttl=vercel_log_ttl,
            debug=debug,
        )

        # Set up log buffer
        self._log_buffer = LogBuffer(capacity=self.config.log_buffer_size)
        logging.getLogger().addHandler(self._log_buffer)

        # Set up Vercel log store
        self._vercel_store = VercelLogStore(ttl_seconds=self.config.vercel_log_ttl)

        # Debug logging for initialization
        if self.config.debug:
            logger.warning(
                f"[SPLAT DEBUG] Initialized with config: "
                f"repo={self.config.repo}, "
                f"token={_mask_token(self.config.token)}, "
                f"enabled={self.config.enabled}, "
                f"labels={self.config.labels}"
            )

        if not self.is_enabled():
            logger.warning(
                "Splat is disabled. Set SPLAT_GITHUB_REPO and SPLAT_GITHUB_TOKEN "
                "environment variables or pass repo/token to enable."
            )
            if self.config.debug:
                logger.warning(
                    f"[SPLAT DEBUG] is_enabled=False because: "
                    f"config.enabled={self.config.enabled}, "
                    f"config.repo={'set' if self.config.repo else 'NOT SET'}, "
                    f"config.token={'set' if self.config.token else 'NOT SET'}"
                )

    def is_enabled(self) -> bool:
        """Check if Splat is enabled and properly configured."""
        return bool(self.config.enabled and self.config.repo and self.config.token)

    async def report(
        self,
        exception: BaseException,
        context: dict[str, Any] | None = None,
        logs: str | None = None,
        vercel_request_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Report an exception to GitHub Issues.

        Args:
            exception: The exception to report
            context: Optional user-provided context dict
            logs: Optional log string (uses buffered logs if not provided)
            vercel_request_id: Optional Vercel request ID to fetch logs from store

        Returns:
            Created issue data dict, or None if disabled/duplicate
        """
        if self.config.debug:
            logger.warning(
                f"[SPLAT DEBUG] report() called with: "
                f"exception={type(exception).__name__}: {exception}, "
                f"context={context}, "
                f"vercel_request_id={vercel_request_id}"
            )

        if not self.is_enabled():
            if self.config.debug:
                logger.warning(
                    "[SPLAT DEBUG] report() returning None - splat is disabled"
                )
            return None

        assert self.config.repo is not None
        assert self.config.token is not None

        signature = generate_signature(exception)
        if self.config.debug:
            logger.warning(f"[SPLAT DEBUG] Generated signature: {signature}")

        try:
            existing = await check_duplicate(
                repo=self.config.repo,
                token=self.config.token,
                signature=signature,
            )
            if self.config.debug:
                logger.warning(f"[SPLAT DEBUG] Dedup check result: existing={existing}")
        except Exception as e:
            if self.config.debug:
                logger.warning(f"[SPLAT DEBUG] Dedup check FAILED with error: {e}")
            raise

        if existing is not None:
            logger.info(f"Duplicate error, issue #{existing} already exists")
            return None

        # Determine which logs to use
        if logs is None:
            if vercel_request_id is not None and self._vercel_store.has_logs(
                vercel_request_id
            ):
                # Use Vercel logs and remove them from store
                logs = self._vercel_store.format_logs_as_string(vercel_request_id)
                self._vercel_store.pop_logs(vercel_request_id)
                if self.config.debug:
                    logger.warning(
                        f"[SPLAT DEBUG] Using Vercel logs ({len(logs)} chars)"
                    )
            else:
                # Fall back to Python log buffer
                logs = self._log_buffer.get_logs_as_string()
                if self.config.debug:
                    logger.warning(
                        f"[SPLAT DEBUG] Using Python log buffer ({len(logs)} chars)"
                    )

        return await self._create_issue(
            exception=exception,
            signature=signature,
            context=context,
            logs=logs,
        )

    async def _create_issue(
        self,
        exception: BaseException,
        signature: str,
        context: dict[str, Any] | None,
        logs: str,
    ) -> dict[str, Any]:
        """
        Create a GitHub issue for the exception.

        Args:
            exception: The exception to report
            signature: The generated signature for deduplication
            context: Optional user-provided context dict
            logs: Log string to include in the issue

        Returns:
            Created issue data dict
        """
        assert self.config.repo is not None
        assert self.config.token is not None

        title = format_issue_title(exception)
        body = format_issue_body(
            exception,
            signature=signature,
            context=context,
            logs=logs,
        )

        if self.config.debug:
            logger.warning(
                f"[SPLAT DEBUG] Creating GitHub issue: "
                f"repo={self.config.repo}, title={title[:50]}..."
            )

        try:
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
                if self.config.debug:
                    logger.warning(
                        f"[SPLAT DEBUG] GitHub API response: "
                        f"status={response.status_code}"
                    )
                response.raise_for_status()
                issue_data: dict[str, Any] = response.json()
        except Exception as e:
            if self.config.debug:
                logger.warning(f"[SPLAT DEBUG] GitHub API call FAILED: {e}")
            raise

        logger.info(f"Created issue #{issue_data['number']}: {issue_data['html_url']}")
        return issue_data
