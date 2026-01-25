# Vercel Logs Integration - Design Document

**Date:** 2025-01-25
**Status:** Approved

## Overview

Add Vercel Log Drain integration to Splat, allowing automatic capture of Vercel runtime logs when errors occur. Instead of relying on Python's logging module, Splat can receive logs directly from Vercel via webhook and include them in GitHub issues.

## Core Value Proposition

- **Zero-config log capture** - Vercel pushes logs to Splat automatically
- **Request-scoped logs** - Get exactly the logs for the failed request, not a random time window
- **Rich Vercel context** - Includes request ID, deployment ID, region, path, status code, etc.
- **Replaces Python buffer** - When Vercel logs are available, use those instead (they already capture stdout/stderr)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Log delivery | Webhook (Log Drain) | Real-time, no polling, Vercel pushes to us |
| Log storage | Request-keyed with TTL | Precise (logs per request), bounded memory |
| Python buffer | Replace when Vercel available | Vercel logs already include stdout/stderr |
| Webhook auth | Optional but recommended | Easy setup, secure when configured |
| TTL for logs | 60 seconds | Long enough for error handling, short enough to bound memory |

## Architecture

### New Module: `vercel_logs.py`

```python
class VercelLogStore:
    """Request-keyed log storage with TTL expiration."""

    def __init__(self, ttl_seconds: int = 60):
        self._logs: dict[str, list[dict]] = {}
        self._timestamps: dict[str, float] = {}
        self._ttl = ttl_seconds

    def add_logs(self, logs: list[dict]) -> None:
        """Add logs from webhook, keyed by requestId."""
        self._cleanup_expired()
        for log in logs:
            request_id = log.get("requestId")
            if request_id:
                if request_id not in self._logs:
                    self._logs[request_id] = []
                    self._timestamps[request_id] = time.time()
                self._logs[request_id].append(log)

    def get_logs(self, request_id: str) -> list[dict]:
        """Get logs for a specific request."""
        return self._logs.get(request_id, [])

    def pop_logs(self, request_id: str) -> list[dict]:
        """Get and remove logs for a request."""
        logs = self._logs.pop(request_id, [])
        self._timestamps.pop(request_id, None)
        return logs
```

### Webhook Flow

```
Vercel Runtime
    │
    ▼
Log Drain POST to /splat/logs
    │
    ▼
Verify signature (if configured)
    │
    ▼
Parse logs (JSON or NDJSON)
    │
    ▼
Filter to lambda/edge sources
    │
    ▼
Store keyed by requestId
    │
    ▼
Error occurs in app
    │
    ▼
Middleware captures x-vercel-id header
    │
    ▼
splat.report(exc, vercel_request_id=request_id)
    │
    ▼
Fetch logs for that request ID
    │
    ▼
Create GitHub issue with Vercel logs
```

### Log Source Selection

```python
async def report(
    self,
    exception: BaseException,
    context: dict | None = None,
    logs: str | None = None,
    vercel_request_id: str | None = None,
) -> dict | None:
    if logs is None:
        if vercel_request_id and self._vercel_store.has_logs(vercel_request_id):
            logs = self._format_vercel_logs(
                self._vercel_store.pop_logs(vercel_request_id)
            )
        else:
            logs = self._log_buffer.get_logs_as_string()
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SPLAT_VERCEL_SECRET` | Webhook verification secret | (optional) |
| `SPLAT_VERCEL_WEBHOOK_PATH` | Webhook route path | `/splat/logs` |
| `SPLAT_VERCEL_LOG_TTL` | Seconds to keep logs | `60` |

### pyproject.toml

```toml
[tool.splat]
vercel_secret = "whsec_..."
vercel_webhook_path = "/splat/logs"
vercel_log_ttl = 60
```

### Programmatic

```python
splat = Splat(
    repo="owner/repo",
    token="ghp_...",
    vercel_secret="whsec_...",
)
```

## Webhook Handlers

### Signature Verification

```python
def verify_signature(body: bytes, secret: str, signature: str) -> bool:
    """Verify Vercel webhook signature."""
    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha1
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### Flask Integration

```python
# Automatically registers /splat/logs when init_app is called
splat = SplatFlask()
splat.init_app(app, repo="...", token="...")
```

### FastAPI Integration

```python
app.add_middleware(SplatMiddleware, repo="...", token="...")
app.include_router(splat.webhook_router())
```

## Middleware Changes

Middleware automatically captures `x-vercel-id` header:

```python
# FastAPI
class SplatMiddleware:
    async def __call__(self, scope, receive, send):
        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            headers = dict(scope.get("headers", []))
            request_id = headers.get(b"x-vercel-id", b"").decode() or None
            await self.splat.report(exc, vercel_request_id=request_id)
            raise

# Flask
def create_error_handler(splat):
    def handler(error):
        request_id = request.headers.get("x-vercel-id")
        asyncio.run(splat.report(error, vercel_request_id=request_id))
        raise error
    return handler
```

## CLI Wizard Changes

### Vercel Detection

Check for:
- `vercel.json` file
- `.vercel/` directory
- `VERCEL` environment variable

### New Wizard Step

```
Step 4/5: Vercel Integration (optional)
  Detected Vercel project.

  Enable Vercel log capture? [y/n] → y

  Add webhook route to app.py? [y/n] → y
  ✓ Added /splat/logs webhook route

  Generate verification secret? [y/n] → y
  ✓ Generated SPLAT_VERCEL_SECRET
  ✓ Added to .env

  To complete setup, add a Log Drain in Vercel:
  1. Go to: https://vercel.com/{team}/{project}/settings/log-drains
  2. Create new Log Drain:
     - Delivery format: JSON
     - Endpoint: https://your-app.vercel.app/splat/logs
     - Secret: [copied to clipboard]

  Open Vercel dashboard now? [y/n] → y
  ✓ Opened browser
```

## File Changes

### New Files

- `src/splat/core/vercel_logs.py` - VercelLogStore class
- `src/splat/webhooks/__init__.py`
- `src/splat/webhooks/vercel.py` - Signature verification, log parsing
- `src/splat/webhooks/flask.py` - Flask webhook route
- `src/splat/webhooks/fastapi.py` - FastAPI webhook router
- `tests/core/test_vercel_logs.py`
- `tests/webhooks/test_vercel.py`
- `tests/webhooks/test_flask_webhook.py`
- `tests/webhooks/test_fastapi_webhook.py`

### Modified Files

- `src/splat/core/config.py` - Add vercel config options
- `src/splat/core/reporter.py` - Add vercel_request_id param, VercelLogStore
- `src/splat/middleware/flask.py` - Capture request ID, mount webhook
- `src/splat/middleware/fastapi.py` - Capture request ID, add router
- `src/splat/cli/init.py` - Vercel detection & setup wizard
- `README.md` - Document Vercel integration

## Vercel Log Drain Payload

Reference: https://vercel.com/docs/drains/reference/logs

Key fields we use:
- `requestId` - Groups logs by request
- `timestamp` - For ordering
- `level` - info, warning, error, fatal
- `message` - The log content
- `source` - lambda, edge (we filter to these)
- `path` - Request path
- `statusCode` - HTTP status

## Future Considerations (Not v1)

- **Log search** - Query logs across requests for debugging
- **Log forwarding** - Forward to other services (Datadog, etc.)
- **Build logs** - Option to capture build failures too
