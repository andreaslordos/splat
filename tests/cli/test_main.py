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
        assert "init" in result.output.lower() or "wizard" in result.output.lower()

    def test_cli_has_install_autofix_command(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["install-autofix", "--help"])
        assert result.exit_code == 0

    def test_cli_help_shows_description(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "splat" in result.output.lower()

    def test_init_command_runs(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0
        assert "wizard" in result.output.lower() or "init" in result.output.lower()

    def test_install_autofix_command_runs(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["install-autofix"])
        assert result.exit_code == 0
        assert "autofix" in result.output.lower()
