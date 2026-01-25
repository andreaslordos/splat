"""FastAPI webhook router for Vercel Log Drain."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

try:
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse

    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

from splat.webhooks.vercel import parse_logs, verify_signature

if TYPE_CHECKING:
    from splat.core.reporter import Splat

logger = logging.getLogger(__name__)

# Module-level flag to ensure warning is only logged once
_warned_no_secret: bool = False


def create_webhook_router(splat: Splat) -> APIRouter:
    """
    Create a FastAPI router to handle Vercel Log Drain webhooks.

    Args:
        splat: The Splat instance to store logs in.

    Returns:
        A FastAPI APIRouter with a POST endpoint at the configured path.

    Raises:
        ImportError: If FastAPI is not installed.
    """
    if not _FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI is required for the webhook router. "
            "Install it with: pip install fastapi"
        )

    router = APIRouter()

    async def webhook_handler(request: Request) -> JSONResponse:
        global _warned_no_secret

        body = await request.body()

        # Verify signature if secret is configured
        if splat.config.vercel_secret:
            signature = request.headers.get("x-vercel-signature")
            if not verify_signature(body, splat.config.vercel_secret, signature):
                return JSONResponse(
                    content={"error": "Invalid signature"},
                    status_code=401,
                )
        else:
            # Warn once about missing secret
            if not _warned_no_secret:
                logger.warning(
                    "Vercel webhook secret is not configured. "
                    "Set SPLAT_VERCEL_SECRET or vercel_secret in config for security."
                )
                _warned_no_secret = True

        # Parse logs with source filtering
        logs = parse_logs(body, filter_sources=True)

        # Store logs in the Vercel store
        splat._vercel_store.add_logs(logs)

        return JSONResponse(content={"received": len(logs)})

    router.add_api_route(
        splat.config.vercel_webhook_path,
        webhook_handler,
        methods=["POST"],
        response_model=None,
    )

    return router
