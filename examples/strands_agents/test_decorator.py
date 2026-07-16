"""
Decorator-route trajectory tests — Strands Agents example.

Pattern
-------
Record once (python main.py), then test forever.

How it works
------------
@replay fixes the tool response to what was recorded. The LLM is still live —
toolsnap only intercepts the tool call. The agent receives identical data to
the real run, so its tool-calling decisions are consistent across test runs.

    @tool
    @replay(FIXTURE)              ← tool body replaced by recorded response
    def get_current_time(): ...

    make_agent(tools=[get_current_time])   ← agent with fixed tool response
        ↓
    agent("What is the current time?")     ← LLM runs, tool response is fixed

What we assert
--------------
Not the LLM's text — that varies. We assert on what the LLM did with the
fixed tool response: did it incorporate the recorded date? did the recorded
trajectory show exactly one call? did the real tool backend stay silent?
"""

from pathlib import Path

from strands import tool

from toolsnap import replay
from toolsnap.store import CallStore

from agent import make_agent

FIXTURE = str(Path(__file__).parent / "fixtures" / "session.jsonl")


def test_agent_response_incorporates_recorded_tool_result():
    """The agent's response references the timestamp the tool recorded.

    The LLM receives the fixed timestamp from the fixture — not from the real
    clock — so its response should include the recorded date. If the agent
    ignores the tool result, or the tool was never called, the date would not
    appear in the response.
    """
    recorded_time = next(
        r.result for r in CallStore(FIXTURE).load() if r.fn == "get_current_time"
    )

    @tool
    @replay(FIXTURE)
    def get_current_time() -> str:
        """Return the current UTC date and time."""
        ...

    response = str(make_agent(tools=[get_current_time])("What is the current time?"))

    date_part = recorded_time.split()[0]  # e.g. "2026-07-15"
    assert date_part in response, (
        f"agent response {response!r} does not reference the recorded date {date_part!r}. "
        "This may mean the agent answered without using the tool."
    )


def test_agent_called_time_tool_exactly_once():
    """A simple time query causes the agent to call get_current_time once.

    The fixture is the ground truth for call count — it reflects what the
    real agent did. If the fixture contains zero or more than one call the
    agent's behavior has drifted from what was recorded.
    """
    calls = [r for r in CallStore(FIXTURE).load() if r.fn == "get_current_time"]
    assert len(calls) == 1, (
        f"expected exactly 1 call in trajectory, found {len(calls)}. "
        "Re-record with: python main.py"
    )


def test_replay_intercepts_before_real_tool_executes():
    """The real tool body (which reads the system clock) never runs during replay.

    @replay intercepts the call and returns the recorded value before the
    function body is reached. This test makes that guarantee explicit: the
    body raises, but the test passes because toolsnap never reaches it.
    """

    @tool
    @replay(FIXTURE)
    def get_current_time() -> str:
        """Return the current UTC date and time."""
        raise AssertionError(
            "real tool must not execute — replay should intercept first"
        )

    # No AssertionError raised → replay provided the response from the fixture
    response = str(make_agent(tools=[get_current_time])("What is the current time?"))
    assert response
