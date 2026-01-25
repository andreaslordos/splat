# Splat

[![PyPI version](https://img.shields.io/pypi/v/py-splat.svg)](https://pypi.org/project/py-splat/)
[![Python versions](https://img.shields.io/pypi/pyversions/py-splat.svg)](https://pypi.org/project/py-splat/)
[![License](https://img.shields.io/pypi/l/py-splat.svg)](https://github.com/andreaslordos/splat/blob/main/LICENSE)

Automatic GitHub issue creation on application crashes with optional Claude Code auto-fix.

## Features

- **Zero-config crash reporting** - Add two lines, get GitHub issues on errors
- **True deduplication** - Checks GitHub before creating, works across restarts/instances
- **Rich context** - Rolling log buffer, framework-specific request context, custom metadata
- **Auto-fix ready** - One command installs a GitHub Action that uses Claude Code to fix reported bugs

## Installation

```bash
pip install py-splat
```

## Quick Start

### Basic Usage

```python
from splat import Splat

splat = Splat(repo="owner/repo", token="ghp_...")

try:
    do_something()
except Exception as e:
    await splat.report(e)  # async - use in async context
```

### With Context

```python
try:
    process_order(user)
except Exception as e:
    await splat.report(
        e,
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
| `SPLAT_VERCEL_SECRET` | Vercel webhook verification secret | (optional) |
| `SPLAT_VERCEL_WEBHOOK_PATH` | Vercel webhook endpoint path | `/splat/logs` |
| `SPLAT_VERCEL_LOG_TTL` | Seconds to keep Vercel logs in memory | `60` |

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

## Vercel Log Integration

Splat can capture Vercel runtime logs via Log Drain webhooks, providing precise logs for each failed request.

### Setup

1. **Configure your app:**

   Flask (webhook auto-registered):
   ```python
   from flask import Flask
   from splat.middleware.flask import SplatFlask

   app = Flask(__name__)
   splat = SplatFlask()
   splat.init_app(app, repo="owner/repo", token="ghp_...")
   # Automatically registers /splat/logs webhook
   ```

   FastAPI (manual middleware wrapping to share Splat instance):
   ```python
   from fastapi import FastAPI
   from splat.middleware.fastapi import SplatMiddleware
   from splat.webhooks.fastapi import create_webhook_router

   app = FastAPI()
   # Add webhook router first
   middleware = SplatMiddleware(app, repo="owner/repo", token="ghp_...")
   app.include_router(create_webhook_router(middleware.splat))
   # Use middleware.app or wrap app manually if needed
   ```

2. **Add Log Drain in Vercel:**
   - Go to your project's Settings → Log Drains
   - Create a new Log Drain:
     - **Delivery format:** JSON
     - **Endpoint:** `https://your-app.vercel.app/splat/logs`
     - **Sources:** Lambda, Edge (runtime logs)

3. **(Recommended) Add verification secret:**
   ```bash
   # Generate a secret
   export SPLAT_VERCEL_SECRET=$(openssl rand -hex 32)
   # Add to your environment variables and Vercel Log Drain config
   ```

### How It Works

1. Vercel pushes runtime logs to your `/splat/logs` endpoint
2. Splat stores logs keyed by request ID (from `x-vercel-id` header)
3. When an error occurs, middleware captures the request ID
4. `splat.report()` fetches logs for that specific request
5. GitHub issue includes the exact logs for the failed request

Logs automatically expire after 60 seconds (configurable via `SPLAT_VERCEL_LOG_TTL`).

## Issue Format

Created issues include:

- Error type, message, file, line, and function
- Full traceback
- Optional context (custom metadata you provide)
- Recent logs (last 200 entries by default)
- Unique signature for deduplication

## License

MIT
