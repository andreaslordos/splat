# Getting Started

## Requirements

- Python 3.9+
- Flask or FastAPI application
- GitHub repository
- GitHub token with `repo` scope

## Installation

```bash
pip install py-splat
```

## Setup

### Using the Setup Wizard (Recommended)

Run the interactive setup wizard in your project directory:

```bash
splat init
```

The wizard will:

1. **Detect your framework** - Finds Flask or FastAPI apps in your project
2. **Configure GitHub** - Prompts for your repository and token
3. **Inject middleware** - Automatically adds Splat to your application
4. **Set up auto-fix** - Creates a GitHub Action for Claude Code (optional)

### Manual Setup

If you prefer to set up manually:

**FastAPI:**

```python
from fastapi import FastAPI
from splat.middleware.fastapi import SplatMiddleware

app = FastAPI()
app.add_middleware(SplatMiddleware)
```

**Flask:**

```python
from flask import Flask
from splat.middleware.flask import SplatFlask

app = Flask(__name__)
splat = SplatFlask(app)
```

Then set the required environment variables:

```bash
export SPLAT_GITHUB_REPO="owner/repo"
export SPLAT_GITHUB_TOKEN="ghp_your_token_here"
```

## Setting Up Auto-Fix

To enable Claude Code auto-fix without re-running the full wizard:

```bash
splat install-autofix
```

This creates `.github/workflows/splat-autofix.yml` which triggers when issues with the `splat` label are created.

## Verifying the Setup

1. **Trigger a test error** - Add a route that raises an exception:

    ```python
    @app.get("/test-error")
    def test_error():
        raise ValueError("Test error for Splat")
    ```

2. **Visit the route** - This should create a GitHub issue

3. **Check your repository** - You should see a new issue with the `splat` label

4. **Watch the action** - If auto-fix is enabled, Claude Code will start working on a fix

## Next Steps

- [Configuration](configuration.md) - Customize Splat's behavior
- [How It Works](how-it-works.md) - Understand the internals
