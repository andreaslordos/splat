"""Main Splat error reporter class."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from splat.core.config import load_config
from splat.core.dedup import check_duplicate, generate_signature
from splat.core.formatter import format_issue_body, format_issue_title
from splat.core.http import github_request
from splat.core.log_buffer import LogBuffer
from splat.core.queue import ErrorQueue, ErrorReport

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
        debug: bool | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        github_api_url: str | None = None,
        ignore_exceptions: list[type] | None = None,
        exception_filter: Any | None = None,
        max_traceback_length: int | None = None,
        max_log_entries: int | None = None,
        max_context_value_length: int | None = None,
    ) -> None:
        self.config = load_config(
            repo=repo,
            token=token,
            enabled=enabled,
            log_buffer_size=log_buffer_size,
            labels=labels,
            debug=debug,
            timeout=timeout,
            max_retries=max_retries,
            github_api_url=github_api_url,
            ignore_exceptions=ignore_exceptions,
            exception_filter=exception_filter,
            max_traceback_length=max_traceback_length,
            max_log_entries=max_log_entries,
            max_context_value_length=max_context_value_length,
        )

        # Set up log buffer
        self._log_buffer = LogBuffer(capacity=self.config.log_buffer_size)
        logging.getLogger().addHandler(self._log_buffer)

        # Set up background queue
        self._queue = ErrorQueue(
            max_retries=self.config.max_retries,
            timeout=self.config.timeout,
        )
        self._queue._process_report = self._process_report
        self._queue_started = False

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

    def _should_report(self, exception: BaseException) -> bool:
        """Check if this exception should be reported."""
        # Callback takes precedence
        if self.config.exception_filter is not None:
            return self.config.exception_filter(exception)

        # Check ignore list
        for exc_type in self.config.ignore_exceptions:
            if isinstance(exception, exc_type):
                if self.config.debug:
                    logger.warning(
                        f"[SPLAT DEBUG] Ignoring {type(exception).__name__} "
                        f"(in ignore_exceptions list)"
                    )
                return False

        return True

    async def _ensure_queue_started(self) -> None:
        """Start the queue worker if not already started."""
        if not self._queue_started:
            await self._queue.start()
            self._queue_started = True

    async def report(
        self,
        exception: BaseException,
        context: dict[str, Any] | None = None,
        logs: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Report an exception to GitHub Issues (non-blocking).

        The error is queued for background processing with retries.

        Args:
            exception: The exception to report
            context: Optional user-provided context dict
            logs: Optional log string (uses buffered logs if not provided)

        Returns:
            None (reporting happens asynchronously)
        """
        if self.config.debug:
            logger.warning(
                f"[SPLAT DEBUG] report() called with: "
                f"exception={type(exception).__name__}: {exception}, "
                f"context={context}"
            )

        if not self.is_enabled():
            if self.config.debug:
                logger.warning(
                    "[SPLAT DEBUG] report() returning None - splat is disabled"
                )
            return None

        if not self._should_report(exception):
            return None

        # Get logs before queuing
        if logs is None:
            logs = self._log_buffer.get_logs_as_string()
            if self.config.debug:
                logger.warning(f"[SPLAT DEBUG] Using log buffer ({len(logs)} chars)")

        signature = generate_signature(exception)
        if self.config.debug:
            logger.warning(f"[SPLAT DEBUG] Generated signature: {signature}")

        report = ErrorReport(
            exception=exception,
            context=context,
            logs=logs,
            signature=signature,
        )

        await self._ensure_queue_started()
        await self._queue.enqueue(report)

        return None  # Async processing, no immediate result

    def report_sync(
        self,
        exception: BaseException,
        context: dict[str, Any] | None = None,
        logs: str | None = None,
    ) -> None:
        """
        Synchronous wrapper for report().

        Queues the error for background processing without blocking.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.report(exception, context, logs))
            else:
                loop.run_until_complete(self.report(exception, context, logs))
        except RuntimeError:
            asyncio.run(self.report(exception, context, logs))

    async def _process_report(self, report: ErrorReport) -> bool:
        """
        Process a queued error report.

        Returns:
            True if successful, False if should retry
        """
        assert self.config.repo is not None
        assert self.config.token is not None

        try:
            # Check for duplicate
            existing = await check_duplicate(
                repo=self.config.repo,
                token=self.config.token,
                signature=report.signature,
                config=self.config,
            )
            if self.config.debug:
                logger.warning(f"[SPLAT DEBUG] Dedup check result: existing={existing}")

            if existing is not None:
                logger.info(f"Duplicate error, issue #{existing} already exists")
                return True  # Success (no need to retry)

            # Create issue
            await self._create_issue(report)
            return True

        except Exception as e:
            if self.config.debug:
                logger.warning(f"[SPLAT DEBUG] Report processing failed: {e}")
            return False

    async def _create_issue(self, report: ErrorReport) -> dict[str, Any]:
        """Create a GitHub issue for the error report."""
        assert self.config.repo is not None

        title = format_issue_title(report.exception)
        body = format_issue_body(
            report.exception,
            signature=report.signature,
            context=report.context,
            logs=report.logs,
            max_traceback_length=self.config.max_traceback_length,
            max_log_entries=self.config.max_log_entries,
            max_context_value_length=self.config.max_context_value_length,
        )

        if self.config.debug:
            logger.warning(
                f"[SPLAT DEBUG] Creating GitHub issue: "
                f"repo={self.config.repo}, title={title[:50]}..."
            )

        response = await github_request(
            "post",
            f"/repos/{self.config.repo}/issues",
            self.config,
            json={
                "title": title,
                "body": body,
                "labels": self.config.labels,
            },
        )
        if self.config.debug:
            logger.warning(
                f"[SPLAT DEBUG] GitHub API response: status={response.status_code}"
            )
        response.raise_for_status()
        issue_data: dict[str, Any] = response.json()

        logger.info(f"Created issue #{issue_data['number']}: {issue_data['html_url']}")
        return issue_data

    async def shutdown(self, timeout: float = 5.0) -> None:
        """Gracefully shutdown the background queue."""
        if self._queue_started:
            await self._queue.shutdown(timeout=timeout)
