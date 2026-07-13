"""
Pytest tests for the recorded get_current_time fixture.

toolsnap replays *tool calls*, not LLM decisions.  These tests verify:
  - the fixture was written correctly by main.py
  - replay() returns recorded results without touching the real function

No API key is needed. Run after recording: pytest test.py
"""

from toolsnap import UnexpectedToolCall, replay
from toolsnap.store import CallStore

FIXTURE = "fixtures/current_time.jsonl"


def test_fixture_has_get_current_time_calls():
    """main.py must have written at least one get_current_time call to the fixture."""
    records = CallStore(FIXTURE).load()
    time_records = [r for r in records if r.fn == "get_current_time"]
    assert len(time_records) >= 1, "No records found — run: python main.py"
    assert all(r.error is None for r in time_records)


def test_replay_returns_recorded_result_without_calling_real_function():
    """replay() serves the fixture result; the real function is never invoked."""
    records = CallStore(FIXTURE).load()
    recorded = next(r for r in records if r.fn == "get_current_time")

    call_log: list = []

    def get_current_time():
        call_log.append(True)
        return "should not run"

    replayed_fn = replay(FIXTURE)(get_current_time)
    result = replayed_fn()

    assert result == recorded.result, f"Expected {recorded.result!r}, got {result!r}"
    assert call_log == [], "real function was called during replay"


def test_replay_raises_on_extra_call():
    """replay() raises UnexpectedToolCall when called more times than recorded."""
    records = CallStore(FIXTURE).load()
    call_count = sum(1 for r in records if r.fn == "get_current_time")

    def get_current_time(): ...

    replayed_fn = replay(FIXTURE)(get_current_time)

    for _ in range(call_count):
        replayed_fn()

    try:
        replayed_fn()
        assert False, "Expected UnexpectedToolCall"
    except UnexpectedToolCall:
        pass
