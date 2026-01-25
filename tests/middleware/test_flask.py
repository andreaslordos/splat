"""Tests for Flask middleware."""

from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from splat.middleware.flask import create_error_handler, SplatFlask


class TestCreateErrorHandler:
    """Test Flask error handler creation."""

    def test_creates_callable_handler(self) -> None:
        handler = create_error_handler()
        assert callable(handler)

    def test_handler_calls_splat_report(self) -> None:
        mock_splat = MagicMock()
        mock_splat.report = AsyncMock(return_value={"number": 1})

        with patch("splat.middleware.flask._get_splat", return_value=mock_splat):
            handler = create_error_handler()
            error = ValueError("test")

            with patch("splat.middleware.flask._run_async") as mock_run:
                mock_run.return_value = {"number": 1}
                try:
                    handler(error)
                except ValueError:
                    pass  # Expected to re-raise
                mock_run.assert_called_once()

    def test_handler_extracts_request_context(self) -> None:
        mock_splat = MagicMock()
        mock_splat.report = AsyncMock(return_value={"number": 1})

        with patch("splat.middleware.flask._get_splat", return_value=mock_splat):
            with patch("splat.middleware.flask._run_async") as mock_run:
                mock_request = MagicMock()
                mock_request.method = "POST"
                mock_request.path = "/api/test"
                mock_request.remote_addr = "127.0.0.1"
                mock_request.url = "http://localhost/api/test"

                with patch.dict(
                    "sys.modules",
                    {"flask": MagicMock(request=mock_request)}
                ):
                    handler = create_error_handler()
                    try:
                        handler(ValueError("test"))
                    except ValueError:
                        pass

                    call_args = mock_run.call_args
                    assert call_args is not None

    def test_handler_reraises_error(self) -> None:
        mock_splat = MagicMock()
        mock_splat.report = AsyncMock(return_value={"number": 1})

        with patch("splat.middleware.flask._get_splat", return_value=mock_splat):
            with patch("splat.middleware.flask._run_async"):
                handler = create_error_handler()
                error = ValueError("test error")

                with pytest.raises(ValueError, match="test error"):
                    handler(error)

    def test_handler_raises_if_no_splat_instance(self) -> None:
        with patch("splat.middleware.flask._get_splat", return_value=None):
            handler = create_error_handler()
            error = ValueError("test")

            with pytest.raises(ValueError, match="test"):
                handler(error)

    def test_handler_with_explicit_splat_instance(self) -> None:
        mock_splat = MagicMock()
        mock_splat.report = AsyncMock(return_value={"number": 1})

        with patch("splat.middleware.flask._run_async") as mock_run:
            handler = create_error_handler(splat=mock_splat)
            try:
                handler(ValueError("test"))
            except ValueError:
                pass
            mock_run.assert_called_once()

    def test_handler_handles_import_error_gracefully(self) -> None:
        mock_splat = MagicMock()
        mock_splat.report = AsyncMock(return_value={"number": 1})

        with patch("splat.middleware.flask._get_splat", return_value=mock_splat):
            with patch("splat.middleware.flask._run_async") as mock_run:
                # Simulate ImportError when flask is not available
                with patch.dict("sys.modules", {"flask": None}):
                    handler = create_error_handler()
                    try:
                        handler(ValueError("test"))
                    except ValueError:
                        pass
                    mock_run.assert_called_once()

    def test_handler_captures_vercel_id_header(self) -> None:
        """Test handler captures x-vercel-id header and passes to report()."""
        mock_splat = MagicMock()
        mock_splat.report = AsyncMock(return_value={"number": 1})

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.path = "/test"
        mock_request.remote_addr = "127.0.0.1"
        mock_request.url = "http://localhost/test"
        mock_request.headers.get = MagicMock(return_value="fra1::abc123-1234567890")

        mock_flask = MagicMock()
        mock_flask.request = mock_request

        with patch("splat.middleware.flask._get_splat", return_value=mock_splat):
            with patch.dict("sys.modules", {"flask": mock_flask}):
                handler = create_error_handler()
                try:
                    handler(ValueError("test"))
                except ValueError:
                    pass

                # Verify report was called with vercel_request_id
                mock_splat.report.assert_called_once()
                call_kwargs = mock_splat.report.call_args[1]
                assert call_kwargs.get("vercel_request_id") == "fra1::abc123-1234567890"

    def test_handler_works_without_vercel_id_header(self) -> None:
        """Test handler works when x-vercel-id header is not present."""
        mock_splat = MagicMock()
        mock_splat.report = AsyncMock(return_value={"number": 1})

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.path = "/test"
        mock_request.remote_addr = "127.0.0.1"
        mock_request.url = "http://localhost/test"
        mock_request.headers.get = MagicMock(return_value=None)

        mock_flask = MagicMock()
        mock_flask.request = mock_request

        with patch("splat.middleware.flask._get_splat", return_value=mock_splat):
            with patch.dict("sys.modules", {"flask": mock_flask}):
                handler = create_error_handler()
                try:
                    handler(ValueError("test"))
                except ValueError:
                    pass

                # Verify report was called with vercel_request_id=None
                mock_splat.report.assert_called_once()
                call_kwargs = mock_splat.report.call_args[1]
                assert call_kwargs.get("vercel_request_id") is None


class TestSplatFlask:
    """Test SplatFlask extension."""

    def test_init_app_registers_error_handler(self) -> None:
        mock_app = MagicMock()

        ext = SplatFlask()
        ext.init_app(mock_app, repo="owner/repo", token="ghp_test")

        mock_app.register_error_handler.assert_called_once()
        args = mock_app.register_error_handler.call_args[0]
        assert args[0] == Exception

    def test_init_with_app_in_constructor(self) -> None:
        mock_app = MagicMock()

        ext = SplatFlask(app=mock_app, repo="owner/repo", token="ghp_test")

        mock_app.register_error_handler.assert_called_once()
        assert ext.splat is not None

    def test_init_without_app(self) -> None:
        ext = SplatFlask()
        assert ext.splat is None

    def test_init_app_creates_splat_instance(self) -> None:
        mock_app = MagicMock()

        ext = SplatFlask()
        ext.init_app(mock_app, repo="owner/repo", token="ghp_test")

        assert ext.splat is not None

    def test_init_app_sets_global_instance(self) -> None:
        mock_app = MagicMock()

        ext = SplatFlask()
        ext.init_app(mock_app, repo="owner/repo", token="ghp_test")

        from splat.middleware.flask import _get_splat
        assert _get_splat() is ext.splat

    def test_init_app_registers_webhook_route_at_default_path(self) -> None:
        """Test init_app registers webhook route at default path /splat/logs."""
        mock_app = MagicMock()

        ext = SplatFlask()
        ext.init_app(mock_app, repo="owner/repo", token="ghp_test")

        # Verify add_url_rule was called with default path
        mock_app.add_url_rule.assert_called_once()
        call_args = mock_app.add_url_rule.call_args
        assert call_args[0][0] == "/splat/logs"
        assert call_args[1]["endpoint"] == "splat_vercel_webhook"
        assert call_args[1]["methods"] == ["POST"]

    def test_init_app_uses_custom_webhook_path(self) -> None:
        """Test init_app uses custom path from vercel_webhook_path kwarg."""
        mock_app = MagicMock()

        ext = SplatFlask()
        ext.init_app(
            mock_app,
            repo="owner/repo",
            token="ghp_test",
            vercel_webhook_path="/custom/webhook",
        )

        # Verify add_url_rule was called with custom path
        mock_app.add_url_rule.assert_called_once()
        call_args = mock_app.add_url_rule.call_args
        assert call_args[0][0] == "/custom/webhook"

    def test_init_app_webhook_route_accepts_post_requests(self) -> None:
        """Test webhook route is registered for POST method only."""
        mock_app = MagicMock()

        ext = SplatFlask()
        ext.init_app(mock_app, repo="owner/repo", token="ghp_test")

        # Verify methods is ["POST"]
        call_args = mock_app.add_url_rule.call_args
        assert call_args[1]["methods"] == ["POST"]

    def test_init_app_webhook_handler_is_callable(self) -> None:
        """Test webhook handler passed to add_url_rule is callable."""
        mock_app = MagicMock()

        ext = SplatFlask()
        ext.init_app(mock_app, repo="owner/repo", token="ghp_test")

        # Verify view_func is callable
        call_args = mock_app.add_url_rule.call_args
        view_func = call_args[1]["view_func"]
        assert callable(view_func)


class TestRunAsync:
    """Test _run_async helper function."""

    def test_run_async_with_simple_coroutine(self) -> None:
        from splat.middleware.flask import _run_async

        async def simple_coro() -> str:
            return "result"

        result = _run_async(simple_coro())
        assert result == "result"

    def test_run_async_handles_runtime_error(self) -> None:
        from splat.middleware.flask import _run_async

        async def simple_coro() -> str:
            return "result"

        with patch("asyncio.get_event_loop", side_effect=RuntimeError):
            result = _run_async(simple_coro())
            assert result == "result"


class TestGetSplat:
    """Test _get_splat helper function."""

    def test_get_splat_returns_global_instance(self) -> None:
        from splat.middleware.flask import _get_splat, _splat_instance
        import splat.middleware.flask as flask_module

        # Set global instance
        mock_splat = MagicMock()
        flask_module._splat_instance = mock_splat

        assert _get_splat() is mock_splat

        # Clean up
        flask_module._splat_instance = None

    def test_get_splat_returns_none_when_not_set(self) -> None:
        from splat.middleware.flask import _get_splat
        import splat.middleware.flask as flask_module

        flask_module._splat_instance = None
        assert _get_splat() is None
