# toolsnap
[![PyPI Version](https://img.shields.io/pypi/v/toolsnap?pypiBaseUrl=https%3A%2F%2Fpypi.org&logo=pypi&logoColor=white&label=PyPI&color=neongreen)](https://pypi.org/project/toolsnap/)
[![Tests](https://img.shields.io/github/actions/workflow/status/waitasecant/toolsnap/test.yml?logo=github&label=Tests)](https://github.com/waitasecant/toolsnap/actions/workflows/test.yml)
[![Codecov](https://img.shields.io/codecov/c/github/waitasecant/toolsnap?logo=codecov&label=Coverage&color=neongreen)](https://codecov.io/gh/waitasecant/toolsnap)
[![License: MIT](https://img.shields.io/badge/License-MIT-neon.svg)](LICENSE)

*Zero-dependency, SDK-agnostic recorder and replayer for LLM agent. Record once, test the trajectory forever.*

## Why toolsnap?

LLM agents are non-deterministic at the model level, but their tool call trajectory i.e. which tools they call, in what order, with what arguments is the real observable behavior.

Existing approaches' shortcomings:
- **Live APIs in every test run**: Slow and expensive. Worse: varying tool responses mean the agent takes different paths each run — trajectory assertions are unreliable.
- **Hand-written mocks**: You write the return value before seeing what the real agent produces. If the agent never calls the tool, the mock never fails. You're testing a fiction.
- **Network-level recording**: Records all HTTP — including every LLM request. Fixtures balloon in size and break on any SDK update, header change, or streaming format shift.

`toolsnap` takes a different approach: **record the real trajectory once, then replay and assert on it forever.**

---

## What `toolsnap` is/isn't?

### It is
- A trajectory recorder and assertion library for LLM agent tool calls
- A way to pin what the agent *does* so prompt or code changes that alter behavior surface immediately
- Most valuable when tools call external services you cannot or should not hit in CI

### It isn't
- A mock framework:  you never invent return values by hand
- A network recorder: it operates at the Python function boundary, not HTTP
- A way to eliminate LLM calls: the LLM still runs in replay mode; only the tool backends are fixed
- An evaluation framework: it does not measure response quality or semantic correctness

---

## When to use `toolsnap`?

### Use when
- Tools that call external APIs, databases, clocks, or any service you don't want in CI
- Multi-step agents where tool call order matters
- Teams that want to catch when a prompt change silently alters agent behavior
- Any scenario where "does the agent still call the right tools?" is the key question

### Don't use when
- Tools that are already pure functions with no external calls — just unit test them directly
- Testing LLM output quality or reasoning — use evals for that
- HTTP-level fidelity (exact headers, status codes) — use vcrpy or pytest-recording

---

## Installation

```bash
pip install toolsnap
```

## Quick Start

### Step 1: Record a real agent run

```python
# main.py — run once against live APIs
from toolsnap import snap

# auto-saves to fixtures/search.jsonl
@snap
def search(query: str) -> list[str]:
    return real_search_api(query)

# auto-saves to fixtures/get_weather.jsonl
@snap
def get_weather(city: str) -> dict:
    return real_weather_api(city)

agent.run("what's the weather in london and find llm docs")
# fixtures/search.jsonl and fixtures/get_weather.jsonl written
```

```bash
python main.py
```

### Step 2: Assert the trajectory in tests

```python
# test_agent.py — tool backends don't run; the LLM still runs
from toolsnap import replay

# reads from fixtures/search.jsonl
@replay
def search(query: str) -> list[str]: ...

# reads from fixtures/get_weather.jsonl
@replay
def get_weather(city: str) -> dict: ...

def test_research_agent_trajectory():
    agent.run("what's the weather in london and find llm docs")
    # search() and get_weather() returned their recorded responses
    # assert on the agent's output or behaviour here
```

```bash
pytest test_agent.py   # tool backends free, LLM still runs, trajectory deterministic
```

---

## Three ways to test

### 1. `@snap` / `@replay` — single-tool, decorator style

Best when you have one tool and want the simplest possible setup.

```python
# Record
@snap("fixtures/search.jsonl")
def search(query: str) -> list[str]:
    return real_search_api(query)

# Test
@replay("fixtures/search.jsonl")
def search(query: str) -> list[str]: ...

def test_agent_uses_search():
    result = agent.run("find llm docs")  # search() returns recorded response
    assert result is not None
```

### 2. `SnapSession` — multi-tool, with trajectory assertions

Best for agents that coordinate several tools. Wraps them all under one fixture and provides the full assertion API.

```python
from toolsnap import SnapSession, contains

def test_multi_tool_agent():
    with SnapSession.replay("fixtures/session.jsonl") as s:
        s.wrap(search)
        s.wrap(summarize)
        agent.run("find and summarize llm docs")

    s.assert_called("search", times=1)
    s.assert_called_with("search", query=contains("llm"))
    s.assert_call_order(["search", "summarize"])
    s.assert_no_errors()
```

### 3. `toolsnap_session` pytest fixture — CLI-controlled record/replay

Best for teams. Record and replay modes are controlled from the command line — no code changes needed.

```python
# conftest.py
pytest_plugins = ["toolsnap.pytest_plugin"]

# test_agent.py
@pytest.mark.toolsnap_fixture("fixtures/session.jsonl")
def test_agent_trajectory(toolsnap_session):
    toolsnap_session.wrap(search)
    toolsnap_session.wrap(summarize)
    agent.run("find and summarize llm docs")
    toolsnap_session.assert_called("search", times=1)
    toolsnap_session.assert_call_order(["search", "summarize"])
```

```bash
pytest tests/                    # replay — tool backends free, LLM still runs
pytest tests/ --toolsnap-record  # re-record after prompt/code changes
pytest tests/ --toolsnap-strict=false  # allow unexpected calls to fall through
```

---

## Assertion predicates

All assertion methods accept predicate objects for structural matching:

| Predicate | Matches when |
|---|---|
| `contains("llm")` | value contains the substring |
| `matches(r"\d{4}-\d{2}")` | value matches the regex |
| `any_of("london", "paris")` | value is one of the given options |
| `gt(0)` / `lt(100)` | value is greater / less than threshold |

```python
s.assert_called_with("search", query=contains("london"))
s.assert_called_with("embed", n_tokens=lt(512))
```

---

## CLI: inspect and diff fixtures

After a prompt change, `toolsnap diff` shows exactly what shifted in the agent's trajectory:

```bash
toolsnap diff fixtures/before.jsonl fixtures/after.jsonl
# Diff: fixtures/before.jsonl → fixtures/after.jsonl
# ────────────────────────────────────────────────────
#   search      call 0  args unchanged   result CHANGED (3 items → 2 items)
# + summarize   call 0  ADDED

toolsnap show fixtures/session.jsonl    # pretty-print all records
toolsnap stats fixtures/session.jsonl   # call counts, avg/p95 latency, errors
toolsnap validate fixtures/session.jsonl
toolsnap list
```
