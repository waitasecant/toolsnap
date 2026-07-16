"""
Google ADK agent definition — no toolsnap here.

toolsnap is applied in main.py (recording) and tests (replay).
This file contains only the tool and agent that would exist in production.

Note: ADK tools are plain Python functions — no SDK decorator is needed.
"""

import asyncio
import os
from datetime import datetime, timezone

from google.adk import Agent
from google.adk.runners import InMemoryRunner


def get_current_time() -> str:
    """Return the current UTC date and time."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


async def _run(query: str, tools: list) -> str:
    runner = InMemoryRunner(
        agent=Agent(
            name="Google ADK Example Agent",
            model="gemini-2.0-flash",
            tools=tools,
        )
    )
    result = await runner.run_debug(query)
    return str(result) if result is not None else ""


def make_agent(tools=None):
    """Return a callable(str) -> str that runs the ADK agent synchronously."""
    _tools = tools if tools is not None else [get_current_time]

    def _agent(query: str) -> str:
        return asyncio.run(_run(query, _tools))

    return _agent
