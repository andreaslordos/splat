# Vercel Logs Integration - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Vercel Log Drain integration so Splat can capture and include Vercel runtime logs in GitHub issues.

**Architecture:** Webhook receives logs from Vercel Log Drain, stores them keyed by request ID with TTL expiration. When an error occurs, middleware captures the `x-vercel-id` header and passes it to `splat.report()`, which fetches the logs for that specific request.

**Tech Stack:** Python 3.10+, httpx, pytest, Flask, FastAPI/Starlette

---

## Task 1: Configuration - Add Vercel Config Options

**Files:**
- Modify: `src/splat/core/config.py`
- Test: `tests/core/test_config.py`

**Step 1: Write the failing tests**

Add to `tests/core/test_config.py`:

```python
class TestVercelConfig:
    """Test Vercel-related configuration."""

    def test_load_config_vercel_secret_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPLAT_VERCEL_SECRET", "whsec_test123")
        config = load_config()
        assert config.vercel_secret == "whsec_test123"

    def test_load_config_vercel_secret_default_none(self) -> None:
        config = load_config()
        assert config.vercel_secret is None

    def test_load_config_vercel_webhook_path_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPLAT_VERCEL_WEBHOOK_PATH", "/custom/logs")
        config = load_config()
        assert config.vercel_webhook_path == "/custom/logs"

    def test_load_config_vercel_webhook_path_default(self) -> None:
        config = load_config()
        assert config.vercel_webhook_path == "/splat/logs"

    def test_load_config_vercel_log_ttl_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPLAT_VERCEL_LOG_TTL", "120")
        config = load_config()
        assert config.vercel_log_ttl == 120

    def test_load_config_vercel_log_ttl_default(self) -> None:
        config = load_config()
        assert config.vercel_log_ttl == 60

    def test_load_config_vercel_from_toml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('''
[tool.splat]
vercel_secret = "whsec_toml"
vercel_webhook_path = "/toml/logs"
vercel_log_ttl = 90
''')
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.vercel_secret == "whsec_toml"
        assert config.vercel_webhook_path == "/toml/logs"
        assert config.vercel_log_ttl == 90

    def test_load_config_vercel_programmatic_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPLAT_VERCEL_SECRET", "env_secret")
        config = load_config(vercel_secret="programmatic_secret")
        assert config.vercel_secret == "programmatic_secret"
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/core/test_config.py::TestVercelConfig -v
```

Expected: FAIL - `vercel_secret` attribute does not exist

**Step 3: Implement the configuration changes**

Update `src/splat/core/config.py`:

1. Add to `SplatConfig` dataclass:
```python
@dataclass
class SplatConfig:
    """Splat configuration."""

    repo: str | None = None
    token: str | None = None
    enabled: bool = True
    log_buffer_size: int = 200
    labels: list[str] = field(default_factory=lambda: ["bug", "splat"])
    # Vercel integration
    vercel_secret: str | None = None
    vercel_webhook_path: str = "/splat/logs"
    vercel_log_ttl: int = 60
```

2. Add to `_load_from_env()`:
```python
if vercel_secret := os.environ.get("SPLAT_VERCEL_SECRET"):
    config["vercel_secret"] = vercel_secret

if vercel_webhook_path := os.environ.get("SPLAT_VERCEL_WEBHOOK_PATH"):
    config["vercel_webhook_path"] = vercel_webhook_path

if vercel_log_ttl := os.environ.get("SPLAT_VERCEL_LOG_TTL"):
    config["vercel_log_ttl"] = int(vercel_log_ttl)
```

3. Add to toml loading section in `load_config()`:
```python
if "vercel_secret" in toml_config:
    config.vercel_secret = toml_config["vercel_secret"]
if "vercel_webhook_path" in toml_config:
    config.vercel_webhook_path = toml_config["vercel_webhook_path"]
if "vercel_log_ttl" in toml_config:
    config.vercel_log_ttl = toml_config["vercel_log_ttl"]
```

4. Add to programmatic override section in `load_config()`:
```python
if vercel_secret is not None:
    config.vercel_secret = vercel_secret
if vercel_webhook_path is not None:
    config.vercel_webhook_path = vercel_webhook_path
if vercel_log_ttl is not None:
    config.vercel_log_ttl = vercel_log_ttl
```

5. Update `load_config()` function signature:
```python
def load_config(
    *,
    repo: str | None = None,
    token: str | None = None,
    enabled: bool | None = None,
    log_buffer_size: int | None = None,
    labels: list[str] | None = None,
    vercel_secret: str | None = None,
    vercel_webhook_path: str | None = None,
    vercel_log_ttl: int | None = None,
) -> SplatConfig:
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/core/test_config.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
cd /Users/andreas/Desktop/projects/splat && git add src/splat/core/config.py tests/core/test_config.py && git commit -m "feat(config): add Vercel integration config options"
```

---

## Task 2: VercelLogStore - Request-Keyed Storage

**Files:**
- Create: `src/splat/core/vercel_logs.py`
- Create: `tests/core/test_vercel_logs.py`

**Step 1: Write the failing tests**

Create `tests/core/test_vercel_logs.py`:

```python
"""Tests for Vercel log storage."""

from __future__ import annotations

import time

import pytest

from splat.core.vercel_logs import VercelLogStore


class TestVercelLogStore:
    """Test VercelLogStore class."""

    def test_add_logs_stores_by_request_id(self) -> None:
        store = VercelLogStore(ttl_seconds=60)
        logs = [
            {"requestId": "req-123", "message": "Log 1", "timestamp": 1000},
            {"requestId": "req-123", "message": "Log 2", "timestamp": 1001},
        ]
        store.add_logs(logs)

        result = store.get_logs("req-123")
        assert len(result) == 2
        assert result[0]["message"] == "Log 1"
        assert result[1]["message"] == "Log 2"

    def test_add_logs_groups_by_request_id(self) -> None:
        store = VercelLogStore(ttl_seconds=60)
        logs = [
            {"requestId": "req-1", "message": "Request 1 Log"},
            {"requestId": "req-2", "message": "Request 2 Log"},
            {"requestId": "req-1", "message": "Request 1 Another"},
        ]
        store.add_logs(logs)

        assert len(store.get_logs("req-1")) == 2
        assert len(store.get_logs("req-2")) == 1

    def test_add_logs_skips_entries_without_request_id(self) -> None:
        store = VercelLogStore(ttl_seconds=60)
        logs = [
            {"requestId": "req-123", "message": "Valid"},
            {"message": "No request ID"},
            {"requestId": None, "message": "Null request ID"},
        ]
        store.add_logs(logs)

        assert len(store.get_logs("req-123")) == 1

    def test_get_logs_returns_empty_for_unknown_request(self) -> None:
        store = VercelLogStore(ttl_seconds=60)
        result = store.get_logs("unknown-req")
        assert result == []

    def test_pop_logs_removes_logs_after_retrieval(self) -> None:
        store = VercelLogStore(ttl_seconds=60)
        store.add_logs([{"requestId": "req-123", "message": "Test"}])

        result = store.pop_logs("req-123")
        assert len(result) == 1

        # Should be empty now
        assert store.get_logs("req-123") == []

    def test_pop_logs_returns_empty_for_unknown(self) -> None:
        store = VercelLogStore(ttl_seconds=60)
        result = store.pop_logs("unknown")
        assert result == []

    def test_has_logs_returns_true_when_present(self) -> None:
        store = VercelLogStore(ttl_seconds=60)
        store.add_logs([{"requestId": "req-123", "message": "Test"}])
        assert store.has_logs("req-123") is True

    def test_has_logs_returns_false_when_absent(self) -> None:
        store = VercelLogStore(ttl_seconds=60)
        assert store.has_logs("unknown") is False

    def test_expired_logs_are_cleaned_up(self) -> None:
        store = VercelLogStore(ttl_seconds=0)  # Immediate expiration
        store.add_logs([{"requestId": "req-123", "message": "Test"}])

        time.sleep(0.01)  # Small delay to ensure expiration

        # Adding new logs triggers cleanup
        store.add_logs([{"requestId": "req-456", "message": "New"}])

        assert store.get_logs("req-123") == []
        assert len(store.get_logs("req-456")) == 1

    def test_format_logs_as_string(self) -> None:
        store = VercelLogStore(ttl_seconds=60)
        logs = [
            {"requestId": "req-123", "message": "First log", "timestamp": 1000, "level": "info"},
            {"requestId": "req-123", "message": "Second log", "timestamp": 1001, "level": "error"},
        ]
        store.add_logs(logs)

        result = store.format_logs_as_string("req-123")
        assert "First log" in result
        assert "Second log" in result
        assert "info" in result.lower() or "INFO" in result

    def test_format_logs_as_string_empty_request(self) -> None:
        store = VercelLogStore(ttl_seconds=60)
        result = store.format_logs_as_string("unknown")
        assert result == ""
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/core/test_vercel_logs.py -v
```

Expected: FAIL - module not found

**Step 3: Implement VercelLogStore**

Create `src/splat/core/vercel_logs.py`:

```python
"""Vercel log storage with request-keyed TTL expiration."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any


class VercelLogStore:
    """
    Request-keyed log storage with TTL expiration.

    Stores logs received from Vercel Log Drain webhook, keyed by requestId.
    Logs automatically expire after TTL seconds to prevent unbounded memory growth.
    """

    def __init__(self, ttl_seconds: int = 60) -> None:
        """
        Initialize the log store.

        Args:
            ttl_seconds: Seconds to keep logs before expiration (default 60)
        """
        self._logs: dict[str, list[dict[str, Any]]] = {}
        self._timestamps: dict[str, float] = {}
        self._ttl = ttl_seconds

    def _cleanup_expired(self) -> None:
        """Remove expired log entries."""
        now = time.time()
        expired = [
            req_id
            for req_id, ts in self._timestamps.items()
            if now - ts > self._ttl
        ]
        for req_id in expired:
            self._logs.pop(req_id, None)
            self._timestamps.pop(req_id, None)

    def add_logs(self, logs: list[dict[str, Any]]) -> None:
        """
        Add logs from webhook, keyed by requestId.

        Args:
            logs: List of log entries from Vercel
        """
        self._cleanup_expired()
        for log in logs:
            request_id = log.get("requestId")
            if not request_id:
                continue
            if request_id not in self._logs:
                self._logs[request_id] = []
                self._timestamps[request_id] = time.time()
            self._logs[request_id].append(log)

    def get_logs(self, request_id: str) -> list[dict[str, Any]]:
        """
        Get logs for a specific request.

        Args:
            request_id: The Vercel request ID

        Returns:
            List of log entries, or empty list if not found
        """
        return self._logs.get(request_id, [])

    def pop_logs(self, request_id: str) -> list[dict[str, Any]]:
        """
        Get and remove logs for a request.

        Args:
            request_id: The Vercel request ID

        Returns:
            List of log entries, or empty list if not found
        """
        logs = self._logs.pop(request_id, [])
        self._timestamps.pop(request_id, None)
        return logs

    def has_logs(self, request_id: str) -> bool:
        """
        Check if logs exist for a request.

        Args:
            request_id: The Vercel request ID

        Returns:
            True if logs exist
        """
        return request_id in self._logs

    def format_logs_as_string(self, request_id: str) -> str:
        """
        Format logs for a request as a string.

        Args:
            request_id: The Vercel request ID

        Returns:
            Formatted log string, or empty string if no logs
        """
        logs = self.get_logs(request_id)
        if not logs:
            return ""

        lines = []
        for log in sorted(logs, key=lambda x: x.get("timestamp", 0)):
            timestamp = log.get("timestamp", 0)
            if timestamp:
                dt = datetime.fromtimestamp(timestamp / 1000)
                time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                time_str = "unknown"

            level = log.get("level", "info").upper()
            message = log.get("message", "")
            lines.append(f"{time_str} {level:5} {message}")

        return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/core/test_vercel_logs.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
cd /Users/andreas/Desktop/projects/splat && git add src/splat/core/vercel_logs.py tests/core/test_vercel_logs.py && git commit -m "feat(vercel): add request-keyed log storage with TTL"
```

---

## Task 3: Webhook Verification - Signature Validation

**Files:**
- Create: `src/splat/webhooks/__init__.py`
- Create: `src/splat/webhooks/vercel.py`
- Create: `tests/webhooks/__init__.py`
- Create: `tests/webhooks/test_vercel.py`

**Step 1: Write the failing tests**

Create `tests/webhooks/__init__.py` (empty file)

Create `tests/webhooks/test_vercel.py`:

```python
"""Tests for Vercel webhook utilities."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from splat.webhooks.vercel import verify_signature, parse_logs


class TestVerifySignature:
    """Test webhook signature verification."""

    def test_verify_signature_valid(self) -> None:
        body = b'{"test": "data"}'
        secret = "test_secret"
        signature = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()

        assert verify_signature(body, secret, signature) is True

    def test_verify_signature_invalid(self) -> None:
        body = b'{"test": "data"}'
        secret = "test_secret"

        assert verify_signature(body, secret, "invalid_signature") is False

    def test_verify_signature_empty_signature(self) -> None:
        body = b'{"test": "data"}'
        secret = "test_secret"

        assert verify_signature(body, secret, "") is False

    def test_verify_signature_none_signature(self) -> None:
        body = b'{"test": "data"}'
        secret = "test_secret"

        assert verify_signature(body, secret, None) is False


class TestParseLogs:
    """Test log parsing from webhook payload."""

    def test_parse_logs_json_array(self) -> None:
        body = json.dumps([
            {"requestId": "req-1", "message": "Log 1"},
            {"requestId": "req-2", "message": "Log 2"},
        ]).encode()

        logs = parse_logs(body)
        assert len(logs) == 2
        assert logs[0]["requestId"] == "req-1"

    def test_parse_logs_ndjson(self) -> None:
        body = b'{"requestId": "req-1", "message": "Log 1"}\n{"requestId": "req-2", "message": "Log 2"}'

        logs = parse_logs(body)
        assert len(logs) == 2
        assert logs[0]["requestId"] == "req-1"
        assert logs[1]["requestId"] == "req-2"

    def test_parse_logs_ndjson_with_trailing_newline(self) -> None:
        body = b'{"requestId": "req-1", "message": "Log 1"}\n'

        logs = parse_logs(body)
        assert len(logs) == 1

    def test_parse_logs_single_object(self) -> None:
        body = b'{"requestId": "req-1", "message": "Log 1"}'

        logs = parse_logs(body)
        assert len(logs) == 1

    def test_parse_logs_empty_body(self) -> None:
        logs = parse_logs(b"")
        assert logs == []

    def test_parse_logs_invalid_json(self) -> None:
        logs = parse_logs(b"not json at all")
        assert logs == []

    def test_parse_logs_filters_to_runtime_sources(self) -> None:
        body = json.dumps([
            {"requestId": "req-1", "source": "lambda", "message": "Lambda log"},
            {"requestId": "req-2", "source": "edge", "message": "Edge log"},
            {"requestId": "req-3", "source": "build", "message": "Build log"},
            {"requestId": "req-4", "source": "static", "message": "Static log"},
        ]).encode()

        logs = parse_logs(body, filter_sources=True)
        assert len(logs) == 2
        assert all(log["source"] in ("lambda", "edge") for log in logs)

    def test_parse_logs_no_filter(self) -> None:
        body = json.dumps([
            {"requestId": "req-1", "source": "build", "message": "Build log"},
        ]).encode()

        logs = parse_logs(body, filter_sources=False)
        assert len(logs) == 1
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/webhooks/test_vercel.py -v
```

Expected: FAIL - module not found

**Step 3: Implement webhook utilities**

Create `src/splat/webhooks/__init__.py`:

```python
"""Webhook handlers for Splat integrations."""
```

Create `src/splat/webhooks/vercel.py`:

```python
"""Vercel webhook utilities."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


RUNTIME_SOURCES = ("lambda", "edge")


def verify_signature(body: bytes, secret: str, signature: str | None) -> bool:
    """
    Verify Vercel webhook signature.

    Args:
        body: Raw request body bytes
        secret: Webhook secret
        signature: Signature from x-vercel-signature header

    Returns:
        True if signature is valid
    """
    if not signature:
        return False

    expected = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_logs(
    body: bytes,
    filter_sources: bool = True,
) -> list[dict[str, Any]]:
    """
    Parse logs from Vercel webhook payload.

    Handles both JSON array and NDJSON formats.

    Args:
        body: Raw request body bytes
        filter_sources: If True, only return lambda/edge logs (default True)

    Returns:
        List of log entries
    """
    if not body:
        return []

    logs: list[dict[str, Any]] = []

    # Try JSON array first
    try:
        data = json.loads(body)
        if isinstance(data, list):
            logs = data
        elif isinstance(data, dict):
            logs = [data]
    except json.JSONDecodeError:
        # Try NDJSON
        for line in body.decode().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if filter_sources:
        logs = [log for log in logs if log.get("source") in RUNTIME_SOURCES]

    return logs
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/webhooks/test_vercel.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
cd /Users/andreas/Desktop/projects/splat && git add src/splat/webhooks/ tests/webhooks/ && git commit -m "feat(webhooks): add Vercel signature verification and log parsing"
```

---

## Task 4: Reporter - Add Vercel Request ID Support

**Files:**
- Modify: `src/splat/core/reporter.py`
- Modify: `tests/core/test_reporter.py`

**Step 1: Write the failing tests**

Add to `tests/core/test_reporter.py`:

```python
class TestSplatVercelIntegration:
    """Test Vercel log integration in Splat."""

    @pytest.mark.asyncio
    async def test_report_uses_vercel_logs_when_request_id_provided(self) -> None:
        splat = Splat(repo="owner/repo", token="test_token")

        # Add logs to vercel store
        splat._vercel_store.add_logs([
            {"requestId": "req-123", "message": "Vercel log 1", "timestamp": 1000, "level": "info"},
            {"requestId": "req-123", "message": "Vercel log 2", "timestamp": 1001, "level": "error"},
        ])

        with patch.object(splat, "_create_issue") as mock_create:
            mock_create.return_value = {"number": 1, "html_url": "http://test"}

            await splat.report(ValueError("test"), vercel_request_id="req-123")

            call_args = mock_create.call_args
            body = call_args[1]["body"]
            assert "Vercel log 1" in body
            assert "Vercel log 2" in body

    @pytest.mark.asyncio
    async def test_report_falls_back_to_python_logs_without_vercel_request_id(self) -> None:
        splat = Splat(repo="owner/repo", token="test_token")

        # Add a Python log
        import logging
        logger = logging.getLogger("test_fallback")
        logger.setLevel(logging.INFO)
        logger.info("Python log message")

        with patch.object(splat, "_create_issue") as mock_create:
            mock_create.return_value = {"number": 1, "html_url": "http://test"}

            await splat.report(ValueError("test"))

            call_args = mock_create.call_args
            body = call_args[1]["body"]
            assert "Python log message" in body

    @pytest.mark.asyncio
    async def test_report_falls_back_when_vercel_request_id_has_no_logs(self) -> None:
        splat = Splat(repo="owner/repo", token="test_token")

        # Add a Python log but no Vercel logs for this request
        import logging
        logger = logging.getLogger("test_no_vercel")
        logger.setLevel(logging.INFO)
        logger.info("Fallback python log")

        with patch.object(splat, "_create_issue") as mock_create:
            mock_create.return_value = {"number": 1, "html_url": "http://test"}

            await splat.report(ValueError("test"), vercel_request_id="unknown-req")

            call_args = mock_create.call_args
            body = call_args[1]["body"]
            # Should contain python logs since no vercel logs for this request
            assert "Fallback python log" in body

    @pytest.mark.asyncio
    async def test_report_pops_vercel_logs_after_use(self) -> None:
        splat = Splat(repo="owner/repo", token="test_token")

        splat._vercel_store.add_logs([
            {"requestId": "req-123", "message": "Test", "timestamp": 1000, "level": "info"},
        ])

        with patch.object(splat, "_create_issue") as mock_create:
            mock_create.return_value = {"number": 1, "html_url": "http://test"}

            await splat.report(ValueError("test"), vercel_request_id="req-123")

        # Logs should be removed after report
        assert splat._vercel_store.has_logs("req-123") is False

    def test_splat_initializes_vercel_store(self) -> None:
        splat = Splat(repo="owner/repo", token="test_token")
        assert splat._vercel_store is not None

    def test_splat_vercel_store_uses_config_ttl(self) -> None:
        splat = Splat(repo="owner/repo", token="test_token", vercel_log_ttl=120)
        assert splat._vercel_store._ttl == 120
```

Add import at top of test file:
```python
from unittest.mock import patch
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/core/test_reporter.py::TestSplatVercelIntegration -v
```

Expected: FAIL - `_vercel_store` does not exist

**Step 3: Implement Vercel support in reporter**

Update `src/splat/core/reporter.py`:

1. Add import:
```python
from splat.core.vercel_logs import VercelLogStore
```

2. Update `__init__`:
```python
def __init__(
    self,
    *,
    repo: str | None = None,
    token: str | None = None,
    enabled: bool | None = None,
    log_buffer_size: int | None = None,
    labels: list[str] | None = None,
    vercel_secret: str | None = None,
    vercel_webhook_path: str | None = None,
    vercel_log_ttl: int | None = None,
) -> None:
    self.config = load_config(
        repo=repo,
        token=token,
        enabled=enabled,
        log_buffer_size=log_buffer_size,
        labels=labels,
        vercel_secret=vercel_secret,
        vercel_webhook_path=vercel_webhook_path,
        vercel_log_ttl=vercel_log_ttl,
    )

    # Set up log buffer
    self._log_buffer = LogBuffer(capacity=self.config.log_buffer_size)
    logging.getLogger().addHandler(self._log_buffer)

    # Set up Vercel log store
    self._vercel_store = VercelLogStore(ttl_seconds=self.config.vercel_log_ttl)

    if not self.is_enabled():
        logger.warning(
            "Splat is disabled. Set SPLAT_GITHUB_REPO and SPLAT_GITHUB_TOKEN "
            "environment variables or pass repo/token to enable."
        )
```

3. Update `report()` method signature and log selection:
```python
async def report(
    self,
    exception: BaseException,
    context: dict[str, Any] | None = None,
    logs: str | None = None,
    vercel_request_id: str | None = None,
) -> dict[str, Any] | None:
    """
    Report an exception to GitHub Issues.

    Args:
        exception: The exception to report
        context: Optional user-provided context dict
        logs: Optional log string (uses buffered logs if not provided)
        vercel_request_id: Optional Vercel request ID for log lookup

    Returns:
        Created issue data dict, or None if disabled/duplicate
    """
    if not self.is_enabled():
        return None

    assert self.config.repo is not None
    assert self.config.token is not None

    signature = generate_signature(exception)

    existing = await check_duplicate(
        repo=self.config.repo,
        token=self.config.token,
        signature=signature,
    )

    if existing is not None:
        logger.info(f"Duplicate error, issue #{existing} already exists")
        return None

    # Log source selection: explicit > vercel > python buffer
    if logs is None:
        if vercel_request_id and self._vercel_store.has_logs(vercel_request_id):
            logs = self._vercel_store.format_logs_as_string(vercel_request_id)
            # Pop logs after formatting to free memory
            self._vercel_store.pop_logs(vercel_request_id)
        else:
            logs = self._log_buffer.get_logs_as_string()

    return await self._create_issue(exception, signature, context, logs)


async def _create_issue(
    self,
    exception: BaseException,
    signature: str,
    context: dict[str, Any] | None,
    logs: str,
) -> dict[str, Any]:
    """Create the GitHub issue."""
    assert self.config.repo is not None
    assert self.config.token is not None

    title = format_issue_title(exception)
    body = format_issue_body(
        exception,
        signature=signature,
        context=context,
        logs=logs,
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/repos/{self.config.repo}/issues",
            headers={
                "Authorization": f"Bearer {self.config.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
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
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/core/test_reporter.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
cd /Users/andreas/Desktop/projects/splat && git add src/splat/core/reporter.py tests/core/test_reporter.py && git commit -m "feat(reporter): add Vercel request ID support for log lookup"
```

---

## Task 5: Flask Webhook Handler

**Files:**
- Create: `src/splat/webhooks/flask.py`
- Create: `tests/webhooks/test_flask_webhook.py`

**Step 1: Write the failing tests**

Create `tests/webhooks/test_flask_webhook.py`:

```python
"""Tests for Flask webhook handler."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import Mock

import pytest

from splat.core.reporter import Splat
from splat.webhooks.flask import create_webhook_handler


class TestCreateWebhookHandler:
    """Test Flask webhook handler creation."""

    def test_handler_accepts_valid_logs(self) -> None:
        splat = Mock(spec=Splat)
        splat.config = Mock()
        splat.config.vercel_secret = None
        splat._vercel_store = Mock()

        handler = create_webhook_handler(splat)

        # Simulate Flask request
        with pytest.importorskip("flask").Flask(__name__).test_request_context(
            "/splat/logs",
            method="POST",
            data=json.dumps([{"requestId": "req-123", "source": "lambda", "message": "Test"}]),
            content_type="application/json",
        ):
            response = handler()

        assert response[1] == 200
        splat._vercel_store.add_logs.assert_called_once()

    def test_handler_verifies_signature_when_secret_configured(self) -> None:
        splat = Mock(spec=Splat)
        splat.config = Mock()
        splat.config.vercel_secret = "test_secret"
        splat._vercel_store = Mock()

        handler = create_webhook_handler(splat)

        body = json.dumps([{"requestId": "req-123", "source": "lambda"}])
        signature = hmac.new(b"test_secret", body.encode(), hashlib.sha1).hexdigest()

        with pytest.importorskip("flask").Flask(__name__).test_request_context(
            "/splat/logs",
            method="POST",
            data=body,
            content_type="application/json",
            headers={"x-vercel-signature": signature},
        ):
            response = handler()

        assert response[1] == 200

    def test_handler_rejects_invalid_signature(self) -> None:
        splat = Mock(spec=Splat)
        splat.config = Mock()
        splat.config.vercel_secret = "test_secret"
        splat._vercel_store = Mock()

        handler = create_webhook_handler(splat)

        with pytest.importorskip("flask").Flask(__name__).test_request_context(
            "/splat/logs",
            method="POST",
            data=json.dumps([{"requestId": "req-123"}]),
            content_type="application/json",
            headers={"x-vercel-signature": "invalid"},
        ):
            response = handler()

        assert response[1] == 401
        splat._vercel_store.add_logs.assert_not_called()

    def test_handler_warns_without_secret(self, caplog: pytest.LogCaptureFixture) -> None:
        splat = Mock(spec=Splat)
        splat.config = Mock()
        splat.config.vercel_secret = None
        splat._vercel_store = Mock()

        handler = create_webhook_handler(splat)

        with pytest.importorskip("flask").Flask(__name__).test_request_context(
            "/splat/logs",
            method="POST",
            data=json.dumps([{"requestId": "req-123", "source": "lambda"}]),
            content_type="application/json",
        ):
            import logging
            with caplog.at_level(logging.WARNING):
                handler()

        # First call should warn
        assert any("SPLAT_VERCEL_SECRET" in record.message for record in caplog.records)
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/webhooks/test_flask_webhook.py -v
```

Expected: FAIL - module not found

**Step 3: Implement Flask webhook handler**

Create `src/splat/webhooks/flask.py`:

```python
"""Flask webhook handler for Vercel Log Drain."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Tuple

from splat.webhooks.vercel import verify_signature, parse_logs

if TYPE_CHECKING:
    from splat.core.reporter import Splat

logger = logging.getLogger(__name__)

_warned_no_secret = False


def create_webhook_handler(
    splat: Splat,
) -> Callable[[], Tuple[dict[str, Any], int]]:
    """
    Create a Flask view function for Vercel webhook.

    Args:
        splat: Splat instance to store logs in

    Returns:
        Flask view function
    """
    global _warned_no_secret

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
            if not _warned_no_secret:
                logger.warning(
                    "Vercel webhook received without SPLAT_VERCEL_SECRET configured. "
                    "Set SPLAT_VERCEL_SECRET for secure webhook verification."
                )
                _warned_no_secret = True

        logs = parse_logs(body, filter_sources=True)
        splat._vercel_store.add_logs(logs)

        return {"received": len(logs)}, 200

    return handler


def register_webhook_route(app: Any, splat: Splat) -> None:
    """
    Register the webhook route on a Flask app.

    Args:
        app: Flask application
        splat: Splat instance
    """
    handler = create_webhook_handler(splat)
    app.add_url_rule(
        splat.config.vercel_webhook_path,
        "splat_vercel_webhook",
        handler,
        methods=["POST"],
    )
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/webhooks/test_flask_webhook.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
cd /Users/andreas/Desktop/projects/splat && git add src/splat/webhooks/flask.py tests/webhooks/test_flask_webhook.py && git commit -m "feat(flask): add Vercel webhook handler"
```

---

## Task 6: FastAPI Webhook Router

**Files:**
- Create: `src/splat/webhooks/fastapi.py`
- Create: `tests/webhooks/test_fastapi_webhook.py`

**Step 1: Write the failing tests**

Create `tests/webhooks/test_fastapi_webhook.py`:

```python
"""Tests for FastAPI webhook router."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import Mock

import pytest

from splat.core.reporter import Splat


class TestFastAPIWebhookRouter:
    """Test FastAPI webhook router."""

    @pytest.fixture
    def client(self) -> Any:
        """Create test client with webhook router."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from splat.webhooks.fastapi import create_webhook_router

        splat = Mock(spec=Splat)
        splat.config = Mock()
        splat.config.vercel_secret = None
        splat.config.vercel_webhook_path = "/splat/logs"
        splat._vercel_store = Mock()

        app = FastAPI()
        router = create_webhook_router(splat)
        app.include_router(router)

        return TestClient(app), splat

    def test_router_accepts_valid_logs(self, client: Any) -> None:
        test_client, splat = client

        response = test_client.post(
            "/splat/logs",
            json=[{"requestId": "req-123", "source": "lambda", "message": "Test"}],
        )

        assert response.status_code == 200
        splat._vercel_store.add_logs.assert_called_once()

    def test_router_verifies_signature(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from splat.webhooks.fastapi import create_webhook_router

        splat = Mock(spec=Splat)
        splat.config = Mock()
        splat.config.vercel_secret = "test_secret"
        splat.config.vercel_webhook_path = "/splat/logs"
        splat._vercel_store = Mock()

        app = FastAPI()
        router = create_webhook_router(splat)
        app.include_router(router)
        test_client = TestClient(app)

        body = json.dumps([{"requestId": "req-123", "source": "lambda"}])
        signature = hmac.new(b"test_secret", body.encode(), hashlib.sha1).hexdigest()

        response = test_client.post(
            "/splat/logs",
            content=body,
            headers={
                "x-vercel-signature": signature,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200

    def test_router_rejects_invalid_signature(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from splat.webhooks.fastapi import create_webhook_router

        splat = Mock(spec=Splat)
        splat.config = Mock()
        splat.config.vercel_secret = "test_secret"
        splat.config.vercel_webhook_path = "/splat/logs"
        splat._vercel_store = Mock()

        app = FastAPI()
        router = create_webhook_router(splat)
        app.include_router(router)
        test_client = TestClient(app)

        response = test_client.post(
            "/splat/logs",
            json=[{"requestId": "req-123"}],
            headers={"x-vercel-signature": "invalid"},
        )

        assert response.status_code == 401

    def test_router_returns_log_count(self, client: Any) -> None:
        test_client, splat = client

        response = test_client.post(
            "/splat/logs",
            json=[
                {"requestId": "req-1", "source": "lambda"},
                {"requestId": "req-2", "source": "edge"},
            ],
        )

        assert response.status_code == 200
        assert response.json()["received"] == 2
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/webhooks/test_fastapi_webhook.py -v
```

Expected: FAIL - module not found

**Step 3: Implement FastAPI webhook router**

Create `src/splat/webhooks/fastapi.py`:

```python
"""FastAPI webhook router for Vercel Log Drain."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from splat.webhooks.vercel import verify_signature, parse_logs

if TYPE_CHECKING:
    from splat.core.reporter import Splat

logger = logging.getLogger(__name__)

_warned_no_secret = False


def create_webhook_router(splat: Splat) -> Any:
    """
    Create a FastAPI router for Vercel webhook.

    Args:
        splat: Splat instance to store logs in

    Returns:
        FastAPI APIRouter
    """
    from fastapi import APIRouter, Request, Response

    router = APIRouter()

    @router.post(splat.config.vercel_webhook_path)
    async def vercel_webhook(request: Request) -> dict[str, Any]:
        global _warned_no_secret

        body = await request.body()

        # Verify signature if secret is configured
        if splat.config.vercel_secret:
            signature = request.headers.get("x-vercel-signature")
            if not verify_signature(body, splat.config.vercel_secret, signature):
                return Response(
                    content='{"error": "Invalid signature"}',
                    status_code=401,
                    media_type="application/json",
                )
        else:
            if not _warned_no_secret:
                logger.warning(
                    "Vercel webhook received without SPLAT_VERCEL_SECRET configured. "
                    "Set SPLAT_VERCEL_SECRET for secure webhook verification."
                )
                _warned_no_secret = True

        logs = parse_logs(body, filter_sources=True)
        splat._vercel_store.add_logs(logs)

        return {"received": len(logs)}

    return router
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/webhooks/test_fastapi_webhook.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
cd /Users/andreas/Desktop/projects/splat && git add src/splat/webhooks/fastapi.py tests/webhooks/test_fastapi_webhook.py && git commit -m "feat(fastapi): add Vercel webhook router"
```

---

## Task 7: Update Middleware - Capture x-vercel-id

**Files:**
- Modify: `src/splat/middleware/flask.py`
- Modify: `src/splat/middleware/fastapi.py`
- Modify: `tests/middleware/test_flask.py`
- Modify: `tests/middleware/test_fastapi.py`

**Step 1: Write the failing tests**

Add to `tests/middleware/test_flask.py`:

```python
class TestFlaskVercelIntegration:
    """Test Flask middleware Vercel integration."""

    def test_error_handler_captures_vercel_request_id(self) -> None:
        from unittest.mock import patch, AsyncMock

        splat = Mock()
        splat.report = AsyncMock()

        handler = create_error_handler(splat)

        with Flask(__name__).test_request_context(
            "/test",
            headers={"x-vercel-id": "req-123"},
        ):
            try:
                handler(ValueError("test error"))
            except ValueError:
                pass

        splat.report.assert_called_once()
        call_kwargs = splat.report.call_args[1]
        assert call_kwargs.get("vercel_request_id") == "req-123"

    def test_error_handler_works_without_vercel_header(self) -> None:
        from unittest.mock import patch, AsyncMock

        splat = Mock()
        splat.report = AsyncMock()

        handler = create_error_handler(splat)

        with Flask(__name__).test_request_context("/test"):
            try:
                handler(ValueError("test error"))
            except ValueError:
                pass

        splat.report.assert_called_once()
        call_kwargs = splat.report.call_args[1]
        assert call_kwargs.get("vercel_request_id") is None
```

Add to `tests/middleware/test_fastapi.py`:

```python
class TestFastAPIVercelIntegration:
    """Test FastAPI middleware Vercel integration."""

    @pytest.mark.asyncio
    async def test_middleware_captures_vercel_request_id(self) -> None:
        from unittest.mock import patch, AsyncMock

        with patch("splat.middleware.fastapi.Splat") as MockSplat:
            mock_splat = Mock()
            mock_splat.report = AsyncMock()
            mock_splat.is_enabled.return_value = True
            MockSplat.return_value = mock_splat

            app = FastAPI()

            @app.get("/test")
            async def error_route() -> None:
                raise ValueError("test error")

            app.add_middleware(SplatMiddleware, repo="owner/repo", token="test")

            client = TestClient(app, raise_server_exceptions=False)
            client.get("/test", headers={"x-vercel-id": "req-123"})

            mock_splat.report.assert_called_once()
            call_kwargs = mock_splat.report.call_args[1]
            assert call_kwargs.get("vercel_request_id") == "req-123"
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/middleware/test_flask.py::TestFlaskVercelIntegration tests/middleware/test_fastapi.py::TestFastAPIVercelIntegration -v
```

Expected: FAIL - vercel_request_id not passed

**Step 3: Update middleware to capture Vercel request ID**

Update `src/splat/middleware/flask.py` `create_error_handler`:

```python
def create_error_handler(
    splat: Splat | None = None,
) -> Callable[[Exception], Any]:
    """Create a Flask error handler that reports errors to Splat."""
    def handler(error: Exception) -> Any:
        instance = splat or _get_splat()
        if instance is None:
            raise error

        context: dict[str, Any] = {}
        vercel_request_id: str | None = None
        try:
            from flask import request
            context = {
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
                "url": request.url,
            }
            vercel_request_id = request.headers.get("x-vercel-id")
        except (ImportError, RuntimeError):
            pass

        _run_async(instance.report(error, context=context, vercel_request_id=vercel_request_id))
        raise error

    return handler
```

Update `src/splat/middleware/fastapi.py` `dispatch` method:

```python
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
        vercel_request_id = request.headers.get("x-vercel-id")
        await self.splat.report(e, context=context, vercel_request_id=vercel_request_id)
        raise
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/middleware/ -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
cd /Users/andreas/Desktop/projects/splat && git add src/splat/middleware/ tests/middleware/ && git commit -m "feat(middleware): capture x-vercel-id header for log lookup"
```

---

## Task 8: Flask Integration - Auto-Register Webhook

**Files:**
- Modify: `src/splat/middleware/flask.py`
- Modify: `tests/middleware/test_flask.py`

**Step 1: Write the failing tests**

Add to `tests/middleware/test_flask.py`:

```python
class TestSplatFlaskWebhookRegistration:
    """Test automatic webhook registration."""

    def test_init_app_registers_webhook_route(self) -> None:
        app = Flask(__name__)
        splat_flask = SplatFlask()
        splat_flask.init_app(app, repo="owner/repo", token="test")

        # Check route was registered
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        assert "/splat/logs" in rules

    def test_init_app_uses_custom_webhook_path(self) -> None:
        app = Flask(__name__)
        splat_flask = SplatFlask()
        splat_flask.init_app(
            app,
            repo="owner/repo",
            token="test",
            vercel_webhook_path="/custom/webhook",
        )

        rules = [rule.rule for rule in app.url_map.iter_rules()]
        assert "/custom/webhook" in rules

    def test_webhook_route_accepts_post(self) -> None:
        app = Flask(__name__)
        splat_flask = SplatFlask()
        splat_flask.init_app(app, repo="owner/repo", token="test")

        client = app.test_client()
        response = client.post(
            "/splat/logs",
            json=[{"requestId": "req-123", "source": "lambda"}],
        )

        assert response.status_code == 200
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/middleware/test_flask.py::TestSplatFlaskWebhookRegistration -v
```

Expected: FAIL - route not registered

**Step 3: Update SplatFlask to register webhook**

Update `src/splat/middleware/flask.py`:

Add import:
```python
from splat.webhooks.flask import register_webhook_route
```

Update `init_app` method:
```python
def init_app(self, app: Any, **kwargs: Any) -> None:
    global _splat_instance
    self.splat = Splat(**kwargs)
    _splat_instance = self.splat
    app.register_error_handler(Exception, create_error_handler(self.splat))
    register_webhook_route(app, self.splat)
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/middleware/test_flask.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
cd /Users/andreas/Desktop/projects/splat && git add src/splat/middleware/flask.py tests/middleware/test_flask.py && git commit -m "feat(flask): auto-register Vercel webhook route"
```

---

## Task 9: CLI Init Wizard - Vercel Detection

**Files:**
- Modify: `src/splat/cli/init.py`
- Modify: `tests/cli/test_init.py`

**Step 1: Write the failing tests**

Add to `tests/cli/test_init.py`:

```python
class TestVercelDetection:
    """Test Vercel project detection."""

    def test_detect_vercel_by_vercel_json(self, tmp_path: Path) -> None:
        (tmp_path / "vercel.json").write_text("{}")
        assert detect_vercel_project(tmp_path) is True

    def test_detect_vercel_by_dotvercel_folder(self, tmp_path: Path) -> None:
        (tmp_path / ".vercel").mkdir()
        assert detect_vercel_project(tmp_path) is True

    def test_detect_vercel_by_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VERCEL", "1")
        assert detect_vercel_project(tmp_path) is True

    def test_detect_vercel_returns_false_when_not_vercel(self, tmp_path: Path) -> None:
        assert detect_vercel_project(tmp_path) is False


class TestProjectInfoVercel:
    """Test ProjectInfo includes Vercel detection."""

    def test_project_info_includes_is_vercel(self, tmp_path: Path) -> None:
        (tmp_path / "vercel.json").write_text("{}")
        (tmp_path / "pyproject.toml").write_text("")

        info = detect_project_info(tmp_path)
        assert info.is_vercel is True
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/cli/test_init.py::TestVercelDetection tests/cli/test_init.py::TestProjectInfoVercel -v
```

Expected: FAIL - detect_vercel_project not found

**Step 3: Implement Vercel detection**

Update `src/splat/cli/init.py`:

Add to `ProjectInfo` dataclass:
```python
@dataclass
class ProjectInfo:
    """Detected project information."""

    project_type: str
    framework: str | None
    framework_file: Path | None
    github_repo: str | None
    base_path: Path
    is_vercel: bool = False
```

Add new function:
```python
def detect_vercel_project(base_path: Path) -> bool:
    """Detect if this is a Vercel project."""
    # Check for vercel.json
    if (base_path / "vercel.json").exists():
        return True

    # Check for .vercel directory
    if (base_path / ".vercel").is_dir():
        return True

    # Check for VERCEL environment variable
    if os.environ.get("VERCEL"):
        return True

    return False
```

Add import:
```python
import os
```

Add helper function for full detection:
```python
def detect_project_info(base_path: Path) -> ProjectInfo:
    """Detect all project information."""
    project_type = detect_project_type(base_path)
    framework, framework_file = detect_framework(base_path)
    github_repo = detect_github_remote(base_path)
    is_vercel = detect_vercel_project(base_path)

    return ProjectInfo(
        project_type=project_type,
        framework=framework,
        framework_file=framework_file,
        github_repo=github_repo,
        base_path=base_path,
        is_vercel=is_vercel,
    )
```

Update `run_init_wizard` to use `detect_project_info` and show Vercel status:
```python
def run_init_wizard(base_path: Path | None = None) -> None:
    """Run the interactive setup wizard."""
    if base_path is None:
        base_path = Path.cwd()

    click.echo("\nWelcome to Splat!\n")
    click.echo("Detecting project...")

    info = detect_project_info(base_path)

    if info.project_type != "unknown":
        click.echo(f"  - {info.project_type.title()} project detected")
    else:
        click.echo("  - Could not detect project type")

    if info.framework:
        click.echo(
            f"  - {info.framework.title()} app in "
            f"{info.framework_file.name if info.framework_file else 'unknown'}"
        )
    else:
        click.echo("  - No framework detected")

    if info.github_repo:
        click.echo(f"  - GitHub remote: {info.github_repo}")
    else:
        click.echo("  - No GitHub remote detected")

    if info.is_vercel:
        click.echo("  - Vercel project detected")

    click.echo()
    click.echo("Full wizard coming soon!")
    click.echo("For now, configure manually in pyproject.toml or environment variables.")
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/cli/test_init.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
cd /Users/andreas/Desktop/projects/splat && git add src/splat/cli/init.py tests/cli/test_init.py && git commit -m "feat(cli): add Vercel project detection to init wizard"
```

---

## Task 10: Update README - Document Vercel Integration

**Files:**
- Modify: `README.md`

**Step 1: Update README with Vercel documentation**

Add a new section after "Auto-Fix with Claude Code":

```markdown
## Vercel Log Integration

Splat can capture Vercel runtime logs via Log Drain webhooks, providing precise logs for each failed request.

### Setup

1. **Configure your app:**

   Flask:
   ```python
   from flask import Flask
   from splat.middleware.flask import SplatFlask

   app = Flask(__name__)
   splat = SplatFlask()
   splat.init_app(app, repo="owner/repo", token="ghp_...")
   # Automatically registers /splat/logs webhook
   ```

   FastAPI:
   ```python
   from fastapi import FastAPI
   from splat.middleware.fastapi import SplatMiddleware
   from splat.webhooks.fastapi import create_webhook_router

   app = FastAPI()
   app.add_middleware(SplatMiddleware, repo="owner/repo", token="ghp_...")

   # Create Splat instance for webhook
   from splat import Splat
   splat = Splat(repo="owner/repo", token="ghp_...")
   app.include_router(create_webhook_router(splat))
   ```

2. **Add Log Drain in Vercel:**
   - Go to your project's Settings → Log Drains
   - Create a new Log Drain:
     - **Delivery format:** JSON
     - **Endpoint:** `https://your-app.vercel.app/splat/logs`
     - **Sources:** Lambda, Edge (runtime logs)

3. **(Recommended) Add verification secret:**
   ```bash
   # Generate a secret
   export SPLAT_VERCEL_SECRET=$(openssl rand -hex 32)

   # Add to Vercel Log Drain configuration
   # Add to your environment variables
   ```

### Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SPLAT_VERCEL_SECRET` | Webhook verification secret | (optional) |
| `SPLAT_VERCEL_WEBHOOK_PATH` | Webhook route path | `/splat/logs` |
| `SPLAT_VERCEL_LOG_TTL` | Seconds to keep logs in memory | `60` |

### How It Works

1. Vercel pushes runtime logs to your `/splat/logs` endpoint
2. Splat stores logs keyed by request ID (from `x-vercel-id` header)
3. When an error occurs, middleware captures the request ID
4. `splat.report()` fetches logs for that specific request
5. GitHub issue includes the exact logs for the failed request

Logs automatically expire after 60 seconds to prevent memory growth.
```

**Step 2: Commit**

```bash
cd /Users/andreas/Desktop/projects/splat && git add README.md && git commit -m "docs: add Vercel log integration documentation"
```

---

## Task 11: Run Full Test Suite & Verify

**Step 1: Run all tests**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m pytest tests/ -v
```

Expected: All tests PASS

**Step 2: Check coverage**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m coverage run -m pytest tests/ && python -m coverage report --fail-under=80
```

Expected: Coverage ≥80%

**Step 3: Run type checking**

```bash
cd /Users/andreas/Desktop/projects/splat && source .venv/bin/activate && python -m mypy --ignore-missing-imports --strict src/splat
```

Expected: No errors

**Step 4: Commit any final fixes if needed**

---

## Summary

This plan adds Vercel Log Drain integration to Splat through 11 tasks:

1. **Configuration** - Add vercel_secret, vercel_webhook_path, vercel_log_ttl
2. **VercelLogStore** - Request-keyed storage with TTL expiration
3. **Webhook Verification** - Signature validation and log parsing
4. **Reporter** - Add vercel_request_id parameter
5. **Flask Webhook** - Create webhook handler
6. **FastAPI Webhook** - Create webhook router
7. **Middleware Updates** - Capture x-vercel-id header
8. **Flask Integration** - Auto-register webhook route
9. **CLI Init** - Vercel project detection
10. **README** - Document Vercel integration
11. **Verification** - Full test suite, coverage, types
