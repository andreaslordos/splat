"""Tests for the main Splat reporter class."""

import os
from unittest.mock import patch

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

        assert result is not None
        assert result["number"] == 1
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

        assert result is None
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
