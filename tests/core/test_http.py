"""Tests for shared HTTP client."""

import httpx
import pytest
import respx

from splat.core.config import SplatConfig
from splat.core.http import github_request


class TestGithubRequest:
    """Test GitHub API request helper."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_makes_get_request(self) -> None:
        config = SplatConfig(
            repo="owner/repo",
            token="ghp_test",
            timeout=10.0,
        )
        route = respx.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(200, json={"id": 123})
        )

        response = await github_request("get", "/repos/owner/repo", config)

        assert route.called
        assert response.status_code == 200

    @respx.mock
    @pytest.mark.asyncio
    async def test_makes_post_request_with_json(self) -> None:
        config = SplatConfig(
            repo="owner/repo",
            token="ghp_test",
        )
        route = respx.post("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(201, json={"number": 1})
        )

        response = await github_request(
            "post",
            "/repos/owner/repo/issues",
            config,
            json={"title": "Test"},
        )

        assert route.called
        assert response.status_code == 201

    @respx.mock
    @pytest.mark.asyncio
    async def test_uses_bearer_token(self) -> None:
        config = SplatConfig(token="ghp_secret")
        route = respx.get("https://api.github.com/test").mock(
            return_value=httpx.Response(200)
        )

        await github_request("get", "/test", config)

        request = route.calls[0].request
        assert request.headers["Authorization"] == "Bearer ghp_secret"

    @respx.mock
    @pytest.mark.asyncio
    async def test_uses_custom_api_url(self) -> None:
        config = SplatConfig(
            token="ghp_test",
            github_api_url="https://github.example.com/api/v3",
        )
        route = respx.get("https://github.example.com/api/v3/test").mock(
            return_value=httpx.Response(200)
        )

        await github_request("get", "/test", config)

        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_uses_configured_timeout(self) -> None:
        config = SplatConfig(token="ghp_test", timeout=5.0)
        respx.get("https://api.github.com/test").mock(return_value=httpx.Response(200))

        response = await github_request("get", "/test", config)
        assert response.status_code == 200
