"""Interactive setup wizard for Splat."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Tuple

import click

# GitHub token generation URL with pre-filled scopes
GITHUB_TOKEN_URL = "https://github.com/settings/tokens/new?scopes=repo&description=Splat%20Error%20Reporter"


@dataclass
class ProjectInfo:
    """Detected project information."""

    project_type: str
    framework: str | None
    framework_file: Path | None
    github_repo: str | None
    base_path: Path
    is_vercel: bool = field(default=False)
    existing_token: str | None = field(default=None)


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
        # Match repo name including optional .git suffix
        # Using [^/\s]+ to capture everything up to whitespace
        https_match = re.search(
            r"url\s*=\s*https://github\.com/([^/]+)/([^/\s]+)", content
        )
        if https_match:
            owner, repo = https_match.groups()
            # Use removesuffix instead of rstrip to avoid stripping chars from the set
            repo = repo.removesuffix(".git")
            return f"{owner}/{repo}"

        ssh_match = re.search(
            r"url\s*=\s*git@github\.com:([^/]+)/([^/\s]+)", content
        )
        if ssh_match:
            owner, repo = ssh_match.groups()
            repo = repo.removesuffix(".git")
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


def detect_existing_token(base_path: Path) -> str | None:
    """Check if a GitHub token already exists.

    Checks in order:
    1. SPLAT_GITHUB_TOKEN environment variable
    2. .env file in project root
    """
    # Check environment variable
    token = os.environ.get("SPLAT_GITHUB_TOKEN")
    if token:
        return token

    # Check .env file
    env_file = base_path / ".env"
    if env_file.exists():
        try:
            content = env_file.read_text()
            match = re.search(r"SPLAT_GITHUB_TOKEN\s*=\s*['\"]?([^'\"\s\n]+)", content)
            if match:
                return match.group(1)
        except Exception:
            pass

    return None


def validate_github_token(token: str) -> bool:
    """Validate that a token looks like a GitHub token.

    GitHub tokens start with:
    - ghp_ (classic personal access token)
    - github_pat_ (fine-grained personal access token)
    - gho_ (OAuth token)
    - ghu_ (user-to-server token)
    - ghs_ (server-to-server token)
    - ghr_ (refresh token)
    """
    valid_prefixes = ("ghp_", "github_pat_", "gho_", "ghu_", "ghs_", "ghr_")
    return token.startswith(valid_prefixes) and len(token) > 10


def save_token_to_env(base_path: Path, token: str) -> None:
    """Save the GitHub token to .env file."""
    env_file = base_path / ".env"

    if env_file.exists():
        content = env_file.read_text()
        # Check if token already exists and replace it
        if "SPLAT_GITHUB_TOKEN" in content:
            content = re.sub(
                r"SPLAT_GITHUB_TOKEN\s*=\s*[^\n]*",
                f"SPLAT_GITHUB_TOKEN={token}",
                content,
            )
        else:
            # Append to file
            if not content.endswith("\n"):
                content += "\n"
            content += f"SPLAT_GITHUB_TOKEN={token}\n"
        env_file.write_text(content)
    else:
        env_file.write_text(f"SPLAT_GITHUB_TOKEN={token}\n")


def ensure_env_in_gitignore(base_path: Path) -> bool:
    """Ensure .env is in .gitignore. Returns True if it was added."""
    gitignore = base_path / ".gitignore"

    if not gitignore.exists():
        gitignore.write_text(".env\n")
        return True

    content = gitignore.read_text()
    lines = content.splitlines()

    # Check if .env is already ignored (accounting for comments and patterns)
    for line in lines:
        stripped = line.strip()
        if stripped == ".env" or stripped == "*.env" or stripped == ".env*":
            return False

    # Add .env to gitignore
    if not content.endswith("\n"):
        content += "\n"
    content += ".env\n"
    gitignore.write_text(content)
    return True


def detect_project_info(base_path: Path) -> ProjectInfo:
    """Detect all project information.

    Combines all detection methods to return a populated ProjectInfo.
    """
    project_type = detect_project_type(base_path)
    framework, framework_file = detect_framework(base_path)
    github_repo = detect_github_remote(base_path)
    is_vercel = detect_vercel_project(base_path)
    existing_token = detect_existing_token(base_path)

    return ProjectInfo(
        project_type=project_type,
        framework=framework,
        framework_file=framework_file,
        github_repo=github_repo,
        base_path=base_path,
        is_vercel=is_vercel,
        existing_token=existing_token,
    )


def update_pyproject_toml(base_path: Path, config: dict[str, Any]) -> None:
    """Update pyproject.toml with splat configuration."""
    pyproject_path = base_path / "pyproject.toml"
    
    # Prepare the splat section
    lines = ["\n[tool.splat]\n"]
    for key, value in config.items():
        if isinstance(value, str):
            lines.append(f'{key} = "{value}"\n')
        elif isinstance(value, list):
            formatted_list = ", ".join(f'"{v}"' for v in value)
            lines.append(f"{key} = [{formatted_list}]\n")
        else:
            lines.append(f"{key} = {str(value).lower()}\n")

    new_section = "".join(lines)

    if not pyproject_path.exists():
        pyproject_path.write_text(new_section)
        return

    content = pyproject_path.read_text()
    
    # Check if [tool.splat] already exists
    if "[tool.splat]" in content:
        # Simple regex-less replacement: find start of section and next section or end
        start_idx = content.find("[tool.splat]")
        next_section_idx = content.find("\n[", start_idx + 1)
        
        if next_section_idx == -1:
            new_content = content[:start_idx].rstrip() + "\n" + new_section
        else:
            new_content = content[:start_idx] + new_section + content[next_section_idx:]
    else:
        new_content = content.rstrip() + "\n" + new_section
    
    pyproject_path.write_text(new_content)


def _prompt_for_token(base_path: Path, info: ProjectInfo) -> str | None:
    """Handle GitHub token setup interactively.

    Returns the token if configured, None if skipped.
    """
    click.echo("\n" + "-" * 40)
    click.echo("GitHub Token Setup")
    click.echo("-" * 40)
    click.echo("Splat needs a GitHub token with 'repo' scope to create issues.")

    # Check if token already exists
    if info.existing_token:
        masked = info.existing_token[:7] + "..." + info.existing_token[-4:]
        click.echo(f"\nExisting token found: {masked}")
        if click.confirm("Keep using this token?", default=True):
            return info.existing_token

    # Offer options
    click.echo("\nHow would you like to set up your token?")
    click.echo("  [1] Open GitHub to generate a new token")
    click.echo("  [2] Paste an existing token")
    click.echo("  [3] Skip for now (add manually later)")

    choice = click.prompt("Choose an option", type=click.Choice(["1", "2", "3"]), default="1")

    if choice == "3":
        click.echo("\nYou can add the token later by:")
        click.echo("  - Setting SPLAT_GITHUB_TOKEN environment variable")
        click.echo("  - Adding SPLAT_GITHUB_TOKEN=your_token to .env file")
        return None

    if choice == "1":
        click.echo(f"\nOpening: {GITHUB_TOKEN_URL}")
        click.launch(GITHUB_TOKEN_URL)
        click.echo("\nOnce you've created the token, paste it below.")

    # Get token from user
    while True:
        token = click.prompt("Paste your GitHub token", hide_input=True, default="", show_default=False)

        if not token:
            if click.confirm("Skip token setup for now?", default=False):
                return None
            continue

        if not validate_github_token(token):
            click.echo("That doesn't look like a valid GitHub token.")
            click.echo("Tokens usually start with 'ghp_' or 'github_pat_'")
            if not click.confirm("Try again?", default=True):
                return None
            continue

        break

    # Save to .env
    if click.confirm("Save token to .env file?", default=True):
        save_token_to_env(base_path, token)
        click.echo("Token saved to .env")

        # Ensure .env is gitignored
        if ensure_env_in_gitignore(base_path):
            click.echo("Added .env to .gitignore")

    return token


def run_init_wizard(base_path: Path | None = None) -> None:
    """Run the interactive setup wizard."""
    if base_path is None:
        base_path = Path.cwd()

    click.echo("\n" + "=" * 40)
    click.echo("Welcome to Splat!")
    click.echo("=" * 40)

    # 1. Detect project info and show summary
    click.echo("\nDetecting project...")
    info = detect_project_info(base_path)

    click.echo("\nProject detected:")
    click.echo(f"  - Type: {info.project_type}")
    if info.framework:
        file_name = info.framework_file.name if info.framework_file else "unknown"
        click.echo(f"  - Framework: {info.framework.title()} (in {file_name})")
    if info.github_repo:
        click.echo(f"  - GitHub: {info.github_repo}")
    if info.is_vercel:
        click.echo("  - Vercel project detected")
    if info.existing_token:
        click.echo("  - GitHub token: configured")

    # 2. Confirm repository
    click.echo("\n" + "-" * 40)
    click.echo("Repository Configuration")
    click.echo("-" * 40)

    repo = info.github_repo
    if repo:
        if not click.confirm(f"Use {repo} as your Splat repository?", default=True):
            repo = click.prompt("Enter GitHub repository (owner/repo)")
    else:
        repo = click.prompt("Enter GitHub repository (owner/repo)")

    # 3. GitHub token setup
    token = _prompt_for_token(base_path, info)

    # 4. Features configuration
    click.echo("\n" + "-" * 40)
    click.echo("Features")
    click.echo("-" * 40)

    labels = ["bug", "splat"]
    if click.confirm("Enable Claude Code auto-fix?", default=True):
        labels.append("auto-fix")
        install_autofix = True
    else:
        install_autofix = False

    # 5. Write configuration
    config = {
        "repo": repo,
        "labels": labels,
    }

    click.echo("\n" + "-" * 40)
    click.echo("Save Configuration")
    click.echo("-" * 40)

    if click.confirm("Write configuration to pyproject.toml?", default=True):
        update_pyproject_toml(base_path, config)
        click.echo("Updated pyproject.toml")

    # 6. Install autofix workflow if requested
    if install_autofix:
        from splat.cli.autofix import install_autofix_workflow

        install_autofix_workflow(base_path)

    # 7. Summary
    click.echo("\n" + "=" * 40)
    click.echo("Setup Complete!")
    click.echo("=" * 40)

    click.echo("\nConfiguration summary:")
    click.echo(f"  - Repository: {repo}")
    click.echo(f"  - Labels: {', '.join(labels)}")
    click.echo(f"  - Token: {'configured' if token else 'not configured'}")
    click.echo(f"  - Auto-fix: {'enabled' if install_autofix else 'disabled'}")

    # 8. Vercel reminder
    if info.is_vercel and token:
        click.echo("\n" + "-" * 40)
        click.echo("Vercel Setup")
        click.echo("-" * 40)
        click.echo("Don't forget to add SPLAT_GITHUB_TOKEN to your Vercel environment:")
        click.echo("  vercel env add SPLAT_GITHUB_TOKEN")
        click.echo("Or add it in the Vercel dashboard under Project Settings > Environment Variables")

    # 9. Next steps based on framework
    click.echo("\n" + "-" * 40)
    click.echo("Next Steps")
    click.echo("-" * 40)

    if info.framework == "flask":
        click.echo("Add Splat middleware to your Flask app:\n")
        click.echo("  from splat.middleware.flask import SplatFlask")
        click.echo("  ")
        click.echo("  splat = SplatFlask()")
        click.echo("  splat.init_app(app)")
    elif info.framework == "fastapi":
        click.echo("Add Splat middleware to your FastAPI app:\n")
        click.echo("  from splat.middleware.fastapi import SplatMiddleware")
        click.echo("  ")
        click.echo("  app.add_middleware(SplatMiddleware)")
    else:
        click.echo("To report errors manually:\n")
        click.echo("  from splat import Splat")
        click.echo("  ")
        click.echo("  splat = Splat()")
        click.echo("  try:")
        click.echo("      ...")
        click.echo("  except Exception as e:")
        click.echo("      await splat.report(e)")

    click.echo("\nDocumentation: https://github.com/andreaslordos/splat")
