from dataclasses import dataclass
from typing import Any


@dataclass
class CallRecord:
    call_index: int
    fn: str
    args: list
    kwargs: dict
    result: Any
    duration_ms: float
    ts: float
    error: dict | None
