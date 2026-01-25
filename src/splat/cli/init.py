"""Interactive setup wizard for Splat."""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Tuple

import click
import questionary
from questionary import Style

# Custom style for questionary prompts
CUSTOM_STYLE = Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "bold"),
        ("answer", "fg:cyan"),
        ("pointer", "fg:magenta bold"),
        ("highlighted", "fg:magenta bold"),
        ("selected", "fg:green"),
        ("separator", "fg:gray"),
        ("instruction", "fg:gray"),
    ]
)


class UserCancelledError(Exception):
    """Raised when user cancels the wizard with Ctrl+C."""

    pass


def ask(question: questionary.Question) -> Any:
    """Wrapper for questionary.ask() that raises on Ctrl+C cancellation."""
    result: Any = question.ask()
    if result is None:
        raise UserCancelledError()
    return result


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
    has_test_infrastructure: bool = field(default=False)


@dataclass
class WizardState:
    """State collected during wizard execution."""

    repo: str | None = None
    github_token: str | None = None
    enable_autofix: bool = False
    claude_auth_type: str | None = None  # "oauth" or "api_key"
    claude_token: str | None = None
    model: str | None = None
    middleware_injected: bool = False
    workflow_created: bool = False
    vercel_env_added: bool = False
    github_secret_added: bool = False
    config_written: bool = False


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

        ssh_match = re.search(r"url\s*=\s*git@github\.com:([^/]+)/([^/\s]+)", content)
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


def detect_test_infrastructure(base_path: Path) -> bool:
    """Detect if the project has test infrastructure."""
    # Check for test directories
    test_dirs = ["tests", "test", "spec", "__tests__"]
    for d in test_dirs:
        if (base_path / d).is_dir():
            return True

    # Check for pytest in pyproject.toml or requirements
    pyproject = base_path / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text()
            if "pytest" in content:
                return True
        except Exception:
            pass

    requirements = base_path / "requirements.txt"
    if requirements.exists():
        try:
            content = requirements.read_text()
            if "pytest" in content:
                return True
        except Exception:
            pass

    # Check for jest/mocha in package.json
    package_json = base_path / "package.json"
    if package_json.exists():
        try:
            content = package_json.read_text()
            if '"test"' in content or "jest" in content or "mocha" in content:
                return True
        except Exception:
            pass

    return False


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
    has_test_infrastructure = detect_test_infrastructure(base_path)

    return ProjectInfo(
        project_type=project_type,
        framework=framework,
        framework_file=framework_file,
        github_repo=github_repo,
        base_path=base_path,
        is_vercel=is_vercel,
        existing_token=existing_token,
        has_test_infrastructure=has_test_infrastructure,
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


# ============================================================================
# CLI Tool Helpers
# ============================================================================


def check_cli_exists(cmd: str) -> bool:
    """Check if a CLI tool exists."""
    return shutil.which(cmd) is not None


def run_command(
    args: list[str], capture: bool = True, input_text: str | None = None
) -> tuple[bool, str]:
    """Run a command and return (success, output)."""
    try:
        result = subprocess.run(
            args,
            capture_output=capture,
            text=True,
            input=input_text,
            timeout=60,
        )
        output = result.stdout + result.stderr if capture else ""
        return result.returncode == 0, output.strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def check_gh_auth() -> bool:
    """Check if gh CLI is authenticated."""
    success, _ = run_command(["gh", "auth", "status"])
    return success


def check_vercel_auth() -> bool:
    """Check if vercel CLI is authenticated."""
    success, output = run_command(["vercel", "whoami"])
    return success and "Error" not in output


def check_vercel_linked() -> bool:
    """Check if the current project is linked to Vercel."""
    # Check for .vercel directory with project.json
    vercel_dir = Path.cwd() / ".vercel"
    project_json = vercel_dir / "project.json"
    if project_json.exists():
        return True
    # Fallback: vercel env ls returns error if not linked
    success, output = run_command(["vercel", "env", "ls"])
    return (
        success
        and "isn't linked" not in output.lower()
        and "not linked" not in output.lower()
    )


def set_github_secret(repo: str, name: str, value: str) -> bool:
    """Set a GitHub secret using gh CLI."""
    success, _ = run_command(
        ["gh", "secret", "set", name, "-R", repo],
        input_text=value,
    )
    return success


def add_vercel_env(name: str, value: str) -> tuple[bool, str]:
    """Add environment variable to Vercel for all environments.

    Vercel CLI requires adding to each environment separately when piping values.
    Returns (success, error_message).
    """
    errors = []
    for env in ["production", "preview", "development"]:
        success, output = run_command(
            ["vercel", "env", "add", name, env, "-y"],
            input_text=value,
        )
        if not success:
            # Check if it failed because variable already exists
            if "already exists" not in output.lower():
                errors.append(f"{env}: {output}")
    if errors:
        return False, "; ".join(errors)
    return True, ""


# ============================================================================
# AST-Based Middleware Injection
# ============================================================================


def find_top_level_import_block_end(tree: ast.Module) -> int:
    """Find the last line of the top-level import block.

    Only counts consecutive Import/ImportFrom statements at module level,
    stopping at the first non-import statement.
    """
    last_import_line = 0

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Track the end line (for multi-line imports)
            end_line = getattr(node, "end_lineno", node.lineno)
            last_import_line = max(last_import_line, end_line)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            # Allow docstrings (string expressions) - they can appear after imports
            if isinstance(node.value.value, str):
                continue
            else:
                break
        else:
            # Non-import, non-docstring statement - end of import block
            break

    return last_import_line


class AppFinder(ast.NodeVisitor):
    """Find app instantiation in AST."""

    def __init__(self, framework: str):
        self.framework = framework
        self.app_name: str | None = None
        self.app_line: int | None = None
        self.app_end_line: int | None = None
        self.has_splat_import: bool = False
        self.has_middleware: bool = False

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            if "splat" in alias.name:
                self.has_splat_import = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module and "splat" in node.module:
            self.has_splat_import = True
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        # Look for app = FastAPI() or app = Flask(__name__)
        if isinstance(node.value, ast.Call):
            func = node.value.func
            func_name = None

            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr

            if func_name in ("FastAPI", "Flask"):
                # Get the variable name
                if node.targets and isinstance(node.targets[0], ast.Name):
                    self.app_name = node.targets[0].id
                    self.app_line = node.lineno
                    self.app_end_line = getattr(node, "end_lineno", node.lineno)

        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:  # noqa: N802
        # Look for app.add_middleware(SplatMiddleware)
        if isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute):
                if call.func.attr == "add_middleware":
                    for arg in call.args:
                        if isinstance(arg, ast.Name) and arg.id == "SplatMiddleware":
                            self.has_middleware = True
                elif call.func.attr == "init_app":
                    # Check for splat.init_app(app) pattern
                    if isinstance(call.func.value, ast.Name):
                        if "splat" in call.func.value.id.lower():
                            self.has_middleware = True

        self.generic_visit(node)


def analyze_framework_file(file_path: Path, framework: str) -> dict[str, Any]:
    """Analyze a framework file to find injection points."""
    content = file_path.read_text()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {"error": "Could not parse file"}

    # Find the end of the top-level import block
    last_import_line = find_top_level_import_block_end(tree)

    finder = AppFinder(framework)
    finder.visit(tree)

    return {
        "app_name": finder.app_name,
        "app_line": finder.app_line,
        "app_end_line": finder.app_end_line,
        "last_import_line": last_import_line,
        "has_splat_import": finder.has_splat_import,
        "has_middleware": finder.has_middleware,
        "file_content": content,
    }


def generate_injection_preview(
    file_path: Path,
    framework: str,
    analysis: dict[str, Any],
) -> str | None:
    """Generate a preview of the middleware injection with context lines."""
    if analysis.get("error"):
        return None

    if analysis["has_middleware"]:
        return None  # Already has middleware

    if not analysis["app_name"] or not analysis["app_line"]:
        return None  # Couldn't find app

    app_name = analysis["app_name"]
    content = analysis.get("file_content", "")
    file_lines = content.splitlines()

    output_parts = []
    output_parts.append(click.style(f"File: {file_path}", fg="white", bold=True))
    output_parts.append("")

    # Prepare import statement
    if framework == "fastapi":
        import_stmt = "from splat.middleware.fastapi import SplatMiddleware"
    elif framework == "flask":
        import_stmt = "from splat.middleware.flask import SplatFlask"
    else:
        return None

    # Prepare middleware statement(s)
    if framework == "fastapi":
        middleware_stmts = [f"{app_name}.add_middleware(SplatMiddleware)"]
    elif framework == "flask":
        middleware_stmts = ["splat = SplatFlask()", f"splat.init_app({app_name})"]
    else:
        return None

    # Show import insertion with context (if needed)
    if not analysis["has_splat_import"]:
        import_line = analysis["last_import_line"]  # Insert after this line (1-indexed)
        output_parts.append(click.style("Import statement:", bold=True))

        # Show 2 lines before insertion point
        start = max(0, import_line - 2)
        for i in range(start, import_line):
            line_num = i + 1
            line_content = file_lines[i] if i < len(file_lines) else ""
            output_parts.append(
                click.style(f"  {line_num:4d} │ ", fg="bright_black") + line_content
            )

        # Show the new import line
        new_line_num = import_line + 1
        output_parts.append(
            click.style(f"  {new_line_num:4d} │ ", fg="green")
            + click.style(f"+ {import_stmt}", fg="green", bold=True)
        )

        # Show 2 lines after insertion point
        for i in range(import_line, min(import_line + 2, len(file_lines))):
            line_num = i + 2  # +2 because we inserted a line
            line_content = file_lines[i]
            output_parts.append(
                click.style(f"  {line_num:4d} │ ", fg="bright_black") + line_content
            )

        output_parts.append("")

    # Show middleware insertion with context
    app_end_line = analysis.get("app_end_line") or analysis["app_line"]
    output_parts.append(click.style("Middleware setup:", bold=True))

    # Show 2 lines before app instantiation
    start = max(0, analysis["app_line"] - 3)  # -3 because app_line is 1-indexed
    for i in range(start, analysis["app_line"] - 1):
        line_num = i + 1
        line_content = file_lines[i] if i < len(file_lines) else ""
        output_parts.append(
            click.style(f"  {line_num:4d} │ ", fg="bright_black") + line_content
        )

    # Show the app instantiation line
    app_line_content = (
        file_lines[analysis["app_line"] - 1]
        if analysis["app_line"] - 1 < len(file_lines)
        else ""
    )
    output_parts.append(
        click.style(f"  {analysis['app_line']:4d} │ ", fg="cyan")
        + click.style(app_line_content, fg="cyan")
    )

    # Show the new middleware lines
    for idx, stmt in enumerate(middleware_stmts):
        new_line_num = app_end_line + 1 + idx
        output_parts.append(
            click.style(f"  {new_line_num:4d} │ ", fg="green")
            + click.style(f"+ {stmt}", fg="green", bold=True)
        )

    # Show 2 lines after app instantiation
    for i in range(app_end_line, min(app_end_line + 2, len(file_lines))):
        line_num = i + 1 + len(middleware_stmts)  # Account for inserted lines
        line_content = file_lines[i]
        output_parts.append(
            click.style(f"  {line_num:4d} │ ", fg="bright_black") + line_content
        )

    return "\n".join(output_parts)


def inject_middleware(
    file_path: Path, framework: str, analysis: dict[str, Any]
) -> bool:
    """Inject middleware into the framework file."""
    if analysis.get("error") or analysis["has_middleware"]:
        return False

    if not analysis["app_name"] or not analysis["app_line"]:
        return False

    content = file_path.read_text()
    lines = content.splitlines(keepends=True)

    app_name = analysis["app_name"]
    app_end_line = analysis.get("app_end_line") or analysis["app_line"]
    app_end_idx = app_end_line - 1  # 0-indexed
    import_line_idx = analysis["last_import_line"]  # Insert after this line (0-indexed)

    # Prepare injection code
    if framework == "fastapi":
        import_stmt = "from splat.middleware.fastapi import SplatMiddleware\n"
        middleware_stmt = f"{app_name}.add_middleware(SplatMiddleware)\n"
    elif framework == "flask":
        import_stmt = "from splat.middleware.flask import SplatFlask\n"
        middleware_stmt = f"splat = SplatFlask()\nsplat.init_app({app_name})\n"
    else:
        return False

    # Insert import after the import block (if not already present)
    if not analysis["has_splat_import"]:
        lines.insert(import_line_idx, import_stmt)
        app_end_idx += 1  # Shift due to import insertion

    # Insert middleware after app instantiation
    lines.insert(app_end_idx + 1, middleware_stmt)

    file_path.write_text("".join(lines))
    return True


# ============================================================================
# Workflow Template Generation
# ============================================================================


def get_workflow_template(
    auth_type: str,
    model: str,
    project_type: str,
    has_test_infrastructure: bool,
    base_path: Path,
) -> str:
    """Generate the workflow YAML content."""

    # Determine auth line
    if auth_type == "oauth":
        auth_line = "claude_code_oauth_token: ${{ secrets.CLAUDE_OAUTH_TOKEN }}"
    else:
        auth_line = "anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}"

    # Determine model ID
    if model == "opus":
        model_id = "claude-opus-4-5-20250514"
    else:
        model_id = "claude-sonnet-4-20250514"

    # Determine setup steps based on project type
    setup_steps = ""
    if project_type == "python":
        # Check for requirements.txt or pyproject.toml
        if (base_path / "requirements.txt").exists():
            install_cmd = "pip install -r requirements.txt"
        elif (base_path / "pyproject.toml").exists():
            install_cmd = "pip install -e ."
        else:
            install_cmd = "echo 'No dependencies to install'"

        setup_steps = f"""
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: {install_cmd}
"""
    elif project_type == "node":
        setup_steps = """
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci
"""

    # Load skills content
    skills_dir = base_path / "docs" / "skills"

    # Read skill files or use embedded defaults
    try:
        systematic_debugging = (skills_dir / "systematic-debugging.md").read_text()
    except Exception:
        systematic_debugging = "[Systematic debugging skill not found]"

    try:
        tdd = (skills_dir / "test-driven-development.md").read_text()
    except Exception:
        tdd = "[TDD skill not found]"

    try:
        verification = (skills_dir / "verification-before-completion.md").read_text()
    except Exception:
        verification = "[Verification skill not found]"

    # TDD modification for projects without test infrastructure
    tdd_modification = ""
    if not has_test_infrastructure:
        tdd_modification = """

## IMPORTANT: This Project Has No Test Infrastructure

Since this project does NOT have existing test infrastructure (no test directory,
no pytest/jest configured), you must:

- Create TEMPORARY test scripts to verify the fix (not permanent tests)
- Use simple assertions, not a testing framework:

```python
# test_fix.py (TEMPORARY - delete after verification)
from module import function_to_test

# Test the bug is fixed
result = function_to_test(problematic_input)
assert result == expected_output, f"Expected {expected_output}, got {result}"
print("✓ Bug fix verified")
```

- Run the script to see it FAIL (proving it catches the bug)
- Implement the fix
- Run the script to see it PASS
- DELETE the temporary test script after verification
- The goal is red-green proof, not permanent test infrastructure
"""

    # Build the full prompt
    prompt = f"""You are fixing a bug reported in this GitHub issue. \
Follow these three skills in order:

===============================================================================
SKILL 1: SYSTEMATIC DEBUGGING
===============================================================================

{systematic_debugging}

===============================================================================
SKILL 2: TEST-DRIVEN DEVELOPMENT
===============================================================================

{tdd}
{tdd_modification}

===============================================================================
SKILL 3: VERIFICATION BEFORE COMPLETION
===============================================================================

{verification}

===============================================================================
FINAL INSTRUCTIONS
===============================================================================

1. Follow Systematic Debugging to find root cause (Phase 1-3)
2. Follow TDD to create failing test, then fix (Phase 4)
3. Follow Verification to prove it works before claiming success
4. Create a PR with your changes when complete

Remember: NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.
"""

    # Escape the prompt for YAML (use literal block scalar)
    # We'll use the | style with proper indentation
    prompt_lines = prompt.split("\n")
    indented_prompt = "\n".join(
        "            " + line if line else "" for line in prompt_lines
    )

    workflow = f"""name: Splat Auto-Fix

on:
  issues:
    types: [labeled]
  issue_comment:
    types: [created]

permissions:
  contents: write
  pull-requests: write
  issues: write
  id-token: write

concurrency:
  group: autofix-${{{{ github.event.issue.number }}}}
  cancel-in-progress: true

jobs:
  autofix:
    if: |
      (github.event_name == 'issues' && github.event.label.name == 'auto-fix') ||
      (github.event_name == 'issue_comment' && \
contains(github.event.comment.body, '@claude'))
    runs-on: ubuntu-latest
    timeout-minutes: 120

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1
{setup_steps}
      - name: Fix with Claude Code
        uses: anthropics/claude-code-action@v1
        with:
          {auth_line}
          model: {model_id}
          max_turns: 100
          prompt: |
{indented_prompt}
"""

    return workflow


def install_workflow(base_path: Path, content: str) -> bool:
    """Install the workflow file."""
    workflows_dir = base_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    workflow_path = workflows_dir / "splat-autofix.yml"
    workflow_path.write_text(content)
    return True


# ============================================================================
# Interactive Prompts
# ============================================================================


def prompt_github_token(info: ProjectInfo) -> str | None:
    """Handle GitHub token setup interactively.

    Note: Token is only used for Vercel deployment, not saved locally.
    Local development doesn't report errors to avoid noise.
    """
    click.echo("\n" + click.style("─" * 50, fg="cyan"))
    click.echo(click.style("GitHub Token Setup", fg="cyan", bold=True))
    click.echo(click.style("─" * 50, fg="cyan"))
    click.echo("Splat needs a GitHub token with 'repo' scope to create issues.")
    click.echo(
        click.style(
            "(Only used in deployed environments, not local dev)", fg="bright_black"
        )
    )

    # Offer options
    choice: str = ask(
        questionary.select(
            "How would you like to set up your token?",
            choices=[
                "Open GitHub to generate a new token",
                "Paste an existing token",
                "Skip for now",
            ],
            style=CUSTOM_STYLE,
        )
    )

    if choice == "Skip for now":
        click.echo("\nYou can add the token later in Vercel dashboard:")
        click.echo("  Project Settings > Environment Variables > SPLAT_GITHUB_TOKEN")
        return None

    if choice == "Open GitHub to generate a new token":
        click.echo(f"\nOpening: {GITHUB_TOKEN_URL}")
        click.launch(GITHUB_TOKEN_URL)
        click.echo("\nOnce you've created the token, paste it below.")

    # Get token from user
    while True:
        token: str = ask(
            questionary.password(
                "Paste your GitHub token:",
                style=CUSTOM_STYLE,
            )
        )

        if not token:
            skip: bool = ask(
                questionary.confirm(
                    "Skip token setup for now?",
                    default=False,
                    style=CUSTOM_STYLE,
                )
            )
            if skip:
                return None
            continue

        if not validate_github_token(token):
            click.echo(
                click.style("That doesn't look like a valid GitHub token.", fg="yellow")
            )
            click.echo("Tokens usually start with 'ghp_' or 'github_pat_'")

            retry: bool = ask(
                questionary.confirm(
                    "Try again?",
                    default=True,
                    style=CUSTOM_STYLE,
                )
            )
            if not retry:
                return None
            continue

        break

    return token


def run_claude_setup_token() -> str | None:
    """Run claude setup-token and capture the OAuth token from output.

    Uses a pseudo-terminal (pty) to preserve the command's terminal animations
    and colors while still capturing the output to extract the token.
    """
    import pty
    import select

    try:
        # Create a pseudo-terminal so the command thinks it's in a real terminal
        master_fd, slave_fd = pty.openpty()

        process = subprocess.Popen(
            ["claude", "setup-token"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )

        os.close(slave_fd)  # Close slave in parent process

        captured_output = []
        captured_token = None

        def extract_token(text: str) -> str | None:
            """Extract OAuth token from text."""
            # Token format: sk-ant-oat01-...
            import re

            match = re.search(r"sk-ant-oat01-[A-Za-z0-9_-]+", text)
            if match:
                return match.group(0)
            return None

        while True:
            # Check if there's data to read (with timeout)
            r, _, _ = select.select([master_fd], [], [], 0.1)
            if r:
                try:
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    decoded = data.decode("utf-8", errors="replace")
                    sys.stdout.write(decoded)
                    sys.stdout.flush()
                    captured_output.append(decoded)

                    # Look for token in output
                    token = extract_token(decoded)
                    if token:
                        captured_token = token
                except OSError:
                    break

            # Check if process has finished
            if process.poll() is not None:
                # Read any remaining output
                try:
                    while True:
                        r, _, _ = select.select([master_fd], [], [], 0.1)
                        if not r:
                            break
                        data = os.read(master_fd, 4096)
                        if not data:
                            break
                        decoded = data.decode("utf-8", errors="replace")
                        sys.stdout.write(decoded)
                        sys.stdout.flush()
                        captured_output.append(decoded)

                        token = extract_token(decoded)
                        if token:
                            captured_token = token
                except OSError:
                    pass
                break

        os.close(master_fd)
        return captured_token

    except Exception:
        return None


def prompt_claude_auth() -> tuple[str, str] | tuple[None, None]:
    """Prompt for Claude authentication type and token."""
    click.echo("\n" + click.style("─" * 50, fg="cyan"))
    click.echo(click.style("Claude Code Authentication", fg="cyan", bold=True))
    click.echo(click.style("─" * 50, fg="cyan"))

    auth_type: str = ask(
        questionary.select(
            "How do you want to authenticate Claude Code?",
            choices=[
                questionary.Choice(
                    "Claude Code subscription (OAuth token)", value="oauth"
                ),
                questionary.Choice("Anthropic API key", value="api_key"),
            ],
            style=CUSTOM_STYLE,
        )
    )

    token = None

    if auth_type == "oauth":
        # Check if Claude CLI is available
        if check_cli_exists("claude"):
            click.echo("\nRunning claude setup-token...")
            click.echo("Complete the browser authentication flow.\n")

            # Run and capture token automatically
            token = run_claude_setup_token()

            if token:
                click.echo(
                    click.style("\n✓ OAuth token captured automatically!", fg="green")
                )
            else:
                click.echo(
                    click.style("\nCouldn't capture token automatically.", fg="yellow")
                )
        else:
            click.echo("\nClaude Code CLI not found. To get your OAuth token:")
            click.echo("  1. Install Claude Code CLI and log in")
            click.echo("  2. Run: claude setup-token")
            click.echo("  3. Complete the browser authentication flow")
            click.echo("  4. Copy the token shown")
    else:
        click.echo("\nTo get your API key:")
        click.echo("  1. Go to https://console.anthropic.com/settings/keys")
        click.echo("  2. Create or copy an existing API key")

    # If we didn't capture token automatically, ask user to paste
    if not token:
        token = ask(
            questionary.password(
                f"Paste your {'OAuth token' if auth_type == 'oauth' else 'API key'}:",
                style=CUSTOM_STYLE,
            )
        )

    if not token:
        return None, None

    return auth_type, token


def prompt_model_selection() -> str:
    """Prompt for model selection."""
    click.echo("\n" + click.style("─" * 50, fg="cyan"))
    click.echo(click.style("Model Selection", fg="cyan", bold=True))
    click.echo(click.style("─" * 50, fg="cyan"))

    model: str = ask(
        questionary.select(
            "Which model should Claude Code use for auto-fixes?",
            choices=[
                questionary.Choice("Claude Opus 4.5 (most capable)", value="opus"),
                questionary.Choice(
                    "Claude Sonnet 4 (faster, lower cost)", value="sonnet"
                ),
            ],
            style=CUSTOM_STYLE,
        )
    )

    return model


def prompt_github_secret_setup(repo: str, auth_type: str, token: str) -> bool:
    """Set up GitHub secret for Claude authentication."""
    click.echo("\n" + click.style("─" * 50, fg="cyan"))
    click.echo(click.style("GitHub Secret Setup", fg="cyan", bold=True))
    click.echo(click.style("─" * 50, fg="cyan"))

    secret_name = "CLAUDE_OAUTH_TOKEN" if auth_type == "oauth" else "ANTHROPIC_API_KEY"

    # Try gh CLI first
    if check_cli_exists("gh") and check_gh_auth():
        use_gh: bool = ask(
            questionary.confirm(
                f"Use GitHub CLI to set {secret_name} secret?",
                default=True,
                style=CUSTOM_STYLE,
            )
        )

        if use_gh:
            click.echo(f"Setting {secret_name}...")
            if set_github_secret(repo, secret_name, token):
                click.echo(
                    click.style(f"✓ {secret_name} added to GitHub secrets", fg="green")
                )
                return True
            else:
                click.echo(click.style("Failed to set secret via gh CLI", fg="yellow"))

    # Fall back to manual instructions
    click.echo(f"\nTo add {secret_name} manually:")
    click.echo(f"  1. Go to https://github.com/{repo}/settings/secrets/actions/new")
    click.echo(f"  2. Name: {secret_name}")
    value_type = "OAuth token" if auth_type == "oauth" else "API key"
    click.echo(f"  3. Value: [paste your {value_type}]")

    open_browser: bool = ask(
        questionary.confirm(
            "Open GitHub secrets page in browser?",
            default=True,
            style=CUSTOM_STYLE,
        )
    )

    if open_browser:
        click.launch(f"https://github.com/{repo}/settings/secrets/actions/new")

    return False


def prompt_vercel_setup(token: str) -> bool:
    """Set up Vercel environment variable."""
    click.echo("\n" + click.style("─" * 50, fg="cyan"))
    click.echo(click.style("Vercel Environment Setup", fg="cyan", bold=True))
    click.echo(click.style("─" * 50, fg="cyan"))

    if not check_cli_exists("vercel"):
        install: bool = ask(
            questionary.confirm(
                "Vercel CLI not found. Install it?",
                default=True,
                style=CUSTOM_STYLE,
            )
        )

        if install:
            click.echo("Installing Vercel CLI...")
            success, output = run_command(["npm", "install", "-g", "vercel"])
            if not success:
                click.echo(click.style(f"Failed to install: {output}", fg="yellow"))
                click.echo("\nAdd SPLAT_GITHUB_TOKEN manually in Vercel dashboard:")
                click.echo("  Project Settings > Environment Variables")
                return False
            click.echo(click.style("✓ Vercel CLI installed", fg="green"))
        else:
            click.echo("\nAdd SPLAT_GITHUB_TOKEN manually in Vercel dashboard:")
            click.echo("  Project Settings > Environment Variables")
            return False

    if not check_vercel_auth():
        click.echo("Please log in to Vercel CLI first:")
        click.echo("  vercel login")

        open_login: bool = ask(
            questionary.confirm(
                "Run 'vercel login' now?",
                default=True,
                style=CUSTOM_STYLE,
            )
        )

        if open_login:
            # Run login interactively
            subprocess.run(["vercel", "login"])

            if not check_vercel_auth():
                click.echo(click.style("Still not logged in", fg="yellow"))
                click.echo("\nAdd SPLAT_GITHUB_TOKEN manually in Vercel dashboard:")
                click.echo("  Project Settings > Environment Variables")
                return False
        else:
            click.echo("\nAdd SPLAT_GITHUB_TOKEN manually in Vercel dashboard:")
            click.echo("  Project Settings > Environment Variables")
            return False

    # Check if project is linked to Vercel CLI
    if not check_vercel_linked():
        click.echo("Project isn't linked to Vercel CLI (needed to add env vars).")

        run_link: bool = ask(
            questionary.confirm(
                "Run 'vercel link' now?",
                default=True,
                style=CUSTOM_STYLE,
            )
        )

        if run_link:
            subprocess.run(["vercel", "link"])

            if not check_vercel_linked():
                click.echo(click.style("Project still not linked", fg="yellow"))
                click.echo("\nAdd SPLAT_GITHUB_TOKEN manually in Vercel dashboard:")
                click.echo("  Project Settings > Environment Variables")
                return False
        else:
            click.echo("\nAdd SPLAT_GITHUB_TOKEN manually in Vercel dashboard:")
            click.echo("  Project Settings > Environment Variables")
            return False

    # Add environment variable
    add_env: bool = ask(
        questionary.confirm(
            "Add SPLAT_GITHUB_TOKEN to Vercel environment?",
            default=True,
            style=CUSTOM_STYLE,
        )
    )

    if add_env:
        click.echo("Adding SPLAT_GITHUB_TOKEN to Vercel...")
        success, error = add_vercel_env("SPLAT_GITHUB_TOKEN", token)
        if success:
            click.echo(click.style("✓ SPLAT_GITHUB_TOKEN added to Vercel", fg="green"))
            return True
        else:
            click.echo(click.style("Failed to add environment variable", fg="yellow"))
            if error:
                click.echo(click.style(f"  Error: {error}", fg="bright_black"))
            # Check if project needs linking
            if "not linked" in error.lower() or "link" in error.lower():
                retry_link: bool = ask(
                    questionary.confirm(
                        "Project may not be linked. Run 'vercel link'?",
                        default=True,
                        style=CUSTOM_STYLE,
                    )
                )
                if retry_link:
                    subprocess.run(["vercel", "link"])
                    # Retry adding env var
                    click.echo("Retrying...")
                    success, error = add_vercel_env("SPLAT_GITHUB_TOKEN", token)
                    if success:
                        click.echo(
                            click.style(
                                "✓ SPLAT_GITHUB_TOKEN added to Vercel", fg="green"
                            )
                        )
                        return True
            click.echo("\nAdd SPLAT_GITHUB_TOKEN manually in Vercel dashboard:")
            click.echo("  Project Settings > Environment Variables")
            return False
    else:
        click.echo("")
        click.echo(
            click.style("⚠ Warning: ", fg="yellow", bold=True)
            + "Splat won't be able to create GitHub issues from Vercel deployments."
        )
        click.echo("  Add SPLAT_GITHUB_TOKEN manually:")
        click.echo("  Project Settings > Environment Variables")
        return False


def prompt_middleware_injection(info: ProjectInfo) -> bool:
    """Prompt for and perform middleware injection."""
    if not info.framework or not info.framework_file:
        return False

    click.echo("\n" + click.style("─" * 50, fg="cyan"))
    click.echo(click.style("Middleware Setup", fg="cyan", bold=True))
    click.echo(click.style("─" * 50, fg="cyan"))

    analysis = analyze_framework_file(info.framework_file, info.framework)

    if analysis.get("has_middleware"):
        click.echo(click.style("✓ Splat middleware already configured", fg="green"))
        return True

    if analysis.get("error") or not analysis.get("app_name"):
        click.echo(
            click.style("Could not automatically detect app configuration", fg="yellow")
        )
        click.echo(f"\nAdd Splat middleware manually to {info.framework_file}:")
        if info.framework == "fastapi":
            click.echo("  from splat.middleware.fastapi import SplatMiddleware")
            click.echo("  app.add_middleware(SplatMiddleware)")
        elif info.framework == "flask":
            click.echo("  from splat.middleware.flask import SplatFlask")
            click.echo("  splat = SplatFlask()")
            click.echo("  splat.init_app(app)")
        return False

    preview = generate_injection_preview(info.framework_file, info.framework, analysis)

    if not preview:
        click.echo(click.style("✓ Splat middleware already configured", fg="green"))
        return True

    click.echo("\nProposed changes:")
    click.echo(click.style(preview, fg="cyan"))

    proceed: bool = ask(
        questionary.confirm(
            "Apply these changes?",
            default=True,
            style=CUSTOM_STYLE,
        )
    )

    if proceed:
        if inject_middleware(info.framework_file, info.framework, analysis):
            click.echo(click.style("✓ Middleware injected successfully", fg="green"))
            return True
        else:
            click.echo(click.style("Failed to inject middleware", fg="yellow"))
            return False
    else:
        click.echo("")
        click.echo(
            click.style("⚠ Warning: ", fg="yellow", bold=True)
            + "Splat won't capture errors without middleware."
        )
        click.echo(f"  Add manually to {info.framework_file.name}:")
        if info.framework == "fastapi":
            click.echo("    from splat.middleware.fastapi import SplatMiddleware")
            click.echo("    app.add_middleware(SplatMiddleware)")
        elif info.framework == "flask":
            click.echo("    from splat.middleware.flask import SplatFlask")
            click.echo("    splat = SplatFlask()")
            click.echo("    splat.init_app(app)")
        return False


# ============================================================================
# Main Wizard
# ============================================================================


def run_init_wizard(base_path: Path | None = None) -> None:
    """Run the interactive setup wizard."""
    if base_path is None:
        base_path = Path.cwd()

    state = WizardState()

    try:
        _run_wizard_steps(base_path, state)
    except UserCancelledError:
        click.echo("\n" + click.style("Setup cancelled.", fg="yellow"))
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\n" + click.style("Setup cancelled.", fg="yellow"))
        sys.exit(1)


def _run_wizard_steps(base_path: Path, state: WizardState) -> None:
    """Run the actual wizard steps. Separated for cancellation handling."""
    # Welcome
    click.echo("\n" + click.style("═" * 50, fg="cyan"))
    click.echo(click.style("  Welcome to Splat!", fg="cyan", bold=True))
    click.echo(click.style("═" * 50, fg="cyan"))

    # 1. Detect project info and show summary
    click.echo("\nDetecting project...")
    info = detect_project_info(base_path)

    click.echo("\n" + click.style("Project detected:", bold=True))
    click.echo(f"  • Type: {click.style(info.project_type, fg='cyan')}")
    if info.framework:
        file_name = info.framework_file.name if info.framework_file else "unknown"
        styled_fw = click.style(info.framework.title(), fg="cyan")
        click.echo(f"  • Framework: {styled_fw} (in {file_name})")
    if info.github_repo:
        click.echo(f"  • GitHub: {click.style(info.github_repo, fg='cyan')}")
    if info.is_vercel:
        click.echo(f"  • {click.style('Vercel project detected', fg='cyan')}")
    if info.existing_token:
        click.echo(f"  • GitHub token: {click.style('configured', fg='green')}")
    if info.has_test_infrastructure:
        click.echo(f"  • Test infrastructure: {click.style('detected', fg='green')}")

    # 2. Confirm repository
    click.echo("\n" + click.style("─" * 50, fg="cyan"))
    click.echo(click.style("Repository Configuration", fg="cyan", bold=True))
    click.echo(click.style("─" * 50, fg="cyan"))

    if info.github_repo:
        use_detected: bool = ask(
            questionary.confirm(
                f"Use {info.github_repo} as your Splat repository?",
                default=True,
                style=CUSTOM_STYLE,
            )
        )

        if use_detected:
            state.repo = info.github_repo
        else:
            state.repo = ask(
                questionary.text(
                    "Enter GitHub repository (owner/repo):",
                    style=CUSTOM_STYLE,
                )
            )
    else:
        state.repo = ask(
            questionary.text(
                "Enter GitHub repository (owner/repo):",
                style=CUSTOM_STYLE,
            )
        )

    # 3. GitHub token setup
    state.github_token = prompt_github_token(info)

    # 4. Enable auto-fix?
    click.echo("\n" + click.style("─" * 50, fg="cyan"))
    click.echo(click.style("Features", fg="cyan", bold=True))
    click.echo(click.style("─" * 50, fg="cyan"))

    state.enable_autofix = ask(
        questionary.confirm(
            "Enable Claude Code auto-fix? (automatically fix bugs via GitHub issues)",
            default=True,
            style=CUSTOM_STYLE,
        )
    )

    # 5-7. Auto-fix specific setup
    if state.enable_autofix:
        # Claude authentication
        state.claude_auth_type, state.claude_token = prompt_claude_auth()

        if state.claude_auth_type and state.claude_token:
            # Model selection
            state.model = prompt_model_selection()

            # GitHub secret setup
            if state.repo:
                state.github_secret_added = prompt_github_secret_setup(
                    state.repo, state.claude_auth_type, state.claude_token
                )

    # 8. Vercel integration (if detected and token exists)
    if info.is_vercel and state.github_token:
        state.vercel_env_added = prompt_vercel_setup(state.github_token)

    # 9. Middleware injection
    state.middleware_injected = prompt_middleware_injection(info)

    # 10. Write configuration
    labels = ["bug", "splat"]
    if state.enable_autofix:
        labels.append("auto-fix")

    config = {
        "repo": state.repo,
        "labels": labels,
    }

    # Save configuration automatically
    update_pyproject_toml(base_path, config)
    state.config_written = True

    # 11. Install autofix workflow if enabled
    if state.enable_autofix and state.claude_auth_type and state.model:
        workflow_content = get_workflow_template(
            auth_type=state.claude_auth_type,
            model=state.model,
            project_type=info.project_type,
            has_test_infrastructure=info.has_test_infrastructure,
            base_path=base_path,
        )
        install_workflow(base_path, workflow_content)
        state.workflow_created = True
        click.echo(
            click.style("✓ Created .github/workflows/splat-autofix.yml", fg="green")
        )

    # 12. Final summary
    click.echo("\n" + click.style("═" * 50, fg="green"))
    click.echo(click.style("  Setup Complete!", fg="green", bold=True))
    click.echo(click.style("═" * 50, fg="green"))

    click.echo("")

    # Show what was configured
    if state.repo:
        click.echo(click.style("✓", fg="green") + f" Repository: {state.repo}")

    if state.enable_autofix:
        if state.github_secret_added:
            secret_name = (
                "CLAUDE_OAUTH_TOKEN"
                if state.claude_auth_type == "oauth"
                else "ANTHROPIC_API_KEY"
            )
            click.echo(
                click.style("✓", fg="green")
                + f" Claude auth: {secret_name} added to GitHub secrets"
            )
        else:
            click.echo(
                click.style("○", fg="yellow") + " Claude auth: add secret manually"
            )

    if info.is_vercel:
        if state.vercel_env_added:
            click.echo(
                click.style("✓", fg="green") + " Vercel: SPLAT_GITHUB_TOKEN added"
            )
        elif state.github_token:
            click.echo(
                click.style("○", fg="yellow")
                + " Vercel: add SPLAT_GITHUB_TOKEN manually"
            )
        else:
            click.echo(
                click.style("○", fg="yellow") + " Vercel: GitHub token not configured"
            )

    if state.middleware_injected:
        file_name = info.framework_file.name if info.framework_file else "app"
        click.echo(
            click.style("✓", fg="green") + f" Middleware: injected into {file_name}"
        )
    elif info.framework:
        click.echo(click.style("○", fg="yellow") + " Middleware: add manually")

    if state.workflow_created:
        click.echo(
            click.style("✓", fg="green")
            + " Workflow: .github/workflows/splat-autofix.yml created"
        )

    if state.config_written:
        click.echo(click.style("✓", fg="green") + " Config: pyproject.toml updated")

    # Final instructions
    click.echo("\n" + click.style("─" * 50, fg="cyan"))
    click.echo(click.style("Ready to go!", fg="cyan", bold=True))
    click.echo(click.style("─" * 50, fg="cyan"))

    click.echo("\nJust commit and push:")
    click.echo(
        click.style(
            '  git add . && git commit -m "Add Splat error reporting" && git push',
            fg="cyan",
        )
    )

    if state.enable_autofix:
        autofix_label = click.style("auto-fix", fg="green")
        claude_mention = click.style("@claude", fg="green")
        click.echo(
            f"\nLabel any issue with {autofix_label} or mention {claude_mention} "
            "in comments to trigger fixes."
        )

    doc_url = click.style(
        "https://github.com/andreaslordos/splat", fg="blue", underline=True
    )
    click.echo(f"\nDocumentation: {doc_url}")
