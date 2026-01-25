"""Flask webhook handler for Vercel Log Drain."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Tuple

from splat.webhooks.vercel import parse_logs, verify_signature

if TYPE_CHECKING:
    from splat.core.reporter import Splat

logger = logging.getLogger(__name__)

# Module-level flag to ensure warning is only logged once
_warned_no_secret: bool = False


def create_webhook_handler(
    splat: Splat,
) -> Callable[[], Tuple[dict[str, Any], int]]:
    """
    Create a Flask view function to handle Vercel Log Drain webhooks.

    Args:
        splat: The Splat instance to store logs in.

    Returns:
        A Flask view function that returns (response_dict, status_code).
    """

    def handler() -> Tuple[dict[str, Any], int]:
        global _warned_no_secret
        from flask import request

        body = request.get_data()

        # Verify signature if secret is configured
        if splat.config.vercel_secret:
            signature = request.headers.get("x-vercel-signature")
            if not verify_signature(body, splat.config.vercel_secret, signature):
                return {"error": "Invalid signature"}, 401
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

        return {"received": len(logs)}, 200

    return handler


def register_webhook_route(app: Any, splat: Splat) -> None:
    """
    Register the Vercel webhook handler route on a Flask app.

    Args:
        app: The Flask application instance.
        splat: The Splat instance to use for the webhook handler.
    """
    handler = create_webhook_handler(splat)
    app.add_url_rule(
        splat.config.vercel_webhook_path,
        endpoint="splat_vercel_webhook",
        view_func=handler,
        methods=["POST"],
    )
