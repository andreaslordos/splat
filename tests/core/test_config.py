"""Tests for configuration loading."""

import os
from pathlib import Path
from unittest.mock import patch

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
        with patch("splat.core.config._find_pyproject", return_value=None):
            with patch.dict(os.environ, {"SPLAT_GITHUB_REPO": "owner/repo"}):
                config = load_config()
                assert config.repo == "owner/repo"

    def test_load_config_reads_token_from_env(self) -> None:
        with patch("splat.core.config._find_pyproject", return_value=None):
            with patch.dict(os.environ, {"SPLAT_GITHUB_TOKEN": "ghp_test123"}):
                config = load_config()
                assert config.token == "ghp_test123"

    def test_load_config_reads_enabled_from_env(self) -> None:
        with patch("splat.core.config._find_pyproject", return_value=None):
            with patch.dict(os.environ, {"SPLAT_ENABLED": "false"}):
                config = load_config()
                assert config.enabled is False

    def test_load_config_reads_log_buffer_size_from_env(self) -> None:
        with patch("splat.core.config._find_pyproject", return_value=None):
            with patch.dict(os.environ, {"SPLAT_LOG_BUFFER_SIZE": "500"}):
                config = load_config()
                assert config.log_buffer_size == 500

    def test_load_config_reads_labels_from_env(self) -> None:
        with patch("splat.core.config._find_pyproject", return_value=None):
            with patch.dict(os.environ, {"SPLAT_LABELS": "bug,splat,auto-fix"}):
                config = load_config()
                assert config.labels == ["bug", "splat", "auto-fix"]


class TestLoadConfigFromToml:
    """Test loading config from pyproject.toml."""

    def test_load_config_reads_from_pyproject_toml(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.splat]
repo = "toml/repo"
labels = ["custom", "labels"]
log_buffer_size = 300
"""
        )
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
        pyproject.write_text(
            """
[tool.splat]
repo = "toml/repo"
"""
        )
        with patch.dict(os.environ, {"SPLAT_GITHUB_REPO": "env/repo"}):
            with patch("splat.core.config._find_pyproject", return_value=pyproject):
                config = load_config()
                assert config.repo == "toml/repo"

    def test_programmatic_overrides_toml(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.splat]
repo = "toml/repo"
"""
        )
        with patch("splat.core.config._find_pyproject", return_value=pyproject):
            config = load_config(repo="programmatic/repo")
            assert config.repo == "programmatic/repo"


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
            with patch.dict(
                os.environ,
                {"SPLAT_GITHUB_API_URL": "https://github.example.com/api/v3"},
            ):
                config = load_config()
                assert config.github_api_url == "https://github.example.com/api/v3"
