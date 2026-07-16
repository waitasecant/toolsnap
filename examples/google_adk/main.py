"""
Record the agent's tool-call trajectory.

    python main.py

Wraps every tool with SnapSession before the agent runs so that each call —
function name, arguments, return value, duration — is saved to a single fixture.

    fixtures/session.jsonl   ← written here, read by both test files

Re-run whenever you change the agent prompt, tools, or model.
The LLM call is live (requires GEMINI_API_KEY); only the tool backends are
captured and will be free to replay in tests.
"""

import os

from toolsnap import SnapSession

from agent import get_current_time, make_agent

FIXTURE = "fixtures/session.jsonl"


def main() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY is not set")

    with SnapSession.snap(FIXTURE) as s:
        wrapped = s.wrap(get_current_time)
        agent = make_agent(tools=[wrapped])
        response = agent("What is the current time?")

    print(response)
    print(f"\nTrajectory saved to {FIXTURE}")


if __name__ == "__main__":
    main()
