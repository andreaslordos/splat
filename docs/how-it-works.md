# How It Works

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Application                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Splat Middleware                        │    │
│  │  • Catches unhandled exceptions                      │    │
│  │  • Captures request context                          │    │
│  │  • Collects recent logs                              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Issue                              │
│  • Exception type and message                                │
│  • Full stack trace                                          │
│  • Request context (method, path, client IP)                 │
│  • Recent application logs                                   │
│  • Error signature for deduplication                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 GitHub Action (Auto-Fix)                     │
│  • Triggered by "splat" label                                │
│  • Runs Claude Code with debugging instructions              │
│  • Creates a PR with the fix                                 │
└─────────────────────────────────────────────────────────────┘
```

## Error Capture

When an unhandled exception occurs:

1. **Middleware intercepts** - The Splat middleware wraps your request handlers and catches any unhandled exceptions
2. **Context extraction** - HTTP method, path, and client IP are captured
3. **Log collection** - Recent log entries from Python's logging system are gathered
4. **Re-raise** - The exception is re-raised so your app's normal error handling continues

## Issue Creation

The GitHub issue includes:

- **Title**: `[Splat] ExceptionType in filename:line`
- **Body**:
    - Exception details and message
    - Full stack trace
    - Request context table
    - Recent logs (collapsible section)
    - Error signature for deduplication

### Error Deduplication

Splat generates a unique signature for each error based on:

- Exception type
- Filename where error occurred
- Line number
- Function name

Before creating an issue, Splat searches for existing open issues with the same signature. If found, it skips creating a duplicate.

## Log Buffering

Splat maintains a rolling buffer of recent log entries:

- Default size: 200 entries
- Attaches to Python's root logger
- Captures logs from all loggers in your application
- FIFO (first-in-first-out) - oldest entries are dropped when full

When an error occurs, the buffered logs are included in the GitHub issue.

## Auto-Fix Workflow

The GitHub Action (`.github/workflows/splat-autofix.yml`) triggers when:

- An issue is opened or labeled with `splat` or `auto-fix`
- Someone comments `@claude` on an issue

The workflow:

1. **Checks out your code**
2. **Sets up the environment** (Python/Node dependencies)
3. **Runs Claude Code** with embedded instructions for:
    - Systematic debugging (find root cause before fixing)
    - Test-driven development (write failing test, implement fix, verify)
    - Verification before completion (run tests before claiming success)
4. **Creates a PR** with the fix

### Authentication

The workflow supports two authentication methods:

- **API Key**: Uses `ANTHROPIC_API_KEY` secret
- **OAuth**: Uses `CLAUDE_OAUTH_TOKEN` secret (for Claude Code subscription)

These are configured during `splat init` or `splat install-autofix`.

## Background Processing

Errors are processed asynchronously in a background queue:

1. **Non-blocking** - `report()` returns immediately, error is queued
2. **Retries** - Failed API calls retry with exponential backoff (1s, 2s, 4s)
3. **Graceful degradation** - After 3 attempts, errors are logged and dropped

This ensures error tracking never slows down your application.

## Payload Limits

Large payloads are automatically truncated to prevent issues:

- **Traceback**: Max 50,000 characters
- **Log entries**: Max 500 entries (most recent kept)
- **Context values**: Max 5,000 characters per value

Truncated content shows `... [truncated]` indicator.
