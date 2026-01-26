# Splat v1.0.0 Reliability & Features Design

## Overview

This design covers the implementation of reliability improvements and new features for Splat v1.0.0:

1. **Rate limiting with retry logic** - Exponential backoff for GitHub API failures
2. **API timeouts** - Configurable timeouts for all GitHub API calls
3. **Exception filtering** - Ignore certain exceptions from reporting
4. **Improved dedup signatures** - 16-char hash to reduce collision risk
5. **Django support** - Standard Django middleware
6. **Payload size limits** - Truncation for large tracebacks/logs
7. **GitHub Enterprise support** - Configurable API URL
8. **Background queue** - Non-blocking error reporting with async worker

## Architecture Decisions

| Feature | Decision |
|---------|----------|
| Background queue | In-process `asyncio.Queue` with background task |
| Exception filtering | Both class-based list AND callback (callback takes precedence) |
| Retry behavior | Silent drop with warning log after exhausting retries |
| Django integration | Standard Django middleware class |
| Payload limits | Generous: 50K traceback, 500 logs, 5K context per field |
| GitHub Enterprise | Single `github_api_url` parameter |
| Dedup signature | 16 hex chars (keep MD5) |
| Config exposure | Minimal: `timeout`, `ignore_exceptions`, `github_api_url` in TOML/env |

---

## Section 1: Core Reporter Changes

The `Splat` class will be refactored to support background queuing and new configuration options.

**New config options in `SplatConfig`:**

```python
@dataclass
class SplatConfig:
    # Existing...
    repo: str | None = None
    token: str | None = None
    enabled: bool = True
    log_buffer_size: int = 200
    labels: list[str] = field(default_factory=lambda: ["bug", "splat"])
    debug: bool = False

    # New options
    timeout: float = 30.0                    # API timeout in seconds
    max_retries: int = 3                     # Retry attempts
    github_api_url: str = "https://api.github.com"
    ignore_exceptions: list[type] = field(default_factory=list)
    exception_filter: Callable[[BaseException], bool] | None = None

    # Payload limits (not exposed in TOML/env, programmatic only)
    max_traceback_length: int = 50000
    max_log_entries: int = 500
    max_context_value_length: int = 5000
```

**Background queue architecture:**

- `Splat.__init__` starts a background asyncio task
- `report()` becomes non-blocking - adds to queue and returns immediately
- New `_worker()` coroutine processes queue with retries
- `shutdown()` method for graceful cleanup (drain queue)

**Exception filtering flow:**

1. Check `exception_filter` callback if provided → if returns `False`, skip
2. Check if exception type is in `ignore_exceptions` list → if yes, skip
3. Otherwise, queue for reporting

---

## Section 2: Background Queue & Retry Implementation

**New file: `src/splat/core/queue.py`**

```python
class ErrorQueue:
    """Async queue for background error reporting with retries."""

    def __init__(self, splat: Splat):
        self._queue: asyncio.Queue[ErrorReport] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._shutdown = False

    async def start(self) -> None:
        """Start the background worker."""
        self._worker_task = asyncio.create_task(self._worker())

    async def enqueue(self, report: ErrorReport) -> None:
        """Add error to queue (non-blocking)."""
        await self._queue.put(report)

    async def shutdown(self, timeout: float = 5.0) -> None:
        """Gracefully drain queue and stop worker."""
        # Wait for queue to drain or timeout

    async def _worker(self) -> None:
        """Process queue items with retry logic."""
        while not self._shutdown:
            report = await self._queue.get()
            await self._process_with_retry(report)
```

**Retry logic with exponential backoff:**

- Delays: 1s → 2s → 4s (doubles each attempt)
- On rate limit (429), respect `Retry-After` header if present
- After max retries exhausted: log warning, drop report
- Retryable errors: 429, 500, 502, 503, 504, network errors
- Non-retryable: 401, 403, 404, 422 (fail immediately)

**ErrorReport dataclass:**

```python
@dataclass
class ErrorReport:
    exception: BaseException
    context: dict[str, Any] | None
    logs: str
    signature: str
    attempt: int = 0
```

---

## Section 3: API Timeouts & GitHub Enterprise

**Centralized HTTP client: `src/splat/core/http.py`**

```python
async def github_request(
    method: str,
    endpoint: str,  # e.g., "/repos/{repo}/issues"
    config: SplatConfig,
    **kwargs
) -> httpx.Response:
    """Make authenticated GitHub API request with timeout."""
    url = f"{config.github_api_url}{endpoint}"
    async with httpx.AsyncClient(timeout=config.timeout) as client:
        response = await getattr(client, method)(
            url,
            headers={
                "Authorization": f"Bearer {config.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            **kwargs
        )
        return response
```

**Places that need updating:**

- `reporter.py:_create_issue()` - issue creation
- `dedup.py:check_duplicate()` - issue search

**Config/env support for GitHub Enterprise:**

- Programmatic: `Splat(github_api_url="https://...")`
- Environment: `SPLAT_GITHUB_API_URL`
- TOML: `github_api_url = "https://..."`

---

## Section 4: Payload Size Limits & Truncation

**Changes to `src/splat/core/formatter.py`:**

```python
def _truncate(text: str, max_length: int, suffix: str = "\n... [truncated]") -> str:
    """Truncate text with indicator if over limit."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def format_issue_body(
    exception: BaseException,
    signature: str,
    context: dict[str, Any] | None,
    logs: str,
    *,
    max_traceback_length: int = 50000,
    max_log_entries: int = 500,
    max_context_value_length: int = 5000,
) -> str:
    # Truncate traceback
    tb_str = _truncate(traceback_str, max_traceback_length)

    # Truncate each context value
    if context:
        context = {
            k: _truncate(str(v), max_context_value_length)
            for k, v in context.items()
        }

    # Truncate logs (by line count, not chars)
    log_lines = logs.split('\n')
    if len(log_lines) > max_log_entries:
        logs = '\n'.join(log_lines[-max_log_entries:])  # Keep most recent
        logs = f"... [{len(log_lines) - max_log_entries} earlier entries truncated]\n{logs}"
```

Limits are passed from Splat config to `format_issue_body()`. Limits come from `SplatConfig` (programmatic only, not TOML/env).

---

## Section 5: Django Integration

**New file: `src/splat/middleware/django.py`**

```python
"""Django integration for Splat error reporting."""

from typing import Any, Callable
from splat.core.reporter import Splat

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

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response
        self.splat = self._init_splat()

    def _init_splat(self) -> Splat:
        """Initialize Splat from Django settings."""
        from django.conf import settings
        config = getattr(settings, 'SPLAT', {})
        return Splat(**config)

    def __call__(self, request: Any) -> Any:
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            self._report_error(e, request)
            raise

    def _report_error(self, exc: Exception, request: Any) -> None:
        """Queue error for reporting."""
        context = {
            'method': request.method,
            'path': request.path,
            'remote_addr': request.META.get('REMOTE_ADDR', 'unknown'),
        }
        self.splat.report_sync(exc, context=context)
```

**Sync wrapper in `Splat`:**

Django middleware runs synchronously, so we need a sync entry point:

```python
def report_sync(self, exception: BaseException, context: dict | None = None) -> None:
    """Sync wrapper for report() - queues error without blocking."""
    # Similar to Flask's _run_async pattern but just enqueues
```

---

## Section 6: Improved Dedup Signature

**Changes to `src/splat/core/dedup.py`:**

```python
def generate_signature(
    exception: BaseException,
    tb: TracebackType | None = None,
) -> str:
    """
    Generate a unique signature for an exception.

    Returns:
        16-character hex signature (was 8)
    """
    # ... existing logic unchanged ...

    # Hash to 16 chars (was 8)
    signature_str = "|".join(components)
    hash_bytes = hashlib.md5(signature_str.encode()).hexdigest()
    return hash_bytes[:16]  # Changed from [:8]
```

No backward compatibility concerns - major version bump makes this a clean break.

---

## Section 7: Documentation Updates

**Changes to `docs/configuration.md`:**

Add new configuration options:

- `timeout` - API timeout in seconds (default: 30)
- `github_api_url` - GitHub API base URL (default: https://api.github.com)
- `ignore_exceptions` - List of exception types to ignore (programmatic only)
- Environment variables: `SPLAT_TIMEOUT`, `SPLAT_GITHUB_API_URL`

**Changes to `docs/how-it-works.md`:**

Add new sections:
- Background queue architecture (brief explanation)
- Retry behavior (3 attempts, exponential backoff)
- Payload truncation (mention limits exist, won't lose critical info)

**Changes to `docs/getting-started.md`:**

Add Django setup example alongside Flask/FastAPI.

**README.md:**

Minimal changes - just add Django to the supported frameworks list.

---

## Section 8: File Summary

### Files to Create

| File | Purpose |
|------|---------|
| `src/splat/core/queue.py` | ErrorQueue, ErrorReport, retry logic |
| `src/splat/core/http.py` | Shared GitHub API client helper |
| `src/splat/middleware/django.py` | Django middleware |
| `tests/test_queue.py` | Queue and retry tests |
| `tests/test_django.py` | Django middleware tests |

### Files to Modify

| File | Changes |
|------|---------|
| `src/splat/core/config.py` | New config options |
| `src/splat/core/reporter.py` | Queue integration, exception filtering, sync wrapper |
| `src/splat/core/dedup.py` | 16-char signature, use shared http client |
| `src/splat/core/formatter.py` | Truncation helpers |
| `src/splat/middleware/fastapi.py` | Use queue instead of direct report |
| `src/splat/middleware/flask.py` | Use queue instead of direct report |
| `pyproject.toml` | Version 1.0.0, update classifiers |
| `docs/configuration.md` | New options |
| `docs/getting-started.md` | Django example |
| `docs/how-it-works.md` | Queue/retry explanation |

### Version Bump

```toml
# pyproject.toml
version = "1.0.0"

classifiers = [
    "Development Status :: 4 - Beta",
    ...
]
```

### Test Updates

- Update existing tests for new signature length (16 chars)
- Add tests for retry logic, timeouts, exception filtering
- Add Django middleware tests
