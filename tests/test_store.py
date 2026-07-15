import json
import warnings
from pathlib import Path

import pytest

from toolsnap import snap
from toolsnap.store import CallStore, _resolve_path, fixture_path


def test_load_nonexistent_file(tmp_fixture):
    records = CallStore(tmp_fixture).load()
    assert records == []


def test_load_skips_blank_lines(tmp_fixture):
    record = {
        "call_index": 0,
        "fn": "f",
        "args": [],
        "kwargs": {},
        "result": 1,
        "duration_ms": 0.0,
        "ts": 0.0,
        "error": None,
    }
    record2 = {**record, "call_index": 1, "result": 2}
    Path(tmp_fixture).write_text(
        json.dumps(record) + "\n\n" + json.dumps(record2) + "\n"
    )

    records = CallStore(tmp_fixture).load()
    assert len(records) == 2
    assert records[0].result == 1
    assert records[1].result == 2


def test_load_skips_corrupt_records(tmp_fixture):
    good = json.dumps(
        {
            "call_index": 0,
            "fn": "f",
            "args": [],
            "kwargs": {},
            "result": 99,
            "duration_ms": 0.0,
            "ts": 0.0,
            "error": None,
        }
    )
    Path(tmp_fixture).write_text("not valid json\n" + good + "\n")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        records = CallStore(tmp_fixture).load()

    assert len(records) == 1
    assert records[0].result == 99
    assert "corrupt" in " ".join(str(w.message) for w in caught)


def test_repair_removes_corrupt_lines(tmp_fixture):
    store = CallStore(tmp_fixture)
    Path(tmp_fixture).write_text(
        '{"call_index": 0, "fn": "f", "args": [], "kwargs": {}, "result": 1, '
        '"duration_ms": 1.0, "ts": 1.0, "error": null}\n'
        "NOT VALID JSON\n",
        encoding="utf-8",
    )

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        removed = store.repair()

    assert removed == 1
    records = store.load()
    assert len(records) == 1
    assert records[0].result == 1


def test_repair_no_op_on_clean_fixture(tmp_fixture):
    @snap(tmp_fixture)
    def fn(x):
        return x

    fn(42)

    removed = CallStore(tmp_fixture).repair()
    assert removed == 0


def test_repair_no_op_on_missing_file(tmp_fixture):
    removed = CallStore(tmp_fixture).repair()
    assert removed == 0


def test_fixture_path_with_string():
    assert fixture_path("search") == "fixtures/search.jsonl"
    assert fixture_path("search", directory="my_dir") == "my_dir/search.jsonl"


def test_fixture_path_with_callable():
    def my_tool():
        pass

    assert fixture_path(my_tool) == "fixtures/my_tool.jsonl"
    assert fixture_path(my_tool, directory="custom") == "custom/my_tool.jsonl"


def test_resolve_path_none():
    assert _resolve_path(None, "fn") == "fixtures/fn.jsonl"


def test_resolve_path_empty_string():
    assert _resolve_path("", "my_fn") == "fixtures/my_fn.jsonl"


def test_resolve_path_directory_slash():
    assert _resolve_path("my_dir/", "fn") == "my_dir/fn.jsonl"


def test_resolve_path_backslash_directory():
    assert _resolve_path("my_dir\\", "my_fn") == "my_dir\\my_fn.jsonl"


def test_resolve_path_explicit_file():
    assert _resolve_path("path/to/file.jsonl", "fn") == "path/to/file.jsonl"
