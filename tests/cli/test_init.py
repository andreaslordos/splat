"""Tests for init wizard."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from splat.cli.init import (
    ProjectInfo,
    detect_existing_token,
    detect_framework,
    detect_github_remote,
    detect_project_info,
    detect_project_type,
    detect_vercel_project,
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

    def test_project_info_is_vercel_default_false(self, tmp_path: Path) -> None:
        """Test that is_vercel defaults to False."""
        info = ProjectInfo(
            project_type="python",
            framework=None,
            framework_file=None,
            github_repo=None,
            base_path=tmp_path,
        )
        assert info.is_vercel is False

    def test_project_info_is_vercel_can_be_set_true(self, tmp_path: Path) -> None:
        """Test that is_vercel can be set to True."""
        info = ProjectInfo(
            project_type="python",
            framework=None,
            framework_file=None,
            github_repo=None,
            base_path=tmp_path,
            is_vercel=True,
        )
        assert info.is_vercel is True


class TestRunInitWizard:
    """Test run_init_wizard function."""

    @staticmethod
    def _get_echo_calls(mock_echo: object) -> list[str]:
        """Extract string arguments from mock echo calls, skipping empty calls."""
        # Access call_args_list dynamically since mock_echo is a MagicMock
        call_args_list = getattr(mock_echo, "call_args_list", [])
        return [call.args[0] for call in call_args_list if call.args]

    @staticmethod
    def _mock_prompt_side_effect(prompt_text: str, **kwargs) -> str:
        """Handle different prompt calls in the wizard."""
        if "Choose an option" in prompt_text:
            return "3"  # Skip token setup
        if "owner/repo" in prompt_text:
            return "owner/repo"
        if "token" in prompt_text.lower():
            return ""  # Empty token
        return "default"

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
            with patch("splat.cli.init.click.prompt", side_effect=self._mock_prompt_side_effect):
                with patch("splat.cli.init.click.confirm", return_value=True):
                    with patch("splat.cli.init.update_pyproject_toml"):
                        with patch("splat.cli.autofix.install_autofix_workflow"):
                            run_init_wizard(tmp_path)

        # Verify outputs
        calls = self._get_echo_calls(mock_echo)
        assert any("Flask" in call and "app.py" in call for call in calls)
        assert any("owner/repo" in call for call in calls)
        assert any("Setup Complete!" in call for call in calls)

    def test_wizard_with_unknown_project(self, tmp_path: Path) -> None:
        """Test wizard output for unknown project type."""
        with patch("splat.cli.init.click.echo") as mock_echo:
            with patch("splat.cli.init.click.prompt", side_effect=self._mock_prompt_side_effect):
                with patch("splat.cli.init.click.confirm", return_value=True):
                    with patch("splat.cli.init.update_pyproject_toml"):
                        with patch("splat.cli.autofix.install_autofix_workflow"):
                            run_init_wizard(tmp_path)

        calls = self._get_echo_calls(mock_echo)
        # Verify wizard completed - shows manual error reporting instructions
        assert any("report errors manually" in call for call in calls)

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
                            with patch("splat.cli.init.detect_existing_token") as mock_token:
                                mock_token.return_value = None
                                with patch("splat.cli.init.click.prompt", side_effect=self._mock_prompt_side_effect):
                                    with patch("splat.cli.init.click.confirm", return_value=False):
                                        run_init_wizard(None)

                mock_detect.assert_called_once_with(Path("/fake/path"))

    def test_wizard_shows_welcome_message(self, tmp_path: Path) -> None:
        """Test wizard shows welcome message."""
        with patch("splat.cli.init.click.echo") as mock_echo:
            with patch("splat.cli.init.click.prompt", side_effect=self._mock_prompt_side_effect):
                with patch("splat.cli.init.click.confirm", return_value=False):
                    run_init_wizard(tmp_path)

        calls = self._get_echo_calls(mock_echo)
        assert any("Welcome to Splat!" in call for call in calls)
        assert any("Detecting project..." in call for call in calls)

    def test_wizard_with_node_project(self, tmp_path: Path) -> None:
        """Test wizard output for Node.js project."""
        (tmp_path / "package.json").write_text('{"name": "test"}')

        with patch("splat.cli.init.click.echo") as mock_echo:
            with patch("splat.cli.init.click.prompt", side_effect=self._mock_prompt_side_effect):
                with patch("splat.cli.init.click.confirm", return_value=False):
                    run_init_wizard(tmp_path)

        calls = self._get_echo_calls(mock_echo)
        # Verify node project type detected
        assert any("node" in call for call in calls)

    def test_wizard_with_fastapi_project(self, tmp_path: Path) -> None:
        """Test wizard output for FastAPI project."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        main_file = tmp_path / "main.py"
        main_file.write_text("from fastapi import FastAPI\napp = FastAPI()")

        with patch("splat.cli.init.click.echo") as mock_echo:
            with patch("splat.cli.init.click.confirm", return_value=True):
                with patch("splat.cli.init.click.prompt", side_effect=self._mock_prompt_side_effect):
                    with patch("splat.cli.init.update_pyproject_toml"):
                        with patch("splat.cli.autofix.install_autofix_workflow"):
                            run_init_wizard(tmp_path)

        calls = self._get_echo_calls(mock_echo)
        assert any("Fastapi" in call and "main.py" in call for call in calls)

    def test_wizard_with_django_project(self, tmp_path: Path) -> None:
        """Test wizard output for Django project."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        settings_dir = tmp_path / "myproject"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.py"
        settings_file.write_text("INSTALLED_APPS = ['django.contrib.admin']")

        with patch("splat.cli.init.click.echo") as mock_echo:
            with patch("splat.cli.init.click.confirm", return_value=True):
                with patch("splat.cli.init.click.prompt", side_effect=self._mock_prompt_side_effect):
                    with patch("splat.cli.init.update_pyproject_toml"):
                        with patch("splat.cli.autofix.install_autofix_workflow"):
                            run_init_wizard(tmp_path)

        calls = self._get_echo_calls(mock_echo)
        # It'll show Django app detected
        assert any("Django" in call and "settings.py" in call for call in calls)


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


class TestDetectVercelProject:
    """Test Vercel project detection."""

    def test_detects_vercel_json(self, tmp_path: Path) -> None:
        """Test detect_vercel_project returns True for vercel.json."""
        (tmp_path / "vercel.json").write_text('{"version": 2}')
        result = detect_vercel_project(tmp_path)
        assert result is True

    def test_detects_vercel_directory(self, tmp_path: Path) -> None:
        """Test detect_vercel_project returns True for .vercel directory."""
        (tmp_path / ".vercel").mkdir()
        result = detect_vercel_project(tmp_path)
        assert result is True

    def test_detects_vercel_env_var(self, tmp_path: Path) -> None:
        """Test detect_vercel_project returns True for VERCEL env var."""
        with patch.dict(os.environ, {"VERCEL": "1"}):
            result = detect_vercel_project(tmp_path)
        assert result is True

    def test_returns_false_when_none_present(self, tmp_path: Path) -> None:
        """Test detect_vercel_project returns False when no Vercel indicators."""
        # Ensure VERCEL env var is not set
        with patch.dict(os.environ, {}, clear=True):
            # Remove VERCEL if it exists
            env_copy = os.environ.copy()
            env_copy.pop("VERCEL", None)
            with patch.dict(os.environ, env_copy, clear=True):
                result = detect_vercel_project(tmp_path)
        assert result is False

    def test_returns_true_with_empty_vercel_json(self, tmp_path: Path) -> None:
        """Test detect_vercel_project returns True even if vercel.json is empty."""
        (tmp_path / "vercel.json").write_text("")
        result = detect_vercel_project(tmp_path)
        assert result is True

    def test_detects_vercel_env_var_any_value(self, tmp_path: Path) -> None:
        """Test detect_vercel_project returns True for any VERCEL env var value."""
        with patch.dict(os.environ, {"VERCEL": "true"}):
            result = detect_vercel_project(tmp_path)
        assert result is True


class TestDetectProjectInfo:
    """Test detect_project_info function."""

    def test_combines_all_detection(self, tmp_path: Path) -> None:
        """Test detect_project_info combines all detection methods."""
        # Setup Python project with Flask, GitHub, and Vercel
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        app_file = tmp_path / "app.py"
        app_file.write_text("from flask import Flask\napp = Flask(__name__)")
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text(
            '[remote "origin"]\n    url = https://github.com/owner/repo.git'
        )
        (tmp_path / "vercel.json").write_text('{"version": 2}')

        info = detect_project_info(tmp_path)

        assert info.project_type == "python"
        assert info.framework == "flask"
        assert info.framework_file == app_file
        assert info.github_repo == "owner/repo"
        assert info.base_path == tmp_path
        assert info.is_vercel is True

    def test_returns_project_info_without_vercel(self, tmp_path: Path) -> None:
        """Test detect_project_info when Vercel is not present."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")

        # Ensure VERCEL env var is not set
        env_copy = os.environ.copy()
        env_copy.pop("VERCEL", None)
        with patch.dict(os.environ, env_copy, clear=True):
            info = detect_project_info(tmp_path)

        assert info.project_type == "python"
        assert info.is_vercel is False

    def test_returns_project_info_with_vercel_env_only(self, tmp_path: Path) -> None:
        """Test detect_project_info detects Vercel from env var only."""
        with patch.dict(os.environ, {"VERCEL": "1"}):
            info = detect_project_info(tmp_path)

        assert info.is_vercel is True

    def test_returns_unknown_project_type(self, tmp_path: Path) -> None:
        """Test detect_project_info with unknown project type."""
        env_copy = os.environ.copy()
        env_copy.pop("VERCEL", None)
        with patch.dict(os.environ, env_copy, clear=True):
            info = detect_project_info(tmp_path)

        assert info.project_type == "unknown"
        assert info.framework is None
        assert info.framework_file is None
        assert info.github_repo is None
        assert info.is_vercel is False


class TestRunInitWizardVercel:
    """Test run_init_wizard Vercel-related output."""

    @staticmethod
    def _get_echo_calls(mock_echo: object) -> list[str]:
        """Extract string arguments from mock echo calls, skipping empty calls."""
        call_args_list = getattr(mock_echo, "call_args_list", [])
        return [call.args[0] for call in call_args_list if call.args]

    @staticmethod
    def _mock_prompt_side_effect(prompt_text: str, **kwargs) -> str:
        """Handle different prompt calls in the wizard."""
        if "Choose an option" in prompt_text:
            return "3"  # Skip token setup
        if "owner/repo" in prompt_text:
            return "owner/repo"
        if "token" in prompt_text.lower():
            return ""
        return "default"

    def test_wizard_shows_vercel_detected(self, tmp_path: Path) -> None:
        """Test wizard shows Vercel project detected message."""
        (tmp_path / "vercel.json").write_text('{"version": 2}')

        with patch("splat.cli.init.click.echo") as mock_echo:
            with patch("splat.cli.init.click.prompt", side_effect=self._mock_prompt_side_effect):
                with patch("splat.cli.init.click.confirm", return_value=False):
                    run_init_wizard(tmp_path)

        calls = self._get_echo_calls(mock_echo)
        assert any("Vercel project detected" in call for call in calls)

    def test_wizard_does_not_show_vercel_when_not_present(self, tmp_path: Path) -> None:
        """Test wizard does not show Vercel message when not a Vercel project."""
        env_copy = os.environ.copy()
        env_copy.pop("VERCEL", None)
        with patch.dict(os.environ, env_copy, clear=True):
            with patch("splat.cli.init.click.echo") as mock_echo:
                with patch("splat.cli.init.click.prompt", side_effect=self._mock_prompt_side_effect):
                    with patch("splat.cli.init.click.confirm", return_value=False):
                        run_init_wizard(tmp_path)

        calls = self._get_echo_calls(mock_echo)
        assert not any("Vercel project detected" in call for call in calls)


class TestDetectExistingToken:
    """Test existing token detection."""

    def test_detects_token_from_env(self, tmp_path: Path) -> None:
        """Test detecting token from environment variable."""
        from splat.cli.init import detect_existing_token

        with patch.dict(os.environ, {"SPLAT_GITHUB_TOKEN": "ghp_test123"}):
            result = detect_existing_token(tmp_path)
            assert result == "ghp_test123"

    def test_detects_token_from_env_file(self, tmp_path: Path) -> None:
        """Test detecting token from .env file."""
        from splat.cli.init import detect_existing_token

        env_file = tmp_path / ".env"
        env_file.write_text("SPLAT_GITHUB_TOKEN=ghp_fromfile123\n")

        env_copy = os.environ.copy()
        env_copy.pop("SPLAT_GITHUB_TOKEN", None)
        with patch.dict(os.environ, env_copy, clear=True):
            result = detect_existing_token(tmp_path)
            assert result == "ghp_fromfile123"

    def test_detects_token_from_env_file_with_quotes(self, tmp_path: Path) -> None:
        """Test detecting quoted token from .env file."""
        from splat.cli.init import detect_existing_token

        env_file = tmp_path / ".env"
        env_file.write_text('SPLAT_GITHUB_TOKEN="ghp_quoted123"\n')

        env_copy = os.environ.copy()
        env_copy.pop("SPLAT_GITHUB_TOKEN", None)
        with patch.dict(os.environ, env_copy, clear=True):
            result = detect_existing_token(tmp_path)
            assert result == "ghp_quoted123"

    def test_env_var_takes_precedence_over_file(self, tmp_path: Path) -> None:
        """Test that environment variable takes precedence over .env file."""
        from splat.cli.init import detect_existing_token

        env_file = tmp_path / ".env"
        env_file.write_text("SPLAT_GITHUB_TOKEN=ghp_fromfile\n")

        with patch.dict(os.environ, {"SPLAT_GITHUB_TOKEN": "ghp_fromenv"}):
            result = detect_existing_token(tmp_path)
            assert result == "ghp_fromenv"

    def test_returns_none_when_no_token(self, tmp_path: Path) -> None:
        """Test returning None when no token is found."""
        from splat.cli.init import detect_existing_token

        env_copy = os.environ.copy()
        env_copy.pop("SPLAT_GITHUB_TOKEN", None)
        with patch.dict(os.environ, env_copy, clear=True):
            result = detect_existing_token(tmp_path)
            assert result is None


class TestValidateGithubToken:
    """Test GitHub token validation."""

    def test_validates_classic_token(self) -> None:
        """Test validating classic personal access token."""
        from splat.cli.init import validate_github_token

        assert validate_github_token("ghp_abcdef123456") is True

    def test_validates_fine_grained_token(self) -> None:
        """Test validating fine-grained personal access token."""
        from splat.cli.init import validate_github_token

        assert validate_github_token("github_pat_abcdef123456") is True

    def test_validates_oauth_token(self) -> None:
        """Test validating OAuth token."""
        from splat.cli.init import validate_github_token

        assert validate_github_token("gho_abcdef123456") is True

    def test_rejects_invalid_prefix(self) -> None:
        """Test rejecting token with invalid prefix."""
        from splat.cli.init import validate_github_token

        assert validate_github_token("invalid_token123") is False

    def test_rejects_short_token(self) -> None:
        """Test rejecting too short token."""
        from splat.cli.init import validate_github_token

        assert validate_github_token("ghp_abc") is False


class TestSaveTokenToEnv:
    """Test saving token to .env file."""

    def test_creates_env_file_if_not_exists(self, tmp_path: Path) -> None:
        """Test creating .env file if it doesn't exist."""
        from splat.cli.init import save_token_to_env

        save_token_to_env(tmp_path, "ghp_newtoken123")

        env_file = tmp_path / ".env"
        assert env_file.exists()
        assert "SPLAT_GITHUB_TOKEN=ghp_newtoken123" in env_file.read_text()

    def test_appends_to_existing_env_file(self, tmp_path: Path) -> None:
        """Test appending to existing .env file."""
        from splat.cli.init import save_token_to_env

        env_file = tmp_path / ".env"
        env_file.write_text("OTHER_VAR=value\n")

        save_token_to_env(tmp_path, "ghp_newtoken123")

        content = env_file.read_text()
        assert "OTHER_VAR=value" in content
        assert "SPLAT_GITHUB_TOKEN=ghp_newtoken123" in content

    def test_replaces_existing_token(self, tmp_path: Path) -> None:
        """Test replacing existing token in .env file."""
        from splat.cli.init import save_token_to_env

        env_file = tmp_path / ".env"
        env_file.write_text("SPLAT_GITHUB_TOKEN=ghp_oldtoken\nOTHER=value\n")

        save_token_to_env(tmp_path, "ghp_newtoken123")

        content = env_file.read_text()
        assert "ghp_oldtoken" not in content
        assert "SPLAT_GITHUB_TOKEN=ghp_newtoken123" in content
        assert "OTHER=value" in content


class TestEnsureEnvInGitignore:
    """Test ensuring .env is in .gitignore."""

    def test_creates_gitignore_if_not_exists(self, tmp_path: Path) -> None:
        """Test creating .gitignore if it doesn't exist."""
        from splat.cli.init import ensure_env_in_gitignore

        result = ensure_env_in_gitignore(tmp_path)

        assert result is True
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        assert ".env" in gitignore.read_text()

    def test_adds_env_to_existing_gitignore(self, tmp_path: Path) -> None:
        """Test adding .env to existing .gitignore."""
        from splat.cli.init import ensure_env_in_gitignore

        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n")

        result = ensure_env_in_gitignore(tmp_path)

        assert result is True
        content = gitignore.read_text()
        assert ".env" in content
        assert "*.pyc" in content

    def test_does_not_duplicate_env(self, tmp_path: Path) -> None:
        """Test not adding .env if already in .gitignore."""
        from splat.cli.init import ensure_env_in_gitignore

        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n.env\n")

        result = ensure_env_in_gitignore(tmp_path)

        assert result is False
        content = gitignore.read_text()
        assert content.count(".env") == 1

    def test_recognizes_env_patterns(self, tmp_path: Path) -> None:
        """Test recognizing .env patterns like *.env."""
        from splat.cli.init import ensure_env_in_gitignore

        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.env\n")

        result = ensure_env_in_gitignore(tmp_path)

        assert result is False
