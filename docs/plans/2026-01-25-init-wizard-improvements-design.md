# Init Wizard Improvements Design

**Date:** 2026-01-25
**Status:** Approved

## Overview

Redesign the `splat init` wizard to provide a zero-friction setup experience. After running the wizard, users should only need to `git add . && git commit && git push` - no manual steps remaining.

## Key Changes

### 1. Interactive CLI with questionary

Replace basic Click prompts with `questionary` for arrow-key navigation, multi-select, and colors.

```python
import questionary

choice = questionary.select(
    "How do you want to authenticate Claude Code?",
    choices=[
        "Claude Code subscription (OAuth token)",
        "Anthropic API key",
    ],
).ask()
```

### 2. New Wizard Flow

```
1. Welcome + Project Detection (auto)
2. Repository Confirmation (questionary select/text)
3. GitHub Token Setup (questionary select)
   → Open browser / Paste existing / Skip
   → Save to .env, ensure .gitignore
4. Enable Claude Code auto-fix? (questionary confirm)
   → If NO: skip to step 9
5. Claude Authentication Choice (questionary select)
   → "Claude Code subscription (OAuth)" or "Anthropic API key"
   → Prompt for token/key value
6. Model Selection (questionary select)
   → Opus 4.5 / Sonnet 4
7. GitHub Secret Setup
   → Try gh CLI first
   → Fall back to instructions + browser open
8. Generate Workflow File
9. Vercel Integration (if detected)
   → Check/install vercel CLI
   → Check login
   → Run `vercel env add SPLAT_GITHUB_TOKEN`
10. Middleware Injection (questionary confirm)
    → AST-based injection with preview
11. Summary (no "next steps")
```

### 3. Workflow File Template

Based on `forgotten-realms/auto-bugfix.yml` pattern:

- Triggers: `issues: [labeled]` + `issue_comment: [created]` with `@claude`
- Concurrency group per issue
- 120 minute timeout
- Dynamic auth: `claude_code_oauth_token` OR `anthropic_api_key`
- Dynamic model: user's choice (Opus 4.5 / Sonnet 4)
- Python/Node setup steps based on project type
- Full skills embedded in prompt:
  - systematic-debugging.md
  - test-driven-development.md (with temporary test modification)
  - verification-before-completion.md

### 4. GitHub Token Scopes

Keep `repo` scope (already includes issues). Update description to clarify it enables issue creation.

URL: `https://github.com/settings/tokens/new?scopes=repo&description=Splat%20Error%20Reporter%20(includes%20issue%20creation)`

### 5. AST-Based Middleware Injection

1. Parse framework file with Python AST
2. Find app instantiation (`app = FastAPI()` or `app = Flask(__name__)`)
3. Generate preview showing exact changes
4. On user confirmation, write modified file

**FastAPI:**
```python
from splat.middleware.fastapi import SplatMiddleware
app.add_middleware(SplatMiddleware)
```

**Flask:**
```python
from splat.middleware.flask import SplatFlask
splat = SplatFlask()
splat.init_app(app)
```

### 6. Vercel CLI Integration

1. Check if `vercel` CLI exists
2. Offer to install if missing (`npm install -g vercel`)
3. Check login status (`vercel whoami`)
4. Run `vercel env add SPLAT_GITHUB_TOKEN` for all environments
5. Graceful fallback to manual instructions on any failure

### 7. GitHub CLI Integration (for Claude secrets)

1. Check if `gh` CLI exists and is authenticated
2. If yes: `gh secret set CLAUDE_OAUTH_TOKEN` (or `ANTHROPIC_API_KEY`)
3. If no: show instructions + offer to open browser to secrets page

### 8. TDD Modification for Projects Without Tests

If project lacks test infrastructure, the workflow instructs Claude to:
- Create temporary test scripts (not framework-dependent)
- Use simple assertions to verify fix
- Delete temporary tests after verification
- Goal is red-green proof, not permanent infrastructure

### 9. Final Summary (No "Next Steps")

```
═══════════════════════════════════════════════════════════════════════════════
  Setup Complete!
═══════════════════════════════════════════════════════════════════════════════

✓ Repository: owner/repo
✓ GitHub token: saved to .env
✓ Claude auth: CLAUDE_OAUTH_TOKEN added to GitHub secrets
✓ Vercel env: SPLAT_GITHUB_TOKEN added
✓ Middleware: injected into src/main.py
✓ Workflow: .github/workflows/splat-autofix.yml created
✓ Config: pyproject.toml updated

Ready to go! Just commit and push:

  git add . && git commit -m "Add Splat error reporting" && git push

Label any issue with 'auto-fix' or mention @claude in comments to trigger fixes.
```

## Implementation Tasks

1. Add `questionary` dependency
2. Refactor `init.py` to use questionary for all prompts
3. Add Claude auth choice (OAuth vs API key)
4. Add model selection (Opus 4.5 / Sonnet 4)
5. Implement GitHub CLI secret setup with fallbacks
6. Implement Vercel CLI integration with fallbacks
7. Implement AST-based middleware injection
8. Update workflow template with new structure
9. Embed full skills in workflow prompt
10. Update summary to show completion status, no next steps

## Dependencies

- `questionary` - Interactive prompts with arrow navigation
- Existing: `click` (still used for CLI command definition)
