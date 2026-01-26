"""Flask integration for Splat error reporting."""

from __future__ import annotations

import logging
from typing import Any, Callable

from splat.core.reporter import Splat

logger = logging.getLogger(__name__)

_splat_instance: Splat | None = None


def _get_splat() -> Splat | None:
    """Get the global Splat instance."""
    return _splat_instance


def create_error_handler(
    splat: Splat | None = None,
) -> Callable[[Exception], Any]:
    """Create a Flask error handler that reports errors to Splat."""

    def handler(error: Exception) -> Any:
        instance = splat or _get_splat()
        if instance is None:
            raise error

        if instance.config.debug:
            logger.warning(
                f"[SPLAT DEBUG] Flask error handler caught: "
                f"{type(error).__name__}: {error}"
            )

        context: dict[str, Any] = {}
        try:
            from flask import request

            context = {
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
                "url": request.url,
            }
        except (ImportError, RuntimeError):
            pass

        if instance.config.debug:
            logger.warning(f"[SPLAT DEBUG] Flask context: {context}")

        try:
            instance.report_sync(error, context=context)
        except Exception as report_error:
            if instance.config.debug:
                logger.warning(f"[SPLAT DEBUG] Flask report() raised: {report_error}")
        raise error

    return handler


class SplatFlask:
    """Flask extension for Splat error reporting."""

    def __init__(self, app: Any = None, **kwargs: Any) -> None:
        self.splat: Splat | None = None
        if app is not None:
            self.init_app(app, **kwargs)

    def init_app(self, app: Any, **kwargs: Any) -> None:
        global _splat_instance
        self.splat = Splat(**kwargs)
        _splat_instance = self.splat
        app.register_error_handler(Exception, create_error_handler(self.splat))
