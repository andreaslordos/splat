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
    # Vercel Log Drain settings
    vercel_secret: str | None = None
    vercel_webhook_path: str = "/splat/logs"
    vercel_log_ttl: int = 60


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

    # Vercel settings
    if vercel_secret := os.environ.get("SPLAT_VERCEL_SECRET"):
        config["vercel_secret"] = vercel_secret

    if vercel_webhook_path := os.environ.get("SPLAT_VERCEL_WEBHOOK_PATH"):
        config["vercel_webhook_path"] = vercel_webhook_path

    if vercel_log_ttl := os.environ.get("SPLAT_VERCEL_LOG_TTL"):
        config["vercel_log_ttl"] = int(vercel_log_ttl)

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
    vercel_secret: str | None = None,
    vercel_webhook_path: str | None = None,
    vercel_log_ttl: int | None = None,
) -> SplatConfig:
    """
    Load configuration with precedence: programmatic > toml > env > defaults.

    Args:
        repo: GitHub repository (owner/repo format)
        token: GitHub API token
        enabled: Whether error reporting is enabled
        log_buffer_size: Number of log entries to buffer
        labels: Labels to apply to created issues
        vercel_secret: Webhook secret for Vercel Log Drain signature verification
        vercel_webhook_path: Webhook endpoint path for Vercel logs
        vercel_log_ttl: TTL in seconds for how long to keep logs in memory

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
    if "vercel_secret" in env_config:
        config.vercel_secret = env_config["vercel_secret"]
    if "vercel_webhook_path" in env_config:
        config.vercel_webhook_path = env_config["vercel_webhook_path"]
    if "vercel_log_ttl" in env_config:
        config.vercel_log_ttl = env_config["vercel_log_ttl"]

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
        if "vercel_secret" in toml_config:
            config.vercel_secret = toml_config["vercel_secret"]
        if "vercel_webhook_path" in toml_config:
            config.vercel_webhook_path = toml_config["vercel_webhook_path"]
        if "vercel_log_ttl" in toml_config:
            config.vercel_log_ttl = toml_config["vercel_log_ttl"]

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
    if vercel_secret is not None:
        config.vercel_secret = vercel_secret
    if vercel_webhook_path is not None:
        config.vercel_webhook_path = vercel_webhook_path
    if vercel_log_ttl is not None:
        config.vercel_log_ttl = vercel_log_ttl

    return config
