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


class TestVercelConfigDefaults:
    """Test SplatConfig default values for Vercel settings."""

    def test_config_has_no_default_vercel_secret(self) -> None:
        config = SplatConfig()
        assert config.vercel_secret is None

    def test_config_has_default_vercel_webhook_path(self) -> None:
        config = SplatConfig()
        assert config.vercel_webhook_path == "/splat/logs"

    def test_config_has_default_vercel_log_ttl(self) -> None:
        config = SplatConfig()
        assert config.vercel_log_ttl == 60


class TestLoadVercelConfigFromEnv:
    """Test loading Vercel config from environment variables."""

    def test_load_config_reads_vercel_secret_from_env(self) -> None:
        with patch.dict(os.environ, {"SPLAT_VERCEL_SECRET": "my-webhook-secret"}):
            config = load_config()
            assert config.vercel_secret == "my-webhook-secret"

    def test_load_config_reads_vercel_webhook_path_from_env(self) -> None:
        with patch.dict(os.environ, {"SPLAT_VERCEL_WEBHOOK_PATH": "/custom/path"}):
            config = load_config()
            assert config.vercel_webhook_path == "/custom/path"

    def test_load_config_reads_vercel_log_ttl_from_env(self) -> None:
        with patch.dict(os.environ, {"SPLAT_VERCEL_LOG_TTL": "120"}):
            config = load_config()
            assert config.vercel_log_ttl == 120


class TestLoadVercelConfigFromToml:
    """Test loading Vercel config from pyproject.toml."""

    def test_load_config_reads_vercel_secret_from_toml(
        self, tmp_path: Path
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.splat]
vercel_secret = "toml-secret"
""")
        with patch("splat.core.config._find_pyproject", return_value=pyproject):
            config = load_config()
            assert config.vercel_secret == "toml-secret"

    def test_load_config_reads_vercel_webhook_path_from_toml(
        self, tmp_path: Path
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.splat]
vercel_webhook_path = "/toml/webhook"
""")
        with patch("splat.core.config._find_pyproject", return_value=pyproject):
            config = load_config()
            assert config.vercel_webhook_path == "/toml/webhook"

    def test_load_config_reads_vercel_log_ttl_from_toml(
        self, tmp_path: Path
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.splat]
vercel_log_ttl = 180
""")
        with patch("splat.core.config._find_pyproject", return_value=pyproject):
            config = load_config()
            assert config.vercel_log_ttl == 180


class TestVercelConfigPrecedence:
    """Test precedence for Vercel config: programmatic > toml > env."""

    def test_programmatic_vercel_secret_overrides_env(self) -> None:
        with patch.dict(os.environ, {"SPLAT_VERCEL_SECRET": "env-secret"}):
            config = load_config(vercel_secret="programmatic-secret")
            assert config.vercel_secret == "programmatic-secret"

    def test_programmatic_vercel_webhook_path_overrides_env(self) -> None:
        with patch.dict(os.environ, {"SPLAT_VERCEL_WEBHOOK_PATH": "/env/path"}):
            config = load_config(vercel_webhook_path="/programmatic/path")
            assert config.vercel_webhook_path == "/programmatic/path"

    def test_programmatic_vercel_log_ttl_overrides_env(self) -> None:
        with patch.dict(os.environ, {"SPLAT_VERCEL_LOG_TTL": "60"}):
            config = load_config(vercel_log_ttl=300)
            assert config.vercel_log_ttl == 300

    def test_toml_vercel_secret_overrides_env(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.splat]
vercel_secret = "toml-secret"
""")
        with patch.dict(os.environ, {"SPLAT_VERCEL_SECRET": "env-secret"}):
            with patch("splat.core.config._find_pyproject", return_value=pyproject):
                config = load_config()
                assert config.vercel_secret == "toml-secret"

    def test_programmatic_vercel_secret_overrides_toml(
        self, tmp_path: Path
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.splat]
vercel_secret = "toml-secret"
""")
        with patch("splat.core.config._find_pyproject", return_value=pyproject):
            config = load_config(vercel_secret="programmatic-secret")
            assert config.vercel_secret == "programmatic-secret"
