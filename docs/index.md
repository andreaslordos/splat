# Splat

Splat automatically creates GitHub issues when your Flask or FastAPI app crashes, then uses Claude Code to generate fix PRs.

## Features

- **Automatic Error Reporting** - Catches unhandled exceptions and creates GitHub issues with full context
- **AI-Powered Fixes** - GitHub Action triggers Claude Code to analyze bugs and open fix PRs
- **Error Deduplication** - Avoids creating duplicate issues for the same error
- **Log Capture** - Includes recent application logs in issue reports

## Quick Start

```bash
pip install py-splat
splat init
```

The `splat init` wizard will:

1. Detect your web framework (Flask or FastAPI)
2. Configure your GitHub repository and token
3. Inject the Splat middleware into your application
4. Set up the Claude Code auto-fix GitHub Action

## How It Works

```
Runtime error occurs in your app
         ↓
Splat middleware catches the exception
         ↓
GitHub issue created with error details and "splat" label
         ↓
GitHub Action triggers Claude Code
         ↓
Claude analyzes the bug and opens a fix PR
```

```{toctree}
:maxdepth: 2
:caption: Contents

getting-started
configuration
how-it-works
```
