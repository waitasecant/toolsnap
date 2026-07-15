"""
Strands agent example — recording tool calls with @snap.

Apply @snap inside the SDK decorator so toolsnap intercepts the call:

    @tool   # SDK wrapper reads __signature__
    @snap   # toolsnap auto-saves to fixtures/{fn_name}.jsonl
    def my_tool(...): ...

Record once, then run tests freely:
    python main.py   # captures a real tool call
    pytest test.py   # replays it, zero API calls
"""

import os

from strands import Agent
from strands import tool
from strands.models.gemini import GeminiModel

from toolsnap import snap

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


@tool
@snap  # auto-saves to fixtures/get_current_time.jsonl
def get_current_time() -> str:
    """Return the current UTC date and time."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


agent = Agent(name="Strands Example Agent", model=model, tools=[get_current_time])


def record():
    """Run the agent once against the real API and capture tool calls."""
    response = agent("What is the current time?")
    print(response)


if __name__ == "__main__":
    record()
