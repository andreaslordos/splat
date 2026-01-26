# Splat

[![PyPI version](https://img.shields.io/pypi/v/py-splat.svg)](https://pypi.org/project/py-splat/)
[![Python versions](https://img.shields.io/pypi/pyversions/py-splat.svg)](https://pypi.org/project/py-splat/)
[![Documentation Status](https://readthedocs.org/projects/py-splat/badge/?version=latest)](https://py-splat.readthedocs.io/)
[![License](https://img.shields.io/pypi/l/py-splat.svg)](https://github.com/andreaslordos/splat/blob/main/LICENSE)

Splat automatically creates GitHub issues when your Flask or FastAPI app crashes, then uses Claude Code to generate fix PRs. Set it up once, and bugs fix themselves.

## Quick Start

```bash
pip install py-splat
splat init
```

The `splat init` wizard detects your framework, injects the error-catching middleware, and sets up a GitHub Action that triggers Claude Code when issues are created.

The injected code is minimal: two lines of code for each server you instantiate. `splat init` will figure out where to inject this code and do it for you.

## How It Works

1. **Runtime error occurs** → Splat middleware catches the exception
2. **GitHub issue created** → Contains error details, traceback, and los
3. **GitHub Action triggers** → Claude Code analyzes the bug and opens a fix PR

## Documentation

See the [full documentation](https://py-splat.readthedocs.io/) for configuration options and advanced usage.

## License

MIT
