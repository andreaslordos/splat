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
