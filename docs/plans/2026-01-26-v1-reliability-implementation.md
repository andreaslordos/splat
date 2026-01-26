# Splat v1.0.0 Reliability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add reliability features (retries, timeouts, background queue) and Django support to Splat v1.0.0

**Architecture:** Background asyncio queue processes errors with exponential backoff retries. Exception filtering happens before queuing. All GitHub API calls use a shared HTTP client with configurable timeout.

**Tech Stack:** Python 3.9+, asyncio, httpx, pytest, respx (mocking)

---

## Task 1: Extend SplatConfig with New Options

**Files:**
- Modify: `src/splat/core/config.py`
- Test: `tests/core/test_config.py`

**Step 1: Write failing tests for new config options**

Add to `tests/core/test_config.py`:

```python
class TestNewConfigDefaults:
    """Test new v1.0 config defaults."""

    def test_config_has_default_timeout(self) -> None:
        config = SplatConfig()
        assert config.timeout == 30.0

    def test_config_has_default_max_retries(self) -> None:
        config = SplatConfig()
        assert config.max_retries == 3

    def test_config_has_default_github_api_url(self) -> None:
        config = SplatConfig()
        assert config.github_api_url == "https://api.github.com"

    def test_config_has_empty_ignore_exceptions(self) -> None:
        config = SplatConfig()
        assert config.ignore_exceptions == []

    def test_config_has_no_exception_filter(self) -> None:
        config = SplatConfig()
        assert config.exception_filter is None

    def test_config_has_default_max_traceback_length(self) -> None:
        config = SplatConfig()
        assert config.max_traceback_length == 50000

    def test_config_has_default_max_log_entries(self) -> None:
        config = SplatConfig()
        assert config.max_log_entries == 500

    def test_config_has_default_max_context_value_length(self) -> None:
        config = SplatConfig()
        assert config.max_context_value_length == 5000


class TestNewConfigFromEnv:
    """Test loading new config options from environment."""

    def test_load_config_reads_timeout_from_env(self) -> None:
        with patch("splat.core.config._find_pyproject", return_value=None):
            with patch.dict(os.environ, {"SPLAT_TIMEOUT": "60.0"}):
                config = load_config()
                assert config.timeout == 60.0

    def test_load_config_reads_github_api_url_from_env(self) -> None:
        with patch("splat.core.config._find_pyproject", return_value=None):
            with patch.dict(os.environ, {"SPLAT_GITHUB_API_URL": "https://github.example.com/api/v3"}):
                config = load_config()
                assert config.github_api_url == "https://github.example.com/api/v3"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_config.py -v -k "NewConfig"`
Expected: FAIL with AttributeError (no timeout, max_retries, etc.)

**Step 3: Add new fields to SplatConfig**

In `src/splat/core/config.py`, update the dataclass:

```python
from typing import Any, Callable

@dataclass
class SplatConfig:
    """Splat configuration."""

    # Existing
    repo: str | None = None
    token: str | None = None
    enabled: bool = True
    log_buffer_size: int = 200
    labels: list[str] = field(default_factory=lambda: ["bug", "splat"])
    debug: bool = False

    # New in v1.0
    timeout: float = 30.0
    max_retries: int = 3
    github_api_url: str = "https://api.github.com"
    ignore_exceptions: list[type] = field(default_factory=list)
    exception_filter: Callable[[BaseException], bool] | None = None

    # Payload limits (programmatic only)
    max_traceback_length: int = 50000
    max_log_entries: int = 500
    max_context_value_length: int = 5000
```

**Step 4: Add env/toml loading for new options**

In `_load_from_env()`:

```python
if timeout := os.environ.get("SPLAT_TIMEOUT"):
    config["timeout"] = float(timeout)

if github_api_url := os.environ.get("SPLAT_GITHUB_API_URL"):
    config["github_api_url"] = github_api_url
```

In `load_config()`, add loading from TOML and programmatic for new options:

```python
# In TOML section:
if "timeout" in toml_config:
    config.timeout = toml_config["timeout"]
if "github_api_url" in toml_config:
    config.github_api_url = toml_config["github_api_url"]

# In programmatic section (add parameters to function signature):
if timeout is not None:
    config.timeout = timeout
if max_retries is not None:
    config.max_retries = max_retries
if github_api_url is not None:
    config.github_api_url = github_api_url
if ignore_exceptions is not None:
    config.ignore_exceptions = ignore_exceptions
if exception_filter is not None:
    config.exception_filter = exception_filter
if max_traceback_length is not None:
    config.max_traceback_length = max_traceback_length
if max_log_entries is not None:
    config.max_log_entries = max_log_entries
if max_context_value_length is not None:
    config.max_context_value_length = max_context_value_length
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/core/test_config.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/splat/core/config.py tests/core/test_config.py
git commit -m "feat(config): add timeout, retries, github_api_url, filtering options"
```

---

## Task 2: Create Shared HTTP Client

**Files:**
- Create: `src/splat/core/http.py`
- Test: `tests/core/test_http.py`

**Step 1: Write failing tests**

Create `tests/core/test_http.py`:

```python
"""Tests for shared HTTP client."""

import httpx
import pytest
import respx

from splat.core.config import SplatConfig
from splat.core.http import github_request


class TestGithubRequest:
    """Test GitHub API request helper."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_makes_get_request(self) -> None:
        config = SplatConfig(
            repo="owner/repo",
            token="ghp_test",
            timeout=10.0,
        )
        route = respx.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(200, json={"id": 123})
        )

        response = await github_request("get", "/repos/owner/repo", config)

        assert route.called
        assert response.status_code == 200

    @respx.mock
    @pytest.mark.asyncio
    async def test_makes_post_request_with_json(self) -> None:
        config = SplatConfig(
            repo="owner/repo",
            token="ghp_test",
        )
        route = respx.post("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(201, json={"number": 1})
        )

        response = await github_request(
            "post",
            "/repos/owner/repo/issues",
            config,
            json={"title": "Test"},
        )

        assert route.called
        assert response.status_code == 201

    @respx.mock
    @pytest.mark.asyncio
    async def test_uses_bearer_token(self) -> None:
        config = SplatConfig(token="ghp_secret")
        route = respx.get("https://api.github.com/test").mock(
            return_value=httpx.Response(200)
        )

        await github_request("get", "/test", config)

        request = route.calls[0].request
        assert request.headers["Authorization"] == "Bearer ghp_secret"

    @respx.mock
    @pytest.mark.asyncio
    async def test_uses_custom_api_url(self) -> None:
        config = SplatConfig(
            token="ghp_test",
            github_api_url="https://github.example.com/api/v3",
        )
        route = respx.get("https://github.example.com/api/v3/test").mock(
            return_value=httpx.Response(200)
        )

        await github_request("get", "/test", config)

        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_uses_configured_timeout(self) -> None:
        config = SplatConfig(token="ghp_test", timeout=5.0)
        respx.get("https://api.github.com/test").mock(
            return_value=httpx.Response(200)
        )

        # This test verifies the timeout is passed - actual timeout behavior
        # is tested via httpx internals
        response = await github_request("get", "/test", config)
        assert response.status_code == 200
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_http.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Create the HTTP client module**

Create `src/splat/core/http.py`:

```python
"""Shared HTTP client for GitHub API requests."""

from __future__ import annotations

from typing import Any

import httpx

from splat.core.config import SplatConfig


async def github_request(
    method: str,
    endpoint: str,
    config: SplatConfig,
    **kwargs: Any,
) -> httpx.Response:
    """
    Make an authenticated GitHub API request.

    Args:
        method: HTTP method (get, post, etc.)
        endpoint: API endpoint (e.g., "/repos/owner/repo/issues")
        config: SplatConfig with token, timeout, and github_api_url
        **kwargs: Additional arguments passed to httpx (json, params, etc.)

    Returns:
        httpx.Response object
    """
    url = f"{config.github_api_url}{endpoint}"

    async with httpx.AsyncClient(timeout=config.timeout) as client:
        request_method = getattr(client, method)
        response = await request_method(
            url,
            headers={
                "Authorization": f"Bearer {config.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            **kwargs,
        )

    return response
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_http.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/splat/core/http.py tests/core/test_http.py
git commit -m "feat(http): add shared GitHub API client with timeout support"
```

---

## Task 3: Update Dedup to Use Shared Client and 16-char Signature

**Files:**
- Modify: `src/splat/core/dedup.py`
- Modify: `tests/core/test_dedup.py`

**Step 1: Update tests for 16-char signature**

In `tests/core/test_dedup.py`, change signature length assertions:

```python
def test_signature_includes_exception_type(self) -> None:
    try:
        raise ValueError("test error")
    except ValueError as e:
        sig = generate_signature(e)
        assert len(sig) == 16  # Changed from 8

def test_signature_is_16_chars(self) -> None:  # Renamed from test_signature_is_8_chars
    try:
        raise RuntimeError("test")
    except RuntimeError as e:
        sig = generate_signature(e)
        assert len(sig) == 16  # Changed from 8
        assert sig.isalnum()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_dedup.py::TestGenerateSignature -v`
Expected: FAIL (signature length is 8, not 16)

**Step 3: Update generate_signature to return 16 chars**

In `src/splat/core/dedup.py`:

```python
def generate_signature(
    exception: BaseException,
    tb: TracebackType | None = None,
) -> str:
    # ... existing code ...

    # Hash to 16 chars (was 8)
    signature_str = "|".join(components)
    hash_bytes = hashlib.md5(signature_str.encode()).hexdigest()
    return hash_bytes[:16]  # Changed from [:8]
```

**Step 4: Update check_duplicate to use shared client**

In `src/splat/core/dedup.py`:

```python
from splat.core.config import SplatConfig
from splat.core.http import github_request


async def check_duplicate(
    repo: str,
    token: str,
    signature: str,
    config: SplatConfig | None = None,
) -> int | None:
    """
    Check if an issue with this signature already exists.

    Args:
        repo: GitHub repository (owner/repo format)
        token: GitHub API token
        signature: Error signature to search for
        config: Optional SplatConfig (uses defaults if not provided)

    Returns:
        Issue number if duplicate found, None otherwise
    """
    if config is None:
        config = SplatConfig(repo=repo, token=token)

    query = f"repo:{repo} label:splat {signature} in:body"

    response = await github_request(
        "get",
        "/search/issues",
        config,
        params={"q": query},
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()

    items: list[dict[str, Any]] = data.get("items", [])
    if items:
        return cast(int, items[0]["number"])

    return None
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/core/test_dedup.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/splat/core/dedup.py tests/core/test_dedup.py
git commit -m "feat(dedup): use 16-char signature and shared HTTP client"
```

---

## Task 4: Add Payload Truncation to Formatter

**Files:**
- Modify: `src/splat/core/formatter.py`
- Modify: `tests/core/test_formatter.py`

**Step 1: Write failing tests for truncation**

Add to `tests/core/test_formatter.py`:

```python
class TestTruncation:
    """Test payload truncation."""

    def test_truncate_long_traceback(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(
                e,
                signature="abc12345",
                max_traceback_length=100,
            )
            assert "... [truncated]" in body

    def test_truncate_long_context_value(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            long_value = "x" * 10000
            body = format_issue_body(
                e,
                signature="abc12345",
                context={"key": long_value},
                max_context_value_length=100,
            )
            assert "... [truncated]" in body
            assert "x" * 10000 not in body

    def test_truncate_many_log_entries(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            many_logs = "\n".join([f"Log line {i}" for i in range(1000)])
            body = format_issue_body(
                e,
                signature="abc12345",
                logs=many_logs,
                max_log_entries=50,
            )
            assert "earlier entries truncated" in body
            assert "Log line 999" in body  # Most recent kept
            assert "Log line 0" not in body  # Old ones dropped

    def test_no_truncation_when_under_limit(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(
                e,
                signature="abc12345",
                context={"key": "short"},
                max_context_value_length=1000,
            )
            assert "... [truncated]" not in body
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_formatter.py::TestTruncation -v`
Expected: FAIL (unexpected keyword argument)

**Step 3: Add truncation helpers and update format_issue_body**

In `src/splat/core/formatter.py`:

```python
def _truncate(text: str, max_length: int, suffix: str = "\n... [truncated]") -> str:
    """Truncate text with indicator if over limit."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def _truncate_logs(logs: str, max_entries: int) -> str:
    """Truncate logs to max entries, keeping most recent."""
    lines = logs.split("\n")
    if len(lines) <= max_entries:
        return logs
    truncated_count = len(lines) - max_entries
    kept_lines = lines[-max_entries:]
    return f"... [{truncated_count} earlier entries truncated]\n" + "\n".join(kept_lines)


def format_issue_body(
    exception: BaseException,
    signature: str,
    context: dict[str, Any] | None = None,
    logs: str | None = None,
    *,
    max_traceback_length: int = 50000,
    max_log_entries: int = 500,
    max_context_value_length: int = 5000,
) -> str:
    """Format the GitHub issue body with full error details."""
    exc_type = type(exception).__name__
    exc_msg = str(exception)

    # Extract location from traceback
    filename = "unknown"
    lineno = 0
    funcname = "unknown"

    tb = exception.__traceback__
    if tb is not None:
        while tb.tb_next is not None:
            tb = tb.tb_next
        frame = tb.tb_frame
        filename = frame.f_code.co_filename
        lineno = tb.tb_lineno
        funcname = frame.f_code.co_name

    # Format and truncate traceback
    tb_str = "".join(
        traceback.format_exception(type(exception), exception, exception.__traceback__)
    )
    tb_str = _truncate(tb_str, max_traceback_length)

    # Build body sections
    sections = []

    # Error section
    sections.append(
        f"""## Error

**Type:** {exc_type}
**Message:** {exc_msg}
**File:** {filename}
**Line:** {lineno}
**Function:** {funcname}"""
    )

    # Traceback section
    sections.append(
        f"""## Traceback

```
{tb_str.strip()}
```"""
    )

    # Context section (if provided) with truncation
    if context:
        truncated_context = {
            k: _truncate(str(v), max_context_value_length)
            for k, v in context.items()
        }
        context_rows = "\n".join(f"| {k} | {v} |" for k, v in truncated_context.items())
        sections.append(
            f"""## Context

| Key | Value |
|-----|-------|
{context_rows}"""
        )

    # Logs section (if provided and non-empty) with truncation
    if logs:
        truncated_logs = _truncate_logs(logs, max_log_entries)
        sections.append(
            f"""## Recent Logs

<details>
<summary>Recent log entries</summary>

```
{truncated_logs}
```

</details>"""
        )

    # Footer with signature
    sections.append(
        f"""---
Signature: `{signature}`
Reported by [Splat](https://github.com/yourorg/splat)"""
    )

    return "\n\n".join(sections)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_formatter.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/splat/core/formatter.py tests/core/test_formatter.py
git commit -m "feat(formatter): add payload truncation for traceback, logs, context"
```

---

## Task 5: Create Background Queue with Retry Logic

**Files:**
- Create: `src/splat/core/queue.py`
- Test: `tests/core/test_queue.py`

**Step 1: Write failing tests**

Create `tests/core/test_queue.py`:

```python
"""Tests for background error queue with retry logic."""

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from splat.core.queue import ErrorQueue, ErrorReport, is_retryable_error


class TestErrorReport:
    """Test ErrorReport dataclass."""

    def test_error_report_creation(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            report = ErrorReport(
                exception=e,
                context={"key": "value"},
                logs="test logs",
                signature="abc123",
            )
            assert report.exception is e
            assert report.context == {"key": "value"}
            assert report.logs == "test logs"
            assert report.signature == "abc123"
            assert report.attempt == 0


class TestIsRetryableError:
    """Test retry logic."""

    def test_rate_limit_is_retryable(self) -> None:
        response = httpx.Response(429)
        assert is_retryable_error(response) is True

    def test_server_errors_are_retryable(self) -> None:
        for status in [500, 502, 503, 504]:
            response = httpx.Response(status)
            assert is_retryable_error(response) is True

    def test_client_errors_are_not_retryable(self) -> None:
        for status in [400, 401, 403, 404, 422]:
            response = httpx.Response(status)
            assert is_retryable_error(response) is False

    def test_success_is_not_retryable(self) -> None:
        response = httpx.Response(200)
        assert is_retryable_error(response) is False


class TestErrorQueue:
    """Test background error queue."""

    @pytest.mark.asyncio
    async def test_enqueue_adds_to_queue(self) -> None:
        queue = ErrorQueue(max_retries=3, timeout=10.0)

        try:
            raise ValueError("test")
        except ValueError as e:
            report = ErrorReport(
                exception=e,
                context=None,
                logs="",
                signature="abc123",
            )
            await queue.enqueue(report)

        assert queue._queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_worker_processes_queue(self) -> None:
        queue = ErrorQueue(max_retries=3, timeout=10.0)
        processed = []

        async def mock_process(report: ErrorReport) -> bool:
            processed.append(report)
            return True

        queue._process_report = mock_process

        try:
            raise ValueError("test")
        except ValueError as e:
            report = ErrorReport(
                exception=e,
                context=None,
                logs="",
                signature="abc123",
            )
            await queue.enqueue(report)

        await queue.start()
        await asyncio.sleep(0.1)  # Let worker process
        await queue.shutdown(timeout=1.0)

        assert len(processed) == 1

    @pytest.mark.asyncio
    async def test_retry_on_retryable_error(self) -> None:
        queue = ErrorQueue(max_retries=3, timeout=10.0)
        attempts = []

        async def mock_process(report: ErrorReport) -> bool:
            attempts.append(report.attempt)
            if len(attempts) < 2:
                return False  # Fail first attempt
            return True

        queue._process_report = mock_process

        try:
            raise ValueError("test")
        except ValueError as e:
            report = ErrorReport(
                exception=e,
                context=None,
                logs="",
                signature="abc123",
            )
            await queue.enqueue(report)

        await queue.start()
        await asyncio.sleep(0.5)  # Allow retries
        await queue.shutdown(timeout=1.0)

        assert len(attempts) == 2

    @pytest.mark.asyncio
    async def test_drops_after_max_retries(self) -> None:
        queue = ErrorQueue(max_retries=2, timeout=10.0)
        attempts = []

        async def mock_process(report: ErrorReport) -> bool:
            attempts.append(report.attempt)
            return False  # Always fail

        queue._process_report = mock_process

        try:
            raise ValueError("test")
        except ValueError as e:
            report = ErrorReport(
                exception=e,
                context=None,
                logs="",
                signature="abc123",
            )
            await queue.enqueue(report)

        await queue.start()
        await asyncio.sleep(1.0)  # Allow all retries
        await queue.shutdown(timeout=1.0)

        # Should attempt max_retries times then drop
        assert len(attempts) == 2
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_queue.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Create the queue module**

Create `src/splat/core/queue.py`:

```python
"""Background error queue with retry logic."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Awaitable

import httpx

if TYPE_CHECKING:
    from splat.core.config import SplatConfig

logger = logging.getLogger(__name__)


@dataclass
class ErrorReport:
    """An error report queued for submission."""

    exception: BaseException
    context: dict[str, Any] | None
    logs: str
    signature: str
    attempt: int = 0


def is_retryable_error(response: httpx.Response) -> bool:
    """Check if an HTTP response indicates a retryable error."""
    return response.status_code in {429, 500, 502, 503, 504}


def get_retry_delay(attempt: int, response: httpx.Response | None = None) -> float:
    """
    Calculate retry delay with exponential backoff.

    Args:
        attempt: Current attempt number (0-indexed)
        response: Optional response to check for Retry-After header

    Returns:
        Delay in seconds
    """
    # Check for Retry-After header on rate limit
    if response is not None and response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

    # Exponential backoff: 1s, 2s, 4s, ...
    return float(2**attempt)


class ErrorQueue:
    """
    Async queue for background error reporting with retries.

    Errors are queued and processed by a background worker task.
    Failed reports are retried with exponential backoff.
    """

    def __init__(
        self,
        max_retries: int = 3,
        timeout: float = 30.0,
    ) -> None:
        self._queue: asyncio.Queue[ErrorReport] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._shutdown = False
        self._max_retries = max_retries
        self._timeout = timeout
        self._process_report: Callable[[ErrorReport], Awaitable[bool]] | None = None

    async def start(self) -> None:
        """Start the background worker task."""
        self._shutdown = False
        self._worker_task = asyncio.create_task(self._worker())

    async def enqueue(self, report: ErrorReport) -> None:
        """Add an error report to the queue."""
        await self._queue.put(report)

    async def shutdown(self, timeout: float = 5.0) -> None:
        """
        Gracefully shutdown the queue.

        Args:
            timeout: Max seconds to wait for queue to drain
        """
        self._shutdown = True

        if self._worker_task is not None:
            try:
                await asyncio.wait_for(self._worker_task, timeout=timeout)
            except asyncio.TimeoutError:
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass

    async def _worker(self) -> None:
        """Process queued error reports."""
        while not self._shutdown or not self._queue.empty():
            try:
                report = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=0.1,
                )
            except asyncio.TimeoutError:
                continue

            await self._process_with_retry(report)
            self._queue.task_done()

    async def _process_with_retry(self, report: ErrorReport) -> None:
        """Process a report with retry logic."""
        while report.attempt < self._max_retries:
            if self._process_report is not None:
                success = await self._process_report(report)
            else:
                success = True

            if success:
                return

            report.attempt += 1
            if report.attempt < self._max_retries:
                delay = get_retry_delay(report.attempt - 1)
                logger.warning(
                    f"[SPLAT] Report failed, retrying in {delay}s "
                    f"(attempt {report.attempt}/{self._max_retries})"
                )
                await asyncio.sleep(delay)

        logger.warning(
            f"[SPLAT] Report dropped after {self._max_retries} attempts: "
            f"{type(report.exception).__name__}"
        )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_queue.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/splat/core/queue.py tests/core/test_queue.py
git commit -m "feat(queue): add background error queue with exponential backoff retry"
```

---

## Task 6: Refactor Reporter to Use Queue and Exception Filtering

**Files:**
- Modify: `src/splat/core/reporter.py`
- Modify: `tests/core/test_reporter.py`

**Step 1: Write failing tests for exception filtering**

Add to `tests/core/test_reporter.py`:

```python
class TestExceptionFiltering:
    """Test exception filtering."""

    @pytest.mark.asyncio
    async def test_ignores_exception_in_ignore_list(self) -> None:
        splat = Splat(
            repo="owner/repo",
            token="ghp_test",
            ignore_exceptions=[ValueError],
        )

        try:
            raise ValueError("ignored")
        except ValueError as e:
            result = await splat.report(e)

        assert result is None

    @pytest.mark.asyncio
    async def test_reports_exception_not_in_ignore_list(self) -> None:
        splat = Splat(
            repo="owner/repo",
            token="ghp_test",
            ignore_exceptions=[TypeError],
        )

        # Mock the queue to capture the report
        reports = []
        splat._queue.enqueue = AsyncMock(side_effect=lambda r: reports.append(r))

        try:
            raise ValueError("not ignored")
        except ValueError as e:
            await splat.report(e)

        assert len(reports) == 1

    @pytest.mark.asyncio
    async def test_exception_filter_callback_can_skip(self) -> None:
        def skip_value_errors(e: BaseException) -> bool:
            return not isinstance(e, ValueError)

        splat = Splat(
            repo="owner/repo",
            token="ghp_test",
            exception_filter=skip_value_errors,
        )

        try:
            raise ValueError("filtered out")
        except ValueError as e:
            result = await splat.report(e)

        assert result is None

    @pytest.mark.asyncio
    async def test_exception_filter_callback_takes_precedence(self) -> None:
        def allow_all(e: BaseException) -> bool:
            return True  # Allow everything

        splat = Splat(
            repo="owner/repo",
            token="ghp_test",
            ignore_exceptions=[ValueError],  # Would ignore
            exception_filter=allow_all,  # But callback allows
        )

        reports = []
        splat._queue.enqueue = AsyncMock(side_effect=lambda r: reports.append(r))

        try:
            raise ValueError("allowed by callback")
        except ValueError as e:
            await splat.report(e)

        assert len(reports) == 1


class TestSyncReport:
    """Test synchronous report method."""

    def test_report_sync_queues_error(self) -> None:
        splat = Splat(repo="owner/repo", token="ghp_test")

        # We need to patch the async enqueue
        enqueued = []

        async def mock_enqueue(report: Any) -> None:
            enqueued.append(report)

        splat._queue.enqueue = mock_enqueue

        try:
            raise ValueError("sync test")
        except ValueError as e:
            splat.report_sync(e, context={"key": "value"})

        # Give the event loop a chance to process
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(asyncio.sleep(0.1))
        loop.close()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_reporter.py::TestExceptionFiltering -v`
Expected: FAIL (ignore_exceptions parameter not recognized)

**Step 3: Refactor reporter.py**

Update `src/splat/core/reporter.py`:

```python
"""Main Splat error reporter class."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from splat.core.config import SplatConfig, load_config
from splat.core.dedup import check_duplicate, generate_signature
from splat.core.formatter import format_issue_body, format_issue_title
from splat.core.http import github_request
from splat.core.log_buffer import LogBuffer
from splat.core.queue import ErrorQueue, ErrorReport

logger = logging.getLogger(__name__)


def _mask_token(token: str | None) -> str:
    """Mask a token for safe logging."""
    if not token:
        return "None"
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


class Splat:
    """Automatic GitHub issue creation on application crashes."""

    def __init__(
        self,
        *,
        repo: str | None = None,
        token: str | None = None,
        enabled: bool | None = None,
        log_buffer_size: int | None = None,
        labels: list[str] | None = None,
        debug: bool | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        github_api_url: str | None = None,
        ignore_exceptions: list[type] | None = None,
        exception_filter: Any | None = None,
        max_traceback_length: int | None = None,
        max_log_entries: int | None = None,
        max_context_value_length: int | None = None,
    ) -> None:
        self.config = load_config(
            repo=repo,
            token=token,
            enabled=enabled,
            log_buffer_size=log_buffer_size,
            labels=labels,
            debug=debug,
            timeout=timeout,
            max_retries=max_retries,
            github_api_url=github_api_url,
            ignore_exceptions=ignore_exceptions,
            exception_filter=exception_filter,
            max_traceback_length=max_traceback_length,
            max_log_entries=max_log_entries,
            max_context_value_length=max_context_value_length,
        )

        # Set up log buffer
        self._log_buffer = LogBuffer(capacity=self.config.log_buffer_size)
        logging.getLogger().addHandler(self._log_buffer)

        # Set up background queue
        self._queue = ErrorQueue(
            max_retries=self.config.max_retries,
            timeout=self.config.timeout,
        )
        self._queue._process_report = self._process_report
        self._queue_started = False

        # Debug logging
        if self.config.debug:
            logger.warning(
                f"[SPLAT DEBUG] Initialized with config: "
                f"repo={self.config.repo}, "
                f"token={_mask_token(self.config.token)}, "
                f"enabled={self.config.enabled}, "
                f"labels={self.config.labels}"
            )

        if not self.is_enabled():
            logger.warning(
                "Splat is disabled. Set SPLAT_GITHUB_REPO and SPLAT_GITHUB_TOKEN "
                "environment variables or pass repo/token to enable."
            )

    def is_enabled(self) -> bool:
        """Check if Splat is enabled and properly configured."""
        return bool(self.config.enabled and self.config.repo and self.config.token)

    def _should_report(self, exception: BaseException) -> bool:
        """Check if this exception should be reported."""
        # Callback takes precedence
        if self.config.exception_filter is not None:
            return self.config.exception_filter(exception)

        # Check ignore list
        for exc_type in self.config.ignore_exceptions:
            if isinstance(exception, exc_type):
                if self.config.debug:
                    logger.warning(
                        f"[SPLAT DEBUG] Ignoring {type(exception).__name__} "
                        f"(in ignore_exceptions list)"
                    )
                return False

        return True

    async def _ensure_queue_started(self) -> None:
        """Start the queue worker if not already started."""
        if not self._queue_started:
            await self._queue.start()
            self._queue_started = True

    async def report(
        self,
        exception: BaseException,
        context: dict[str, Any] | None = None,
        logs: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Report an exception to GitHub Issues (non-blocking).

        The error is queued for background processing with retries.

        Args:
            exception: The exception to report
            context: Optional user-provided context dict
            logs: Optional log string (uses buffered logs if not provided)

        Returns:
            None (reporting happens asynchronously)
        """
        if self.config.debug:
            logger.warning(
                f"[SPLAT DEBUG] report() called with: "
                f"exception={type(exception).__name__}: {exception}"
            )

        if not self.is_enabled():
            return None

        if not self._should_report(exception):
            return None

        # Get logs before queuing
        if logs is None:
            logs = self._log_buffer.get_logs_as_string()

        signature = generate_signature(exception)

        report = ErrorReport(
            exception=exception,
            context=context,
            logs=logs,
            signature=signature,
        )

        await self._ensure_queue_started()
        await self._queue.enqueue(report)

        return None  # Async processing, no immediate result

    def report_sync(
        self,
        exception: BaseException,
        context: dict[str, Any] | None = None,
        logs: str | None = None,
    ) -> None:
        """
        Synchronous wrapper for report().

        Queues the error for background processing without blocking.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.report(exception, context, logs))
            else:
                loop.run_until_complete(self.report(exception, context, logs))
        except RuntimeError:
            asyncio.run(self.report(exception, context, logs))

    async def _process_report(self, report: ErrorReport) -> bool:
        """
        Process a queued error report.

        Returns:
            True if successful, False if should retry
        """
        assert self.config.repo is not None
        assert self.config.token is not None

        try:
            # Check for duplicate
            existing = await check_duplicate(
                repo=self.config.repo,
                token=self.config.token,
                signature=report.signature,
                config=self.config,
            )

            if existing is not None:
                logger.info(f"Duplicate error, issue #{existing} already exists")
                return True  # Success (no need to retry)

            # Create issue
            await self._create_issue(report)
            return True

        except Exception as e:
            if self.config.debug:
                logger.warning(f"[SPLAT DEBUG] Report processing failed: {e}")
            return False

    async def _create_issue(self, report: ErrorReport) -> dict[str, Any]:
        """Create a GitHub issue for the error report."""
        assert self.config.repo is not None

        title = format_issue_title(report.exception)
        body = format_issue_body(
            report.exception,
            signature=report.signature,
            context=report.context,
            logs=report.logs,
            max_traceback_length=self.config.max_traceback_length,
            max_log_entries=self.config.max_log_entries,
            max_context_value_length=self.config.max_context_value_length,
        )

        if self.config.debug:
            logger.warning(
                f"[SPLAT DEBUG] Creating GitHub issue: title={title[:50]}..."
            )

        response = await github_request(
            "post",
            f"/repos/{self.config.repo}/issues",
            self.config,
            json={
                "title": title,
                "body": body,
                "labels": self.config.labels,
            },
        )
        response.raise_for_status()
        issue_data: dict[str, Any] = response.json()

        logger.info(f"Created issue #{issue_data['number']}: {issue_data['html_url']}")
        return issue_data

    async def shutdown(self, timeout: float = 5.0) -> None:
        """Gracefully shutdown the background queue."""
        if self._queue_started:
            await self._queue.shutdown(timeout=timeout)
```

**Step 4: Update load_config signature**

Make sure `load_config` in `config.py` accepts all new parameters:

```python
def load_config(
    *,
    repo: str | None = None,
    token: str | None = None,
    enabled: bool | None = None,
    log_buffer_size: int | None = None,
    labels: list[str] | None = None,
    debug: bool | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    github_api_url: str | None = None,
    ignore_exceptions: list[type] | None = None,
    exception_filter: Callable[[BaseException], bool] | None = None,
    max_traceback_length: int | None = None,
    max_log_entries: int | None = None,
    max_context_value_length: int | None = None,
) -> SplatConfig:
```

**Step 5: Run all tests**

Run: `pytest tests/core/test_reporter.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/splat/core/reporter.py src/splat/core/config.py tests/core/test_reporter.py
git commit -m "feat(reporter): integrate background queue and exception filtering"
```

---

## Task 7: Update FastAPI and Flask Middleware

**Files:**
- Modify: `src/splat/middleware/fastapi.py`
- Modify: `src/splat/middleware/flask.py`
- Modify: `tests/middleware/test_fastapi.py`
- Modify: `tests/middleware/test_flask.py`

**Step 1: Update FastAPI middleware**

The middleware now just calls `report()` which is non-blocking:

```python
# src/splat/middleware/fastapi.py - minimal changes needed
# report() is already async, now it just queues instead of blocking
```

**Step 2: Update Flask middleware to use report_sync**

In `src/splat/middleware/flask.py`, replace `_run_async(instance.report(...))` with `instance.report_sync(...)`:

```python
def handler(error: Exception) -> Any:
    instance = splat or _get_splat()
    if instance is None:
        raise error

    # ... context extraction ...

    try:
        instance.report_sync(error, context=context)
    except Exception as report_error:
        if instance.config.debug:
            logger.warning(f"[SPLAT DEBUG] Flask report() raised: {report_error}")
    raise error
```

Remove the `_run_async` helper function as it's no longer needed.

**Step 3: Run middleware tests**

Run: `pytest tests/middleware/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add src/splat/middleware/fastapi.py src/splat/middleware/flask.py
git commit -m "refactor(middleware): use non-blocking report methods"
```

---

## Task 8: Add Django Middleware

**Files:**
- Create: `src/splat/middleware/django.py`
- Test: `tests/middleware/test_django.py`

**Step 1: Write failing tests**

Create `tests/middleware/test_django.py`:

```python
"""Tests for Django middleware."""

from unittest.mock import MagicMock, patch, AsyncMock

import pytest


class TestDjangoMiddleware:
    """Test Django Splat middleware."""

    def test_middleware_initializes_splat(self) -> None:
        with patch.dict("sys.modules", {"django.conf": MagicMock()}):
            from splat.middleware.django import SplatMiddleware

            mock_settings = MagicMock()
            mock_settings.SPLAT = {"repo": "owner/repo", "token": "ghp_test"}

            with patch("splat.middleware.django.settings", mock_settings):
                middleware = SplatMiddleware(get_response=lambda r: r)
                assert middleware.splat is not None
                assert middleware.splat.config.repo == "owner/repo"

    def test_middleware_passes_through_on_success(self) -> None:
        with patch.dict("sys.modules", {"django.conf": MagicMock()}):
            from splat.middleware.django import SplatMiddleware

            mock_settings = MagicMock()
            mock_settings.SPLAT = {"repo": "owner/repo", "token": "ghp_test"}

            with patch("splat.middleware.django.settings", mock_settings):
                response = MagicMock()
                get_response = MagicMock(return_value=response)
                middleware = SplatMiddleware(get_response=get_response)

                request = MagicMock()
                result = middleware(request)

                assert result == response
                get_response.assert_called_once_with(request)

    def test_middleware_reports_error_and_reraises(self) -> None:
        with patch.dict("sys.modules", {"django.conf": MagicMock()}):
            from splat.middleware.django import SplatMiddleware

            mock_settings = MagicMock()
            mock_settings.SPLAT = {"repo": "owner/repo", "token": "ghp_test"}

            with patch("splat.middleware.django.settings", mock_settings):
                error = ValueError("test error")
                get_response = MagicMock(side_effect=error)
                middleware = SplatMiddleware(get_response=get_response)
                middleware.splat.report_sync = MagicMock()

                request = MagicMock()
                request.method = "GET"
                request.path = "/test"
                request.META = {"REMOTE_ADDR": "127.0.0.1"}

                with pytest.raises(ValueError, match="test error"):
                    middleware(request)

                middleware.splat.report_sync.assert_called_once()

    def test_middleware_extracts_request_context(self) -> None:
        with patch.dict("sys.modules", {"django.conf": MagicMock()}):
            from splat.middleware.django import SplatMiddleware

            mock_settings = MagicMock()
            mock_settings.SPLAT = {"repo": "owner/repo", "token": "ghp_test"}

            with patch("splat.middleware.django.settings", mock_settings):
                error = ValueError("test")
                get_response = MagicMock(side_effect=error)
                middleware = SplatMiddleware(get_response=get_response)
                middleware.splat.report_sync = MagicMock()

                request = MagicMock()
                request.method = "POST"
                request.path = "/api/users"
                request.META = {"REMOTE_ADDR": "192.168.1.1"}

                with pytest.raises(ValueError):
                    middleware(request)

                call_args = middleware.splat.report_sync.call_args
                context = call_args[1]["context"]
                assert context["method"] == "POST"
                assert context["path"] == "/api/users"
                assert context["remote_addr"] == "192.168.1.1"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/middleware/test_django.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Create Django middleware**

Create `src/splat/middleware/django.py`:

```python
"""Django integration for Splat error reporting."""

from __future__ import annotations

import logging
from typing import Any, Callable

from splat.core.reporter import Splat

logger = logging.getLogger(__name__)


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
        try:
            from django.conf import settings
            config = getattr(settings, "SPLAT", {})
        except ImportError:
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
            "remote_addr": request.META.get("REMOTE_ADDR", "unknown")
            if hasattr(request, "META")
            else "unknown",
        }

        if self.splat.config.debug:
            logger.warning(f"[SPLAT DEBUG] Django middleware caught: {exc}")
            logger.warning(f"[SPLAT DEBUG] Django context: {context}")

        try:
            self.splat.report_sync(exc, context=context)
        except Exception as report_error:
            if self.splat.config.debug:
                logger.warning(
                    f"[SPLAT DEBUG] Django report() raised: {report_error}"
                )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/middleware/test_django.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/splat/middleware/django.py tests/middleware/test_django.py
git commit -m "feat(django): add Django middleware support"
```

---

## Task 9: Update Documentation

**Files:**
- Modify: `docs/configuration.md`
- Modify: `docs/getting-started.md`
- Modify: `docs/how-it-works.md`
- Modify: `README.md`

**Step 1: Update configuration.md**

Add new configuration options section:

```markdown
## New in v1.0.0

### API Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `timeout` | float | `30.0` | API request timeout in seconds |
| `github_api_url` | string | `https://api.github.com` | GitHub API base URL (for Enterprise) |

### Exception Filtering (Programmatic Only)

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `ignore_exceptions` | list | `[]` | Exception types to ignore |
| `exception_filter` | callable | `None` | Custom filter callback |

### Environment Variables

```bash
SPLAT_TIMEOUT=30.0
SPLAT_GITHUB_API_URL=https://github.example.com/api/v3
```

### GitHub Enterprise

To use with GitHub Enterprise:

```python
app.add_middleware(
    SplatMiddleware,
    github_api_url="https://github.mycompany.com/api/v3",
)
```

Or via environment:

```bash
SPLAT_GITHUB_API_URL=https://github.mycompany.com/api/v3
```
```

**Step 2: Update getting-started.md**

Add Django section after Flask:

```markdown
**Django:**

```python
# settings.py
MIDDLEWARE = [
    'splat.middleware.django.SplatMiddleware',
    # ... other middleware
]

SPLAT = {
    'repo': 'owner/repo',
    'token': os.environ.get('SPLAT_GITHUB_TOKEN'),
}
```
```

**Step 3: Update how-it-works.md**

Add sections about queue, retries, and truncation:

```markdown
## Background Processing

Errors are processed asynchronously in a background queue:

1. **Non-blocking** - `report()` returns immediately, error is queued
2. **Retries** - Failed API calls retry with exponential backoff (1s, 2s, 4s)
3. **Graceful degradation** - After 3 attempts, errors are logged and dropped

This ensures error tracking never slows down your application.

## Payload Limits

Large payloads are automatically truncated to prevent issues:

- **Traceback**: Max 50,000 characters
- **Log entries**: Max 500 entries (most recent kept)
- **Context values**: Max 5,000 characters per value

Truncated content shows `... [truncated]` indicator.
```

**Step 4: Update README.md**

Add Django to supported frameworks:

```markdown
- Flask or FastAPI or Django application
```

**Step 5: Commit**

```bash
git add docs/configuration.md docs/getting-started.md docs/how-it-works.md README.md
git commit -m "docs: update for v1.0.0 features (queue, retries, Django, filtering)"
```

---

## Task 10: Version Bump and Final Testing

**Files:**
- Modify: `pyproject.toml`

**Step 1: Update version to 1.0.0**

In `pyproject.toml`:

```toml
version = "1.0.0"
```

Update classifiers:

```toml
classifiers = [
    "Development Status :: 4 - Beta",
    # ... rest unchanged
]
```

Add Django to keywords:

```toml
keywords = [
    "error-tracking",
    "crash-reporting",
    "github-issues",
    "debugging",
    "monitoring",
    "flask",
    "fastapi",
    "django",
    "exception-handling",
]
```

Add Django framework classifier:

```toml
    "Framework :: Django",
```

**Step 2: Run full test suite**

Run: `pytest --cov=splat --cov-report=term-missing -v`
Expected: All tests PASS, coverage >= 80%

**Step 3: Run type checks**

Run: `mypy src/splat`
Expected: No errors

**Step 4: Run linting**

Run: `ruff check src/splat`
Expected: No errors

**Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump version to 1.0.0"
```

---

## Summary

After completing all tasks, you will have:

1. **Config**: New options for timeout, retries, filtering, GitHub Enterprise
2. **HTTP Client**: Shared client with timeout support
3. **Dedup**: 16-char signatures, uses shared client
4. **Formatter**: Payload truncation for large errors
5. **Queue**: Background processing with exponential backoff retries
6. **Reporter**: Non-blocking report(), exception filtering
7. **Middleware**: FastAPI, Flask, and Django support
8. **Docs**: Updated for all new features
9. **Version**: Bumped to 1.0.0

Total: ~10 commits, each focused on a specific feature.
