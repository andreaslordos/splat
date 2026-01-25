# Splat

Automatic GitHub issue creation on application crashes with optional Claude Code auto-fix.

## Features

- **Zero-config crash reporting** - Add two lines, get GitHub issues on errors
- **True deduplication** - Checks GitHub before creating, works across restarts/instances
- **Rich context** - Rolling log buffer, framework-specific request context, custom metadata
- **Auto-fix ready** - One command installs a GitHub Action that uses Claude Code to fix reported bugs

## Installation

```bash
pip install splat
```

With framework support:
```bash
pip install splat[flask]    # Flask
pip install splat[fastapi]  # FastAPI
pip install splat[cli]      # CLI tools
```

## Quick Start

### Basic Usage

```python
from splat import Splat

splat = Splat(repo="owner/repo", token="ghp_...")

try:
    do_something()
except Exception as e:
    await splat.report(e)
```

### With Context

```python
await splat.report(
    exception=e,
    context={
        "user_id": user.id,
        "endpoint": "/checkout",
    },
)
```

### Flask Integration

```python
from flask import Flask
from splat.middleware.flask import SplatFlask

app = Flask(__name__)
splat = SplatFlask()
splat.init_app(app, repo="owner/repo", token="ghp_...")
```

### FastAPI Integration

```python
from fastapi import FastAPI
from splat.middleware.fastapi import SplatMiddleware

app = FastAPI()
app.add_middleware(SplatMiddleware, repo="owner/repo", token="ghp_...")
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SPLAT_GITHUB_TOKEN` | GitHub API token | (required) |
| `SPLAT_GITHUB_REPO` | Repository (owner/repo) | (required) |
| `SPLAT_ENABLED` | Enable/disable reporting | `true` |
| `SPLAT_LOG_BUFFER_SIZE` | Log buffer capacity | `200` |
| `SPLAT_LABELS` | Issue labels (comma-separated) | `bug,splat` |

### pyproject.toml

```toml
[tool.splat]
repo = "owner/repo"
labels = ["bug", "splat", "auto-fix"]
log_buffer_size = 500
```

### Precedence

Configuration is loaded with precedence: **Programmatic > pyproject.toml > Environment Variables > Defaults**

## CLI

```bash
# Interactive setup wizard
splat init

# Install auto-fix GitHub Action
splat install-autofix
```

## Auto-Fix with Claude Code

Splat can automatically create PRs to fix reported bugs using Claude Code:

1. Install the auto-fix workflow:
   ```bash
   splat install-autofix
   ```

2. Add `ANTHROPIC_API_KEY` to your repository secrets

3. Add `auto-fix` to your labels:
   ```toml
   [tool.splat]
   labels = ["bug", "splat", "auto-fix"]
   ```

When an error is reported, Claude Code will analyze the issue, write a failing test, implement a fix, and open a PR.

## Issue Format

Created issues include:

- Error type, message, file, line, and function
- Full traceback
- Optional context (custom metadata you provide)
- Recent logs (last 200 entries by default)
- Unique signature for deduplication

## License

MIT
