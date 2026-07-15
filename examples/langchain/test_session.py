"""
SnapSession example — replay with call assertions.

SnapSession is the alternative to @snap/@replay when you want assertion
helpers on top of replay: assert_called, assert_called_with, assert_no_errors, etc.

To record a session fixture instead of per-tool fixtures:
    with SnapSession.snap("fixtures/session.jsonl") as s:
        s.wrap(get_current_time)
        agent.invoke({"messages": [{"role": "user", "content": "What is the current time?"}]})

Replay in tests (zero API calls):
    pytest test_session.py
"""

from pathlib import Path

from toolsnap import SnapSession

FIXTURE = str(Path(__file__).parent / "fixtures" / "session.jsonl")


def _stub() -> str:
    """Stub body — never runs during replay."""
    raise RuntimeError("real function called during replay")


_stub.__name__ = "get_current_time"


def test_tool_was_called():
    """SnapSession confirms the tool was invoked during the recorded run."""
    with SnapSession.replay(FIXTURE) as s:
        wrapped = s.wrap(_stub)
        wrapped()

    s.assert_called("get_current_time")


def test_result_is_utc_formatted():
    """Replayed result still satisfies the format contract."""
    with SnapSession.replay(FIXTURE) as s:
        wrapped = s.wrap(_stub)
        result = wrapped()

    assert result.endswith("UTC"), f"Expected UTC suffix, got: {result!r}"
    s.assert_no_errors()


def test_called_exactly_once():
    """Tool was called exactly once in the recorded session."""
    with SnapSession.replay(FIXTURE) as s:
        wrapped = s.wrap(_stub)
        wrapped()

    s.assert_called("get_current_time", times=1)
