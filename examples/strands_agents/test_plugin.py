"""
Plugin-route trajectory tests — Strands Agents example.

Pattern
-------
Record once (python main.py), then test forever.

How it works
------------
The toolsnap_session fixture wires SnapSession into pytest so record/replay
mode is a CLI flag, not a code change.

    toolsnap_session.wrap(get_current_time)   ← tool response fixed
    make_agent(tools=[wrapped])
    agent("What is the current time?")        ← LLM runs, tool is intercepted

    toolsnap_session.assert_called("get_current_time", times=1)

CLI modes:

    pytest test_plugin.py                    # replay (default) — LLM live, tool fixed
    pytest test_plugin.py --toolsnap-record  # re-record via CLI, no code change
    pytest test_plugin.py --toolsnap-strict=false

The @pytest.mark.toolsnap_fixture marker sets the fixture path for this test.
An absolute path (derived from __file__) resolves correctly regardless of
which directory pytest is launched from.

Why the plugin route over SnapSession directly
----------------------------------------------
Record/replay is controlled from the CLI, not the code. --toolsnap-record
re-runs the live agent and writes a fresh fixture. All other runs replay
deterministically. No code change needed between recording and testing.
"""

from pathlib import Path

import pytest

from agent import get_current_time as _real_tool
from agent import make_agent

_FIXTURE = str(Path(__file__).parent / "fixtures" / "session.jsonl")


@pytest.mark.toolsnap_fixture(_FIXTURE)
def test_agent_called_time_tool_exactly_once(toolsnap_session):
    """A simple time query causes the agent to call get_current_time once.

    In replay mode: the fixture drives the tool response; the LLM is live.
    In --toolsnap-record mode: the real function runs and the result is saved.
    assert_called(times=1) catches any prompt change that makes the agent
    call the tool zero or more than once.
    """
    wrapped = toolsnap_session.wrap(_real_tool)
    agent = make_agent(tools=[wrapped])
    agent("What is the current time?")

    toolsnap_session.assert_called("get_current_time", times=1)


@pytest.mark.toolsnap_fixture(_FIXTURE)
def test_agent_trajectory_completed_without_errors(toolsnap_session):
    """No tool call in the trajectory raised an exception.

    assert_no_errors() fails if the fixture contains any error record —
    catching silent tool failures that might still produce an agent response.
    """
    wrapped = toolsnap_session.wrap(_real_tool)
    agent = make_agent(tools=[wrapped])
    agent("What is the current time?")

    toolsnap_session.assert_no_errors()
    toolsnap_session.assert_called("get_current_time")


@pytest.mark.toolsnap_fixture(_FIXTURE)
def test_fixed_tool_response_drives_agent_response(toolsnap_session):
    """The agent's response incorporates the recorded timestamp.

    The tool response is fixed to the recorded value so the LLM receives
    the same timestamp every run. The agent should reference that date in
    its response — if it doesn't, it answered without using the tool.
    """
    from toolsnap.store import CallStore

    recorded_time = next(
        r.result for r in CallStore(_FIXTURE).load() if r.fn == "get_current_time"
    )

    wrapped = toolsnap_session.wrap(_real_tool)
    agent = make_agent(tools=[wrapped])
    response = str(agent("What is the current time?"))

    date_part = recorded_time.split()[0]  # e.g. "2026-07-15"
    assert date_part in response, (
        f"agent response {response!r} does not reference the recorded date "
        f"{date_part!r} — agent may have answered without calling the tool"
    )

