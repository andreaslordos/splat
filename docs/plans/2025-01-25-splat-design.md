# Splat - Design Document

**Date:** 2025-01-25
**Status:** Draft

## Overview

Splat is a Python library that automatically creates GitHub issues when your application crashes. It captures rich context (traceback, logs, custom metadata), deduplicates to avoid issue spam, and optionally enables one-command auto-fix via Claude Code.

## Core Value Proposition

1. **Zero-config crash reporting** - Add two lines, get GitHub issues on errors
2. **True deduplication** - Checks GitHub before creating, works across restarts/instances
3. **Rich context** - Rolling log buffer, framework-specific request context, custom metadata
4. **Auto-fix ready** - One command installs a GitHub Action that uses Claude Code to fix reported bugs

## Target Users

- Solo developers wanting crash visibility without SaaS (Sentry, etc.)
- Teams already using GitHub Issues for bug tracking
- Projects that want to experiment with AI-assisted bug fixing

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Issue tracker | GitHub only (v1) | Start focused, expand later based on demand |
| Language | Python first, design for ports | Ship fast, document protocol for community ports |
| Auto-fix workflow | Separate but linked | Clean separation, easy one-step enable |
| Configuration | Env → config → programmatic | Standard precedence pattern developers expect |
| Context capture | Core + middleware + user extras | Flexible without framework lock-in |
| Log buffering | Auto-capture + allow override | Works for 80%, escape hatch for edge cases |
| Deduplication | Check GitHub API before creating | True dedup across restarts/instances |

## Package Structure

```
splat/
├── __init__.py          # Main Splat class, report() function
├── core/
│   ├── __init__.py
│   ├── reporter.py      # ErrorReporter class
│   ├── dedup.py         # Signature generation, GitHub search
│   ├── log_buffer.py    # Rolling log capture
│   └── config.py        # Configuration loading (env/file/programmatic)
├── middleware/
│   ├── __init__.py
│   ├── flask.py         # Flask error handler
│   ├── fastapi.py       # FastAPI exception handler
│   └── django.py        # Django middleware
├── cli/
│   ├── __init__.py
│   ├── main.py          # CLI entry point
│   ├── init.py          # splat init wizard
│   └── autofix.py       # splat install-autofix
└── templates/
    └── splat-autofix.yml # GitHub Action template
```

## Core API

### Basic Usage

```python
from splat import Splat

# Initialize once at startup
splat = Splat(
    repo="owner/repo",           # or via SPLAT_GITHUB_REPO env var
    token="ghp_...",             # or via SPLAT_GITHUB_TOKEN env var
)

# Report an error
try:
    do_something()
except Exception as e:
    await splat.report(e)
```

### With Context

```python
await splat.report(
    exception=e,
    context={                    # Optional user-defined metadata
        "user_id": user.id,
        "endpoint": "/checkout",
        "cart_items": 3,
    },
    logs=custom_logs,            # Optional override/supplement
)
```

### Framework Middleware

```python
# Flask
from splat.middleware.flask import splat_error_handler
app.register_error_handler(Exception, splat_error_handler)

# FastAPI
from splat.middleware.fastapi import SplatMiddleware
app.add_middleware(SplatMiddleware)

# Django - add to MIDDLEWARE in settings.py
MIDDLEWARE = [
    'splat.middleware.django.SplatMiddleware',
    # ...
]
```

## Configuration

### Precedence

```
Programmatic → Config File → Environment Variables → Defaults
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SPLAT_GITHUB_TOKEN` | GitHub API token | (required) |
| `SPLAT_GITHUB_REPO` | Repository (owner/repo) | (required) |
| `SPLAT_ENABLED` | Kill switch | `true` |
| `SPLAT_LOG_BUFFER_SIZE` | Rolling log capacity | `200` |
| `SPLAT_LABELS` | Comma-separated issue labels | `bug,splat` |

### Config File (pyproject.toml)

```toml
[tool.splat]
repo = "owner/repo"
labels = ["bug", "splat", "auto-fix"]
log_buffer_size = 500
```

## CLI Wizard

### `splat init`

Interactive setup wizard that auto-detects project configuration and asks before making changes.

```bash
$ splat init

🎯 Welcome to Splat!

Detecting project...
  ✓ Python project (pyproject.toml)
  ✓ Flask app in app.py
  ✓ GitHub remote: owner/repo

Step 1/3: GitHub Token
  → Opening browser to create token...
  Paste token: ghp_****
  ✓ Saved to .env

Step 2/3: Integration
  Detected Flask app. Add error handler to app.py? [y/n] → y
  ✓ Added Flask error handler to app.py

  Add splat to requirements.txt? [y/n] → y
  ✓ Added splat to requirements.txt

Step 3/3: Auto-Fix (optional)
  Enable Claude Code auto-fix? [y/n] → y
  ✓ Created .github/workflows/splat-autofix.yml

  Paste your Anthropic API key: sk-****
  ✓ Set ANTHROPIC_API_KEY via gh CLI

🎉 Done!
```

### Framework Detection

The wizard detects:
- **Flask**: Looks for `Flask(__name__)` pattern
- **FastAPI**: Looks for `FastAPI()` pattern
- **Django**: Looks for `settings.py` with `INSTALLED_APPS`
- **Generic Python**: Falls back to manual try/catch instructions

## Deduplication

### Signature Generation

Error signature combines:
- Exception type name
- Source file path (relative to repo root)
- Line number
- Function name

Hashed to 8-character identifier.

### GitHub Search Before Create

Before creating an issue, Splat searches:

```
GET /search/issues?q=repo:owner/repo+label:splat+{signature}+in:body
```

If found, skips creation and logs "Duplicate error, issue #{number} already exists".

## Auto-Fix Workflow

### GitHub Action Template

```yaml
name: Splat Auto-Fix

on:
  issues:
    types: [labeled]

jobs:
  autofix:
    if: github.event.label.name == 'auto-fix'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Fix with Claude Code
        uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          issue_number: ${{ github.event.issue.number }}
          model: claude-sonnet-4-20250514
          max_turns: 50
```

### Enabling Auto-Fix

Add `auto-fix` to labels config:

```toml
[tool.splat]
labels = ["bug", "splat", "auto-fix"]
```

Or via wizard: answer "y" to "Enable Claude Code auto-fix?"

## Issue Format

### Title

```
[Splat] {ExceptionType} in {filename}:{line}
```

### Body

```markdown
## Error

**Type:** ValueError
**Message:** invalid literal for int()
**File:** app/handlers.py
**Line:** 42
**Function:** process_order

## Traceback

\`\`\`
Traceback (most recent call last):
  File "app/handlers.py", line 42, in process_order
    quantity = int(request.form['qty'])
ValueError: invalid literal for int() with base 10: 'abc'
\`\`\`

## Context

| Key | Value |
|-----|-------|
| user_id | 12345 |
| endpoint | /checkout |

## Recent Logs

<details>
<summary>Last 200 log entries</summary>

\`\`\`
2025-01-25 10:30:01 INFO  Request started: POST /checkout
2025-01-25 10:30:01 DEBUG Processing cart items...
...
\`\`\`

</details>

---
Signature: `a1b2c3d4`
Reported by [Splat](https://github.com/yourorg/splat)
```

## Future Considerations (Not v1)

- **GitLab/Jira adapters** - Plugin architecture for other issue trackers
- **JavaScript/TypeScript port** - Document protocol for community implementation
- **Rate limiting** - Respect GitHub API limits, queue issues if needed
- **Severity levels** - Different labels/handling for warnings vs errors
- **Slack/Discord notifications** - Notify on issue creation
