"""
Strands agent example with toolsnap recording and replay.

KEY INSIGHT — @snap / @replay work with ANY agent SDK because every SDK
ultimately calls fn(**args). There is zero framework-specific code for
tools you define yourself.

TWO PATTERNS:

  A) User-defined tool — apply toolsnap INSIDE the SDK decorator:

      @strands_tool          # SDK wrapper — reads __signature__
      @snap("fixture.jsonl") # toolsnap — intercepts the call
      def my_tool(...): ...

  B) Pre-built tool (e.g. strands_tools.calculator) — the SDK has already
     wrapped it in DecoratedFunctionTool, so patch its inner _tool_func:

      with patch_strands_tool(calculator.calculator, snap(FIXTURE)):
          agent = Agent(model=model, tools=[calculator])

STEP 1 — Record (run once against the real APIs):
    python strands_agent.py record

STEP 2 — Replay in tests (no API key needed):
    python strands_agent.py replay
    pytest test_strands_agent.py
"""

import os
import sys
from contextlib import contextmanager

from strands import Agent
from strands import tool as strands_tool
from strands.models.gemini import GeminiModel
from strands_tools import calculator as calc_module

from toolsnap import replay, snap

FIXTURE = "fixtures/calculator_calls.jsonl"

model = GeminiModel(
    client_args={
        "api_key": os.getenv("GEMINI_API_KEY"),
    },
    model_id="gemini-3-flash-preview",
    params={
        "temperature": 0.7,
        "max_output_tokens": 2048,
        "top_p": 0.9,
        "top_k": 40,
    },
)


# Helper for pre-built Strands tools
@contextmanager
def patch_strands_tool(decorated_tool, wrapper_factory):
    """
    Temporarily replace the inner function of a DecoratedFunctionTool.

    DecoratedFunctionTool stores the actual Python callable in _tool_func.
    This helper swaps it for a snap/replay wrapper for the duration of the
    block, then restores the original — leaving the tool object itself intact
    so Strands' module scan still recognises it.

    Usage:
        with patch_strands_tool(calc_module.calculator, snap(FIXTURE)):
            agent = Agent(model=model, tools=[calc_module])
    """
    original = decorated_tool._tool_func
    decorated_tool._tool_func = wrapper_factory(original)
    try:
        yield
    finally:
        decorated_tool._tool_func = original


# Pattern A: user-defined tool (works with any SDK)
def _calculator_impl(expression: str) -> str:
    return "2 + 2 = 4"


def record_custom():
    """Record using a tool you define yourself — zero framework-specific code."""

    @strands_tool
    @snap(FIXTURE)
    def calculator(expression: str) -> str:
        """Evaluate a mathematical expression."""
        return _calculator_impl(expression)

    agent = Agent(model=model, tools=[calculator])
    response = agent("What is 2+2?")
    print(response)
    print(f"\nFixture written → {FIXTURE}")


def replay_custom():
    @strands_tool
    @replay(FIXTURE)
    def calculator(expression: str) -> str:
        """Evaluate a mathematical expression."""
        ...

    print(Agent(model=model, tools=[calculator])("What is 2+2?"))


# Pattern B: pre-built strands_tools tool
def record_prebuilt():
    """Record using strands_tools.calculator — patches _tool_func in place."""
    with patch_strands_tool(calc_module.calculator, snap(FIXTURE)):
        agent = Agent(model=model, tools=[calc_module])
        response = agent("What is 2+2?")
    print(response)
    print(f"\nFixture written → {FIXTURE}")


def replay_prebuilt():
    """Replay strands_tools.calculator calls from fixture."""
    with patch_strands_tool(calc_module.calculator, replay(FIXTURE)):
        agent = Agent(model=model, tools=[calc_module])
        response = agent("What is 2+2?")
    print(response)


# Entry point
MODES = {
    "record": record_prebuilt,  # change to record_custom to demo pattern A
    "replay": replay_prebuilt,  # change to replay_custom to demo pattern A
}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "record"
    MODES.get(mode, record_prebuilt)()
