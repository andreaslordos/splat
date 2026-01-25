# Splat

Automatic GitHub issue creation on application crashes.

## Installation

```bash
pip install splat
```

## Quick Start

```python
from splat import Splat

splat = Splat(repo="owner/repo", token="ghp_...")

try:
    do_something()
except Exception as e:
    await splat.report(e)
```

## CLI Setup

```bash
pip install splat[cli]
splat init
```
