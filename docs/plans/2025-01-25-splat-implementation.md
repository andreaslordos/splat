# Splat Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python library that automatically creates GitHub issues on application crashes with deduplication, log capture, and optional Claude Code auto-fix.

**Architecture:** Core library with config/log-buffer/dedup/reporter modules. Framework middleware as optional add-ons. CLI wizard for zero-config setup. All async-first with httpx.

**Tech Stack:** Python 3.9+, httpx (async HTTP), click (CLI), pytest (testing), tomli (config parsing)

---

## Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `src/splat/__init__.py`
- Create: `tests/__init__.py`
- Create: `.gitignore`
- Create: `README.md`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "splat"
version = "0.1.0"
description = "Automatic GitHub issue creation on application crashes"
readme = "README.md"
requires-python = ">=3.9"
license = "MIT"
authors = [
    { name = "Your Name", email = "you@example.com" }
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "httpx>=0.25.0",
    "tomli>=2.0.0;python_version<'3.11'",
]

[project.optional-dependencies]
cli = ["click>=8.0.0"]
flask = ["flask>=2.0.0"]
fastapi = ["fastapi>=0.100.0"]
django = ["django>=4.0.0"]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "respx>=0.20.0",
    "black",
    "ruff",
    "mypy",
]
all = ["splat[cli,flask,fastapi,django,dev]"]

[project.scripts]
splat = "splat.cli.main:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/splat"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
strict = true
ignore_missing_imports = true

[tool.ruff]
line-length = 88
select = ["E", "F", "I", "N", "W"]

[tool.coverage.run]
source = ["src/splat"]
omit = ["*/tests/*"]

[tool.coverage.report]
fail_under = 80
```

**Step 2: Create directory structure**

```bash
mkdir -p src/splat/core src/splat/middleware src/splat/cli src/splat/templates tests/core tests/middleware tests/cli
```

**Step 3: Create src/splat/__init__.py**

```python
"""Splat - Automatic GitHub issue creation on application crashes."""

from splat.core.reporter import Splat

__version__ = "0.1.0"
__all__ = ["Splat", "__version__"]
```

**Step 4: Create empty __init__.py files**

```bash
touch src/splat/core/__init__.py
touch src/splat/middleware/__init__.py
touch src/splat/cli/__init__.py
touch tests/__init__.py
touch tests/core/__init__.py
touch tests/middleware/__init__.py
touch tests/cli/__init__.py
```

**Step 5: Create .gitignore**

```
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.env
.venv
venv/
ENV/
.pytest_cache/
.coverage
htmlcov/
.mypy_cache/
.ruff_cache/
```

**Step 6: Create README.md**

```markdown
# Splat

Automatic GitHub issue creation on application crashes.

## Installation

```bash
pip install splat
```

## Quick Start

```python
from splat import Splat

splat = Splat(repo="owner/repo", token="ghp_...")

try:
    do_something()
except Exception as e:
    await splat.report(e)
```

## CLI Setup

```bash
pip install splat[cli]
splat init
```
```

**Step 7: Commit**

```bash
git add -A
git commit -m "chore: initial project setup with pyproject.toml"
```

---

## Task 2: Configuration Module

**Files:**
- Create: `src/splat/core/config.py`
- Create: `tests/core/test_config.py`

**Step 1: Write failing tests for config loading**

```python
# tests/core/test_config.py
"""Tests for configuration loading."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from splat.core.config import SplatConfig, load_config


class TestSplatConfigDefaults:
    """Test SplatConfig default values."""

    def test_config_has_default_enabled_true(self) -> None:
        config = SplatConfig()
        assert config.enabled is True

    def test_config_has_default_log_buffer_size_200(self) -> None:
        config = SplatConfig()
        assert config.log_buffer_size == 200

    def test_config_has_default_labels(self) -> None:
        config = SplatConfig()
        assert config.labels == ["bug", "splat"]

    def test_config_has_no_default_repo(self) -> None:
        config = SplatConfig()
        assert config.repo is None

    def test_config_has_no_default_token(self) -> None:
        config = SplatConfig()
        assert config.token is None


class TestLoadConfigFromEnv:
    """Test loading config from environment variables."""

    def test_load_config_reads_repo_from_env(self) -> None:
        with patch.dict(os.environ, {"SPLAT_GITHUB_REPO": "owner/repo"}):
            config = load_config()
            assert config.repo == "owner/repo"

    def test_load_config_reads_token_from_env(self) -> None:
        with patch.dict(os.environ, {"SPLAT_GITHUB_TOKEN": "ghp_test123"}):
            config = load_config()
            assert config.token == "ghp_test123"

    def test_load_config_reads_enabled_from_env(self) -> None:
        with patch.dict(os.environ, {"SPLAT_ENABLED": "false"}):
            config = load_config()
            assert config.enabled is False

    def test_load_config_reads_log_buffer_size_from_env(self) -> None:
        with patch.dict(os.environ, {"SPLAT_LOG_BUFFER_SIZE": "500"}):
            config = load_config()
            assert config.log_buffer_size == 500

    def test_load_config_reads_labels_from_env(self) -> None:
        with patch.dict(os.environ, {"SPLAT_LABELS": "bug,splat,auto-fix"}):
            config = load_config()
            assert config.labels == ["bug", "splat", "auto-fix"]


class TestLoadConfigFromToml:
    """Test loading config from pyproject.toml."""

    def test_load_config_reads_from_pyproject_toml(
        self, tmp_path: Path
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.splat]
repo = "toml/repo"
labels = ["custom", "labels"]
log_buffer_size = 300
""")
        with patch("splat.core.config._find_pyproject", return_value=pyproject):
            config = load_config()
            assert config.repo == "toml/repo"
            assert config.labels == ["custom", "labels"]
            assert config.log_buffer_size == 300


class TestConfigPrecedence:
    """Test that programmatic > toml > env."""

    def test_programmatic_overrides_env(self) -> None:
        with patch.dict(os.environ, {"SPLAT_GITHUB_REPO": "env/repo"}):
            config = load_config(repo="programmatic/repo")
            assert config.repo == "programmatic/repo"

    def test_toml_overrides_env(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.splat]
repo = "toml/repo"
""")
        with patch.dict(os.environ, {"SPLAT_GITHUB_REPO": "env/repo"}):
            with patch("splat.core.config._find_pyproject", return_value=pyproject):
                config = load_config()
                assert config.repo == "toml/repo"

    def test_programmatic_overrides_toml(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.splat]
repo = "toml/repo"
""")
        with patch("splat.core.config._find_pyproject", return_value=pyproject):
            config = load_config(repo="programmatic/repo")
            assert config.repo == "programmatic/repo"
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/andreas/Desktop/projects/splat
pytest tests/core/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'splat.core.config'`

**Step 3: Implement config module**

```python
# src/splat/core/config.py
"""Configuration loading with precedence: programmatic > toml > env > defaults."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class SplatConfig:
    """Splat configuration."""

    repo: str | None = None
    token: str | None = None
    enabled: bool = True
    log_buffer_size: int = 200
    labels: list[str] = field(default_factory=lambda: ["bug", "splat"])


def _find_pyproject() -> Path | None:
    """Find pyproject.toml by walking up from cwd."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            return pyproject
    return None


def _load_from_env() -> dict[str, Any]:
    """Load config from environment variables."""
    config: dict[str, Any] = {}

    if repo := os.environ.get("SPLAT_GITHUB_REPO"):
        config["repo"] = repo

    if token := os.environ.get("SPLAT_GITHUB_TOKEN"):
        config["token"] = token

    if enabled := os.environ.get("SPLAT_ENABLED"):
        config["enabled"] = enabled.lower() not in ("false", "0", "no")

    if buffer_size := os.environ.get("SPLAT_LOG_BUFFER_SIZE"):
        config["log_buffer_size"] = int(buffer_size)

    if labels := os.environ.get("SPLAT_LABELS"):
        config["labels"] = [l.strip() for l in labels.split(",")]

    return config


def _load_from_toml(path: Path) -> dict[str, Any]:
    """Load config from pyproject.toml [tool.splat] section."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return data.get("tool", {}).get("splat", {})
    except Exception:
        return {}


def load_config(
    *,
    repo: str | None = None,
    token: str | None = None,
    enabled: bool | None = None,
    log_buffer_size: int | None = None,
    labels: list[str] | None = None,
) -> SplatConfig:
    """
    Load configuration with precedence: programmatic > toml > env > defaults.

    Args:
        repo: GitHub repository (owner/repo format)
        token: GitHub API token
        enabled: Whether error reporting is enabled
        log_buffer_size: Number of log entries to buffer
        labels: Labels to apply to created issues

    Returns:
        SplatConfig with merged values
    """
    # Start with defaults
    config = SplatConfig()

    # Layer 1: Environment variables
    env_config = _load_from_env()
    if "repo" in env_config:
        config.repo = env_config["repo"]
    if "token" in env_config:
        config.token = env_config["token"]
    if "enabled" in env_config:
        config.enabled = env_config["enabled"]
    if "log_buffer_size" in env_config:
        config.log_buffer_size = env_config["log_buffer_size"]
    if "labels" in env_config:
        config.labels = env_config["labels"]

    # Layer 2: pyproject.toml
    if pyproject := _find_pyproject():
        toml_config = _load_from_toml(pyproject)
        if "repo" in toml_config:
            config.repo = toml_config["repo"]
        if "token" in toml_config:
            config.token = toml_config["token"]
        if "enabled" in toml_config:
            config.enabled = toml_config["enabled"]
        if "log_buffer_size" in toml_config:
            config.log_buffer_size = toml_config["log_buffer_size"]
        if "labels" in toml_config:
            config.labels = toml_config["labels"]

    # Layer 3: Programmatic overrides (highest priority)
    if repo is not None:
        config.repo = repo
    if token is not None:
        config.token = token
    if enabled is not None:
        config.enabled = enabled
    if log_buffer_size is not None:
        config.log_buffer_size = log_buffer_size
    if labels is not None:
        config.labels = labels

    return config
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/core/test_config.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/splat/core/config.py tests/core/test_config.py
git commit -m "feat(config): add configuration loading with precedence"
```

---

## Task 3: Log Buffer Module

**Files:**
- Create: `src/splat/core/log_buffer.py`
- Create: `tests/core/test_log_buffer.py`

**Step 1: Write failing tests for log buffer**

```python
# tests/core/test_log_buffer.py
"""Tests for log buffer capture."""

import logging

import pytest

from splat.core.log_buffer import LogBuffer, install_log_buffer, get_recent_logs


class TestLogBuffer:
    """Test LogBuffer class."""

    def test_buffer_captures_log_messages(self) -> None:
        buffer = LogBuffer(capacity=10)
        logger = logging.getLogger("test_capture")
        logger.addHandler(buffer)
        logger.setLevel(logging.INFO)

        logger.info("Test message")

        logs = buffer.get_logs()
        assert len(logs) == 1
        assert "Test message" in logs[0]

    def test_buffer_respects_capacity(self) -> None:
        buffer = LogBuffer(capacity=3)
        logger = logging.getLogger("test_capacity")
        logger.addHandler(buffer)
        logger.setLevel(logging.INFO)

        for i in range(5):
            logger.info(f"Message {i}")

        logs = buffer.get_logs()
        assert len(logs) == 3
        assert "Message 2" in logs[0]
        assert "Message 4" in logs[2]

    def test_buffer_formats_with_timestamp(self) -> None:
        buffer = LogBuffer(capacity=10)
        logger = logging.getLogger("test_format")
        logger.addHandler(buffer)
        logger.setLevel(logging.INFO)

        logger.info("Formatted message")

        logs = buffer.get_logs()
        assert "INFO" in logs[0]
        assert "Formatted message" in logs[0]

    def test_get_logs_as_string_joins_entries(self) -> None:
        buffer = LogBuffer(capacity=10)
        logger = logging.getLogger("test_string")
        logger.addHandler(buffer)
        logger.setLevel(logging.INFO)

        logger.info("Line 1")
        logger.info("Line 2")

        log_string = buffer.get_logs_as_string()
        assert "Line 1" in log_string
        assert "Line 2" in log_string
        assert "\n" in log_string


class TestInstallLogBuffer:
    """Test global log buffer installation."""

    def test_install_creates_global_buffer(self) -> None:
        buffer = install_log_buffer(capacity=50)
        assert buffer is not None

    def test_get_recent_logs_returns_captured_logs(self) -> None:
        install_log_buffer(capacity=50)
        logger = logging.getLogger("test_global")
        logger.setLevel(logging.INFO)

        logger.info("Global test message")

        logs = get_recent_logs()
        # May contain other logs too, just check ours is there
        assert any("Global test message" in log for log in logs)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/core/test_log_buffer.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'splat.core.log_buffer'`

**Step 3: Implement log buffer module**

```python
# src/splat/core/log_buffer.py
"""Rolling log buffer that captures recent log entries."""

from __future__ import annotations

import logging
from collections import deque
from typing import Deque

_global_buffer: LogBuffer | None = None


class LogBuffer(logging.Handler):
    """A logging handler that maintains a rolling buffer of recent entries."""

    def __init__(self, capacity: int = 200) -> None:
        """
        Initialize the log buffer.

        Args:
            capacity: Maximum number of log entries to retain
        """
        super().__init__()
        self._buffer: Deque[str] = deque(maxlen=capacity)
        self.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-5s %(name)s: %(message)s")
        )

    def emit(self, record: logging.LogRecord) -> None:
        """
        Add a log record to the buffer.

        Args:
            record: The log record to add
        """
        try:
            msg = self.format(record)
            self._buffer.append(msg)
        except Exception:
            self.handleError(record)

    def get_logs(self) -> list[str]:
        """
        Get all buffered log entries.

        Returns:
            List of formatted log strings, oldest first
        """
        return list(self._buffer)

    def get_logs_as_string(self) -> str:
        """
        Get all buffered log entries as a single string.

        Returns:
            Newline-joined log entries
        """
        return "\n".join(self._buffer)


def install_log_buffer(capacity: int = 200) -> LogBuffer:
    """
    Install a global log buffer on the root logger.

    Args:
        capacity: Maximum number of log entries to retain

    Returns:
        The installed LogBuffer instance
    """
    global _global_buffer
    _global_buffer = LogBuffer(capacity=capacity)
    logging.getLogger().addHandler(_global_buffer)
    return _global_buffer


def get_recent_logs() -> list[str]:
    """
    Get recent logs from the global buffer.

    Returns:
        List of recent log entries, or empty list if not installed
    """
    if _global_buffer is None:
        return []
    return _global_buffer.get_logs()


def get_recent_logs_as_string() -> str:
    """
    Get recent logs from the global buffer as a string.

    Returns:
        Newline-joined log entries, or empty string if not installed
    """
    if _global_buffer is None:
        return ""
    return _global_buffer.get_logs_as_string()
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/core/test_log_buffer.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/splat/core/log_buffer.py tests/core/test_log_buffer.py
git commit -m "feat(log_buffer): add rolling log capture"
```

---

## Task 4: Deduplication Module

**Files:**
- Create: `src/splat/core/dedup.py`
- Create: `tests/core/test_dedup.py`

**Step 1: Write failing tests for signature generation**

```python
# tests/core/test_dedup.py
"""Tests for error deduplication."""

import pytest
import httpx
import respx

from splat.core.dedup import generate_signature, check_duplicate


class TestGenerateSignature:
    """Test error signature generation."""

    def test_signature_includes_exception_type(self) -> None:
        try:
            raise ValueError("test error")
        except ValueError as e:
            sig = generate_signature(e)
            # Same exception type should produce same prefix
            assert len(sig) == 8

    def test_same_error_produces_same_signature(self) -> None:
        def raise_error() -> None:
            raise ValueError("test")

        sigs = []
        for _ in range(2):
            try:
                raise_error()
            except ValueError as e:
                sigs.append(generate_signature(e))

        assert sigs[0] == sigs[1]

    def test_different_errors_produce_different_signatures(self) -> None:
        try:
            raise ValueError("error 1")
        except ValueError as e1:
            sig1 = generate_signature(e1)

        try:
            raise TypeError("error 2")
        except TypeError as e2:
            sig2 = generate_signature(e2)

        assert sig1 != sig2

    def test_signature_is_8_chars(self) -> None:
        try:
            raise RuntimeError("test")
        except RuntimeError as e:
            sig = generate_signature(e)
            assert len(sig) == 8
            assert sig.isalnum()


class TestCheckDuplicate:
    """Test GitHub duplicate checking."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_none_when_no_duplicate(self) -> None:
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )

        result = await check_duplicate(
            repo="owner/repo",
            token="ghp_test",
            signature="abc12345",
        )

        assert result is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_issue_number_when_duplicate_found(self) -> None:
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"number": 42, "title": "Test issue"}]},
            )
        )

        result = await check_duplicate(
            repo="owner/repo",
            token="ghp_test",
            signature="abc12345",
        )

        assert result == 42

    @respx.mock
    @pytest.mark.asyncio
    async def test_searches_with_correct_query(self) -> None:
        route = respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )

        await check_duplicate(
            repo="owner/repo",
            token="ghp_test",
            signature="abc12345",
        )

        assert route.called
        request = route.calls[0].request
        assert "repo:owner/repo" in str(request.url)
        assert "abc12345" in str(request.url)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/core/test_dedup.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'splat.core.dedup'`

**Step 3: Implement dedup module**

```python
# src/splat/core/dedup.py
"""Error deduplication via signature generation and GitHub search."""

from __future__ import annotations

import hashlib
import traceback
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from types import TracebackType


def generate_signature(
    exception: BaseException,
    tb: TracebackType | None = None,
) -> str:
    """
    Generate a unique signature for an exception.

    The signature is based on:
    - Exception type name
    - Source file path
    - Line number
    - Function name

    Args:
        exception: The exception to generate a signature for
        tb: Optional traceback (uses exception's __traceback__ if not provided)

    Returns:
        8-character hex signature
    """
    if tb is None:
        tb = exception.__traceback__

    # Extract location info from traceback
    filename = "unknown"
    lineno = 0
    funcname = "unknown"

    if tb is not None:
        # Get the innermost frame (where the exception was raised)
        while tb.tb_next is not None:
            tb = tb.tb_next

        frame = tb.tb_frame
        filename = frame.f_code.co_filename
        lineno = tb.tb_lineno
        funcname = frame.f_code.co_name

    # Build signature components
    components = [
        type(exception).__name__,
        filename,
        str(lineno),
        funcname,
    ]

    # Hash to 8 chars
    signature_str = "|".join(components)
    hash_bytes = hashlib.md5(signature_str.encode()).hexdigest()
    return hash_bytes[:8]


async def check_duplicate(
    repo: str,
    token: str,
    signature: str,
) -> int | None:
    """
    Check if an issue with this signature already exists on GitHub.

    Args:
        repo: GitHub repository (owner/repo format)
        token: GitHub API token
        signature: Error signature to search for

    Returns:
        Issue number if duplicate found, None otherwise
    """
    query = f"repo:{repo} label:splat {signature} in:body"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/search/issues",
            params={"q": query},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response.raise_for_status()
        data = response.json()

    items = data.get("items", [])
    if items:
        return items[0]["number"]

    return None
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/core/test_dedup.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/splat/core/dedup.py tests/core/test_dedup.py
git commit -m "feat(dedup): add signature generation and GitHub search"
```

---

## Task 5: Issue Formatter Module

**Files:**
- Create: `src/splat/core/formatter.py`
- Create: `tests/core/test_formatter.py`

**Step 1: Write failing tests for issue formatting**

```python
# tests/core/test_formatter.py
"""Tests for GitHub issue formatting."""

import pytest

from splat.core.formatter import format_issue_title, format_issue_body


class TestFormatIssueTitle:
    """Test issue title formatting."""

    def test_title_includes_splat_prefix(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            title = format_issue_title(e)
            assert title.startswith("[Splat]")

    def test_title_includes_exception_type(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            title = format_issue_title(e)
            assert "ValueError" in title

    def test_title_includes_filename_and_line(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            title = format_issue_title(e)
            assert "test_formatter.py" in title
            assert ":" in title  # filename:line format


class TestFormatIssueBody:
    """Test issue body formatting."""

    def test_body_includes_error_section(self) -> None:
        try:
            raise ValueError("test message")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345")
            assert "## Error" in body
            assert "ValueError" in body
            assert "test message" in body

    def test_body_includes_traceback(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345")
            assert "## Traceback" in body
            assert "ValueError" in body

    def test_body_includes_signature(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345")
            assert "abc12345" in body

    def test_body_includes_context_when_provided(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(
                e,
                signature="abc12345",
                context={"user_id": 123, "endpoint": "/api"},
            )
            assert "## Context" in body
            assert "user_id" in body
            assert "123" in body

    def test_body_includes_logs_when_provided(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(
                e,
                signature="abc12345",
                logs="2025-01-25 INFO Test log",
            )
            assert "## Recent Logs" in body
            assert "Test log" in body

    def test_body_omits_context_when_empty(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345")
            assert "## Context" not in body

    def test_body_omits_logs_when_empty(self) -> None:
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345", logs="")
            assert "## Recent Logs" not in body
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/core/test_formatter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'splat.core.formatter'`

**Step 3: Implement formatter module**

```python
# src/splat/core/formatter.py
"""GitHub issue formatting for error reports."""

from __future__ import annotations

import traceback
from typing import Any


def format_issue_title(exception: BaseException) -> str:
    """
    Format the GitHub issue title.

    Format: [Splat] {ExceptionType} in {filename}:{line}

    Args:
        exception: The exception to format

    Returns:
        Formatted issue title
    """
    exc_type = type(exception).__name__

    # Extract location from traceback
    filename = "unknown"
    lineno = 0

    tb = exception.__traceback__
    if tb is not None:
        while tb.tb_next is not None:
            tb = tb.tb_next
        filename = tb.tb_frame.f_code.co_filename.split("/")[-1]
        lineno = tb.tb_lineno

    return f"[Splat] {exc_type} in {filename}:{lineno}"


def format_issue_body(
    exception: BaseException,
    signature: str,
    context: dict[str, Any] | None = None,
    logs: str | None = None,
) -> str:
    """
    Format the GitHub issue body with full error details.

    Args:
        exception: The exception to format
        signature: Error signature for deduplication
        context: Optional user-provided context dict
        logs: Optional log string

    Returns:
        Formatted Markdown issue body
    """
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

    # Format traceback
    tb_str = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    # Build body sections
    sections = []

    # Error section
    sections.append(f"""## Error

**Type:** {exc_type}
**Message:** {exc_msg}
**File:** {filename}
**Line:** {lineno}
**Function:** {funcname}""")

    # Traceback section
    sections.append(f"""## Traceback

```
{tb_str.strip()}
```""")

    # Context section (if provided)
    if context:
        context_rows = "\n".join(f"| {k} | {v} |" for k, v in context.items())
        sections.append(f"""## Context

| Key | Value |
|-----|-------|
{context_rows}""")

    # Logs section (if provided and non-empty)
    if logs:
        sections.append(f"""## Recent Logs

<details>
<summary>Recent log entries</summary>

```
{logs}
```

</details>""")

    # Footer with signature
    sections.append(f"""---
Signature: `{signature}`
Reported by [Splat](https://github.com/yourorg/splat)""")

    return "\n\n".join(sections)
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/core/test_formatter.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/splat/core/formatter.py tests/core/test_formatter.py
git commit -m "feat(formatter): add GitHub issue formatting"
```

---

## Task 6: Reporter Module (Main Splat Class)

**Files:**
- Create: `src/splat/core/reporter.py`
- Create: `tests/core/test_reporter.py`

**Step 1: Write failing tests for Splat class**

```python
# tests/core/test_reporter.py
"""Tests for the main Splat reporter class."""

import os
from unittest.mock import patch, AsyncMock

import pytest
import httpx
import respx

from splat.core.reporter import Splat


class TestSplatInit:
    """Test Splat initialization."""

    def test_init_with_explicit_args(self) -> None:
        splat = Splat(repo="owner/repo", token="ghp_test")
        assert splat.config.repo == "owner/repo"
        assert splat.config.token == "ghp_test"

    def test_init_loads_from_env(self) -> None:
        with patch.dict(os.environ, {
            "SPLAT_GITHUB_REPO": "env/repo",
            "SPLAT_GITHUB_TOKEN": "ghp_env",
        }):
            splat = Splat()
            assert splat.config.repo == "env/repo"
            assert splat.config.token == "ghp_env"

    def test_init_installs_log_buffer(self) -> None:
        splat = Splat(repo="owner/repo", token="ghp_test")
        # Buffer should be accessible
        assert splat._log_buffer is not None


class TestSplatEnabled:
    """Test enabled/disabled behavior."""

    def test_is_enabled_when_configured(self) -> None:
        splat = Splat(repo="owner/repo", token="ghp_test")
        assert splat.is_enabled() is True

    def test_is_disabled_when_missing_repo(self) -> None:
        splat = Splat(token="ghp_test")
        assert splat.is_enabled() is False

    def test_is_disabled_when_missing_token(self) -> None:
        splat = Splat(repo="owner/repo")
        assert splat.is_enabled() is False

    def test_is_disabled_when_enabled_false(self) -> None:
        splat = Splat(repo="owner/repo", token="ghp_test", enabled=False)
        assert splat.is_enabled() is False


class TestSplatReport:
    """Test error reporting."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_creates_github_issue(self) -> None:
        # Mock the duplicate check (no duplicate found)
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )

        # Mock issue creation
        create_route = respx.post("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(201, json={"number": 1, "html_url": "https://github.com/owner/repo/issues/1"})
        )

        splat = Splat(repo="owner/repo", token="ghp_test")

        try:
            raise ValueError("test error")
        except ValueError as e:
            result = await splat.report(e)

        assert result is not None
        assert result["number"] == 1
        assert create_route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_skips_duplicate(self) -> None:
        # Mock duplicate found
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": [{"number": 42}]})
        )

        # Issue creation should NOT be called
        create_route = respx.post("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(201, json={})
        )

        splat = Splat(repo="owner/repo", token="ghp_test")

        try:
            raise ValueError("test error")
        except ValueError as e:
            result = await splat.report(e)

        assert result is None
        assert not create_route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_includes_context(self) -> None:
        respx.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )

        create_route = respx.post("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(201, json={"number": 1, "html_url": "url"})
        )

        splat = Splat(repo="owner/repo", token="ghp_test")

        try:
            raise ValueError("test")
        except ValueError as e:
            await splat.report(e, context={"user_id": 123})

        assert create_route.called
        request_body = create_route.calls[0].request.content.decode()
        assert "user_id" in request_body

    @pytest.mark.asyncio
    async def test_report_does_nothing_when_disabled(self) -> None:
        splat = Splat(repo="owner/repo", token="ghp_test", enabled=False)

        try:
            raise ValueError("test")
        except ValueError as e:
            result = await splat.report(e)

        assert result is None
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/core/test_reporter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'splat.core.reporter'`

**Step 3: Implement reporter module**

```python
# src/splat/core/reporter.py
"""Main Splat error reporter class."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from splat.core.config import SplatConfig, load_config
from splat.core.dedup import generate_signature, check_duplicate
from splat.core.formatter import format_issue_title, format_issue_body
from splat.core.log_buffer import LogBuffer, get_recent_logs_as_string

logger = logging.getLogger(__name__)


class Splat:
    """
    Automatic GitHub issue creation on application crashes.

    Usage:
        splat = Splat(repo="owner/repo", token="ghp_...")

        try:
            do_something()
        except Exception as e:
            await splat.report(e)
    """

    def __init__(
        self,
        *,
        repo: str | None = None,
        token: str | None = None,
        enabled: bool | None = None,
        log_buffer_size: int | None = None,
        labels: list[str] | None = None,
    ) -> None:
        """
        Initialize Splat with configuration.

        Args:
            repo: GitHub repository (owner/repo format)
            token: GitHub API token
            enabled: Whether error reporting is enabled
            log_buffer_size: Number of log entries to buffer
            labels: Labels to apply to created issues
        """
        self.config = load_config(
            repo=repo,
            token=token,
            enabled=enabled,
            log_buffer_size=log_buffer_size,
            labels=labels,
        )

        # Set up log buffer
        self._log_buffer = LogBuffer(capacity=self.config.log_buffer_size)
        logging.getLogger().addHandler(self._log_buffer)

        if not self.is_enabled():
            logger.warning(
                "Splat is disabled. Set SPLAT_GITHUB_REPO and SPLAT_GITHUB_TOKEN "
                "environment variables or pass repo/token to enable."
            )

    def is_enabled(self) -> bool:
        """Check if Splat is enabled and properly configured."""
        return bool(
            self.config.enabled
            and self.config.repo
            and self.config.token
        )

    async def report(
        self,
        exception: BaseException,
        context: dict[str, Any] | None = None,
        logs: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Report an exception to GitHub Issues.

        Args:
            exception: The exception to report
            context: Optional user-provided context dict
            logs: Optional log string (uses buffered logs if not provided)

        Returns:
            Created issue data dict, or None if disabled/duplicate
        """
        if not self.is_enabled():
            return None

        assert self.config.repo is not None
        assert self.config.token is not None

        # Generate signature for deduplication
        signature = generate_signature(exception)

        # Check for existing issue
        existing = await check_duplicate(
            repo=self.config.repo,
            token=self.config.token,
            signature=signature,
        )

        if existing is not None:
            logger.info(f"Duplicate error, issue #{existing} already exists")
            return None

        # Get logs if not provided
        if logs is None:
            logs = self._log_buffer.get_logs_as_string()

        # Format issue
        title = format_issue_title(exception)
        body = format_issue_body(
            exception,
            signature=signature,
            context=context,
            logs=logs,
        )

        # Create issue
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
            issue_data = response.json()

        logger.info(f"Created issue #{issue_data['number']}: {issue_data['html_url']}")
        return issue_data
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/core/test_reporter.py -v
```

Expected: All tests PASS

**Step 5: Update src/splat/__init__.py to export Splat**

The file already exports Splat, but verify the import works:

```bash
python -c "from splat import Splat; print('Import successful')"
```

**Step 6: Commit**

```bash
git add src/splat/core/reporter.py tests/core/test_reporter.py
git commit -m "feat(reporter): add main Splat class with GitHub integration"
```

---

## Task 7: Flask Middleware

**Files:**
- Create: `src/splat/middleware/flask.py`
- Create: `tests/middleware/test_flask.py`

**Step 1: Write failing tests for Flask middleware**

```python
# tests/middleware/test_flask.py
"""Tests for Flask middleware."""

from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from splat.middleware.flask import create_error_handler, SplatFlask


class TestCreateErrorHandler:
    """Test Flask error handler creation."""

    def test_creates_callable_handler(self) -> None:
        handler = create_error_handler()
        assert callable(handler)

    @pytest.mark.asyncio
    async def test_handler_calls_splat_report(self) -> None:
        mock_splat = MagicMock()
        mock_splat.report = AsyncMock(return_value={"number": 1})

        with patch("splat.middleware.flask._get_splat", return_value=mock_splat):
            handler = create_error_handler()
            error = ValueError("test")

            # Flask handlers are sync, but internally run async
            with patch("splat.middleware.flask._run_async") as mock_run:
                mock_run.return_value = {"number": 1}
                handler(error)
                mock_run.assert_called_once()

    def test_handler_extracts_request_context(self) -> None:
        mock_splat = MagicMock()
        mock_splat.report = AsyncMock(return_value={"number": 1})

        with patch("splat.middleware.flask._get_splat", return_value=mock_splat):
            with patch("splat.middleware.flask._run_async") as mock_run:
                with patch("splat.middleware.flask.request") as mock_request:
                    mock_request.method = "POST"
                    mock_request.path = "/api/test"
                    mock_request.remote_addr = "127.0.0.1"

                    handler = create_error_handler()
                    handler(ValueError("test"))

                    # Check context was passed
                    call_args = mock_run.call_args
                    assert call_args is not None


class TestSplatFlask:
    """Test SplatFlask extension."""

    def test_init_app_registers_error_handler(self) -> None:
        mock_app = MagicMock()

        ext = SplatFlask()
        ext.init_app(mock_app, repo="owner/repo", token="ghp_test")

        mock_app.register_error_handler.assert_called_once()
        args = mock_app.register_error_handler.call_args[0]
        assert args[0] == Exception
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/middleware/test_flask.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'splat.middleware.flask'`

**Step 3: Implement Flask middleware**

```python
# src/splat/middleware/flask.py
"""Flask integration for Splat error reporting."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from splat.core.reporter import Splat

# Global splat instance for the middleware
_splat_instance: Splat | None = None


def _get_splat() -> Splat | None:
    """Get the global Splat instance."""
    return _splat_instance


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If there's already a running loop, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def create_error_handler(
    splat: Splat | None = None,
) -> Callable[[Exception], Any]:
    """
    Create a Flask error handler that reports errors to Splat.

    Args:
        splat: Optional Splat instance (uses global if not provided)

    Returns:
        Flask error handler function
    """
    def handler(error: Exception) -> Any:
        instance = splat or _get_splat()
        if instance is None:
            raise error

        # Try to get Flask request context
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

        # Report error (run async in sync context)
        _run_async(instance.report(error, context=context))

        # Re-raise so Flask handles the response
        raise error

    return handler


class SplatFlask:
    """
    Flask extension for Splat error reporting.

    Usage:
        app = Flask(__name__)
        splat = SplatFlask()
        splat.init_app(app, repo="owner/repo", token="ghp_...")
    """

    def __init__(self, app: Any = None, **kwargs: Any) -> None:
        """
        Initialize the extension.

        Args:
            app: Optional Flask app to initialize with
            **kwargs: Passed to Splat constructor
        """
        self.splat: Splat | None = None
        if app is not None:
            self.init_app(app, **kwargs)

    def init_app(self, app: Any, **kwargs: Any) -> None:
        """
        Initialize Splat with a Flask app.

        Args:
            app: Flask application
            **kwargs: Passed to Splat constructor
        """
        global _splat_instance

        self.splat = Splat(**kwargs)
        _splat_instance = self.splat

        # Register error handler
        app.register_error_handler(Exception, create_error_handler(self.splat))
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/middleware/test_flask.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/splat/middleware/flask.py tests/middleware/test_flask.py
git commit -m "feat(flask): add Flask error handler middleware"
```

---

## Task 8: FastAPI Middleware

**Files:**
- Create: `src/splat/middleware/fastapi.py`
- Create: `tests/middleware/test_fastapi.py`

**Step 1: Write failing tests for FastAPI middleware**

```python
# tests/middleware/test_fastapi.py
"""Tests for FastAPI middleware."""

from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from splat.middleware.fastapi import SplatMiddleware


class TestSplatMiddleware:
    """Test FastAPI Splat middleware."""

    def test_middleware_initializes_splat(self) -> None:
        mock_app = MagicMock()

        middleware = SplatMiddleware(mock_app, repo="owner/repo", token="ghp_test")

        assert middleware.splat is not None
        assert middleware.splat.config.repo == "owner/repo"

    @pytest.mark.asyncio
    async def test_middleware_passes_through_on_success(self) -> None:
        mock_app = MagicMock()

        async def call_next(request: Any) -> str:
            return "response"

        middleware = SplatMiddleware(mock_app, repo="owner/repo", token="ghp_test")

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.client.host = "127.0.0.1"

        # The dispatch method handles the call
        response = await middleware.dispatch(mock_request, call_next)

        assert response == "response"

    @pytest.mark.asyncio
    async def test_middleware_reports_errors(self) -> None:
        mock_app = MagicMock()

        async def call_next(request: Any) -> None:
            raise ValueError("test error")

        middleware = SplatMiddleware(mock_app, repo="owner/repo", token="ghp_test")
        middleware.splat.report = AsyncMock(return_value={"number": 1})

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.client.host = "127.0.0.1"

        with pytest.raises(ValueError):
            await middleware.dispatch(mock_request, call_next)

        middleware.splat.report.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_includes_request_context(self) -> None:
        mock_app = MagicMock()

        async def call_next(request: Any) -> None:
            raise ValueError("test")

        middleware = SplatMiddleware(mock_app, repo="owner/repo", token="ghp_test")
        middleware.splat.report = AsyncMock(return_value={"number": 1})

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/api/checkout"
        mock_request.client.host = "192.168.1.1"

        with pytest.raises(ValueError):
            await middleware.dispatch(mock_request, call_next)

        call_kwargs = middleware.splat.report.call_args[1]
        context = call_kwargs["context"]
        assert context["method"] == "POST"
        assert context["path"] == "/api/checkout"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/middleware/test_fastapi.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'splat.middleware.fastapi'`

**Step 3: Implement FastAPI middleware**

```python
# src/splat/middleware/fastapi.py
"""FastAPI integration for Splat error reporting."""

from __future__ import annotations

from typing import Any, Callable, Awaitable

from splat.core.reporter import Splat


class SplatMiddleware:
    """
    FastAPI middleware for Splat error reporting.

    Usage:
        app = FastAPI()
        app.add_middleware(SplatMiddleware, repo="owner/repo", token="ghp_...")
    """

    def __init__(self, app: Any, **kwargs: Any) -> None:
        """
        Initialize the middleware.

        Args:
            app: FastAPI application
            **kwargs: Passed to Splat constructor
        """
        self.app = app
        self.splat = Splat(**kwargs)

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """ASGI interface."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Create a simple request-like object for dispatch
        from starlette.requests import Request
        request = Request(scope, receive, send)

        async def call_next(req: Request) -> Any:
            # This is a simplified version - in real use, Starlette handles this
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
        """
        Process request and catch errors.

        Args:
            request: Starlette/FastAPI Request object
            call_next: Next middleware/route handler

        Returns:
            Response from call_next
        """
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # Extract request context
            context = {
                "method": request.method,
                "path": request.url.path,
                "client": getattr(request.client, "host", "unknown") if request.client else "unknown",
            }

            # Report error
            await self.splat.report(e, context=context)

            # Re-raise so FastAPI handles the response
            raise
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/middleware/test_fastapi.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/splat/middleware/fastapi.py tests/middleware/test_fastapi.py
git commit -m "feat(fastapi): add FastAPI middleware"
```

---

## Task 9: CLI Entry Point

**Files:**
- Create: `src/splat/cli/main.py`
- Create: `tests/cli/test_main.py`

**Step 1: Write failing tests for CLI**

```python
# tests/cli/test_main.py
"""Tests for CLI entry point."""

from click.testing import CliRunner

from splat.cli.main import cli


class TestCli:
    """Test CLI commands."""

    def test_cli_has_version_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_cli_has_init_command(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0
        assert "init" in result.output.lower() or "setup" in result.output.lower()

    def test_cli_has_install_autofix_command(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["install-autofix", "--help"])
        assert result.exit_code == 0
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/cli/test_main.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'splat.cli.main'`

**Step 3: Implement CLI entry point**

```python
# src/splat/cli/main.py
"""Splat CLI entry point."""

from __future__ import annotations

import click

from splat import __version__


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Splat - Automatic GitHub issue creation on application crashes."""
    pass


@cli.command()
def init() -> None:
    """Interactive setup wizard for Splat."""
    from splat.cli.init import run_init_wizard
    run_init_wizard()


@cli.command("install-autofix")
def install_autofix() -> None:
    """Install the Claude Code auto-fix GitHub Action."""
    from splat.cli.autofix import install_autofix_workflow
    install_autofix_workflow()


if __name__ == "__main__":
    cli()
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/cli/test_main.py -v
```

Expected: All tests PASS (some may skip if subcommand modules don't exist yet)

**Step 5: Commit**

```bash
git add src/splat/cli/main.py tests/cli/test_main.py
git commit -m "feat(cli): add CLI entry point with init and install-autofix commands"
```

---

## Task 10: Auto-Fix Installer

**Files:**
- Create: `src/splat/cli/autofix.py`
- Create: `src/splat/templates/splat-autofix.yml`
- Create: `tests/cli/test_autofix.py`

**Step 1: Write failing tests for autofix installer**

```python
# tests/cli/test_autofix.py
"""Tests for auto-fix workflow installer."""

from pathlib import Path

import pytest

from splat.cli.autofix import install_autofix_workflow, get_workflow_template


class TestGetWorkflowTemplate:
    """Test workflow template loading."""

    def test_template_is_valid_yaml(self) -> None:
        import yaml
        template = get_workflow_template()
        # Should not raise
        parsed = yaml.safe_load(template)
        assert "name" in parsed
        assert parsed["name"] == "Splat Auto-Fix"

    def test_template_has_issue_trigger(self) -> None:
        template = get_workflow_template()
        assert "issues:" in template
        assert "labeled" in template

    def test_template_has_claude_action(self) -> None:
        template = get_workflow_template()
        assert "anthropics/claude-code-action" in template


class TestInstallAutofix:
    """Test workflow installation."""

    def test_creates_workflow_file(self, tmp_path: Path) -> None:
        workflows_dir = tmp_path / ".github" / "workflows"

        install_autofix_workflow(base_path=tmp_path)

        workflow_file = workflows_dir / "splat-autofix.yml"
        assert workflow_file.exists()

    def test_creates_github_directory_if_missing(self, tmp_path: Path) -> None:
        install_autofix_workflow(base_path=tmp_path)

        assert (tmp_path / ".github" / "workflows").is_dir()

    def test_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        existing = workflows_dir / "splat-autofix.yml"
        existing.write_text("existing content")

        # Should not overwrite (or should prompt - test behavior)
        install_autofix_workflow(base_path=tmp_path, force=False)

        assert existing.read_text() == "existing content"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/cli/test_autofix.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'splat.cli.autofix'`

**Step 3: Create workflow template**

```yaml
# src/splat/templates/splat-autofix.yml
name: Splat Auto-Fix

on:
  issues:
    types: [labeled]

jobs:
  autofix:
    if: github.event.label.name == 'auto-fix'
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
      pull-requests: write

    steps:
      - uses: actions/checkout@v4

      - name: Fix with Claude Code
        uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          issue_number: ${{ github.event.issue.number }}
          model: claude-sonnet-4-20250514
          max_turns: 50
```

**Step 4: Implement autofix installer**

```python
# src/splat/cli/autofix.py
"""Auto-fix workflow installer."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import click


def get_workflow_template() -> str:
    """
    Load the auto-fix workflow template.

    Returns:
        Workflow YAML content
    """
    # Try importlib.resources first (Python 3.9+)
    try:
        if hasattr(resources, "files"):
            # Python 3.9+
            template_path = resources.files("splat.templates").joinpath("splat-autofix.yml")
            return template_path.read_text()
        else:
            # Fallback for older Python
            with resources.open_text("splat.templates", "splat-autofix.yml") as f:
                return f.read()
    except (FileNotFoundError, TypeError):
        # Fallback: read from package directory
        package_dir = Path(__file__).parent.parent
        template_file = package_dir / "templates" / "splat-autofix.yml"
        return template_file.read_text()


def install_autofix_workflow(
    base_path: Path | None = None,
    force: bool = False,
) -> Path:
    """
    Install the auto-fix GitHub Action workflow.

    Args:
        base_path: Base directory (defaults to cwd)
        force: Overwrite existing file if True

    Returns:
        Path to created workflow file
    """
    if base_path is None:
        base_path = Path.cwd()

    workflows_dir = base_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    workflow_file = workflows_dir / "splat-autofix.yml"

    if workflow_file.exists() and not force:
        click.echo(f"Workflow already exists: {workflow_file}")
        click.echo("Use --force to overwrite.")
        return workflow_file

    template = get_workflow_template()
    workflow_file.write_text(template)

    click.echo(f"Created {workflow_file}")
    click.echo("\nNext steps:")
    click.echo("1. Add ANTHROPIC_API_KEY to your repository secrets")
    click.echo("2. Add 'auto-fix' to your splat labels config")
    click.echo("3. Commit and push the workflow file")

    return workflow_file
```

**Step 5: Create templates __init__.py for package discovery**

```bash
touch src/splat/templates/__init__.py
```

**Step 6: Run tests to verify they pass**

```bash
pytest tests/cli/test_autofix.py -v
```

Expected: All tests PASS

**Step 7: Commit**

```bash
git add src/splat/cli/autofix.py src/splat/templates/ tests/cli/test_autofix.py
git commit -m "feat(autofix): add auto-fix workflow installer"
```

---

## Task 11: Init Wizard - Project Detection

**Files:**
- Create: `src/splat/cli/init.py`
- Create: `tests/cli/test_init.py`

**Step 1: Write failing tests for project detection**

```python
# tests/cli/test_init.py
"""Tests for init wizard."""

from pathlib import Path
from unittest.mock import patch

import pytest

from splat.cli.init import (
    detect_project_type,
    detect_framework,
    detect_github_remote,
    ProjectInfo,
)


class TestDetectProjectType:
    """Test project type detection."""

    def test_detects_python_by_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")

        result = detect_project_type(tmp_path)

        assert result == "python"

    def test_detects_python_by_requirements(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("flask")

        result = detect_project_type(tmp_path)

        assert result == "python"

    def test_detects_python_by_setup_py(self, tmp_path: Path) -> None:
        (tmp_path / "setup.py").write_text("from setuptools import setup")

        result = detect_project_type(tmp_path)

        assert result == "python"

    def test_returns_unknown_for_empty_dir(self, tmp_path: Path) -> None:
        result = detect_project_type(tmp_path)

        assert result == "unknown"


class TestDetectFramework:
    """Test framework detection."""

    def test_detects_flask(self, tmp_path: Path) -> None:
        app_file = tmp_path / "app.py"
        app_file.write_text("from flask import Flask\napp = Flask(__name__)")

        result = detect_framework(tmp_path)

        assert result == ("flask", app_file)

    def test_detects_fastapi(self, tmp_path: Path) -> None:
        main_file = tmp_path / "main.py"
        main_file.write_text("from fastapi import FastAPI\napp = FastAPI()")

        result = detect_framework(tmp_path)

        assert result == ("fastapi", main_file)

    def test_detects_django(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "myproject" / "settings.py"
        settings_file.parent.mkdir()
        settings_file.write_text("INSTALLED_APPS = ['django.contrib.admin']")

        result = detect_framework(tmp_path)

        assert result[0] == "django"

    def test_returns_none_for_unknown(self, tmp_path: Path) -> None:
        result = detect_framework(tmp_path)

        assert result == (None, None)


class TestDetectGithubRemote:
    """Test GitHub remote detection."""

    def test_extracts_repo_from_https(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        config = git_dir / "config"
        config.write_text("""
[remote "origin"]
    url = https://github.com/owner/repo.git
""")

        result = detect_github_remote(tmp_path)

        assert result == "owner/repo"

    def test_extracts_repo_from_ssh(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        config = git_dir / "config"
        config.write_text("""
[remote "origin"]
    url = git@github.com:owner/repo.git
""")

        result = detect_github_remote(tmp_path)

        assert result == "owner/repo"

    def test_returns_none_for_non_git(self, tmp_path: Path) -> None:
        result = detect_github_remote(tmp_path)

        assert result is None
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/cli/test_init.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'splat.cli.init'`

**Step 3: Implement init wizard (detection functions)**

```python
# src/splat/cli/init.py
"""Interactive setup wizard for Splat."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import click


@dataclass
class ProjectInfo:
    """Detected project information."""

    project_type: str
    framework: str | None
    framework_file: Path | None
    github_repo: str | None
    base_path: Path


def detect_project_type(base_path: Path) -> str:
    """
    Detect the project type.

    Args:
        base_path: Project root directory

    Returns:
        Project type: "python", "node", or "unknown"
    """
    # Python indicators
    python_files = ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"]
    for f in python_files:
        if (base_path / f).exists():
            return "python"

    # Node indicators
    if (base_path / "package.json").exists():
        return "node"

    return "unknown"


def detect_framework(base_path: Path) -> Tuple[str | None, Path | None]:
    """
    Detect the web framework in use.

    Args:
        base_path: Project root directory

    Returns:
        Tuple of (framework_name, main_file_path) or (None, None)
    """
    # Common Python file patterns
    py_files = list(base_path.glob("*.py")) + list(base_path.glob("**/*.py"))

    for py_file in py_files[:50]:  # Limit search
        try:
            content = py_file.read_text()
        except Exception:
            continue

        # Flask detection
        if "from flask import Flask" in content or "import flask" in content.lower():
            if "Flask(__name__)" in content or "Flask(" in content:
                return ("flask", py_file)

        # FastAPI detection
        if "from fastapi import FastAPI" in content or "import fastapi" in content.lower():
            if "FastAPI()" in content or "FastAPI(" in content:
                return ("fastapi", py_file)

    # Django detection (settings.py with INSTALLED_APPS)
    for settings_file in base_path.glob("**/settings.py"):
        try:
            content = settings_file.read_text()
            if "INSTALLED_APPS" in content:
                return ("django", settings_file)
        except Exception:
            continue

    return (None, None)


def detect_github_remote(base_path: Path) -> str | None:
    """
    Detect GitHub repository from git remote.

    Args:
        base_path: Project root directory

    Returns:
        Repository in "owner/repo" format, or None
    """
    git_config = base_path / ".git" / "config"
    if not git_config.exists():
        return None

    try:
        content = git_config.read_text()

        # Match HTTPS URLs
        https_match = re.search(r'url\s*=\s*https://github\.com/([^/]+)/([^/\s.]+)', content)
        if https_match:
            owner, repo = https_match.groups()
            repo = repo.rstrip(".git")
            return f"{owner}/{repo}"

        # Match SSH URLs
        ssh_match = re.search(r'url\s*=\s*git@github\.com:([^/]+)/([^/\s.]+)', content)
        if ssh_match:
            owner, repo = ssh_match.groups()
            repo = repo.rstrip(".git")
            return f"{owner}/{repo}"

    except Exception:
        pass

    return None


def run_init_wizard(base_path: Path | None = None) -> None:
    """
    Run the interactive setup wizard.

    Args:
        base_path: Project root (defaults to cwd)
    """
    if base_path is None:
        base_path = Path.cwd()

    click.echo("\n🎯 Welcome to Splat!\n")
    click.echo("Detecting project...")

    # Detect project info
    project_type = detect_project_type(base_path)
    framework, framework_file = detect_framework(base_path)
    github_repo = detect_github_remote(base_path)

    if project_type != "unknown":
        click.echo(f"  ✓ {project_type.title()} project detected")
    else:
        click.echo("  ⚠ Could not detect project type")

    if framework:
        click.echo(f"  ✓ {framework.title()} app in {framework_file.name if framework_file else 'unknown'}")
    else:
        click.echo("  ⚠ No framework detected")

    if github_repo:
        click.echo(f"  ✓ GitHub remote: {github_repo}")
    else:
        click.echo("  ⚠ No GitHub remote detected")

    click.echo()

    # TODO: Implement remaining wizard steps
    # Step 1: GitHub Token
    # Step 2: Integration
    # Step 3: Auto-Fix

    click.echo("🚧 Full wizard coming soon!")
    click.echo("For now, configure manually in pyproject.toml or environment variables.")
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/cli/test_init.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/splat/cli/init.py tests/cli/test_init.py
git commit -m "feat(init): add project/framework/github detection for wizard"
```

---

## Task 12: Run Full Test Suite & Verify Coverage

**Step 1: Install dev dependencies**

```bash
cd /Users/andreas/Desktop/projects/splat
pip install -e ".[dev]"
```

**Step 2: Run full test suite with coverage**

```bash
pytest --cov=src/splat --cov-report=term-missing -v
```

Expected: All tests PASS, coverage ≥ 80%

**Step 3: Run mypy type checking**

```bash
mypy src/splat --strict --ignore-missing-imports
```

Expected: No errors

**Step 4: Run ruff linting**

```bash
ruff check src/splat
```

Expected: No errors

**Step 5: Commit any fixes**

```bash
git add -A
git commit -m "chore: fix any linting/typing issues"
```

---

## Task 13: Final Setup & README

**Step 1: Update README with full documentation**

Update `/Users/andreas/Desktop/projects/splat/README.md` with:
- Installation instructions
- Quick start guide
- Configuration reference
- CLI usage
- Framework examples

**Step 2: Create GitHub repository**

```bash
gh repo create splat --public --description "Automatic GitHub issue creation on application crashes"
git remote add origin <url>
git push -u origin main
```

**Step 3: Final commit**

```bash
git add -A
git commit -m "docs: complete README with full documentation"
git push
```

---

## Summary

This plan implements Splat in 13 tasks with TDD:

1. **Project Setup** - pyproject.toml, structure
2. **Config Module** - Env/toml/programmatic loading
3. **Log Buffer** - Rolling log capture
4. **Dedup Module** - Signature generation, GitHub search
5. **Formatter** - Issue title/body formatting
6. **Reporter** - Main Splat class
7. **Flask Middleware** - Error handler
8. **FastAPI Middleware** - ASGI middleware
9. **CLI Entry** - Click-based CLI
10. **Autofix Installer** - Workflow template
11. **Init Wizard** - Project detection
12. **Test & Verify** - Full suite, coverage, typing
13. **Final Setup** - README, GitHub repo

Each task follows TDD: write failing test → implement → verify pass → commit.
