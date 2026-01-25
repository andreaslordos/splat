"""Tests for Flask webhook handler."""

import hashlib
import hmac
import json
import logging
from unittest.mock import MagicMock

import pytest
from flask import Flask

from splat.webhooks.flask import create_webhook_handler, register_webhook_route


class TestCreateWebhookHandler:
    """Test Flask webhook handler creation."""

    def test_creates_callable_handler(self) -> None:
        """Test that create_webhook_handler returns a callable."""
        mock_splat = MagicMock()
        mock_splat.config.vercel_secret = None
        mock_splat._vercel_store = MagicMock()

        handler = create_webhook_handler(mock_splat)

        assert callable(handler)

    def test_handler_accepts_valid_logs_and_stores_them(self) -> None:
        """Test handler accepts valid logs and adds them to the store."""
        # Reset the warning flag
        import splat.webhooks.flask as flask_module

        flask_module._warned_no_secret = False

        mock_splat = MagicMock()
        mock_splat.config.vercel_secret = None
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        app = Flask(__name__)
        handler = create_webhook_handler(mock_splat)
        app.add_url_rule("/test", view_func=handler, methods=["POST"])

        logs = [
            {"message": "log1", "source": "lambda", "requestId": "req123"},
            {"message": "log2", "source": "edge", "requestId": "req123"},
        ]
        body = json.dumps(logs)

        with app.test_client() as client:
            response = client.post("/test", data=body, content_type="application/json")

            assert response.status_code == 200
            result = response.get_json()
            assert result == {"received": 2}
            mock_store.add_logs.assert_called_once()
            # Check logs were passed to add_logs
            call_args = mock_store.add_logs.call_args[0][0]
            assert len(call_args) == 2

    def test_handler_verifies_signature_when_secret_configured(self) -> None:
        """Test handler verifies signature when vercel_secret is set."""
        mock_splat = MagicMock()
        secret = "test_secret"
        mock_splat.config.vercel_secret = secret
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        app = Flask(__name__)
        handler = create_webhook_handler(mock_splat)
        app.add_url_rule("/test", view_func=handler, methods=["POST"])

        logs = [{"message": "log1", "source": "lambda"}]
        body = json.dumps(logs).encode()
        valid_sig = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()

        with app.test_client() as client:
            response = client.post(
                "/test",
                data=body,
                content_type="application/json",
                headers={"x-vercel-signature": valid_sig},
            )

            assert response.status_code == 200
            mock_store.add_logs.assert_called_once()

    def test_handler_rejects_invalid_signature_with_401(self) -> None:
        """Test handler returns 401 for invalid signature."""
        mock_splat = MagicMock()
        mock_splat.config.vercel_secret = "test_secret"
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        app = Flask(__name__)
        handler = create_webhook_handler(mock_splat)
        app.add_url_rule("/test", view_func=handler, methods=["POST"])

        logs = [{"message": "log1", "source": "lambda"}]
        body = json.dumps(logs)
        invalid_sig = "invalid_signature"

        with app.test_client() as client:
            response = client.post(
                "/test",
                data=body,
                content_type="application/json",
                headers={"x-vercel-signature": invalid_sig},
            )

            assert response.status_code == 401
            result = response.get_json()
            assert "error" in result
            mock_store.add_logs.assert_not_called()

    def test_handler_rejects_missing_signature_when_secret_configured(self) -> None:
        """Test 401 when signature header is missing but secret is set."""
        mock_splat = MagicMock()
        mock_splat.config.vercel_secret = "test_secret"
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        app = Flask(__name__)
        handler = create_webhook_handler(mock_splat)
        app.add_url_rule("/test", view_func=handler, methods=["POST"])

        logs = [{"message": "log1", "source": "lambda"}]
        body = json.dumps(logs)

        with app.test_client() as client:
            response = client.post(
                "/test", data=body, content_type="application/json"
            )  # No signature header

            assert response.status_code == 401
            mock_store.add_logs.assert_not_called()

    def test_handler_warns_when_no_secret_configured(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test handler logs a warning when no secret is configured."""
        # Reset the module-level warning flag
        import splat.webhooks.flask as flask_module

        flask_module._warned_no_secret = False

        mock_splat = MagicMock()
        mock_splat.config.vercel_secret = None
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        app = Flask(__name__)
        handler = create_webhook_handler(mock_splat)
        app.add_url_rule("/test", view_func=handler, methods=["POST"])

        logs = [{"message": "log1", "source": "lambda"}]
        body = json.dumps(logs)

        with caplog.at_level(logging.WARNING):
            with app.test_client() as client:
                client.post("/test", data=body, content_type="application/json")

        assert any("secret" in record.message.lower() for record in caplog.records)

    def test_handler_warns_only_once_when_no_secret_configured(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test handler only logs warning once for missing secret."""
        # Reset the module-level warning flag
        import splat.webhooks.flask as flask_module

        flask_module._warned_no_secret = False

        mock_splat = MagicMock()
        mock_splat.config.vercel_secret = None
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        app = Flask(__name__)
        handler = create_webhook_handler(mock_splat)
        app.add_url_rule("/test", view_func=handler, methods=["POST"])

        logs = [{"message": "log1", "source": "lambda"}]
        body = json.dumps(logs)

        with caplog.at_level(logging.WARNING):
            with app.test_client() as client:
                # Call handler multiple times
                client.post("/test", data=body, content_type="application/json")
                client.post("/test", data=body, content_type="application/json")
                client.post("/test", data=body, content_type="application/json")

        # Count warning messages about secret
        warning_count = sum(
            1
            for record in caplog.records
            if "secret" in record.message.lower() and record.levelno == logging.WARNING
        )
        assert warning_count == 1

    def test_handler_filters_logs_by_source(self) -> None:
        """Test handler filters logs with filter_sources=True."""
        # Reset the warning flag
        import splat.webhooks.flask as flask_module

        flask_module._warned_no_secret = False

        mock_splat = MagicMock()
        mock_splat.config.vercel_secret = None
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        app = Flask(__name__)
        handler = create_webhook_handler(mock_splat)
        app.add_url_rule("/test", view_func=handler, methods=["POST"])

        logs = [
            {"message": "log1", "source": "lambda"},
            {"message": "log2", "source": "build"},  # Should be filtered out
            {"message": "log3", "source": "edge"},
        ]
        body = json.dumps(logs)

        with app.test_client() as client:
            response = client.post("/test", data=body, content_type="application/json")

            assert response.status_code == 200
            result = response.get_json()
            # Only lambda and edge logs should be kept
            assert result == {"received": 2}

    def test_handler_returns_zero_for_empty_body(self) -> None:
        """Test handler returns received=0 for empty body."""
        # Reset the warning flag
        import splat.webhooks.flask as flask_module

        flask_module._warned_no_secret = False

        mock_splat = MagicMock()
        mock_splat.config.vercel_secret = None
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        app = Flask(__name__)
        handler = create_webhook_handler(mock_splat)
        app.add_url_rule("/test", view_func=handler, methods=["POST"])

        with app.test_client() as client:
            response = client.post("/test", data=b"", content_type="application/json")

            assert response.status_code == 200
            result = response.get_json()
            assert result == {"received": 0}


class TestRegisterWebhookRoute:
    """Test Flask webhook route registration."""

    def test_registers_route_with_correct_path(self) -> None:
        """Test register_webhook_route uses correct path from config."""
        mock_app = MagicMock()
        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = None
        mock_splat._vercel_store = MagicMock()

        register_webhook_route(mock_app, mock_splat)

        mock_app.add_url_rule.assert_called_once()
        call_args = mock_app.add_url_rule.call_args
        assert call_args[0][0] == "/splat/logs"

    def test_registers_route_with_custom_path(self) -> None:
        """Test register_webhook_route uses custom path from config."""
        mock_app = MagicMock()
        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/custom/webhook/path"
        mock_splat.config.vercel_secret = None
        mock_splat._vercel_store = MagicMock()

        register_webhook_route(mock_app, mock_splat)

        call_args = mock_app.add_url_rule.call_args
        assert call_args[0][0] == "/custom/webhook/path"

    def test_registers_route_with_post_method(self) -> None:
        """Test register_webhook_route registers route with POST method."""
        mock_app = MagicMock()
        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = None
        mock_splat._vercel_store = MagicMock()

        register_webhook_route(mock_app, mock_splat)

        call_kwargs = mock_app.add_url_rule.call_args[1]
        assert "methods" in call_kwargs
        assert call_kwargs["methods"] == ["POST"]

    def test_registers_route_with_endpoint_name(self) -> None:
        """Test register_webhook_route sets an endpoint name."""
        mock_app = MagicMock()
        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = None
        mock_splat._vercel_store = MagicMock()

        register_webhook_route(mock_app, mock_splat)

        call_kwargs = mock_app.add_url_rule.call_args[1]
        assert "endpoint" in call_kwargs
        assert call_kwargs["endpoint"] == "splat_vercel_webhook"

    def test_registers_callable_view_function(self) -> None:
        """Test register_webhook_route registers a callable view function."""
        mock_app = MagicMock()
        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = None
        mock_splat._vercel_store = MagicMock()

        register_webhook_route(mock_app, mock_splat)

        call_kwargs = mock_app.add_url_rule.call_args[1]
        assert "view_func" in call_kwargs
        assert callable(call_kwargs["view_func"])

    def test_integration_with_real_flask_app(self) -> None:
        """Test register_webhook_route works with a real Flask app."""
        # Reset the warning flag
        import splat.webhooks.flask as flask_module

        flask_module._warned_no_secret = False

        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = None
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        app = Flask(__name__)
        register_webhook_route(app, mock_splat)

        logs = [{"message": "test", "source": "lambda"}]
        body = json.dumps(logs)

        with app.test_client() as client:
            response = client.post(
                "/splat/logs", data=body, content_type="application/json"
            )

            assert response.status_code == 200
            result = response.get_json()
            assert result == {"received": 1}
            mock_store.add_logs.assert_called_once()
