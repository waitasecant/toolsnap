"""
Pytest tests for the recorded calculator fixture.

toolsnap replays *tool calls*, not LLM decisions.  These tests verify:
  - the fixture was written correctly by record()
  - replay() returns recorded results without touching the real function

No API key is needed.  Run after recording:
    python strands_agent.py record
    pytest test_strands_agent.py
"""

from toolsnap import UnexpectedToolCall, replay
from toolsnap.store import CallStore

FIXTURE = "fixtures/calculator_calls.jsonl"


def test_fixture_has_calculator_calls():
    """record() must have written at least one calculator call to the fixture."""
    records = CallStore(FIXTURE).load()
    calc_records = [r for r in records if r.fn == "calculator"]
    assert len(calc_records) >= 1, (
        "No calculator records found - run: python strands_agent.py record"
    )
    assert all(r.error is None for r in calc_records)


def test_replay_returns_recorded_result_without_calling_real_function():
    """replay() serves the fixture result; the real function is never invoked."""
    records = CallStore(FIXTURE).load()
    recorded = next(r for r in records if r.fn == "calculator")

    call_log: list = []

    def calculator(**kwargs):
        call_log.append(kwargs)
        return "should not run"

    replayed_fn = replay(FIXTURE)(calculator)
    result = replayed_fn(**recorded.kwargs)

    assert result == recorded.result, f"Expected {recorded.result!r}, got {result!r}"
    assert call_log == [], "real function was called during replay"


def test_replay_raises_on_extra_call():
    """replay() raises UnexpectedToolCall when called more times than recorded."""
    records = CallStore(FIXTURE).load()
    call_count = sum(1 for r in records if r.fn == "calculator")
    first_record = next(r for r in records if r.fn == "calculator")

    def calculator(**kwargs): ...

    replayed_fn = replay(FIXTURE)(calculator)

    for _ in range(call_count):
        replayed_fn(**first_record.kwargs)

    try:
        replayed_fn(**first_record.kwargs)
        assert False, "Expected UnexpectedToolCall"
    except UnexpectedToolCall:
        pass
