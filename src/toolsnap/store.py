import json
import warnings
from pathlib import Path

from .models import CallRecord


class CallStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

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

    def load_index(self) -> dict[str, list[CallRecord]]:
        index: dict[str, list[CallRecord]] = {}
        for record in self.load():
            index.setdefault(record.fn, []).append(record)
        return index
