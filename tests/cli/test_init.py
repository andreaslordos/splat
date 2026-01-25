"""Tests for init wizard."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from splat.cli.init import (
    ProjectInfo,
    detect_framework,
    detect_github_remote,
    detect_project_type,
    run_init_wizard,
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

    def test_detects_python_by_setup_cfg(self, tmp_path: Path) -> None:
        (tmp_path / "setup.cfg").write_text("[metadata]\nname = test")
        result = detect_project_type(tmp_path)
        assert result == "python"

    def test_detects_node_by_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"name": "test"}')
        result = detect_project_type(tmp_path)
        assert result == "node"

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

    def test_detects_flask_with_import_flask(self, tmp_path: Path) -> None:
        app_file = tmp_path / "main.py"
        app_file.write_text("import flask\napp = flask.Flask(__name__)")
        result = detect_framework(tmp_path)
        assert result == ("flask", app_file)

    def test_detects_fastapi(self, tmp_path: Path) -> None:
        main_file = tmp_path / "main.py"
        main_file.write_text("from fastapi import FastAPI\napp = FastAPI()")
        result = detect_framework(tmp_path)
        assert result == ("fastapi", main_file)

    def test_detects_fastapi_with_import_fastapi(self, tmp_path: Path) -> None:
        main_file = tmp_path / "api.py"
        main_file.write_text("import fastapi\napp = fastapi.FastAPI()")
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

    def test_returns_none_for_empty_dir(self, tmp_path: Path) -> None:
        result = detect_framework(tmp_path)
        assert result == (None, None)

    def test_handles_unreadable_file(self, tmp_path: Path) -> None:
        # Create a directory that looks like a py file (will fail to read)
        fake_file = tmp_path / "fake.py"
        fake_file.mkdir()
        result = detect_framework(tmp_path)
        assert result == (None, None)


class TestDetectGithubRemote:
    """Test GitHub remote detection."""

    def test_extracts_repo_from_https(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        config = git_dir / "config"
        config.write_text(
            '[remote "origin"]\n    url = https://github.com/owner/repo.git'
        )
        result = detect_github_remote(tmp_path)
        assert result == "owner/repo"

    def test_extracts_repo_from_https_without_git_suffix(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        config = git_dir / "config"
        config.write_text('[remote "origin"]\n    url = https://github.com/owner/repo')
        result = detect_github_remote(tmp_path)
        assert result == "owner/repo"

    def test_extracts_repo_from_ssh(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        config = git_dir / "config"
        config.write_text(
            '[remote "origin"]\n    url = git@github.com:owner/repo.git'
        )
        result = detect_github_remote(tmp_path)
        assert result == "owner/repo"

    def test_extracts_repo_from_ssh_without_git_suffix(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        config = git_dir / "config"
        config.write_text('[remote "origin"]\n    url = git@github.com:owner/repo')
        result = detect_github_remote(tmp_path)
        assert result == "owner/repo"

    def test_returns_none_for_non_git(self, tmp_path: Path) -> None:
        result = detect_github_remote(tmp_path)
        assert result is None

    def test_returns_none_for_non_github_remote(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        config = git_dir / "config"
        config.write_text('[remote "origin"]\n    url = https://gitlab.com/owner/repo')
        result = detect_github_remote(tmp_path)
        assert result is None


class TestProjectInfo:
    """Test ProjectInfo dataclass."""

    def test_project_info_creation(self, tmp_path: Path) -> None:
        info = ProjectInfo(
            project_type="python",
            framework="flask",
            framework_file=tmp_path / "app.py",
            github_repo="owner/repo",
            base_path=tmp_path,
        )
        assert info.project_type == "python"
        assert info.framework == "flask"
        assert info.framework_file == tmp_path / "app.py"
        assert info.github_repo == "owner/repo"
        assert info.base_path == tmp_path

    def test_project_info_with_none_values(self, tmp_path: Path) -> None:
        info = ProjectInfo(
            project_type="unknown",
            framework=None,
            framework_file=None,
            github_repo=None,
            base_path=tmp_path,
        )
        assert info.project_type == "unknown"
        assert info.framework is None
        assert info.framework_file is None
        assert info.github_repo is None


class TestRunInitWizard:
    """Test run_init_wizard function."""

    @staticmethod
    def _get_echo_calls(mock_echo: object) -> list[str]:
        """Extract string arguments from mock echo calls, skipping empty calls."""
        # Access call_args_list dynamically since mock_echo is a MagicMock
        call_args_list = getattr(mock_echo, "call_args_list", [])
        return [call.args[0] for call in call_args_list if call.args]

    def test_wizard_with_python_flask_project(self, tmp_path: Path) -> None:
        """Test wizard output for Python Flask project."""
        # Setup Python project with Flask
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        app_file = tmp_path / "app.py"
        app_file.write_text("from flask import Flask\napp = Flask(__name__)")
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text(
            '[remote "origin"]\n    url = https://github.com/owner/repo.git'
        )

        # Capture output
        with patch("splat.cli.init.click.echo") as mock_echo:
            run_init_wizard(tmp_path)

        # Verify outputs
        calls = self._get_echo_calls(mock_echo)
        assert any("Python project detected" in call for call in calls)
        assert any("Flask app in app.py" in call for call in calls)
        assert any("GitHub remote: owner/repo" in call for call in calls)

    def test_wizard_with_unknown_project(self, tmp_path: Path) -> None:
        """Test wizard output for unknown project type."""
        with patch("splat.cli.init.click.echo") as mock_echo:
            run_init_wizard(tmp_path)

        calls = self._get_echo_calls(mock_echo)
        assert any("Could not detect project type" in call for call in calls)
        assert any("No framework detected" in call for call in calls)
        assert any("No GitHub remote detected" in call for call in calls)

    def test_wizard_uses_cwd_when_no_path(self) -> None:
        """Test wizard defaults to current working directory."""
        with patch("splat.cli.init.click.echo"):
            with patch("splat.cli.init.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path("/fake/path")
                with patch("splat.cli.init.detect_project_type") as mock_detect:
                    mock_detect.return_value = "unknown"
                    with patch("splat.cli.init.detect_framework") as mock_fw:
                        mock_fw.return_value = (None, None)
                        with patch("splat.cli.init.detect_github_remote") as mock_gh:
                            mock_gh.return_value = None
                            run_init_wizard(None)

                mock_detect.assert_called_once_with(Path("/fake/path"))

    def test_wizard_shows_welcome_message(self, tmp_path: Path) -> None:
        """Test wizard shows welcome message."""
        with patch("splat.cli.init.click.echo") as mock_echo:
            run_init_wizard(tmp_path)

        calls = self._get_echo_calls(mock_echo)
        assert any("Welcome to Splat!" in call for call in calls)
        assert any("Detecting project..." in call for call in calls)
        assert any("Full wizard coming soon!" in call for call in calls)

    def test_wizard_with_node_project(self, tmp_path: Path) -> None:
        """Test wizard output for Node.js project."""
        (tmp_path / "package.json").write_text('{"name": "test"}')

        with patch("splat.cli.init.click.echo") as mock_echo:
            run_init_wizard(tmp_path)

        calls = self._get_echo_calls(mock_echo)
        assert any("Node project detected" in call for call in calls)

    def test_wizard_with_fastapi_project(self, tmp_path: Path) -> None:
        """Test wizard output for FastAPI project."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        main_file = tmp_path / "main.py"
        main_file.write_text("from fastapi import FastAPI\napp = FastAPI()")

        with patch("splat.cli.init.click.echo") as mock_echo:
            run_init_wizard(tmp_path)

        calls = self._get_echo_calls(mock_echo)
        assert any("Fastapi app in main.py" in call for call in calls)

    def test_wizard_with_django_project(self, tmp_path: Path) -> None:
        """Test wizard output for Django project."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        settings_dir = tmp_path / "myproject"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.py"
        settings_file.write_text("INSTALLED_APPS = ['django.contrib.admin']")

        with patch("splat.cli.init.click.echo") as mock_echo:
            run_init_wizard(tmp_path)

        calls = self._get_echo_calls(mock_echo)
        assert any("Django app in settings.py" in call for call in calls)


class TestDetectFrameworkEdgeCases:
    """Test edge cases for framework detection."""

    def test_handles_unreadable_django_settings(self, tmp_path: Path) -> None:
        """Test framework detection handles unreadable Django settings file."""
        # Create a directory named settings.py (will fail to read as file)
        settings_dir = tmp_path / "myproject"
        settings_dir.mkdir()
        fake_settings = settings_dir / "settings.py"
        fake_settings.mkdir()  # Create as directory, not file

        result = detect_framework(tmp_path)
        assert result == (None, None)


class TestDetectGithubRemoteEdgeCases:
    """Test edge cases for GitHub remote detection."""

    def test_handles_unreadable_git_config(self, tmp_path: Path) -> None:
        """Test GitHub detection handles unreadable git config."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        # Create config as a directory (will fail to read)
        config_dir = git_dir / "config"
        config_dir.mkdir()

        result = detect_github_remote(tmp_path)
        assert result is None
