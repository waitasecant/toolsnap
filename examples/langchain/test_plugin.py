"""
Plugin-route trajectory tests — LangChain example.

Pattern
-------
Record once (python main.py), then test forever.

How it works
------------
The toolsnap_session fixture wires SnapSession into pytest so record/replay
mode is a CLI flag, not a code change.

    toolsnap_session.wrap(get_current_time)   <- tool response fixed
    make_agent(tools=[wrapped])
    agent("What is the current time?")        <- LLM runs, tool is intercepted

    toolsnap_session.assert_called("get_current_time", times=1)

CLI modes:

    pytest test_plugin.py                    # replay (default) -- LLM live, tool fixed
    pytest test_plugin.py --toolsnap-record  # re-record via CLI, no code change
    pytest test_plugin.py --toolsnap-strict=false

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
    """A simple time query causes the agent to call get_current_time once."""
    wrapped = toolsnap_session.wrap(_real_tool)
    agent = make_agent(tools=[wrapped])
    agent("What is the current time?")

    toolsnap_session.assert_called("get_current_time", times=1)


@pytest.mark.toolsnap_fixture(_FIXTURE)
def test_agent_trajectory_completed_without_errors(toolsnap_session):
    """No tool call in the trajectory raised an exception."""
    wrapped = toolsnap_session.wrap(_real_tool)
    agent = make_agent(tools=[wrapped])
    agent("What is the current time?")

    toolsnap_session.assert_no_errors()
    toolsnap_session.assert_called("get_current_time")


@pytest.mark.toolsnap_fixture(_FIXTURE)
def test_fixed_tool_response_drives_agent_response(toolsnap_session):
    """The agent's response incorporates the recorded timestamp."""
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
        f"{date_part!r} -- agent may have answered without calling the tool"
    )
