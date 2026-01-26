"""Tests for background error queue with retry logic."""

import asyncio
from typing import Any

import httpx
import pytest

from splat.core.queue import ErrorQueue, ErrorReport, is_retryable_error


class TestErrorReport:
    """Test ErrorReport dataclass."""

    def test_error_report_creation(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            report = ErrorReport(
                exception=e,
                context={"key": "value"},
                logs="test logs",
                signature="abc123",
            )
            assert report.exception is e
            assert report.context == {"key": "value"}
            assert report.logs == "test logs"
            assert report.signature == "abc123"
            assert report.attempt == 0


class TestIsRetryableError:
    """Test retry logic."""

    def test_rate_limit_is_retryable(self) -> None:
        response = httpx.Response(429)
        assert is_retryable_error(response) is True

    def test_server_errors_are_retryable(self) -> None:
        for status in [500, 502, 503, 504]:
            response = httpx.Response(status)
            assert is_retryable_error(response) is True

    def test_client_errors_are_not_retryable(self) -> None:
        for status in [400, 401, 403, 404, 422]:
            response = httpx.Response(status)
            assert is_retryable_error(response) is False

    def test_success_is_not_retryable(self) -> None:
        response = httpx.Response(200)
        assert is_retryable_error(response) is False


class TestErrorQueue:
    """Test background error queue."""

    @pytest.mark.asyncio
    async def test_enqueue_adds_to_queue(self) -> None:
        queue = ErrorQueue(max_retries=3, timeout=10.0)

        try:
            raise ValueError("test")
        except ValueError as e:
            report = ErrorReport(
                exception=e,
                context=None,
                logs="",
                signature="abc123",
            )
            await queue.enqueue(report)

        assert queue._queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_worker_processes_queue(self) -> None:
        queue = ErrorQueue(max_retries=3, timeout=10.0)
        processed: list[Any] = []

        async def mock_process(report: ErrorReport) -> bool:
            processed.append(report)
            return True

        queue._process_report = mock_process

        try:
            raise ValueError("test")
        except ValueError as e:
            report = ErrorReport(
                exception=e,
                context=None,
                logs="",
                signature="abc123",
            )
            await queue.enqueue(report)

        await queue.start()
        await asyncio.sleep(0.1)
        await queue.shutdown(timeout=1.0)

        assert len(processed) == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self) -> None:
        queue = ErrorQueue(max_retries=3, timeout=10.0)
        attempts: list[int] = []

        async def mock_process(report: ErrorReport) -> bool:
            attempts.append(report.attempt)
            if len(attempts) < 2:
                return False  # Fail first attempt
            return True

        queue._process_report = mock_process

        try:
            raise ValueError("test")
        except ValueError as e:
            report = ErrorReport(
                exception=e,
                context=None,
                logs="",
                signature="abc123",
            )
            await queue.enqueue(report)

        await queue.start()
        await asyncio.sleep(0.5)
        await queue.shutdown(timeout=1.0)

        assert len(attempts) >= 2

    @pytest.mark.asyncio
    async def test_drops_after_max_retries(self) -> None:
        queue = ErrorQueue(max_retries=2, timeout=10.0)
        attempts: list[int] = []

        async def mock_process(report: ErrorReport) -> bool:
            attempts.append(report.attempt)
            return False  # Always fail

        queue._process_report = mock_process

        try:
            raise ValueError("test")
        except ValueError as e:
            report = ErrorReport(
                exception=e,
                context=None,
                logs="",
                signature="abc123",
            )
            await queue.enqueue(report)

        await queue.start()
        await asyncio.sleep(1.0)
        await queue.shutdown(timeout=1.0)

        assert len(attempts) == 2
