"""
LangChain agent definition — no toolsnap here.

toolsnap is applied in main.py (recording) and tests (replay).
This file contains only the tool and agent that would exist in production.
"""

import os
from datetime import datetime, timezone

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI


@tool
def get_current_time() -> str:
    """Return the current UTC date and time."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def make_model() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=1.0,
    )


def make_agent(tools=None):
    """Return a callable(str) -> str wrapping the LangChain agent."""
    _tools = tools if tools is not None else [get_current_time]
    chain = create_agent(model=make_model(), tools=_tools)

    def _agent(query: str) -> str:
        result = chain.invoke({"messages": [{"role": "user", "content": query}]})
        return result["messages"][-1].content

    return _agent
