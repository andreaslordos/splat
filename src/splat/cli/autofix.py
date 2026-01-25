"""Auto-fix workflow installer."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import click


def get_workflow_template() -> str:
    """Load the auto-fix workflow template."""
    try:
        if hasattr(resources, "files"):
            template_path = resources.files("splat.templates").joinpath(
                "splat-autofix.yml"
            )
            return template_path.read_text()
        else:
            with resources.open_text("splat.templates", "splat-autofix.yml") as f:
                return f.read()
    except (FileNotFoundError, TypeError):
        package_dir = Path(__file__).parent.parent
        template_file = package_dir / "templates" / "splat-autofix.yml"
        return template_file.read_text()


def install_autofix_workflow(
    base_path: Path | None = None,
    force: bool = False,
) -> Path:
    """Install the auto-fix GitHub Action workflow."""
    if base_path is None:
        base_path = Path.cwd()

    workflows_dir = base_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    workflow_file = workflows_dir / "splat-autofix.yml"

    if workflow_file.exists() and not force:
        click.echo(f"Workflow already exists: {workflow_file}")
        click.echo("Use --force to overwrite.")
        return workflow_file

    template = get_workflow_template()
    workflow_file.write_text(template)

    click.echo(f"Created {workflow_file}")
    click.echo("\nTo activate auto-fix:")
    click.echo("1. Add ANTHROPIC_API_KEY to your repository secrets:")
    click.echo("   https://github.com/YOUR_ORG/YOUR_REPO/settings/secrets/actions/new")
    click.echo("2. Commit and push:")
    click.echo("   git add . && git commit -m 'Add auto-fix workflow' && git push")
    click.echo("\nThen label any issue with 'auto-fix' or mention @claude in comments.")
    click.echo(
        "\nTip: Run 'splat init' for a full interactive setup with more options."
    )

    return workflow_file
