"""Tests for Django middleware."""

from unittest.mock import MagicMock, patch

import pytest


class TestDjangoMiddleware:
    """Test Django Splat middleware."""

    def test_middleware_initializes_splat(self) -> None:
        with patch.dict("sys.modules", {"django.conf": MagicMock()}):
            from splat.middleware.django import SplatMiddleware

            mock_settings = MagicMock()
            mock_settings.SPLAT = {"repo": "owner/repo", "token": "ghp_test"}

            with patch("splat.middleware.django.settings", mock_settings):
                middleware = SplatMiddleware(get_response=lambda r: r)
                assert middleware.splat is not None
                assert middleware.splat.config.repo == "owner/repo"

    def test_middleware_passes_through_on_success(self) -> None:
        with patch.dict("sys.modules", {"django.conf": MagicMock()}):
            from splat.middleware.django import SplatMiddleware

            mock_settings = MagicMock()
            mock_settings.SPLAT = {"repo": "owner/repo", "token": "ghp_test"}

            with patch("splat.middleware.django.settings", mock_settings):
                response = MagicMock()
                get_response = MagicMock(return_value=response)
                middleware = SplatMiddleware(get_response=get_response)

                request = MagicMock()
                result = middleware(request)

                assert result == response
                get_response.assert_called_once_with(request)

    def test_middleware_reports_error_and_reraises(self) -> None:
        with patch.dict("sys.modules", {"django.conf": MagicMock()}):
            from splat.middleware.django import SplatMiddleware

            mock_settings = MagicMock()
            mock_settings.SPLAT = {"repo": "owner/repo", "token": "ghp_test"}

            with patch("splat.middleware.django.settings", mock_settings):
                error = ValueError("test error")
                get_response = MagicMock(side_effect=error)
                middleware = SplatMiddleware(get_response=get_response)
                middleware.splat.report_sync = MagicMock()

                request = MagicMock()
                request.method = "GET"
                request.path = "/test"
                request.META = {"REMOTE_ADDR": "127.0.0.1"}

                with pytest.raises(ValueError, match="test error"):
                    middleware(request)

                middleware.splat.report_sync.assert_called_once()

    def test_middleware_extracts_request_context(self) -> None:
        with patch.dict("sys.modules", {"django.conf": MagicMock()}):
            from splat.middleware.django import SplatMiddleware

            mock_settings = MagicMock()
            mock_settings.SPLAT = {"repo": "owner/repo", "token": "ghp_test"}

            with patch("splat.middleware.django.settings", mock_settings):
                error = ValueError("test")
                get_response = MagicMock(side_effect=error)
                middleware = SplatMiddleware(get_response=get_response)
                middleware.splat.report_sync = MagicMock()

                request = MagicMock()
                request.method = "POST"
                request.path = "/api/users"
                request.META = {"REMOTE_ADDR": "192.168.1.1"}

                with pytest.raises(ValueError):
                    middleware(request)

                call_args = middleware.splat.report_sync.call_args
                context = call_args[1]["context"]
                assert context["method"] == "POST"
                assert context["path"] == "/api/users"
                assert context["remote_addr"] == "192.168.1.1"
