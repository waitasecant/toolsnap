"""
Tool tests using toolsnap replay — zero API calls.

toolsnap records and replays *tool* calls.
These tests call the tool function directly through @replay

Record once, then run tests freely:
    python main.py   # captures a real tool call
    pytest test.py   # replays it, zero API calls
"""

from toolsnap import replay
from toolsnap.store import CallStore

from main import FIXTURE


def test_recorded_time_is_utc_formatted():
    """Tool returns a timestamp in the expected 'YYYY-MM-DD HH:MM:SS UTC' format."""

    @replay(FIXTURE)
    def get_current_time() -> str:
        """Return the current UTC date and time."""
        ...

    result = get_current_time()
    assert result.endswith("UTC"), f"Expected UTC suffix, got: {result!r}"
    parts = result.split()
    assert len(parts) == 3, f"Expected 'date time UTC', got: {result!r}"


def test_replay_returns_exact_recorded_value():
    """Replayed tool returns the exact value that was captured during recording."""
    recorded = next(r for r in CallStore(FIXTURE).load() if r.fn == "get_current_time")

    @replay(FIXTURE)
    def get_current_time() -> str:
        """Return the current UTC date and time."""
        ...

    assert get_current_time() == recorded.result
