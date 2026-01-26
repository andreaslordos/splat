"""Tests for the main Splat reporter class."""

from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from splat.core.reporter import Splat


class TestSplatInit:
    """Test Splat initialization."""

    def test_init_with_explicit_args(self) -> None:
        splat = Splat(repo="owner/repo", token="ghp_test")
        assert splat.config.repo == "owner/repo"
        assert splat.config.token == "ghp_test"

    def test_init_loads_from_env(self) -> None:
        with patch("splat.core.config._find_pyproject", return_value=None):
            with patch.dict(
                os.environ,
                {
                    "SPLAT_GITHUB_REPO": "env/repo",
                    "SPLAT_GITHUB_TOKEN": "ghp_env",
                },
            ):
                splat = Splat()
                assert splat.config.repo == "env/repo"
                assert splat.config.token == "ghp_env"

    def test_init_installs_log_buffer(self) -> None:
        splat = Splat(repo="owner/repo", token="ghp_test")
        assert splat._log_buffer is not None


class TestSplatEnabled:
    """Test enabled/disabled behavior."""

    def test_is_enabled_when_configured(self) -> None:
        splat = Splat(repo="owner/repo", token="ghp_test")
        assert splat.is_enabled() is True

    def test_is_disabled_when_missing_repo(self) -> None:
        with patch("splat.core.config._find_pyproject", return_value=None):
            splat = Splat(token="ghp_test")
            assert splat.is_enabled() is False

    def test_is_disabled_when_missing_token(self) -> None:
        splat = Splat(repo="owner/repo")
        assert splat.is_enabled() is False

    def test_is_disabled_when_enabled_false(self) -> None:
        splat = Splat(repo="owner/repo", token="ghp_test", enabled=False)
        assert splat.is_enabled() is False


class TestSplatReport:
    """Test error reporting."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_creates_github_issue(self) -> None:
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        create_route = respx.post(
            "https://api.github.com/repos/owner/repo/issues"
        ).mock(
            return_value=httpx.Response(
                201,
                json={
                    "number": 1,
                    "html_url": "https://github.com/owner/repo/issues/1",
                },
            )
        )

        splat = Splat(repo="owner/repo", token="ghp_test")

        try:
            raise ValueError("test error")
        except ValueError as e:
            result = await splat.report(e)

        # report() now returns None immediately (async processing)
        assert result is None

        # Wait for queue to process
        await asyncio.sleep(0.1)
        await splat.shutdown(timeout=1.0)

        assert create_route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_skips_duplicate(self) -> None:
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": [{"number": 42}]})
        )
        create_route = respx.post(
            "https://api.github.com/repos/owner/repo/issues"
        ).mock(return_value=httpx.Response(201, json={}))

        splat = Splat(repo="owner/repo", token="ghp_test")

        try:
            raise ValueError("test error")
        except ValueError as e:
            result = await splat.report(e)

        # report() now returns None immediately (async processing)
        assert result is None

        # Wait for queue to process
        await asyncio.sleep(0.1)
        await splat.shutdown(timeout=1.0)

        # Issue creation should not be called for duplicates
        assert not create_route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_includes_context(self) -> None:
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        create_route = respx.post(
            "https://api.github.com/repos/owner/repo/issues"
        ).mock(return_value=httpx.Response(201, json={"number": 1, "html_url": "url"}))

        splat = Splat(repo="owner/repo", token="ghp_test")

        try:
            raise ValueError("test")
        except ValueError as e:
            await splat.report(e, context={"user_id": 123})

        # Wait for queue to process
        await asyncio.sleep(0.1)
        await splat.shutdown(timeout=1.0)

        assert create_route.called
        request_body = create_route.calls[0].request.content.decode()
        assert "user_id" in request_body

    @pytest.mark.asyncio
    async def test_report_does_nothing_when_disabled(self) -> None:
        splat = Splat(repo="owner/repo", token="ghp_test", enabled=False)

        try:
            raise ValueError("test")
        except ValueError as e:
            result = await splat.report(e)

        assert result is None

    @pytest.mark.asyncio
    async def test_report_queues_error_for_background_processing(self) -> None:
        """Test that report() queues the error instead of processing immediately."""
        splat = Splat(repo="owner/repo", token="ghp_test")
        reports: list[Any] = []
        splat._queue.enqueue = AsyncMock(side_effect=lambda r: reports.append(r))

        try:
            raise ValueError("test error")
        except ValueError as e:
            await splat.report(e, context={"key": "value"})

        assert len(reports) == 1
        assert isinstance(reports[0].exception, ValueError)
        assert reports[0].context == {"key": "value"}


class TestExceptionFiltering:
    """Test exception filtering."""

    @pytest.mark.asyncio
    async def test_ignores_exception_in_ignore_list(self) -> None:
        splat = Splat(
            repo="owner/repo",
            token="ghp_test",
            ignore_exceptions=[ValueError],
        )

        try:
            raise ValueError("ignored")
        except ValueError as e:
            result = await splat.report(e)

        assert result is None

    @pytest.mark.asyncio
    async def test_reports_exception_not_in_ignore_list(self) -> None:
        splat = Splat(
            repo="owner/repo",
            token="ghp_test",
            ignore_exceptions=[TypeError],
        )
        reports: list[Any] = []
        splat._queue.enqueue = AsyncMock(side_effect=lambda r: reports.append(r))

        try:
            raise ValueError("not ignored")
        except ValueError as e:
            await splat.report(e)

        assert len(reports) == 1

    @pytest.mark.asyncio
    async def test_exception_filter_callback_can_skip(self) -> None:
        def skip_value_errors(e: BaseException) -> bool:
            return not isinstance(e, ValueError)

        splat = Splat(
            repo="owner/repo",
            token="ghp_test",
            exception_filter=skip_value_errors,
        )

        try:
            raise ValueError("filtered out")
        except ValueError as e:
            result = await splat.report(e)

        assert result is None

    @pytest.mark.asyncio
    async def test_exception_filter_callback_takes_precedence(self) -> None:
        def allow_all(e: BaseException) -> bool:
            return True

        splat = Splat(
            repo="owner/repo",
            token="ghp_test",
            ignore_exceptions=[ValueError],
            exception_filter=allow_all,
        )
        reports: list[Any] = []
        splat._queue.enqueue = AsyncMock(side_effect=lambda r: reports.append(r))

        try:
            raise ValueError("allowed by callback")
        except ValueError as e:
            await splat.report(e)

        assert len(reports) == 1
