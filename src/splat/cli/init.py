"""Interactive setup wizard for Splat."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
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
    is_vercel: bool = field(default=False)


def detect_project_type(base_path: Path) -> str:
    """Detect the project type."""
    python_files = ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"]
    for f in python_files:
        if (base_path / f).exists():
            return "python"
    if (base_path / "package.json").exists():
        return "node"
    return "unknown"


def detect_framework(base_path: Path) -> Tuple[str | None, Path | None]:
    """Detect the web framework in use."""
    py_files = list(base_path.glob("*.py")) + list(base_path.glob("**/*.py"))

    for py_file in py_files[:50]:
        try:
            content = py_file.read_text()
        except Exception:
            continue

        if "from flask import Flask" in content or "import flask" in content.lower():
            if "Flask(__name__)" in content or "Flask(" in content:
                return ("flask", py_file)

        if (
            "from fastapi import FastAPI" in content
            or "import fastapi" in content.lower()
        ):
            if "FastAPI()" in content or "FastAPI(" in content:
                return ("fastapi", py_file)

    for settings_file in base_path.glob("**/settings.py"):
        try:
            content = settings_file.read_text()
            if "INSTALLED_APPS" in content:
                return ("django", settings_file)
        except Exception:
            continue

    return (None, None)


def detect_github_remote(base_path: Path) -> str | None:
    """Detect GitHub repository from git remote."""
    git_config = base_path / ".git" / "config"
    if not git_config.exists():
        return None

    try:
        content = git_config.read_text()
        https_match = re.search(
            r"url\s*=\s*https://github\.com/([^/]+)/([^/\s.]+)", content
        )
        if https_match:
            owner, repo = https_match.groups()
            repo = repo.rstrip(".git")
            return f"{owner}/{repo}"

        ssh_match = re.search(
            r"url\s*=\s*git@github\.com:([^/]+)/([^/\s.]+)", content
        )
        if ssh_match:
            owner, repo = ssh_match.groups()
            repo = repo.rstrip(".git")
            return f"{owner}/{repo}"
    except Exception:
        pass

    return None


def detect_vercel_project(base_path: Path) -> bool:
    """Detect if the project is a Vercel project.

    Returns True if any of these exist:
    - vercel.json file
    - .vercel/ directory
    - VERCEL environment variable is set
    """
    if (base_path / "vercel.json").exists():
        return True
    if (base_path / ".vercel").is_dir():
        return True
    if os.environ.get("VERCEL") is not None:
        return True
    return False


def detect_project_info(base_path: Path) -> ProjectInfo:
    """Detect all project information.

    Combines all detection methods to return a populated ProjectInfo.
    """
    project_type = detect_project_type(base_path)
    framework, framework_file = detect_framework(base_path)
    github_repo = detect_github_remote(base_path)
    is_vercel = detect_vercel_project(base_path)

    return ProjectInfo(
        project_type=project_type,
        framework=framework,
        framework_file=framework_file,
        github_repo=github_repo,
        base_path=base_path,
        is_vercel=is_vercel,
    )


def run_init_wizard(base_path: Path | None = None) -> None:
    """Run the interactive setup wizard."""
    if base_path is None:
        base_path = Path.cwd()

    click.echo("\nWelcome to Splat!\n")
    click.echo("Detecting project...")

    info = detect_project_info(base_path)

    if info.project_type != "unknown":
        click.echo(f"  - {info.project_type.title()} project detected")
    else:
        click.echo("  - Could not detect project type")

    if info.framework:
        click.echo(
            f"  - {info.framework.title()} app in "
            f"{info.framework_file.name if info.framework_file else 'unknown'}"
        )
    else:
        click.echo("  - No framework detected")

    if info.github_repo:
        click.echo(f"  - GitHub remote: {info.github_repo}")
    else:
        click.echo("  - No GitHub remote detected")

    if info.is_vercel:
        click.echo("  - Vercel project detected")

    click.echo()
    click.echo("Full wizard coming soon!")
    click.echo("For now, configure manually in pyproject.toml or environment variables.")
