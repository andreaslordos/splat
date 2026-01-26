"""Django integration for Splat error reporting."""

from __future__ import annotations

import logging
from typing import Any, Callable

from splat.core.reporter import Splat

logger = logging.getLogger(__name__)

# Try to import Django settings at module level for easier mocking in tests
try:
    from django.conf import settings
except ImportError:
    settings = None


class SplatMiddleware:
    """
    Django middleware for Splat error reporting.

    Usage in settings.py:
        MIDDLEWARE = [
            'splat.middleware.django.SplatMiddleware',
            ...
        ]

        SPLAT = {
            'repo': 'owner/repo',
            'token': 'ghp_...',
        }
    """

    def __init__(self, get_response: Callable[[Any], Any]) -> None:
        self.get_response = get_response
        self.splat = self._init_splat()

    def _init_splat(self) -> Splat:
        """Initialize Splat from Django settings."""
        if settings is not None:
            config = getattr(settings, "SPLAT", {})
        else:
            config = {}

        return Splat(**config)

    def __call__(self, request: Any) -> Any:
        """Process the request."""
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            self._report_error(e, request)
            raise

    def _report_error(self, exc: Exception, request: Any) -> None:
        """Queue error for reporting."""
        context = {
            "method": getattr(request, "method", "unknown"),
            "path": getattr(request, "path", "unknown"),
            "remote_addr": (
                request.META.get("REMOTE_ADDR", "unknown")
                if hasattr(request, "META")
                else "unknown"
            ),
        }

        if self.splat.config.debug:
            logger.warning(f"[SPLAT DEBUG] Django middleware caught: {exc}")
            logger.warning(f"[SPLAT DEBUG] Django context: {context}")

        try:
            self.splat.report_sync(exc, context=context)
        except Exception as report_error:
            if self.splat.config.debug:
                logger.warning(f"[SPLAT DEBUG] Django report() raised: {report_error}")
