"""Tests for auto-fix workflow installer."""

from pathlib import Path

import pytest

from splat.cli.autofix import install_autofix_workflow, get_workflow_template


class TestGetWorkflowTemplate:
    """Test workflow template loading."""

    def test_template_is_valid_yaml(self) -> None:
        import yaml
        template = get_workflow_template()
        parsed = yaml.safe_load(template)
        assert "name" in parsed
        assert parsed["name"] == "Splat Auto-Fix"

    def test_template_has_issue_trigger(self) -> None:
        template = get_workflow_template()
        assert "issues:" in template
        assert "labeled" in template

    def test_template_has_claude_action(self) -> None:
        template = get_workflow_template()
        assert "anthropics/claude-code-action" in template


class TestInstallAutofix:
    """Test workflow installation."""

    def test_creates_workflow_file(self, tmp_path: Path) -> None:
        install_autofix_workflow(base_path=tmp_path)
        workflow_file = tmp_path / ".github" / "workflows" / "splat-autofix.yml"
        assert workflow_file.exists()

    def test_creates_github_directory_if_missing(self, tmp_path: Path) -> None:
        install_autofix_workflow(base_path=tmp_path)
        assert (tmp_path / ".github" / "workflows").is_dir()

    def test_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        existing = workflows_dir / "splat-autofix.yml"
        existing.write_text("existing content")

        install_autofix_workflow(base_path=tmp_path, force=False)
        assert existing.read_text() == "existing content"
