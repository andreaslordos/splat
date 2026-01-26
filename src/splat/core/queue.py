"""Background error queue with retry logic."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ErrorReport:
    """An error report queued for submission."""

    exception: BaseException
    context: dict[str, Any] | None
    logs: str
    signature: str
    attempt: int = 0


def is_retryable_error(response: httpx.Response) -> bool:
    """Check if an HTTP response indicates a retryable error."""
    return response.status_code in {429, 500, 502, 503, 504}


def get_retry_delay(attempt: int, response: httpx.Response | None = None) -> float:
    """
    Calculate retry delay with exponential backoff.

    Args:
        attempt: Current attempt number (0-indexed)
        response: Optional response to check for Retry-After header

    Returns:
        Delay in seconds
    """
    if response is not None and response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

    # Exponential backoff: 1s, 2s, 4s, ...
    return float(2**attempt)


class ErrorQueue:
    """
    Async queue for background error reporting with retries.

    Errors are queued and processed by a background worker task.
    Failed reports are retried with exponential backoff.
    """

    def __init__(
        self,
        max_retries: int = 3,
        timeout: float = 30.0,
    ) -> None:
        self._queue: asyncio.Queue[ErrorReport] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._shutdown = False
        self._max_retries = max_retries
        self._timeout = timeout
        self._process_report: Callable[[ErrorReport], Awaitable[bool]] | None = None

    async def start(self) -> None:
        """Start the background worker task."""
        self._shutdown = False
        self._worker_task = asyncio.create_task(self._worker())

    async def enqueue(self, report: ErrorReport) -> None:
        """Add an error report to the queue."""
        await self._queue.put(report)

    async def shutdown(self, timeout: float = 5.0) -> None:
        """Gracefully shutdown the queue."""
        self._shutdown = True

        if self._worker_task is not None:
            try:
                await asyncio.wait_for(self._worker_task, timeout=timeout)
            except asyncio.TimeoutError:
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass

    async def _worker(self) -> None:
        """Process queued error reports."""
        while not self._shutdown or not self._queue.empty():
            try:
                report = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=0.1,
                )
            except asyncio.TimeoutError:
                continue

            await self._process_with_retry(report)
            self._queue.task_done()

    async def _process_with_retry(self, report: ErrorReport) -> None:
        """Process a report with retry logic."""
        while report.attempt < self._max_retries:
            if self._process_report is not None:
                success = await self._process_report(report)
            else:
                success = True

            if success:
                return

            report.attempt += 1
            if report.attempt < self._max_retries:
                delay = get_retry_delay(report.attempt - 1)
                logger.warning(
                    f"[SPLAT] Report failed, retrying in {delay}s "
                    f"(attempt {report.attempt}/{self._max_retries})"
                )
                await asyncio.sleep(delay)

        logger.warning(
            f"[SPLAT] Report dropped after {self._max_retries} attempts: "
            f"{type(report.exception).__name__}"
        )
