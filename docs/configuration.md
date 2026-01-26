# Configuration

Splat can be configured through environment variables, `pyproject.toml`, or programmatically.

## Configuration Precedence

Configuration is loaded in this order (highest priority first):

1. **Programmatic** - Parameters passed to `Splat()`, `SplatMiddleware`, or `SplatFlask`
2. **pyproject.toml** - `[tool.splat]` section
3. **Environment variables** - `SPLAT_*` variables
4. **Defaults** - Built-in defaults

## Required Settings

| Setting | Description |
|---------|-------------|
| `repo` | GitHub repository in `owner/repo` format |
| `token` | GitHub API token with `repo` scope |

## All Options

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `repo` | string | - | GitHub repository (`owner/repo`) |
| `token` | string | - | GitHub API token |
| `enabled` | boolean | `true` | Enable/disable error reporting |
| `labels` | list | `["bug", "splat"]` | Labels applied to created issues |
| `log_buffer_size` | integer | `200` | Number of log entries to capture |
| `debug` | boolean | `false` | Enable debug logging |

## Environment Variables

```bash
SPLAT_GITHUB_REPO=owner/repo
SPLAT_GITHUB_TOKEN=ghp_xxxxxxxxxxxx
SPLAT_ENABLED=true
SPLAT_LABELS=bug,splat,auto-fix
SPLAT_LOG_BUFFER_SIZE=200
SPLAT_DEBUG=false
```

```{note}
For `SPLAT_LABELS`, use comma-separated values (e.g., `bug,splat,auto-fix`).
```

## pyproject.toml

```toml
[tool.splat]
repo = "owner/repo"
enabled = true
labels = ["bug", "splat", "auto-fix"]
log_buffer_size = 200
debug = false
```

```{warning}
Don't commit tokens to `pyproject.toml`. Use environment variables for secrets.
```

## Programmatic Configuration

**FastAPI:**

```python
from fastapi import FastAPI
from splat.middleware.fastapi import SplatMiddleware

app = FastAPI()
app.add_middleware(
    SplatMiddleware,
    repo="owner/repo",
    token="ghp_xxxxxxxxxxxx",
    labels=["bug", "splat", "auto-fix"],
    log_buffer_size=500,
    debug=True,
)
```

**Flask:**

```python
from flask import Flask
from splat.middleware.flask import SplatFlask

app = Flask(__name__)
splat = SplatFlask(
    app,
    repo="owner/repo",
    token="ghp_xxxxxxxxxxxx",
    labels=["bug", "splat", "auto-fix"],
    log_buffer_size=500,
    debug=True,
)
```

## New in v1.0.0

### API Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `timeout` | float | `30.0` | API request timeout in seconds |
| `github_api_url` | string | `https://api.github.com` | GitHub API base URL (for Enterprise) |

### Exception Filtering (Programmatic Only)

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `ignore_exceptions` | list | `[]` | Exception types to ignore |
| `exception_filter` | callable | `None` | Custom filter callback |

Example:
```python
app.add_middleware(
    SplatMiddleware,
    ignore_exceptions=[ValueError, KeyError],
    exception_filter=lambda e: not isinstance(e, HTTPException),
)
```

### Environment Variables

```bash
SPLAT_TIMEOUT=30.0
SPLAT_GITHUB_API_URL=https://github.example.com/api/v3
```

### GitHub Enterprise

To use with GitHub Enterprise:

```python
app.add_middleware(
    SplatMiddleware,
    github_api_url="https://github.mycompany.com/api/v3",
)
```

Or via environment:

```bash
SPLAT_GITHUB_API_URL=https://github.mycompany.com/api/v3
```

## Disabling Splat

To temporarily disable error reporting:

```bash
SPLAT_ENABLED=false
```

Or programmatically:

```python
app.add_middleware(SplatMiddleware, enabled=False)
```

## Debug Mode

Enable debug mode to see Splat's internal operations:

```bash
SPLAT_DEBUG=true
```

This logs information about:

- Configuration loading
- Error detection and deduplication
- GitHub API calls
- Issue creation
