"""Tests for FastAPI webhook handler."""

import hashlib
import hmac
import json
import logging
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from splat.webhooks.fastapi import create_webhook_router


class TestCreateWebhookRouter:
    """Test FastAPI webhook router creation."""

    def test_creates_api_router(self) -> None:
        """Test that create_webhook_router returns an APIRouter."""
        from fastapi import APIRouter

        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = None
        mock_splat._vercel_store = MagicMock()

        router = create_webhook_router(mock_splat)

        assert isinstance(router, APIRouter)

    def test_router_creates_correct_endpoint_path(self) -> None:
        """Test router creates endpoint at the configured path."""
        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/custom/webhook"
        mock_splat.config.vercel_secret = None
        mock_splat._vercel_store = MagicMock()

        # Reset the warning flag
        import splat.webhooks.fastapi as fastapi_module

        fastapi_module._warned_no_secret = False

        router = create_webhook_router(mock_splat)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        logs = [{"message": "test", "source": "lambda"}]
        body = json.dumps(logs)

        response = client.post("/custom/webhook", content=body)

        assert response.status_code == 200

    def test_handler_accepts_valid_logs_and_stores_them(self) -> None:
        """Test handler accepts valid logs and adds them to the store."""
        # Reset the warning flag
        import splat.webhooks.fastapi as fastapi_module

        fastapi_module._warned_no_secret = False

        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = None
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        router = create_webhook_router(mock_splat)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        logs = [
            {"message": "log1", "source": "lambda", "requestId": "req123"},
            {"message": "log2", "source": "edge", "requestId": "req123"},
        ]
        body = json.dumps(logs)

        response = client.post("/splat/logs", content=body)

        assert response.status_code == 200
        result = response.json()
        assert result == {"received": 2}
        mock_store.add_logs.assert_called_once()
        # Check logs were passed to add_logs
        call_args = mock_store.add_logs.call_args[0][0]
        assert len(call_args) == 2

    def test_handler_verifies_signature_when_secret_configured(self) -> None:
        """Test handler verifies signature when vercel_secret is set."""
        mock_splat = MagicMock()
        secret = "test_secret"
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = secret
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        router = create_webhook_router(mock_splat)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        logs = [{"message": "log1", "source": "lambda"}]
        body = json.dumps(logs).encode()
        valid_sig = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()

        response = client.post(
            "/splat/logs",
            content=body,
            headers={"x-vercel-signature": valid_sig},
        )

        assert response.status_code == 200
        mock_store.add_logs.assert_called_once()

    def test_handler_rejects_invalid_signature_with_401(self) -> None:
        """Test handler returns 401 for invalid signature."""
        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = "test_secret"
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        router = create_webhook_router(mock_splat)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        logs = [{"message": "log1", "source": "lambda"}]
        body = json.dumps(logs)
        invalid_sig = "invalid_signature"

        response = client.post(
            "/splat/logs",
            content=body,
            headers={"x-vercel-signature": invalid_sig},
        )

        assert response.status_code == 401
        result = response.json()
        assert "error" in result
        mock_store.add_logs.assert_not_called()

    def test_handler_rejects_missing_signature_when_secret_configured(self) -> None:
        """Test 401 when signature header is missing but secret is set."""
        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = "test_secret"
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        router = create_webhook_router(mock_splat)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        logs = [{"message": "log1", "source": "lambda"}]
        body = json.dumps(logs)

        response = client.post(
            "/splat/logs", content=body
        )  # No signature header

        assert response.status_code == 401
        mock_store.add_logs.assert_not_called()

    def test_handler_warns_when_no_secret_configured(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test handler logs a warning when no secret is configured."""
        # Reset the module-level warning flag
        import splat.webhooks.fastapi as fastapi_module

        fastapi_module._warned_no_secret = False

        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = None
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        router = create_webhook_router(mock_splat)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        logs = [{"message": "log1", "source": "lambda"}]
        body = json.dumps(logs)

        with caplog.at_level(logging.WARNING):
            client.post("/splat/logs", content=body)

        assert any("secret" in record.message.lower() for record in caplog.records)

    def test_handler_warns_only_once_when_no_secret_configured(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test handler only logs warning once for missing secret."""
        # Reset the module-level warning flag
        import splat.webhooks.fastapi as fastapi_module

        fastapi_module._warned_no_secret = False

        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = None
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        router = create_webhook_router(mock_splat)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        logs = [{"message": "log1", "source": "lambda"}]
        body = json.dumps(logs)

        with caplog.at_level(logging.WARNING):
            # Call handler multiple times
            client.post("/splat/logs", content=body)
            client.post("/splat/logs", content=body)
            client.post("/splat/logs", content=body)

        # Count warning messages about secret
        warning_count = sum(
            1
            for record in caplog.records
            if "secret" in record.message.lower()
            and record.levelno == logging.WARNING
        )
        assert warning_count == 1

    def test_handler_filters_logs_by_source(self) -> None:
        """Test handler filters logs with filter_sources=True."""
        # Reset the warning flag
        import splat.webhooks.fastapi as fastapi_module

        fastapi_module._warned_no_secret = False

        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = None
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        router = create_webhook_router(mock_splat)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        logs = [
            {"message": "log1", "source": "lambda"},
            {"message": "log2", "source": "build"},  # Should be filtered out
            {"message": "log3", "source": "edge"},
        ]
        body = json.dumps(logs)

        response = client.post("/splat/logs", content=body)

        assert response.status_code == 200
        result = response.json()
        # Only lambda and edge logs should be kept
        assert result == {"received": 2}

    def test_handler_returns_zero_for_empty_body(self) -> None:
        """Test handler returns received=0 for empty body."""
        # Reset the warning flag
        import splat.webhooks.fastapi as fastapi_module

        fastapi_module._warned_no_secret = False

        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = None
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        router = create_webhook_router(mock_splat)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post("/splat/logs", content=b"")

        assert response.status_code == 200
        result = response.json()
        assert result == {"received": 0}

    def test_handler_returns_count_of_received_logs(self) -> None:
        """Test handler returns correct count of received logs."""
        # Reset the warning flag
        import splat.webhooks.fastapi as fastapi_module

        fastapi_module._warned_no_secret = False

        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = None
        mock_store = MagicMock()
        mock_splat._vercel_store = mock_store

        router = create_webhook_router(mock_splat)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        logs = [
            {"message": "log1", "source": "lambda"},
            {"message": "log2", "source": "lambda"},
            {"message": "log3", "source": "edge"},
            {"message": "log4", "source": "edge"},
            {"message": "log5", "source": "lambda"},
        ]
        body = json.dumps(logs)

        response = client.post("/splat/logs", content=body)

        assert response.status_code == 200
        result = response.json()
        assert result == {"received": 5}

    def test_router_uses_post_method(self) -> None:
        """Test router creates a POST endpoint."""
        # Reset the warning flag
        import splat.webhooks.fastapi as fastapi_module

        fastapi_module._warned_no_secret = False

        mock_splat = MagicMock()
        mock_splat.config.vercel_webhook_path = "/splat/logs"
        mock_splat.config.vercel_secret = None
        mock_splat._vercel_store = MagicMock()

        router = create_webhook_router(mock_splat)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # GET should not be allowed
        response = client.get("/splat/logs")
        assert response.status_code == 405

        # POST should work
        response = client.post("/splat/logs", content=b"[]")
        assert response.status_code == 200
