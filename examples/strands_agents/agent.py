"""
Strands agent definition — no toolsnap here.

toolsnap is applied in main.py (recording) and tests (replay).
This file contains only the tool and agent that would exist in production.
"""

import os
from datetime import datetime, timezone

from strands import Agent, tool
from strands.models.gemini import GeminiModel


@tool
def get_current_time() -> str:
    """Return the current UTC date and time."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def make_model() -> GeminiModel:
    return GeminiModel(
        client_args={"api_key": os.environ["GEMINI_API_KEY"]},
        model_id="gemini-2.0-flash",
        params={"temperature": 0.7, "max_output_tokens": 512},
    )


def make_agent(tools=None) -> Agent:
    """Create a fresh agent. Pass *tools* to override the default tool list."""
    return Agent(
        name="Strands Example Agent",
        model=make_model(),
        tools=tools if tools is not None else [get_current_time],
    )
