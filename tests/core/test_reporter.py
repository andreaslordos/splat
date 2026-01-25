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


class TestSplatVercelLogStore:
    """Test Vercel log store integration."""

    def test_init_creates_vercel_store(self) -> None:
        """Splat initializes a VercelLogStore on creation."""
        splat = Splat(repo="owner/repo", token="ghp_test")
        assert hasattr(splat, "_vercel_store")
        from splat.core.vercel_logs import VercelLogStore

        assert isinstance(splat._vercel_store, VercelLogStore)

    def test_vercel_store_uses_config_ttl(self) -> None:
        """VercelLogStore uses TTL from config."""
        splat = Splat(repo="owner/repo", token="ghp_test", vercel_log_ttl=120)
        assert splat._vercel_store._ttl_seconds == 120

    def test_init_accepts_vercel_config_kwargs(self) -> None:
        """Splat __init__ accepts Vercel config kwargs."""
        splat = Splat(
            repo="owner/repo",
            token="ghp_test",
            vercel_secret="test_secret",
            vercel_webhook_path="/custom/path",
            vercel_log_ttl=90,
        )
        assert splat.config.vercel_secret == "test_secret"
        assert splat.config.vercel_webhook_path == "/custom/path"
        assert splat.config.vercel_log_ttl == 90


class TestSplatReportVercelLogs:
    """Test report() with Vercel logs."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_uses_vercel_logs_when_request_id_provided(self) -> None:
        """report() uses Vercel logs when request_id is provided and has logs."""
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        create_route = respx.post(
            "https://api.github.com/repos/owner/repo/issues"
        ).mock(return_value=httpx.Response(201, json={"number": 1, "html_url": "url"}))

        splat = Splat(repo="owner/repo", token="ghp_test")

        # Add logs to Vercel store
        splat._vercel_store.add_logs(
            [
                {
                    "requestId": "req-123",
                    "message": "Vercel log entry",
                    "level": "error",
                    "timestamp": 1700000000000,
                }
            ]
        )

        try:
            raise ValueError("test error")
        except ValueError as e:
            result = await splat.report(e, vercel_request_id="req-123")

        assert result is not None
        request_body = create_route.calls[0].request.content.decode()
        assert "Vercel log entry" in request_body

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_falls_back_to_python_logs_without_request_id(self) -> None:
        """report() uses Python logs when no vercel_request_id provided."""
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        create_route = respx.post(
            "https://api.github.com/repos/owner/repo/issues"
        ).mock(return_value=httpx.Response(201, json={"number": 1, "html_url": "url"}))

        splat = Splat(repo="owner/repo", token="ghp_test")

        # Add Vercel logs (should NOT be used)
        splat._vercel_store.add_logs(
            [
                {
                    "requestId": "req-123",
                    "message": "Vercel log entry",
                    "level": "error",
                    "timestamp": 1700000000000,
                }
            ]
        )

        try:
            raise ValueError("test error")
        except ValueError as e:
            # No vercel_request_id provided
            result = await splat.report(e)

        assert result is not None
        request_body = create_route.calls[0].request.content.decode()
        # Vercel logs should NOT be included when no request_id
        assert "Vercel log entry" not in request_body

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_falls_back_when_request_id_has_no_logs(self) -> None:
        """report() falls back to Python logs when request_id has no logs."""
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        create_route = respx.post(
            "https://api.github.com/repos/owner/repo/issues"
        ).mock(return_value=httpx.Response(201, json={"number": 1, "html_url": "url"}))

        splat = Splat(repo="owner/repo", token="ghp_test")

        # Add logs for different request ID
        splat._vercel_store.add_logs(
            [
                {
                    "requestId": "other-req",
                    "message": "Other log",
                    "level": "info",
                    "timestamp": 1700000000000,
                }
            ]
        )

        try:
            raise ValueError("test error")
        except ValueError as e:
            # Request ID with no logs
            result = await splat.report(e, vercel_request_id="nonexistent-req")

        assert result is not None
        request_body = create_route.calls[0].request.content.decode()
        # Should NOT contain Vercel logs for nonexistent request
        assert "Other log" not in request_body

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_pops_vercel_logs_after_use(self) -> None:
        """report() removes Vercel logs from store after using them."""
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        respx.post("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(201, json={"number": 1, "html_url": "url"})
        )

        splat = Splat(repo="owner/repo", token="ghp_test")

        # Add logs to Vercel store
        splat._vercel_store.add_logs(
            [
                {
                    "requestId": "req-123",
                    "message": "Vercel log entry",
                    "level": "error",
                    "timestamp": 1700000000000,
                }
            ]
        )

        # Verify logs exist before report
        assert splat._vercel_store.has_logs("req-123")

        try:
            raise ValueError("test error")
        except ValueError as e:
            await splat.report(e, vercel_request_id="req-123")

        # Logs should be removed after report
        assert not splat._vercel_store.has_logs("req-123")
