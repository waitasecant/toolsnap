"""
LangChain agent example — recording tool calls with @snap.

Apply @snap inside the SDK decorator so toolsnap intercepts the call:

    @tool   # SDK wrapper reads __signature__
    @snap   # toolsnap auto-saves to fixtures/{fn_name}.jsonl
    def my_tool(...): ...

Record once, then run tests freely:
    python main.py   # captures a real tool call
    pytest test.py   # replays it, zero API calls
"""

from langchain.tools import tool
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from toolsnap import snap

model = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    temperature=1.0,
)


@tool
@snap  # auto-saves to fixtures/get_current_time.jsonl
def get_current_time() -> str:
    """Return the current UTC date and time."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


agent = create_agent(
    model=model,
    tools=[get_current_time],
)


def record():
    """Run the agent once against the real API and capture tool calls."""
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "What is the current time?"}]}
    )
    print(result["messages"][-1].content)


if __name__ == "__main__":
    record()
