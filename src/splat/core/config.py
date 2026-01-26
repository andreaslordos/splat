"""Configuration loading with precedence: programmatic > toml > env > defaults."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

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
        config["labels"] = [label.strip() for label in labels.split(",")]

    if debug := os.environ.get("SPLAT_DEBUG"):
        config["debug"] = debug.lower() in ("true", "1", "yes")

    if timeout := os.environ.get("SPLAT_TIMEOUT"):
        config["timeout"] = float(timeout)

    if github_api_url := os.environ.get("SPLAT_GITHUB_API_URL"):
        config["github_api_url"] = github_api_url

    return config


def _load_from_toml(path: Path) -> dict[str, Any]:
    """Load config from pyproject.toml [tool.splat] section."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        tool_section = data.get("tool", {})
        if not isinstance(tool_section, dict):
            return {}
        splat_section = tool_section.get("splat", {})
        if not isinstance(splat_section, dict):
            return {}
        result: dict[str, Any] = splat_section
        return result
    except Exception:
        return {}


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
    """
    Load configuration with precedence: programmatic > toml > env > defaults.

    Args:
        repo: GitHub repository (owner/repo format)
        token: GitHub API token
        enabled: Whether error reporting is enabled
        log_buffer_size: Number of log entries to buffer
        labels: Labels to apply to created issues
        debug: Enable debug logging
        timeout: Request timeout in seconds (default: 30.0)
        max_retries: Maximum retry attempts (default: 3)
        github_api_url: GitHub API base URL (default: https://api.github.com)
        ignore_exceptions: List of exception types to ignore
        exception_filter: Callable that returns True to report, False to ignore
        max_traceback_length: Maximum traceback length in chars (default: 50000)
        max_log_entries: Maximum log entries to include (default: 500)
        max_context_value_length: Maximum context value length (default: 5000)

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
    if "debug" in env_config:
        config.debug = env_config["debug"]
    if "timeout" in env_config:
        config.timeout = env_config["timeout"]
    if "github_api_url" in env_config:
        config.github_api_url = env_config["github_api_url"]

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
        if "debug" in toml_config:
            config.debug = toml_config["debug"]
        if "timeout" in toml_config:
            config.timeout = toml_config["timeout"]
        if "github_api_url" in toml_config:
            config.github_api_url = toml_config["github_api_url"]

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
    if debug is not None:
        config.debug = debug
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

    return config
