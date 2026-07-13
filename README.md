# toolsnap
[![PyPI Version](https://img.shields.io/pypi/v/toolsnap?logo=pypi&logoColor=white&label=PyPI&color=neongreen)](https://pypi.org/project/toolsnap/)
[![Tests](https://img.shields.io/github/actions/workflow/status/waitasecant/toolsnap/test.yml?logo=github&label=Tests)](https://github.com/waitasecant/toolsnap/actions/workflows/test.yml)
[![Codecov](https://img.shields.io/codecov/c/github/waitasecant/toolsnap?logo=codecov&label=Coverage&color=neongreen)](https://codecov.io/gh/waitasecant/toolsnap)
[![License: MIT](https://img.shields.io/badge/License-MIT-neon.svg)](LICENSE)

*Record your LLM agent's tool calls once. Replay them deterministically in every test run — no API keys, no network.*

## Why toolsnap?

LLM agents are non-deterministic at the model level, but their tool call trajectory i.e. which tools they call, in what order, with what arguments is the real testable surface. Existing approaches either hit live APIs on every test run (slow and expensive) or require writing brittle mocks upfront (tedious and disconnected from real behavior).

`toolsnap` takes a different approach: **record first, assert after**. Run your agent once against the real APIs, capture every tool call to a JSONL fixture, then replay that fixture in CI forever **deterministically, offline, without credentials.**

---

## Installation

```bash
pip install toolsnap
```

## Quick Start

### Step 1: Decorate your tool with `@snap`
```python
from toolsnap import snap
from strands import tool

@tool
@snap   # auto-saves to fixtures/search.jsonl
def search(query: str) -> list[str]:
    """Search the document store."""
    return real_search_api(query)
```

### Step 2: Run your agent once to record real calls
```bash
python main.py
# fixtures/search.jsonl written
```

### Step 3: Replay in tests with `@replay`
```python
from toolsnap import replay
from strands import tool

@tool
@replay   # reads from fixtures/search.jsonl — no API call
def search(query: str) -> list[str]:
    """Search the document store."""
    ...
```

```bash
# No LLM API key. No database connection. The fixture drives everything.
pytest test.py   # fast, offline, deterministic
```
