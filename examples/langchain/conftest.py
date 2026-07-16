"""
Shared test configuration for the LangChain example.

All tests in this directory require:

  1. GEMINI_API_KEY — the LLM is live; toolsnap only fixes tool responses.
  2. fixtures/session.jsonl — produced by running: python main.py

If either is missing every test is skipped with a clear explanation.
"""

import os
import sys
from pathlib import Path

import pytest

# Make agent.py importable when pytest is run from the project root.
sys.path.insert(0, str(Path(__file__).parent))

# Load the toolsnap pytest plugin so toolsnap_session is available in test_plugin.py.
pytest_plugins = ["toolsnap.pytest_plugin"]

# Single fixture file used by all three test routes.
FIXTURE = str(Path(__file__).parent / "fixtures" / "session.jsonl")


def pytest_collection_modifyitems(items: list) -> None:
    if not os.getenv("GEMINI_API_KEY"):
        _skip_all(
            items,
            "GEMINI_API_KEY not set — the LLM is live in these tests. "
            "Run: export GEMINI_API_KEY=<key>",
        )
    elif not Path(FIXTURE).exists():
        _skip_all(
            items,
            "trajectory fixture not recorded yet — run: python main.py",
        )


def _skip_all(items: list, reason: str) -> None:
    marker = pytest.mark.skip(reason=reason)
    for item in items:
        item.add_marker(marker)
