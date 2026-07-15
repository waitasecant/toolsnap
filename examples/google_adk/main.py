"""
Google ADK agent example — recording tool calls with @snap.

In ADK, tools are plain Python functions (no SDK decorator needed),
so apply @snap directly:

    @snap   # toolsnap auto-saves to fixtures/{fn_name}.jsonl
    def my_tool(...): ...

Record once, then run tests freely:
    python main.py   # captures a real tool call
    pytest test.py   # replays it, zero API calls
"""

import asyncio

from google.adk import Agent
from google.adk.runners import InMemoryRunner

from toolsnap import snap


@snap  # auto-saves to fixtures/get_current_time.jsonl
def get_current_time() -> str:
    """Return the current UTC date and time."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


root_agent = Agent(
    name="Google ADK Example Agent",
    model="gemini-3-flash-preview",
    tools=[get_current_time],
)


async def record():
    """Run the agent once against the real API and capture tool calls."""
    runner = InMemoryRunner(agent=root_agent)
    await runner.run_debug("What is the current time?")


if __name__ == "__main__":
    asyncio.run(record())
