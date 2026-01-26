"""Tests for FastAPI middleware."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from splat.middleware.fastapi import SplatMiddleware


class TestSplatMiddleware:
    """Test FastAPI Splat middleware."""

    def test_middleware_initializes_splat(self) -> None:
        mock_app = MagicMock()
        middleware = SplatMiddleware(mock_app, repo="owner/repo", token="ghp_test")
        assert middleware.splat is not None
        assert middleware.splat.config.repo == "owner/repo"

    @pytest.mark.asyncio
    async def test_middleware_passes_through_on_success(self) -> None:
        mock_app = MagicMock()

        async def call_next(request: Any) -> str:
            return "response"

        middleware = SplatMiddleware(mock_app, repo="owner/repo", token="ghp_test")

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.client.host = "127.0.0.1"

        response = await middleware.dispatch(mock_request, call_next)
        assert response == "response"

    @pytest.mark.asyncio
    async def test_middleware_reports_errors(self) -> None:
        mock_app = MagicMock()

        async def call_next(request: Any) -> None:
            raise ValueError("test error")

        middleware = SplatMiddleware(mock_app, repo="owner/repo", token="ghp_test")
        middleware.splat.report = AsyncMock(return_value={"number": 1})

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.client.host = "127.0.0.1"

        with pytest.raises(ValueError):
            await middleware.dispatch(mock_request, call_next)

        middleware.splat.report.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_includes_request_context(self) -> None:
        mock_app = MagicMock()

        async def call_next(request: Any) -> None:
            raise ValueError("test")

        middleware = SplatMiddleware(mock_app, repo="owner/repo", token="ghp_test")
        middleware.splat.report = AsyncMock(return_value={"number": 1})

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/api/checkout"
        mock_request.client.host = "192.168.1.1"

        with pytest.raises(ValueError):
            await middleware.dispatch(mock_request, call_next)

        call_kwargs = middleware.splat.report.call_args[1]
        context = call_kwargs["context"]
        assert context["method"] == "POST"
        assert context["path"] == "/api/checkout"


class TestSplatMiddlewareClientHandling:
    """Test middleware client IP handling edge cases."""

    @pytest.mark.asyncio
    async def test_middleware_handles_none_client(self) -> None:
        """Test middleware handles request with no client info."""
        mock_app = MagicMock()

        async def call_next(request: Any) -> None:
            raise ValueError("test")

        middleware = SplatMiddleware(mock_app, repo="owner/repo", token="ghp_test")
        middleware.splat.report = AsyncMock(return_value={"number": 1})

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.client = None

        with pytest.raises(ValueError):
            await middleware.dispatch(mock_request, call_next)

        call_kwargs = middleware.splat.report.call_args[1]
        context = call_kwargs["context"]
        assert context["client"] == "unknown"

    @pytest.mark.asyncio
    async def test_middleware_handles_client_without_host(self) -> None:
        """Test middleware handles client object without host attribute."""
        mock_app = MagicMock()

        async def call_next(request: Any) -> None:
            raise ValueError("test")

        middleware = SplatMiddleware(mock_app, repo="owner/repo", token="ghp_test")
        middleware.splat.report = AsyncMock(return_value={"number": 1})

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.client = MagicMock(spec=[])  # No host attribute

        with pytest.raises(ValueError):
            await middleware.dispatch(mock_request, call_next)

        call_kwargs = middleware.splat.report.call_args[1]
        context = call_kwargs["context"]
        assert context["client"] == "unknown"


class TestSplatMiddlewareASGI:
    """Test ASGI interface of the middleware."""

    @pytest.mark.asyncio
    async def test_call_passes_through_non_http_requests(self) -> None:
        """Test middleware passes through websocket/lifespan requests."""
        mock_app = AsyncMock()
        middleware = SplatMiddleware(mock_app, repo="owner/repo", token="ghp_test")

        scope = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        mock_app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_call_handles_http_requests(self) -> None:
        """Test middleware handles HTTP requests via dispatch."""
        mock_app = AsyncMock()
        middleware = SplatMiddleware(mock_app, repo="owner/repo", token="ghp_test")

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
            "server": ("localhost", 8000),
        }
        receive = AsyncMock()
        send = AsyncMock()

        # This will call the app since there's no error
        await middleware(scope, receive, send)
        mock_app.assert_called_once()
