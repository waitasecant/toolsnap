import json
import threading
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Union

from .models import CallRecord

# Per-path locks so concurrent threads writing to the same fixture don't interleave.
_append_locks: dict[str, threading.Lock] = {}


def fixture_path(fn: Union[str, "Callable"], directory: str = "fixtures") -> str:
    """Return the auto-generated fixture path for a function or name.

    Convention: ``{directory}/{fn_name}.jsonl``

    Args:
        fn: A callable or its string name.
        directory: Fixture directory (default ``"fixtures"``).
    """
    name = fn if isinstance(fn, str) else fn.__name__
    return f"{directory}/{name}.jsonl"


def _resolve_path(path: str | None, fn_name: str) -> str:
    """Resolve a fixture path, auto-naming from *fn_name* when *path* is absent.

    - ``None`` or empty string  : ``fixtures/{fn_name}.jsonl``
    - ends with ``'/'``         : ``{path}{fn_name}.jsonl``
    - otherwise                 : *path* used as-is
    """
    if not path:
        return fixture_path(fn_name)
    if path.endswith("/") or path.endswith("\\"):
        return f"{path}{fn_name}.jsonl"
    return path


class CallStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def clear(self) -> None:
        if self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def append(self, record: CallRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "call_index": record.call_index,
                "fn": record.fn,
                "args": record.args,
                "kwargs": record.kwargs,
                "result": record.result,
                "duration_ms": record.duration_ms,
                "ts": record.ts,
                "error": record.error,
            }
        )
        key = str(self.path.resolve())
        if key not in _append_locks:
            _append_locks[key] = threading.Lock()
        with _append_locks[key]:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def load(self) -> list[CallRecord]:
        if not self.path.exists():
            return []
        records = []
        skipped = 0
        with self.path.open(encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    records.append(CallRecord(**data))
                except Exception:
                    skipped += 1
                    warnings.warn(
                        f"{self.path}:{lineno}: skipping corrupt record",
                        stacklevel=2,
                    )
        if skipped:
            warnings.warn(
                f"{self.path}: skipped {skipped} corrupt record(s)",
                stacklevel=2,
            )
        return records

    def repair(self) -> int:
        """Rewrite the fixture discarding corrupt lines.

        Returns:
            Number of lines removed.
        """
        if not self.path.exists():
            return 0
        with self.path.open(encoding="utf-8") as f:
            original_count = sum(1 for line in f if line.strip())
        records = self.load()  # load() already skips corrupt lines silently
        removed = original_count - len(records)
        if removed > 0:
            self.clear()
            for record in records:
                self.append(record)
        return removed

    def load_index(self) -> dict[str, list[CallRecord]]:
        index: dict[str, list[CallRecord]] = {}
        for record in self.load():
            index.setdefault(record.fn, []).append(record)
        return index
