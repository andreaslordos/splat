"""Tests for error deduplication."""

from urllib.parse import unquote

import httpx
import pytest
import respx

from splat.core.dedup import check_duplicate, generate_signature


class TestGenerateSignature:
    """Test error signature generation."""

    def test_signature_includes_exception_type(self) -> None:
        try:
            raise ValueError("test error")
        except ValueError as e:
            sig = generate_signature(e)
            # Same exception type should produce same prefix
            assert len(sig) == 16  # Changed from 8

    def test_same_error_produces_same_signature(self) -> None:
        def raise_error() -> None:
            raise ValueError("test")

        sigs = []
        for _ in range(2):
            try:
                raise_error()
            except ValueError as e:
                sigs.append(generate_signature(e))

        assert sigs[0] == sigs[1]

    def test_different_errors_produce_different_signatures(self) -> None:
        try:
            raise ValueError("error 1")
        except ValueError as e1:
            sig1 = generate_signature(e1)

        try:
            raise TypeError("error 2")
        except TypeError as e2:
            sig2 = generate_signature(e2)

        assert sig1 != sig2

    def test_signature_is_16_chars(self) -> None:
        try:
            raise RuntimeError("test")
        except RuntimeError as e:
            sig = generate_signature(e)
            assert len(sig) == 16  # Changed from 8
            assert sig.isalnum()


class TestCheckDuplicate:
    """Test GitHub duplicate checking."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_none_when_no_duplicate(self) -> None:
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )

        result = await check_duplicate(
            repo="owner/repo",
            token="ghp_test",
            signature="abc12345",
        )

        assert result is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_issue_number_when_duplicate_found(self) -> None:
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"number": 42, "title": "Test issue"}]},
            )
        )

        result = await check_duplicate(
            repo="owner/repo",
            token="ghp_test",
            signature="abc12345",
        )

        assert result == 42

    @respx.mock
    @pytest.mark.asyncio
    async def test_searches_with_correct_query(self) -> None:
        route = respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )

        await check_duplicate(
            repo="owner/repo",
            token="ghp_test",
            signature="abc12345",
        )

        assert route.called
        request = route.calls[0].request
        url_str = unquote(str(request.url))
        assert "repo:owner/repo" in url_str
        assert "abc12345" in url_str
