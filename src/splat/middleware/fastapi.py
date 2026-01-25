"""FastAPI integration for Splat error reporting."""

from __future__ import annotations

from typing import Any, Callable, Awaitable, MutableMapping

from splat.core.reporter import Splat


class SplatMiddleware:
    """
    FastAPI middleware for Splat error reporting.

    Usage:
        app = FastAPI()
        app.add_middleware(SplatMiddleware, repo="owner/repo", token="ghp_...")
    """

    def __init__(self, app: Any, **kwargs: Any) -> None:
        self.app = app
        self.splat = Splat(**kwargs)

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ) -> None:
        """ASGI interface."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from starlette.requests import Request
        request = Request(scope, receive, send)

        async def call_next(req: Request) -> Any:
            await self.app(scope, receive, send)

        try:
            await self.dispatch(request, call_next)
        except Exception:
            raise

    async def dispatch(
        self,
        request: Any,
        call_next: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """Process request and catch errors."""
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            context = {
                "method": request.method,
                "path": request.url.path,
                "client": getattr(request.client, "host", "unknown")
                if request.client
                else "unknown",
            }
            await self.splat.report(e, context=context)
            raise
