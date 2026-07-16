"""
Session-route trajectory tests — Strands Agents example.

Pattern
-------
Record once (python main.py), then test forever.

How it works
------------
SnapSession wraps every tool before the agent runs. The LLM is still live;
toolsnap fixes the tool responses. After the run, assertion helpers verify
the trajectory: call counts, argument values, call order, errors.

    with SnapSession.replay(FIXTURE) as s:
        wrapped = s.wrap(get_current_time)   ← tool response fixed
        agent = make_agent(tools=[wrapped])
        agent("What is the current time?")   ← LLM runs, tool is intercepted

    s.assert_called("get_current_time", times=1)
    s.assert_no_errors()

Why SnapSession over @replay
----------------------------
SnapSession covers all tools under one fixture and gives you the full
assertion API. Use it when the trajectory matters more than the return value.
"""

from pathlib import Path

from toolsnap import SnapSession

from agent import get_current_time as _real_tool
from agent import make_agent

FIXTURE = str(Path(__file__).parent / "fixtures" / "session.jsonl")


def test_agent_called_time_tool_exactly_once():
    """A simple time query causes the agent to call get_current_time once.

    assert_called(times=1) fails if the fixture — and therefore the agent's
    actual behavior — contains zero or more than one call. Either deviation
    indicates the agent's tool-calling logic has changed.
    """
    with SnapSession.replay(FIXTURE) as s:
        wrapped = s.wrap(_real_tool)
        agent = make_agent(tools=[wrapped])
        agent("What is the current time?")

    s.assert_called("get_current_time", times=1)


def test_agent_trajectory_completed_without_errors():
    """No tool call in the trajectory raised an exception.

    assert_no_errors() catches cases where the tool failed silently — the
    agent may still produce a response, but the error in the fixture would
    indicate the tool call did not complete successfully.
    """
    with SnapSession.replay(FIXTURE) as s:
        wrapped = s.wrap(_real_tool)
        agent = make_agent(tools=[wrapped])
        agent("What is the current time?")

    s.assert_no_errors()


def test_fixed_tool_response_drives_consistent_trajectory():
    """With the tool response fixed, the agent's trajectory is consistent.

    Runs the agent twice with the same fixture. Both runs must produce the
    same tool-call trajectory: one call, no errors. The LLM's text response
    may differ — we don't assert on that — but the tool-calling decisions
    should be stable when the tool responses are identical.
    """
    sessions = []
    for _ in range(2):
        with SnapSession.replay(FIXTURE) as s:
            wrapped = s.wrap(_real_tool)
            agent = make_agent(tools=[wrapped])
            agent("What is the current time?")
        sessions.append(s)

    for s in sessions:
        s.assert_called("get_current_time", times=1)
        s.assert_no_errors()
