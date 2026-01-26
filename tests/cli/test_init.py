"""Tests for init wizard."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from splat.cli.init import (
    FrameworkFile,
    ProjectInfo,
    WizardState,
    analyze_framework_file,
    detect_existing_token,
    detect_framework,
    detect_github_remote,
    detect_project_info,
    detect_project_type,
    detect_test_infrastructure,
    detect_vercel_project,
    inject_middleware,
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
        config.write_text('[remote "origin"]\n    url = git@github.com:owner/repo.git')
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

    def test_project_info_has_test_infrastructure(self, tmp_path: Path) -> None:
        """Test has_test_infrastructure field."""
        info = ProjectInfo(
            project_type="python",
            framework=None,
            framework_file=None,
            github_repo=None,
            base_path=tmp_path,
            has_test_infrastructure=True,
        )
        assert info.has_test_infrastructure is True


class TestWizardState:
    """Test WizardState dataclass."""

    def test_wizard_state_defaults(self) -> None:
        state = WizardState()
        assert state.repo is None
        assert state.github_token is None
        assert state.enable_autofix is False
        assert state.claude_auth_type is None
        assert state.claude_token is None
        assert state.model is None
        assert state.middleware_injected is False
        assert state.workflow_created is False
        assert state.vercel_env_added is False
        assert state.github_secret_added is False
        assert state.config_written is False


class TestDetectTestInfrastructure:
    """Test test infrastructure detection."""

    def test_detects_tests_directory(self, tmp_path: Path) -> None:
        (tmp_path / "tests").mkdir()
        result = detect_test_infrastructure(tmp_path)
        assert result is True

    def test_detects_test_directory(self, tmp_path: Path) -> None:
        (tmp_path / "test").mkdir()
        result = detect_test_infrastructure(tmp_path)
        assert result is True

    def test_detects_pytest_in_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.pytest]\ntestpaths = ["tests"]')
        result = detect_test_infrastructure(tmp_path)
        assert result is True

    def test_detects_pytest_in_requirements(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("pytest>=7.0\n")
        result = detect_test_infrastructure(tmp_path)
        assert result is True

    def test_detects_jest_in_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"devDependencies": {"jest": "^29.0"}}')
        result = detect_test_infrastructure(tmp_path)
        assert result is True

    def test_returns_false_when_none(self, tmp_path: Path) -> None:
        result = detect_test_infrastructure(tmp_path)
        assert result is False


class TestAnalyzeFrameworkFile:
    """Test AST-based framework file analysis."""

    def test_analyzes_fastapi_file(self, tmp_path: Path) -> None:
        app_file = tmp_path / "main.py"
        app_file.write_text(
            """from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"hello": "world"}
"""
        )
        result = analyze_framework_file(app_file, "fastapi")
        assert result["app_name"] == "app"
        assert result["app_line"] == 3
        assert result["has_splat_import"] is False
        assert result["has_middleware"] is False

    def test_analyzes_flask_file(self, tmp_path: Path) -> None:
        app_file = tmp_path / "app.py"
        app_file.write_text(
            """from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "Hello"
"""
        )
        result = analyze_framework_file(app_file, "flask")
        assert result["app_name"] == "app"
        assert result["app_line"] == 3
        assert result["has_splat_import"] is False
        assert result["has_middleware"] is False

    def test_detects_existing_splat_import(self, tmp_path: Path) -> None:
        app_file = tmp_path / "main.py"
        app_file.write_text(
            """from fastapi import FastAPI
from splat.middleware.fastapi import SplatMiddleware

app = FastAPI()
"""
        )
        result = analyze_framework_file(app_file, "fastapi")
        assert result["has_splat_import"] is True

    def test_detects_existing_middleware(self, tmp_path: Path) -> None:
        app_file = tmp_path / "main.py"
        app_file.write_text(
            """from fastapi import FastAPI
from splat.middleware.fastapi import SplatMiddleware

app = FastAPI()
app.add_middleware(SplatMiddleware)
"""
        )
        result = analyze_framework_file(app_file, "fastapi")
        assert result["has_middleware"] is True

    def test_handles_syntax_error(self, tmp_path: Path) -> None:
        app_file = tmp_path / "main.py"
        app_file.write_text("this is not valid python (((")
        result = analyze_framework_file(app_file, "fastapi")
        assert "error" in result


class TestInjectMiddleware:
    """Test middleware injection."""

    def test_injects_fastapi_middleware(self, tmp_path: Path) -> None:
        app_file = tmp_path / "main.py"
        app_file.write_text(
            """from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"hello": "world"}
"""
        )
        analysis = analyze_framework_file(app_file, "fastapi")
        result = inject_middleware(app_file, "fastapi", analysis)

        assert result is True
        content = app_file.read_text()
        assert "from splat.middleware.fastapi import SplatMiddleware" in content
        assert "app.add_middleware(SplatMiddleware)" in content

    def test_injects_flask_middleware(self, tmp_path: Path) -> None:
        app_file = tmp_path / "app.py"
        app_file.write_text(
            """from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "Hello"
"""
        )
        analysis = analyze_framework_file(app_file, "flask")
        result = inject_middleware(app_file, "flask", analysis)

        assert result is True
        content = app_file.read_text()
        assert "from splat.middleware.flask import SplatFlask" in content
        assert "splat = SplatFlask()" in content
        assert "splat.init_app(app)" in content

    def test_does_not_inject_if_already_present(self, tmp_path: Path) -> None:
        app_file = tmp_path / "main.py"
        original_content = """from fastapi import FastAPI
from splat.middleware.fastapi import SplatMiddleware

app = FastAPI()
app.add_middleware(SplatMiddleware)
"""
        app_file.write_text(original_content)
        analysis = analyze_framework_file(app_file, "fastapi")
        result = inject_middleware(app_file, "fastapi", analysis)

        assert result is False
        assert app_file.read_text() == original_content


class TestRunInitWizard:
    """Test run_init_wizard function."""

    @staticmethod
    def _create_questionary_mock() -> MagicMock:
        """Create a mock for questionary that returns appropriate values."""
        mock = MagicMock()
        # Mock confirm to return True by default
        mock.confirm.return_value.ask.return_value = True
        # Mock select to return first choice
        mock.select.return_value.ask.return_value = "Skip for now"
        # Mock text to return a default value
        mock.text.return_value.ask.return_value = "owner/repo"
        # Mock password to return empty (skip)
        mock.password.return_value.ask.return_value = ""
        return mock

    def test_wizard_detects_project_info(self, tmp_path: Path) -> None:
        """Test wizard detects project info correctly."""
        # Setup Python project with Flask
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        app_file = tmp_path / "app.py"
        app_file.write_text("from flask import Flask\napp = Flask(__name__)")
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text(
            '[remote "origin"]\n    url = https://github.com/owner/repo.git'
        )

        mock_questionary = self._create_questionary_mock()

        with patch("splat.cli.init.questionary", mock_questionary):
            with patch("splat.cli.init.click.echo"):
                with patch("splat.cli.init.update_pyproject_toml"):
                    run_init_wizard(tmp_path)

        # Verify questionary was called with repo confirmation
        confirm_calls = [str(c) for c in mock_questionary.confirm.call_args_list]
        assert any("owner/repo" in str(c) for c in confirm_calls)

    def test_wizard_with_unknown_project(self, tmp_path: Path) -> None:
        """Test wizard output for unknown project type."""
        mock_questionary = self._create_questionary_mock()
        mock_questionary.confirm.return_value.ask.return_value = False

        with patch("splat.cli.init.questionary", mock_questionary):
            with patch("splat.cli.init.click.echo") as mock_echo:
                run_init_wizard(tmp_path)

        # Verify wizard completed
        calls = [str(c) for c in mock_echo.call_args_list]
        assert any("Setup Complete!" in str(c) for c in calls)

    def test_wizard_uses_cwd_when_no_path(self) -> None:
        """Test wizard defaults to current working directory."""
        mock_questionary = self._create_questionary_mock()
        mock_questionary.confirm.return_value.ask.return_value = False

        with patch("splat.cli.init.questionary", mock_questionary):
            with patch("splat.cli.init.click.echo"):
                with patch("splat.cli.init.Path.cwd") as mock_cwd:
                    mock_cwd.return_value = Path("/fake/path")
                    with patch("splat.cli.init.detect_project_info") as mock_detect:
                        with patch("splat.cli.init.update_pyproject_toml"):
                            mock_detect.return_value = ProjectInfo(
                                project_type="unknown",
                                framework=None,
                                framework_file=None,
                                github_repo=None,
                                base_path=Path("/fake/path"),
                            )
                            run_init_wizard(None)

                        mock_detect.assert_called_once_with(Path("/fake/path"))

    def test_wizard_shows_welcome_message(self, tmp_path: Path) -> None:
        """Test wizard shows welcome message."""
        mock_questionary = self._create_questionary_mock()
        mock_questionary.confirm.return_value.ask.return_value = False

        with patch("splat.cli.init.questionary", mock_questionary):
            with patch("splat.cli.init.click.echo") as mock_echo:
                run_init_wizard(tmp_path)

        calls = [str(c) for c in mock_echo.call_args_list]
        assert any("Welcome to Splat!" in str(c) for c in calls)
        assert any("Detecting project..." in str(c) for c in calls)

    def test_wizard_enables_autofix(self, tmp_path: Path) -> None:
        """Test wizard enables autofix when selected."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")

        mock_questionary = self._create_questionary_mock()
        # Enable autofix
        mock_questionary.confirm.return_value.ask.side_effect = [
            True,  # Use detected repo
            False,  # Keep existing token (none)
            True,  # Enable autofix
            True,  # Save config
        ]
        mock_questionary.select.return_value.ask.side_effect = [
            "Skip for now",  # GitHub token
            "oauth",  # Claude auth type
            "opus",  # Model selection
        ]
        mock_questionary.password.return_value.ask.return_value = "test_oauth_token"

        with patch("splat.cli.init.questionary", mock_questionary):
            with patch("splat.cli.init.click.echo"):
                with patch("splat.cli.init.update_pyproject_toml"):
                    with patch("splat.cli.init.install_workflow"):
                        with patch(
                            "splat.cli.init.prompt_github_secret_setup",
                            return_value=False,
                        ):
                            with patch(
                                "splat.cli.init.check_cli_exists",
                                return_value=False,
                            ):
                                run_init_wizard(tmp_path)


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
        (tmp_path / "tests").mkdir()

        info = detect_project_info(tmp_path)

        assert info.project_type == "python"
        assert info.framework == "flask"
        assert info.framework_file == app_file
        assert info.github_repo == "owner/repo"
        assert info.base_path == tmp_path
        assert info.is_vercel is True
        assert info.has_test_infrastructure is True

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
    def _create_questionary_mock() -> MagicMock:
        """Create a mock for questionary that returns appropriate values."""
        mock = MagicMock()
        mock.confirm.return_value.ask.return_value = False
        mock.select.return_value.ask.return_value = "Skip for now"
        mock.text.return_value.ask.return_value = "owner/repo"
        mock.password.return_value.ask.return_value = ""
        return mock

    def test_wizard_shows_vercel_detected(self, tmp_path: Path) -> None:
        """Test wizard shows Vercel project detected message."""
        (tmp_path / "vercel.json").write_text('{"version": 2}')

        mock_questionary = self._create_questionary_mock()

        with patch("splat.cli.init.questionary", mock_questionary):
            with patch("splat.cli.init.click.echo") as mock_echo:
                run_init_wizard(tmp_path)

        calls = [str(c) for c in mock_echo.call_args_list]
        assert any("Vercel project detected" in str(c) for c in calls)

    def test_wizard_does_not_show_vercel_when_not_present(self, tmp_path: Path) -> None:
        """Test wizard does not show Vercel message when not a Vercel project."""
        mock_questionary = self._create_questionary_mock()

        env_copy = os.environ.copy()
        env_copy.pop("VERCEL", None)
        with patch.dict(os.environ, env_copy, clear=True):
            with patch("splat.cli.init.questionary", mock_questionary):
                with patch("splat.cli.init.click.echo") as mock_echo:
                    run_init_wizard(tmp_path)

        calls = [str(c) for c in mock_echo.call_args_list]
        assert not any("Vercel project detected" in str(c) for c in calls)


class TestDetectExistingToken:
    """Test existing token detection."""

    def test_detects_token_from_env(self, tmp_path: Path) -> None:
        """Test detecting token from environment variable."""
        with patch.dict(os.environ, {"SPLAT_GITHUB_TOKEN": "ghp_test123"}):
            result = detect_existing_token(tmp_path)
            assert result == "ghp_test123"

    def test_detects_token_from_env_file(self, tmp_path: Path) -> None:
        """Test detecting token from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("SPLAT_GITHUB_TOKEN=ghp_fromfile123\n")

        env_copy = os.environ.copy()
        env_copy.pop("SPLAT_GITHUB_TOKEN", None)
        with patch.dict(os.environ, env_copy, clear=True):
            result = detect_existing_token(tmp_path)
            assert result == "ghp_fromfile123"

    def test_detects_token_from_env_file_with_quotes(self, tmp_path: Path) -> None:
        """Test detecting quoted token from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text('SPLAT_GITHUB_TOKEN="ghp_quoted123"\n')

        env_copy = os.environ.copy()
        env_copy.pop("SPLAT_GITHUB_TOKEN", None)
        with patch.dict(os.environ, env_copy, clear=True):
            result = detect_existing_token(tmp_path)
            assert result == "ghp_quoted123"

    def test_env_var_takes_precedence_over_file(self, tmp_path: Path) -> None:
        """Test that environment variable takes precedence over .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("SPLAT_GITHUB_TOKEN=ghp_fromfile\n")

        with patch.dict(os.environ, {"SPLAT_GITHUB_TOKEN": "ghp_fromenv"}):
            result = detect_existing_token(tmp_path)
            assert result == "ghp_fromenv"

    def test_returns_none_when_no_token(self, tmp_path: Path) -> None:
        """Test returning None when no token is found."""
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


class TestProjectInfoMultipleFrameworks:
    """Test ProjectInfo with multiple framework files."""

    def test_project_info_with_framework_files_list(self, tmp_path: Path) -> None:
        """Test ProjectInfo holds list of framework files."""
        from splat.cli.init import ProjectInfo

        files = [
            FrameworkFile(
                framework="fastapi", file_path=tmp_path / "api.py", app_name="app"
            ),
            FrameworkFile(
                framework="fastapi", file_path=tmp_path / "admin.py", app_name="admin"
            ),
        ]

        info = ProjectInfo(
            project_type="python",
            framework="fastapi",
            framework_file=tmp_path / "api.py",  # Keep for backwards compat
            framework_files=files,
            github_repo="owner/repo",
            base_path=tmp_path,
        )

        assert len(info.framework_files) == 2
        assert info.framework_files[0].app_name == "app"
        assert info.framework_files[1].app_name == "admin"

    def test_detect_project_info_finds_multiple_files(self, tmp_path: Path) -> None:
        """Test detect_project_info populates framework_files list."""
        from splat.cli.init import detect_project_info

        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        (tmp_path / "api.py").write_text("from fastapi import FastAPI\napp = FastAPI()")
        (tmp_path / "admin.py").write_text(
            "from fastapi import FastAPI\nadmin = FastAPI()"
        )

        info = detect_project_info(tmp_path)

        assert len(info.framework_files) == 2


class TestFindFrameworkFilesWithGrep:
    """Test grep-based framework file detection."""

    def test_finds_single_fastapi_file(self, tmp_path: Path) -> None:
        """Test finding a single FastAPI file."""
        from splat.cli.init import find_framework_files_with_grep

        app_file = tmp_path / "main.py"
        app_file.write_text("from fastapi import FastAPI\napp = FastAPI()")

        result = find_framework_files_with_grep(tmp_path)
        assert len(result) == 1
        assert result[0].file_path == app_file
        assert result[0].framework == "fastapi"

    def test_finds_multiple_fastapi_files(self, tmp_path: Path) -> None:
        """Test finding multiple FastAPI files."""
        from splat.cli.init import find_framework_files_with_grep

        # Create two FastAPI apps
        api_dir = tmp_path / "api"
        api_dir.mkdir()
        (api_dir / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()")
        (api_dir / "admin.py").write_text(
            "from fastapi import FastAPI\nadmin_app = FastAPI()"
        )

        result = find_framework_files_with_grep(tmp_path)
        assert len(result) == 2
        paths = {f.file_path for f in result}
        assert api_dir / "main.py" in paths
        assert api_dir / "admin.py" in paths

    def test_finds_flask_files(self, tmp_path: Path) -> None:
        """Test finding Flask files."""
        from splat.cli.init import find_framework_files_with_grep

        app_file = tmp_path / "app.py"
        app_file.write_text("from flask import Flask\napp = Flask(__name__)")

        result = find_framework_files_with_grep(tmp_path)
        assert len(result) == 1
        assert result[0].framework == "flask"

    def test_finds_mixed_frameworks(self, tmp_path: Path) -> None:
        """Test finding both FastAPI and Flask files."""
        from splat.cli.init import find_framework_files_with_grep

        (tmp_path / "api.py").write_text("from fastapi import FastAPI\napp = FastAPI()")
        (tmp_path / "web.py").write_text(
            "from flask import Flask\napp = Flask(__name__)"
        )

        result = find_framework_files_with_grep(tmp_path)
        assert len(result) == 2
        frameworks = {f.framework for f in result}
        assert frameworks == {"fastapi", "flask"}

    def test_ignores_files_without_instantiation(self, tmp_path: Path) -> None:
        """Test that files with just imports are ignored."""
        from splat.cli.init import find_framework_files_with_grep

        # File with import but no instantiation
        (tmp_path / "utils.py").write_text("from fastapi import FastAPI\n# no app here")

        result = find_framework_files_with_grep(tmp_path)
        assert len(result) == 0

    def test_returns_empty_for_no_matches(self, tmp_path: Path) -> None:
        """Test returning empty list when no framework files found."""
        from splat.cli.init import find_framework_files_with_grep

        (tmp_path / "hello.py").write_text("print('hello')")

        result = find_framework_files_with_grep(tmp_path)
        assert result == []
