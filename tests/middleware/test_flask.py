"""Tests for Flask middleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from splat.middleware.flask import SplatFlask, create_error_handler


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
                    "sys.modules", {"flask": MagicMock(request=mock_request)}
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


class TestSplatFlask:
    """Test SplatFlask extension."""

    def test_init_app_registers_error_handler(self) -> None:
        mock_app = MagicMock()

        ext = SplatFlask()
        ext.init_app(mock_app, repo="owner/repo", token="ghp_test")

        mock_app.register_error_handler.assert_called_once()
        args = mock_app.register_error_handler.call_args[0]
        assert args[0] is Exception

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
        import splat.middleware.flask as flask_module
        from splat.middleware.flask import _get_splat

        # Set global instance
        mock_splat = MagicMock()
        flask_module._splat_instance = mock_splat

        assert _get_splat() is mock_splat

        # Clean up
        flask_module._splat_instance = None

    def test_get_splat_returns_none_when_not_set(self) -> None:
        import splat.middleware.flask as flask_module
        from splat.middleware.flask import _get_splat

        flask_module._splat_instance = None
        assert _get_splat() is None
